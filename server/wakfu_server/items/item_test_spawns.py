"""Finite administrator-only native item30532 test actors, without rewards.

Admin access, one live group per main and ten-minute unused TTL are explicit
Wakemu developer policy. Breed5518's native level/stats/spells are unchanged.
World must install all reward/progression/corpse guards before routing use().
"""
import struct
from .simple_item_actions import _equipped, _idle

ACTION_ID = 13135
ITEM_REF = 30532
MONSTER_REF = 5518


def action_class(body):
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid native item action header")
    action, uid = struct.unpack_from(">iq", body)
    if action != ACTION_ID:
        return None
    if len(body) != 12 or uid <= 0:
        raise ValueError("Invalid native test-spawn action")
    return "bIk"


def _position(db, character, geometry, occupied_cells):
    from wakfu_server.combat_actor_snapshot import native_actor_catalog
    from wakfu_server.combat_obstacle_condition import footprint

    profiles = native_actor_catalog()["npc_profiles"]
    radius = profiles[str(MONSTER_REF)]["physical_radius"]
    cells = {tuple(cell) for cell in geometry["cells"]}
    connected = {tuple(cell) for edge in geometry["edges"] for cell in edge}
    columns = {}
    for cell in cells:
        columns.setdefault(cell[:2], []).append(cell)
    blocked = set()
    for cell in occupied_cells:
        if (
            not isinstance(cell, (tuple, list))
            or len(cell) not in (2, 3)
            or any(type(value) is not int for value in cell)
        ):
            raise ValueError("Invalid authoritative occupied world cell")
        blocked.add(tuple(cell[:2]))
    for row in db.execute(
        "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=%s AND status<>'defeated'",
        (character["map_id"], character["instance_id"]),
    ):
        for member in row["members"]:
            blocked.update(
                footprint(
                    (member["x"], member["y"]),
                    profiles[str(member["ref"])]["physical_radius"],
                )
            )
    for row in db.execute(
        "SELECT x,y FROM planted_resources WHERE map_id=%s AND instance_id=%s "
        "UNION SELECT c.x,c.y FROM characters c JOIN sessions s ON s.character_id=c.id "
        "WHERE c.map_id=%s AND c.instance_id=%s AND s.expires_at>CURRENT_TIMESTAMP",
        (
            character["map_id"],
            character["instance_id"],
            character["map_id"],
            character["instance_id"],
        ),
    ):
        blocked.add((row["x"], row["y"]))
    blocked.add((character["x"], character["y"]))
    anchor = (character["x"], character["y"], character["z"])
    for cell in sorted(
        connected,
        key=lambda c: (
            abs(c[0] - anchor[0]) + abs(c[1] - anchor[1]),
            abs(c[2] - anchor[2]),
            c,
        ),
    ):
        if (
            abs(cell[0] - anchor[0]) + abs(cell[1] - anchor[1]) > 8
            or abs(cell[2] - anchor[2]) > 1
        ):
            continue
        occupied = footprint(cell, radius)
        if any(xy in blocked or len(columns.get(xy, ())) != 1 for xy in occupied):
            continue
        if any(
            columns[xy][0] not in connected or columns[xy][0][2] != cell[2]
            for xy in occupied
        ):
            continue
        return cell
    raise ValueError("No unoccupied native ground for the test actor")


def _result(db, row, *, applied):
    from wakfu_server.combat_monster_world import spawn_group

    group = db.execute(
        "SELECT members,status FROM combat_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s",
        (row["map_id"], row["instance_id"], row["group_id"]),
    ).fetchone()
    return dict(
        applied=applied,
        native_class="bIk",
        consumed=0,
        key=(row["map_id"], row["instance_id"], row["group_id"]),
        packets=[],
        world_packets=[]
        if group["status"] != "available"
        else [(12608, spawn_group(group["members"], group_id=row["group_id"]))],
    )


