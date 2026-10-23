"""Owned Ranch library decorations, isolated from physical bag furniture custody."""
from .haven_ranch_furniture_wire import decode_deploy, add, context


POLICY = "haven_ranch_furniture_policy"


def _policy(db):
    row = db.execute("SELECT value FROM settings WHERE name=%s", (POLICY,)).fetchone()
    document = None if row is None else row["value"]
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("Missing accredited Ranch furniture policy")
    if document.get("map_id") != 1440 or document.get("biome_id") != 1:
        raise ValueError("Unsupported Ranch furniture map")
    areas = document.get("areas")
    if not isinstance(areas, list) or not areas:
        raise ValueError("Missing native Ranch terrain areas")
    chunks = {}
    identities = set()
    for area in areas:
        if (
            not isinstance(area, dict)
            or type(area.get("id")) is not int
            or area["id"] <= 0
            or area["id"] in identities
            or not isinstance(area.get("chunks"), list)
            or not area["chunks"]
        ):
            raise ValueError("Malformed Ranch terrain area")
        identities.add(area["id"])
        for chunk in area["chunks"]:
            if (
                not isinstance(chunk, list)
                or len(chunk) != 2
                or any(type(value) is not int for value in chunk)
                or tuple(chunk) in chunks
            ):
                raise ValueError("Malformed or overlapping Ranch terrain chunks")
            chunks[tuple(chunk)] = area["id"]
    refs = document.get("unconditional_references")
    if (
        not isinstance(refs, list)
        or not refs
        or any(type(ref) is not int or ref <= 0 for ref in refs)
        or len(refs) != len(set(refs))
    ):
        raise ValueError("Missing accredited Ranch placement criteria")
    return document, chunks, set(refs)


def _authorize(store, db, account_id, generation, character, session):
    from wakfu_server.haven_chest import can_access_location
    from wakfu_server.haven_bag_store import owner_id
    from wakfu_server.environment_interactions import _guard

    if (
        session is None
        or character.get("account_id") != account_id
        or not can_access_location(character, session.parent, session)
    ):
        raise ValueError("Ranch decoration requires its current owned child capability")
    session.validate_lease(generation)
    store.lock_character(db, account_id, generation, character["id"])
    _guard(db, character["id"])
    bag_id = owner_id(db, character["id"])
    if bag_id != character.get("instance_id"):
        raise ValueError("Ranch decoration requires the canonical account instance")
    # Serialize account-wide placements across owned heroes.
    db.execute(
        "SELECT character_id FROM haven_bags WHERE character_id=%s FOR UPDATE",
        (bag_id,),
    )
    return bag_id


