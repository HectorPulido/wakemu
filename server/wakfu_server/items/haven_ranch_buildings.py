"""Account-owned native Ranch building operations, separate from learned plans.

The four installed terrain sectors are initially available by Wakemu policy.
Original descriptors govern views and footprints; no construction price or
creature production is inferred from the learning item's inventory price.
"""
from wakfu_server import haven_ranch_building_catalog as catalog
from wakfu_server import haven_ranch_building_wire as wire


def rows(db, account_id, biome_id):
    return [
        dict(row)
        for row in db.execute(
            "SELECT * FROM account_ranch_buildings WHERE account_id=%s AND biome_id=%s ORDER BY uid",
            (account_id, biome_id),
        )
    ]


def initialize_sectors(db, account_id, biome_id):
    """Publish the same native-area policy used by scene and account bootstrap."""
    from wakfu_server.ranch_native_geometry import initial_sectors

    for sector_id in initial_sectors(biome_id):
        db.execute(
            "INSERT INTO account_ranch_sectors(account_id,biome_id,sector_id) "
            "VALUES(%s,%s,%s) ON CONFLICT DO NOTHING",
            (account_id, biome_id, sector_id),
        )


def _authorize(store, db, account_id, generation, character, session):
    from wakfu_server.haven_ranch_furniture import _authorize as authorize_scene

    if session is None or character.get("map_id") != 1440 or session.biome_id != 1:
        raise ValueError("Building operations require the installed native Ranch")
    db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
    authorize_scene(store, db, account_id, generation, character, session)
    initialize_sectors(db, account_id, session.biome_id)


def _destination(db, account_id, biome_id, building, before, *, excluding=None):
    from wakfu_server.ranch_native_geometry import (
        deployed_creature_cells,
        validate_building_placement,
    )

    definition = catalog.validate_published(db, building["building_ref"])
    catalog.view(
        definition, building["mode_id"], building["view_kind"], building["view_value"]
    )
    occupied = tuple(
        (row["x"], row["y"])
        for row in db.execute(
            "SELECT f.x,f.y FROM haven_ranch_furniture f JOIN account_haven_bags b "
            "ON b.character_id=f.owner_character_id WHERE b.account_id=%s AND f.map_id=1440 "
            "UNION SELECT p.x,p.y FROM planted_resources p JOIN account_haven_bags b "
            "ON b.character_id=p.instance_id WHERE b.account_id=%s AND p.map_id=1440",
            (account_id, account_id),
        )
    )
    occupied += tuple(deployed_creature_cells(db, account_id, biome_id))
    destination = validate_building_placement(
        definition,
        building["mode_id"],
        building["view_kind"],
        building["view_value"],
        building["x"],
        building["y"],
        biome_id=biome_id,
        existing_buildings=tuple(row for row in before if row["uid"] != excluding),
        occupied_cells=occupied,
    )
    sector_id = destination["sector_id"]
    if (
        db.execute(
            "SELECT 1 FROM account_ranch_sectors WHERE account_id=%s AND biome_id=%s AND sector_id=%s",
            (account_id, biome_id, sector_id),
        ).fetchone()
        is None
    ):
        raise ValueError("Ranch building destination sector is not owned")
    return sector_id


def _changes(biome_id, before, after):
    from wakfu_server.haven_ranch_building_children import validate_building_children

    previous = {row["uid"]: row for row in before}
    for row in after:
        old = previous.get(row["uid"])
        if old is not None and all(old[key] == value for key, value in row.items()):
            continue
        validate_building_children(
            catalog.definition(row["building_ref"]),
            row["mode_id"],
            row["view_kind"],
            row["view_value"],
        )
    # Exact empty epT declarations produce no attached fBM instances. Removal
    # is handled by the native parent-UID cleanup in ceK.F.
    return ()


def _synchronize_views(db, account_id, biome_id):
    """Persist the native adjacency result also reconstructed by ceK/fBL."""
    from wakfu_server.ranch_native_geometry import recompute_adjacent_building_views

    before = rows(db, account_id, biome_id)
    after = recompute_adjacent_building_views(
        biome_id, tuple(dict(row) for row in before)
    )
    previous = {row["uid"]: row for row in before}
    if len(after) != len(before) or {row["uid"] for row in after} != set(previous):
        raise ValueError("Native building adjacency changed the owned population")
    for row in after:
        old = previous[row["uid"]]
        if any(
            row[key] != value
            for key, value in old.items()
            if key not in {"view_kind", "view_value"}
        ):
            raise ValueError("Native adjacency changed unrelated building state")
        if (row["view_kind"], row["view_value"]) == (
            old["view_kind"],
            old["view_value"],
        ):
            continue
        catalog.view(
            catalog.definition(row["building_ref"]),
            row["mode_id"],
            row["view_kind"],
            row["view_value"],
        )
        db.execute(
            "UPDATE account_ranch_buildings SET view_kind=%s,view_value=%s,revision=revision+1,"
            "updated_at=now() WHERE uid=%s AND account_id=%s AND biome_id=%s",
            (row["view_kind"], row["view_value"], row["uid"], account_id, biome_id),
        )