def use(
    store,
    groups,
    account_id,
    generation,
    character_id,
    body,
    *,
    in_fight,
    location=None,
    geometry=None,
    occupied_cells=()
):
    """Create/recover one finite owned test group; caller publishes after commit."""
    if action_class(body) != "bIk" or type(in_fight) is not bool or in_fight:
        raise ValueError("Test spawning requires an idle administrator")
    _, uid = struct.unpack(">iq", body)
    from wakfu_server.monsters import owned_instance, reference
    from wakfu_server.npc_actor_identity import allocate_block
    from wakfu_server.combat_terrain import map_geometry
    from .haven_bag_furniture_knowledge import _rules

    with groups.lock, store.connection() as db:
        account = db.execute(
            "SELECT is_admin FROM accounts WHERE id=%s FOR UPDATE", (account_id,)
        ).fetchone()
        if account is None or account["is_admin"] is not True:
            raise ValueError("The native developer test item requires an administrator")
        store.lock_character(db, account_id, generation, character_id)
        _idle(db, character_id, store.now())
        character = store.character(account_id, character_id, db)
        source = db.execute(
            "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (uid, character_id),
        ).fetchone()
        rule = _rules().get(ITEM_REF, {})
        if (
            source is None
            or source["reference"] != ITEM_REF
            or source["quantity"] < 1
            or _equipped(character, uid)
            or rule.get("use_action_id") != ACTION_ID
            or rule.get("use_action_class") != "bIk"
        ):
            raise ValueError("Missing original reusable test-spawn source")
        if location is not None:
            keys = ("map_id", "instance_id", "x", "y", "z")
            if location.get("id") != character_id or any(
                type(location.get(k)) is not int for k in keys
            ):
                raise ValueError("Invalid authoritative test-spawn location")
            character = dict(character, **{k: location[k] for k in keys})
        if character["instance_id"] != 0:
            raise ValueError("Developer test actors require ordinary public ground")
        prior = db.execute(
            "SELECT t.*,g.status FROM developer_item_test_groups t JOIN combat_groups g "
            "USING(map_id,instance_id,group_id) WHERE t.character_id=%s AND t.ended_at IS NULL FOR UPDATE OF t,g",
            (character_id,),
        ).fetchone()
        if prior is not None:
            # Never silently replace an old scene actor or a retained fight.
            return dict(_result(db, prior, applied=False), character=character)
        native = (geometry or map_geometry)(character["map_id"])
        if native.get("map_id") != character["map_id"]:
            raise ValueError("Test-spawn terrain belongs to another map")
        position = _position(db, character, native, occupied_cells)
        breed = reference(MONSTER_REF)
        if breed["min_level"] != breed["max_level"]:
            raise ValueError("Original test breed no longer has a fixed level")
        identity = allocate_block(db, 1)
        member = owned_instance(
            MONSTER_REF,
            breed["min_level"],
            -identity,
            map_id=character["map_id"],
            instance_id=0,
            x=position[0],
            y=position[1],
            z=position[2],
        )
        groups.register_transaction(db, character["map_id"], 0, identity, [member])
        row = db.execute(
            "INSERT INTO developer_item_test_groups(map_id,instance_id,group_id,account_id,character_id,source_uid) "
            "VALUES(%s,0,%s,%s,%s,%s) RETURNING *",
            (character["map_id"], identity, account_id, character_id, uid),
        ).fetchone()
        return dict(_result(db, row, applied=True), character=character)