def _destination(
    db, bag_id, request, chunks, geometry, *, account_id, biome_id=1, excluding=None
):
    if geometry.get("map_id") != 1440:
        raise ValueError("Wrong native Ranch placement geometry")
    x, y = request["x"], request["y"]
    area = chunks.get((x // 18, y // 18))
    if area is None:
        raise ValueError("Furniture destination is outside native Ranch terrain areas")
    heights = {
        cell[2] for cell in geometry.get("cells", ()) if cell[0] == x and cell[1] == y
    }
    if len(heights) != 1:
        raise ValueError(
            "Ranch furniture requires one unambiguous native walkable height"
        )
    z = next(iter(heights))
    if not -511 <= z <= 512:
        raise ValueError("Ranch furniture height cannot be represented")
    if db.execute(
        "SELECT 1 FROM haven_ranch_furniture WHERE owner_character_id=%s AND map_id=1440 "
        "AND x=%s AND y=%s AND item_uid<>%s",
        (bag_id, x, y, excluding or 0),
    ).fetchone():
        raise ValueError("Ranch furniture destination is occupied")
    if db.execute(
        "SELECT 1 FROM planted_resources WHERE map_id=1440 AND instance_id=%s AND x=%s AND y=%s",
        (bag_id, x, y),
    ).fetchone():
        raise ValueError("Ranch furniture destination contains a garden plant")
    from wakfu_server.ranch_native_geometry import (
        building_footprint_cells,
        deployed_creature_cells,
    )

    building_rows = tuple(
        dict(row)
        for row in db.execute(
            "SELECT uid,building_ref,mode_id,view_kind,view_value,x,y "
            "FROM account_ranch_buildings WHERE account_id=%s AND biome_id=%s",
            (account_id, biome_id),
        )
    )
    if (x, y) in building_footprint_cells(biome_id, building_rows):
        raise ValueError("Ranch furniture destination overlaps a native building")
    if (x, y) in deployed_creature_cells(db, account_id, biome_id):
        raise ValueError("Ranch furniture destination overlaps a deployed creature")
    return area, z


def _rows(db, bag_id):
    return [
        dict(row, deployed=True, virtual=True)
        for row in db.execute(
            "SELECT * FROM haven_ranch_furniture WHERE owner_character_id=%s AND map_id=1440 ORDER BY item_uid",
            (bag_id,),
        )
    ]


def deploy(
    store, account_id, generation, character, body, *, session, geometry, resolver=None
):
    """Place an actually learned library reference; never select an inventory UID by guess."""
    request = decode_deploy(body)
    if resolver is None:
        from wakfu_server.haven_bag_furniture_catalog import resolve_item

        resolver = resolve_item
    definition = resolver(request["item_ref"])
    if definition is None or definition.get("kind") not in {
        "Decoration",
        "FxDecoration",
        "PortableCraftTable",
    }:
        raise ValueError("Unsupported native Ranch decoration kind")
    from wakfu_server.haven_bag_furniture_knowledge import known
    from wakfu_server.inventory_uids import allocate

    with store.connection() as db:
        bag_id = _authorize(store, db, account_id, generation, character, session)
        _, chunks, unconditional = _policy(db)
        if request["item_ref"] not in unconditional or not known(
            db, account_id, request["item_ref"]
        ):
            raise ValueError(
                "Unknown library furniture or unsupported native placement criterion"
            )
        area, z = _destination(
            db,
            bag_id,
            request,
            chunks,
            geometry,
            account_id=account_id,
            biome_id=session.biome_id,
        )
        item = dict(
            request,
            item_uid=allocate(db),
            template_id=definition["template_id"],
            area_id=area,
            z=z,
            deployed=True,
            virtual=True,
        )
        db.execute(
            "INSERT INTO haven_ranch_furniture(owner_character_id,map_id,item_uid,item_ref,template_id,area_id,direction,x,y,z) "
            "VALUES(%s,1440,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                bag_id,
                item["item_uid"],
                item["item_ref"],
                item["template_id"],
                area,
                item["direction"],
                item["x"],
                item["y"],
                z,
            ),
        )
        from wakfu_server.haven_bag_furniture_world import ranch_upsert

        return dict(
            item=item,
            packets=[add(character["map_id"], area, item), ranch_upsert(bag_id, item)],
        )


def snapshot(store, account_id, generation, character, *, session, now_ms):
    """Reconstruct authoritative native Ranch model deliberately on scene bootstrap."""
    with store.connection() as db:
        if (
            session is None
            or character.get("account_id") != account_id
            or not session.owns(character)
            or not session.parent.owns(session.return_point)
        ):
            raise ValueError("Ranch snapshot requires its current child capability")
        session.validate_lease(generation)
        store.lock_character(db, account_id, generation, character["id"])
        host_account = session.parent.owner["account_id"]
        row = db.execute(
            "SELECT character_id FROM account_haven_bags WHERE account_id=%s",
            (host_account,),
        ).fetchone()
        if row is None or row["character_id"] != character.get("instance_id"):
            raise ValueError("Foreign Ranch snapshot instance")
        bag_id = row["character_id"]
        document, _, _ = _policy(db)
        from wakfu_server.ranch_native_geometry import (
            account_buildings_by_sector,
            bootstrap_account_sectors,
            validate_initial_area_policy,
        )

        biome_id = session.biome_id
        area_ids = validate_initial_area_policy(biome_id, document["areas"])
        # Account locking makes first-entry native sector creation stable across
        # multiple selected heroes. It never materializes fBm.gxg slot records
        # as player-owned buildings.
        bootstrap_account_sectors(db, host_account, biome_id)
        items = _rows(db, bag_id)
        from wakfu_server.haven_ranch_bridges import snapshot as bridge_snapshot
        from wakfu_server.haven_bag_furniture_world import ranch_upsert

        buildings = bridge_snapshot(db, bag_id)
        building_rows = account_buildings_by_sector(db, host_account, biome_id)
        from .haven_ranch_herd import paddocks, synchronize_paddocks

        # Existing fences can predate the herd schema. Initialize their real
        # enclosures before the client evaluates whether deployment is allowed.
        if any(building_rows.values()) and not paddocks(db, host_account, biome_id):
            synchronize_paddocks(
                db,
                host_account,
                biome_id,
                [row for rows in building_rows.values() for row in rows],
            )
        from .haven_ranch_building_knowledge import herd_sectors
        from .ranch_reward_retrieval import records as reward_records

        creatures_by_sector, paddocks_by_sector = herd_sectors(
            db,
            host_account,
            biome_id,
            area_ids,
        )

        return dict(
            items=items,
            packet=context(
                host_account,
                1440,
                area_ids,
                items,
                now_ms,
                building_states=buildings,
                buildings_by_sector=building_rows,
                creatures_by_sector=creatures_by_sector,
                paddocks_by_sector=paddocks_by_sector,
                rewards=reward_records(db, host_account),
            ),
            scene_packets=[ranch_upsert(bag_id, item) for item in items],
        )


def edit(store, account_id, generation, character, opcode, body, *, session, geometry):
    """Move or repack an exact owned Ranch instance, never a reusable template ID."""
    from .haven_ranch_furniture_wire import decode_edit, moved, removed

    request = decode_edit(opcode, body)
    with store.connection() as db:
        bag_id = _authorize(store, db, account_id, generation, character, session)
        _, chunks, _ = _policy(db)
        row = db.execute(
            "SELECT * FROM haven_ranch_furniture WHERE owner_character_id=%s AND map_id=1440 "
            "AND item_uid=%s FOR UPDATE",
            (bag_id, request["item_uid"]),
        ).fetchone()
        if row is None:
            raise ValueError("Unknown or foreign Ranch furniture instance")
        item = dict(row, deployed=True, virtual=True)
        if request["remove"]:
            db.execute(
                "DELETE FROM haven_ranch_furniture WHERE item_uid=%s",
                (item["item_uid"],),
            )
            # Repacking learned furniture removes the virtual placement only;
            # the consumed learning item and physical bag custody are untouched.
            from wakfu_server.haven_bag_furniture_world import remove

            return dict(
                item=item,
                removed=True,
                packets=[removed(character["map_id"], item), remove(item)],
            )
        if request.get("rotate"):
            request.update(
                x=item["x"],
                y=item["y"],
                z=item["z"],
                # Original byZ.dSC -> fkZ.o alternates the supported
                # furniture diagonals; other directions normalize.
                direction=3 if 1 <= item["direction"] < 3 else 1,
            )
        area, z = _destination(
            db,
            bag_id,
            request,
            chunks,
            geometry,
            account_id=account_id,
            biome_id=session.biome_id,
            excluding=item["item_uid"],
        )
        if request["z"] != z:
            raise ValueError("Ranch move height differs from native terrain")
        previous = dict(item)
        item.update(
            x=request["x"],
            y=request["y"],
            z=z,
            direction=request["direction"],
            area_id=area,
        )
        db.execute(
            "UPDATE haven_ranch_furniture SET area_id=%s,direction=%s,x=%s,y=%s,z=%s WHERE item_uid=%s",
            (area, item["direction"], item["x"], item["y"], z, item["item_uid"]),
        )
        packets = [moved(character["map_id"], item)]
        if previous["area_id"] != area:
            # cFp12452 updates coordinates but does not migrate fBV collections.
            packets = [
                removed(character["map_id"], previous),
                add(character["map_id"], area, item),
            ]
        from wakfu_server.haven_bag_furniture_world import remove, ranch_upsert

        return dict(
            item=item,
            removed=False,
            packets=packets + [remove(item), ranch_upsert(bag_id, item)],
        )