def _place(db, account_id, biome_id, request):
    from wakfu_server.inventory_uids import allocate

    definition = catalog.validate_published(db, request["building_ref"])
    if (
        db.execute(
            "SELECT 1 FROM account_ranch_building_knowledge WHERE account_id=%s AND building_ref=%s",
            (account_id, request["building_ref"]),
        ).fetchone()
        is None
    ):
        raise ValueError("The native Ranch building plan is not learned")
    before = rows(db, account_id, biome_id)
    requested = dict(request, mode_id=catalog.mode(definition)["p"])
    # Requests have no client nonce. An exact already-placed instance is the
    # only state-based retry; removal permits a later legitimate new placement.
    prior = next(
        (
            row
            for row in before
            if all(row[key] == value for key, value in requested.items())
        ),
        None,
    )
    if prior is not None:
        return prior, (), False
    candidate = dict(
        requested,
        uid=0,
        account_id=account_id,
        biome_id=biome_id,
        contained_item_ref=-1,
        contained_quantity=0,
        revision=0,
    )
    candidate["sector_id"] = _destination(db, account_id, biome_id, candidate, before)
    # Resolve native scene children before writing a building instance.
    scene_objects = _changes(biome_id, before, before + [candidate])
    candidate["uid"] = allocate(db)
    db.execute(
        "INSERT INTO account_ranch_buildings(uid,account_id,biome_id,sector_id,building_ref,mode_id,"
        "view_kind,view_value,x,y,contained_item_ref,contained_quantity) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        tuple(
            candidate[key]
            for key in (
                "uid",
                "account_id",
                "biome_id",
                "sector_id",
                "building_ref",
                "mode_id",
                "view_kind",
                "view_value",
                "x",
                "y",
                "contained_item_ref",
                "contained_quantity",
            )
        ),
    )
    return candidate, scene_objects, True


def _move(db, account_id, biome_id, request):
    before = rows(db, account_id, biome_id)
    prior = next((row for row in before if row["uid"] == request["uid"]), None)
    if prior is None:
        raise ValueError(
            "Ranch building is missing or belongs to another owner or biome"
        )
    if all(prior[key] == value for key, value in request.items()):
        return prior, (), False
    candidate = dict(prior, **request)
    candidate["sector_id"] = _destination(
        db,
        account_id,
        biome_id,
        candidate,
        before,
        excluding=prior["uid"],
    )
    after = [candidate if row["uid"] == candidate["uid"] else row for row in before]
    scene_objects = _changes(biome_id, before, after)
    candidate["revision"] += 1
    db.execute(
        "UPDATE account_ranch_buildings SET sector_id=%s,view_kind=%s,view_value=%s,x=%s,y=%s,"
        "revision=revision+1,updated_at=now() WHERE uid=%s AND account_id=%s AND biome_id=%s",
        (
            candidate["sector_id"],
            candidate["view_kind"],
            candidate["view_value"],
            candidate["x"],
            candidate["y"],
            candidate["uid"],
            account_id,
            biome_id,
        ),
    )
    return candidate, scene_objects, True


def _remove(db, account_id, biome_id, uid):
    before = rows(db, account_id, biome_id)
    prior = next((row for row in before if row["uid"] == uid), None)
    if prior is None:
        prior = db.execute(
            "SELECT * FROM account_ranch_building_tombstones WHERE uid=%s AND account_id=%s AND biome_id=%s",
            (uid, account_id, biome_id),
        ).fetchone()
        if prior is None:
            raise ValueError("Ranch building removal is missing or foreign")
        return dict(prior), (), False
    if prior["contained_quantity"]:
        raise ValueError("Ranch building contents must be collected before removal")
    scene_objects = _changes(
        biome_id, before, [row for row in before if row["uid"] != uid]
    )
    db.execute(
        "INSERT INTO account_ranch_building_tombstones(uid,account_id,biome_id,sector_id,building_ref,revision) "
        "VALUES(%s,%s,%s,%s,%s,%s)",
        (
            uid,
            account_id,
            biome_id,
            prior["sector_id"],
            prior["building_ref"],
            prior["revision"] + 1,
        ),
    )
    db.execute(
        "DELETE FROM account_ranch_buildings WHERE uid=%s AND account_id=%s",
        (uid, account_id),
    )
    return prior, scene_objects, True


def operate(store, account_id, generation, character, opcode, body, *, session):
    """Execute native12671/12662/13480 atomically; caller sends rejection ACKs on errors."""
    decoders = {
        12671: wire.decode_place,
        12662: wire.decode_move,
        13480: wire.decode_remove,
    }
    if opcode not in decoders:
        raise ValueError("Unknown native Ranch building operation")
    request = decoders[opcode](body)
    with store.connection() as db:
        _authorize(store, db, account_id, generation, character, session)
        biome_id = session.biome_id
        if opcode == 12671:
            building, scene_objects, changed = _place(db, account_id, biome_id, request)
            packet = wire.placed(
                character["map_id"], building, scene_objects=scene_objects
            )
        elif opcode == 12662:
            building, scene_objects, changed = _move(db, account_id, biome_id, request)
            packet = wire.moved(
                character["map_id"], building, scene_objects=scene_objects
            )
        else:
            building, scene_objects, changed = _remove(
                db, account_id, biome_id, request
            )
            # ceK.F removes the building's attached fBM objects and recomputes
            # adjacency itself; the original removal ACK has no child list.
            packet = wire.removed(
                character["map_id"], building["uid"], building["sector_id"]
            )
        if changed:
            _synchronize_views(db, account_id, biome_id)
            from wakfu_server.haven_ranch_herd import synchronize_paddocks

            # Synchronization validates deployed membership before replacing
            # the durable active region set, all within this transaction.
            synchronize_paddocks(
                db, account_id, biome_id, rows(db, account_id, biome_id)
            )
            if opcode != 13480:
                building = next(
                    row
                    for row in rows(db, account_id, biome_id)
                    if row["uid"] == building["uid"]
                )
                emit = wire.placed if opcode == 12671 else wire.moved
                packet = emit(
                    character["map_id"], building, scene_objects=scene_objects
                )
        return dict(
            building=building,
            changed=changed,
            scene_objects=scene_objects,
            packets=[packet],
        )