def is_fight(db, fight_id):
    """Pin classification from the durable group lease, never client metadata."""
    existing = db.execute(
        "SELECT 1 FROM developer_item_test_fights WHERE fight_id=%s", (fight_id,)
    ).fetchone()
    if existing is not None:
        return True
    row = db.execute(
        "SELECT t.map_id,t.instance_id,t.group_id FROM developer_item_test_groups t "
        "JOIN combat_groups g USING(map_id,instance_id,group_id) "
        "WHERE g.fight_id=%s AND g.status='fighting'",
        (fight_id,),
    ).fetchone()
    if row is None:
        return False
    db.execute(
        "INSERT INTO developer_item_test_fights(fight_id,map_id,instance_id,group_id) "
        "VALUES(%s,%s,%s,%s) ON CONFLICT(fight_id) DO NOTHING",
        (fight_id, row["map_id"], row["instance_id"], row["group_id"]),
    )
    return True


def retire_used(db, key, *, fight_id, generation=None, revision=None):
    """Retire a real leased test group before its fight identity is cleared.

    PersistentGroups supplies the lease fence on normal finish and its already
    locked authoritative rows on disconnect/startup recovery. Ordinary groups
    return false without any mutation.
    """
    row = db.execute(
        "SELECT g.status,g.generation,g.fight_id,g.revision FROM combat_groups g "
        "JOIN developer_item_test_groups t USING(map_id,instance_id,group_id) "
        "WHERE g.map_id=%s AND g.instance_id=%s AND g.group_id=%s FOR UPDATE OF g,t",
        key,
    ).fetchone()
    if row is None or row["status"] != "fighting" or row["fight_id"] != fight_id:
        return False
    if (generation is not None and row["generation"] != generation) or (
        revision is not None and row["revision"] != revision
    ):
        return False
    if not is_fight(db, fight_id):
        raise ValueError("Used test group lacks durable fight classification")
    db.execute(
        "UPDATE combat_groups SET status='defeated',generation=NULL,fight_id=NULL,"
        "revision=revision+1,defeated_at=CURRENT_TIMESTAMP "
        "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
        key,
    )
    db.execute(
        "UPDATE developer_item_test_groups SET ended_at=CURRENT_TIMESTAMP "
        "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
        key,
    )
    return True


def finish(db, groups, lease):
    """Retire test encounters on either outcome; no ecology/corpse/repopulation."""
    key, _, fight_id, _ = lease
    row = db.execute(
        "SELECT 1 FROM developer_item_test_groups WHERE map_id=%s AND instance_id=%s AND group_id=%s FOR UPDATE",
        key,
    ).fetchone()
    if row is None:
        return None
    if not is_fight(db, fight_id):
        raise ValueError("Test encounter lost its durable fight classification")
    applied = groups.finish(lease, defeated=True, db=db)
    if applied:
        db.execute(
            "UPDATE developer_item_test_groups SET ended_at=CURRENT_TIMESTAMP WHERE map_id=%s AND instance_id=%s AND group_id=%s",
            key,
        )
    return dict(applied=applied, packets=[], receipts=[])


def expire(store, groups):
    """Retire unused actors after ten minutes; active fights retain their actor."""
    from wakfu_server.combat_monster_world import remove_message

    deliveries = []
    with groups.lock, store.connection() as db:
        for row in db.execute(
            "SELECT t.*,g.members FROM developer_item_test_groups t JOIN combat_groups g "
            "USING(map_id,instance_id,group_id) WHERE t.ended_at IS NULL "
            "AND t.expires_at<=CURRENT_TIMESTAMP AND g.status<>'fighting' FOR UPDATE OF t,g"
        ):
            key = (row["map_id"], row["instance_id"], row["group_id"])
            db.execute(
                "UPDATE combat_groups SET status='defeated',defeated_at=CURRENT_TIMESTAMP,revision=revision+1 "
                "WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                key,
            )
            db.execute(
                "UPDATE developer_item_test_groups SET ended_at=CURRENT_TIMESTAMP WHERE map_id=%s AND instance_id=%s AND group_id=%s",
                key,
            )
            deliveries.append(
                dict(
                    map_id=row["map_id"],
                    instance_id=row["instance_id"],
                    packet=remove_message([m["id"] for m in row["members"]]),
                )
            )
    return tuple(deliveries)
