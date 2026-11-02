"""Pinned dungeon-owned resource access, using normal harvest occupations.

Numerical placement and one-item explosion costs are explicit reviewed Wakemu
reconstruction data. Native cvH supplies item identity, never debit quantity.
Ordinary resources, environmental authority and spell behavior are unchanged.
"""
from hashlib import sha256
import json
import secrets
import struct
from psycopg.types.json import Jsonb


def digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def storage_ready(db):
    return db.execute(
        "SELECT to_regclass('dungeon_resource_obstacles') IS NOT NULL AS ready"
    ).fetchone()["ready"]


def policy(configuration):
    value = configuration["topology"].get("resource_obstacles")
    if value is None:
        return None
    from wakfu_server.planting import RESOURCES

    if (
        type(value) is not dict
        or set(value)
        != {
            "schema_version",
            "policy_id",
            "provenance",
            "resource_reference",
            "resource_sha256",
            "native_collision",
            "initial_stage",
            "placements",
            "actions",
            "unlock_room_order",
        }
        or value["schema_version"] != 1
        or type(value["schema_version"]) is not int
        or type(value["policy_id"]) is not str
        or not value["policy_id"]
        or type(value["provenance"]) is not str
        or not value["provenance"]
        or type(value["resource_reference"]) is not int
        or value["native_collision"] is not True
        or value["unlock_room_order"] != 1
        or type(value["unlock_room_order"]) is not int
    ):
        raise ValueError("Invalid pinned dungeon resource reconstruction")
    native = RESOURCES.get(value["resource_reference"])
    if (
        native is None
        or digest(native) != value["resource_sha256"]
        or native["monster_resource"]
    ):
        raise ValueError("Dungeon resource differs from its original source")
    if (
        type(value["initial_stage"]) is not int
        or value["initial_stage"] not in native["stages"]
    ):
        raise ValueError("Dungeon resource initial stage is not native")
    placements = value["placements"]
    seen = set()
    keys = set()
    first = [
        room
        for room in configuration["topology"]["rooms"]
        if room["order"] == value["unlock_room_order"]
    ]
    if len(first) != 1:
        raise ValueError("Dungeon resource access room is absent or ambiguous")
    logical = {tuple(p) for p in first[0]["cells"]}
    if type(placements) is not list or not placements:
        raise ValueError("Dungeon resource placements are absent")
    for row in placements:
        if (
            type(row) is not dict
            or set(row) != {"key", "position"}
            or type(row["key"]) is not str
            or not row["key"]
            or len(row["key"]) > 128
            or row["key"] in keys
            or type(row["position"]) is not list
            or len(row["position"]) != 3
            or any(type(p) is not int for p in row["position"])
        ):
            raise ValueError("Invalid dungeon resource placement")
        point = tuple(row["position"])
        if point[:2] in seen or point not in logical:
            raise ValueError(
                "Dungeon resource leaves its pinned native floor or aliases an occupied XY"
            )
        keys.add(row["key"])
        seen.add(point[:2])
    actions = value["actions"]
    if type(actions) is not list or not actions:
        raise ValueError("Dungeon resource actions are absent")
    identities = set()
    for row in actions:
        if (
            type(row) is not dict
            or set(row)
            != {
                "stage",
                "action_id",
                "action_sha256",
                "item_reference",
                "quantity",
                "destination_stage",
            }
            or any(
                type(row[k]) is not int
                for k in (
                    "stage",
                    "action_id",
                    "item_reference",
                    "quantity",
                    "destination_stage",
                )
            )
            or not 1 <= row["quantity"] <= 32767
            or (row["stage"], row["action_id"]) in identities
        ):
            raise ValueError("Invalid reviewed dungeon resource action")
        stage = next(
            (s for s in native["stage_definitions"] if s["stage_id"] == row["stage"]),
            None,
        )
        raw = (
            None
            if stage is None
            else next(
                (a for a in stage["actions"] if a["action_id"] == row["action_id"]),
                None,
            )
        )
        if (
            raw is None
            or digest(raw) != row["action_sha256"]
            or raw["profession_id"] != 0
            or raw["criteria"].strip()
            or raw["minimum_level"] != 0
            or row["item_reference"] <= 0
            or raw["raw_getters"]["cvH"] != row["item_reference"]
            or raw["raw_getters"]["cvF"] != row["destination_stage"]
            or (
                row["destination_stage"] != 0
                and row["destination_stage"] not in native["stages"]
            )
        ):
            raise ValueError("Dungeon resource action differs from its native identity")
        identities.add((row["stage"], row["action_id"]))
    return value


def lock_run(db, instance_id):
    from psycopg.errors import LockNotAvailable

    try:
        with db.transaction():
            row = db.execute(
                "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE NOWAIT",
                (instance_id,),
            ).fetchone()
            instance = db.execute(
                "SELECT * FROM dungeon_instances WHERE instance_id=%s FOR UPDATE NOWAIT",
                (instance_id,),
            ).fetchone()
    except LockNotAvailable as error:
        raise ValueError("Dungeon resource owner is busy; retry interaction") from error
    if row is None or instance is None or instance["status"] != "active":
        raise ValueError("Dungeon resource has no active owned run")
    return row, instance


def ensure(db, instance_id, configuration, *, now_ms):
    """Create stable owned resources once; stage0 survives reconnect as a receipt."""
    rule = policy(configuration)
    if rule is None:
        return True
    if not storage_ready(db):
        raise ValueError("Dungeon resource storage is unavailable")
    progress, instance = lock_run(db, instance_id)
    if (
        progress["catalog_hash"] != configuration["compiled_plan"]["document_sha256"]
        or instance["context_route_key"] != configuration["route"]["key"]
        or instance["context_policy_version"] != configuration["version"]
    ):
        raise ValueError("Dungeon resources differ from the immutable run pin")
    map_id = configuration["topology"]["asset_map_id"]
    policy_hash = digest(rule)
    existing = db.execute(
        "SELECT * FROM dungeon_resource_obstacles WHERE instance_id=%s ORDER BY obstacle_key FOR UPDATE",
        (instance_id,),
    ).fetchall()
    by_key = {row["obstacle_key"]: row for row in existing}
    if existing and set(by_key) != {p["key"] for p in rule["placements"]}:
        raise ValueError("Dungeon resource ownership has missing or foreign placements")
    for placement in rule["placements"]:
        point = tuple(placement["position"])
        row = by_key.get(placement["key"])
        if row is None:
            if progress["current_room"] != 1 or progress["status"] != "active":
                raise ValueError(
                    "Dungeon resource ownership cannot be recreated after progression"
                )
            uid = secrets.randbelow(2**63 - 1) + 1
            row = db.execute(
                "INSERT INTO dungeon_resource_obstacles(instance_id,obstacle_key,resource_uid,policy_sha256,map_id,x,y,z,resource_reference,current_stage,creation_time) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                (
                    instance_id,
                    placement["key"],
                    uid,
                    policy_hash,
                    map_id,
                    *point,
                    rule["resource_reference"],
                    rule["initial_stage"],
                    now_ms,
                ),
            ).fetchone()
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    uid,
                    map_id,
                    instance_id,
                    *point,
                    rule["resource_reference"],
                    row["current_stage"],
                    now_ms,
                ),
            )
        if (
            row["policy_sha256"] != policy_hash
            or row["map_id"] != map_id
            or (row["x"], row["y"], row["z"]) != point
            or row["resource_reference"] != rule["resource_reference"]
        ):
            raise ValueError(
                "Dungeon resource receipt contradicts its frozen placement"
            )
        planted = db.execute(
            "SELECT * FROM planted_resources WHERE resource_uid=%s",
            (row["resource_uid"],),
        ).fetchone()
        if row["current_stage"] == 0:
            if planted is not None:
                raise ValueError("Destroyed dungeon resource was resurrected")
        elif (
            planted is None
            or planted["stage"] != row["current_stage"]
            or any(
                planted[k] != row[k]
                for k in (
                    "map_id",
                    "instance_id",
                    "x",
                    "y",
                    "z",
                    "resource_reference",
                    "creation_time",
                )
            )
        ):
            raise ValueError("Active dungeon resource is absent or was altered")
    rows = db.execute(
        "SELECT current_stage FROM dungeon_resource_obstacles WHERE instance_id=%s",
        (instance_id,),
    ).fetchall()
    return all(row["current_stage"] == 0 for row in rows)


def lock_scope(db, resource):
    if not storage_ready(db):
        return False
    row = db.execute(
        "SELECT instance_id FROM dungeon_resource_obstacles WHERE resource_uid=%s",
        (resource["resource_uid"],),
    ).fetchone()
    if row is None:
        return False
    lock_run(db, row["instance_id"])
    return True


def authorize(db, store, account, generation, character, resource, native_action):
    if not lock_scope(db, resource):
        return None
    from wakfu_server import dungeon_runtime

    _, configuration = dungeon_runtime.configuration_for_instance(
        db, resource["instance_id"]
    )
    rule = policy(configuration)
    if rule is None:
        raise ValueError("Dungeon resource lost its pinned source contract")
    row = db.execute(
        "SELECT * FROM dungeon_resource_obstacles WHERE resource_uid=%s FOR UPDATE",
        (resource["resource_uid"],),
    ).fetchone()
    placement = next(
        (p for p in rule["placements"] if p["key"] == row["obstacle_key"]), None
    )
    if (
        placement is None
        or row["policy_sha256"] != digest(rule)
        or row["current_stage"] != resource["stage"]
        or row["current_stage"] == 0
        or resource["resource_reference"] != rule["resource_reference"]
        or tuple(placement["position"]) != tuple(resource[k] for k in ("x", "y", "z"))
        or any(
            resource[k] != row[k]
            for k in (
                "map_id",
                "instance_id",
                "x",
                "y",
                "z",
                "resource_reference",
                "creation_time",
            )
        )
        or any(character[k] != resource[k] for k in ("map_id", "instance_id"))
    ):
        raise ValueError("Dungeon resource no longer matches its owned source")
    member = db.execute(
        "SELECT 1 FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s AND status='active'",
        (resource["instance_id"], character["id"]),
    ).fetchone()
    if member is None:
        raise ValueError("Dungeon resource actor is not a current member")
    for statement, args in [
        (
            "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id WHERE p.character_id=%s AND f.status IN ('placement','active') LIMIT 1",
            (character["id"],),
        ),
        (
            "SELECT 1 FROM player_exchange_members m JOIN player_exchanges e ON e.id=m.exchange_id WHERE m.character_id=%s AND (e.state='active' OR (e.state='invitation' AND e.expires_at>%s)) LIMIT 1",
            (character["id"], store.now()),
        ),
        (
            "SELECT 1 FROM craft_occupations WHERE character_id=%s AND state='active' LIMIT 1",
            (character["id"],),
        ),
    ]:
        if db.execute(statement, args).fetchone():
            raise ValueError(
                "Finish the current activity before using a dungeon resource"
            )
    action = next(
        (
            a
            for a in rule["actions"]
            if a["stage"] == resource["stage"]
            and a["action_id"] == native_action["action_id"]
        ),
        None,
    )
    if action is None or digest(native_action) != action["action_sha256"]:
        raise ValueError("Dungeon resource action is not source-qualified")
    from wakfu_server.dungeon_entry_payment import available

    if not available(db, character["id"], action["item_reference"], action["quantity"]):
        raise ValueError("Required explosion item is unavailable")
    return dict(
        kind="dungeon_resource_obstacle",
        destination_stage=action["destination_stage"],
        region_id=None,
        action=action,
        policy_sha256=digest(rule),
    )


def apply(db, store, character, resource, authority, token):
    """Join the existing occupation receipt transaction; never charge on reserve."""
    from wakfu_server.dungeon_entry_payment import consume

    rows = consume(
        db,
        (character["id"],),
        authority["action"]["item_reference"],
        authority["action"]["quantity"],
    )
    stage = authority["destination_stage"]
    now_ms = int(store.clock() * 1000)
    changed = db.execute(
        "UPDATE dungeon_resource_obstacles SET current_stage=%s,creation_time=%s,last_token=%s "
        "WHERE resource_uid=%s AND current_stage=%s AND policy_sha256=%s",
        (
            stage,
            now_ms,
            token,
            resource["resource_uid"],
            resource["stage"],
            authority["policy_sha256"],
        ),
    )
    if changed.rowcount != 1:
        raise ValueError("Dungeon resource stage changed before explosion")
    event = dict(resource, stage=stage, creation_time=now_ms)
    db.execute(
        "DELETE FROM planting_growth_outbox WHERE resource_uid=%s",
        (resource["resource_uid"],),
    )
    db.execute(
        "DELETE FROM resource_growth_decisions WHERE resource_uid=%s",
        (resource["resource_uid"],),
    )
    if stage == 0:
        db.execute(
            "DELETE FROM planted_resources WHERE resource_uid=%s",
            (resource["resource_uid"],),
        )
    else:
        db.execute(
            "UPDATE planted_resources SET stage=%s,creation_time=%s WHERE resource_uid=%s",
            (stage, now_ms, resource["resource_uid"]),
        )
    db.execute(
        "INSERT INTO planting_growth_outbox(resource_uid,resource,group_payload) VALUES(%s,%s,NULL)",
        (resource["resource_uid"], Jsonb(event)),
    )
    packets = [(12470, struct.pack(">qh", r["uid"], -r["consumed"])) for r in rows]
    return event, packets, [dict(r) for r in rows]


def owned_uids(db):
    if not storage_ready(db):
        return frozenset()
    return frozenset(
        row["resource_uid"]
        for row in db.execute("SELECT resource_uid FROM dungeon_resource_obstacles")
    )


def owns(db, resource_uid):
    """Permanent ownership also excludes delayed foreign growth proposals."""
    if not storage_ready(db):
        return False
    return (
        db.execute(
            "SELECT 1 FROM dungeon_resource_obstacles WHERE resource_uid=%s",
            (resource_uid,),
        ).fetchone()
        is not None
    )


def validate_movement(db, configuration, instance_id, request):
    rule = policy(configuration)
    if rule is None:
        return
    if not storage_ready(db):
        raise ValueError("Dungeon resource storage is unavailable")
    if type(instance_id) is not int:
        raise ValueError("Dungeon resource movement lacks instance ownership")
    rows = db.execute(
        "SELECT o.*,p.stage AS planted_stage FROM dungeon_resource_obstacles o LEFT JOIN planted_resources p USING(resource_uid) WHERE o.instance_id=%s",
        (instance_id,),
    ).fetchall()
    expected = {p["key"]: tuple(p["position"]) for p in rule["placements"]}
    if len(rows) != len(expected) or any(
        r["policy_sha256"] != digest(rule)
        or expected.get(r["obstacle_key"]) != (r["x"], r["y"], r["z"])
        or r["map_id"] != configuration["topology"]["asset_map_id"]
        or r["resource_reference"] != rule["resource_reference"]
        or (r["current_stage"] == 0 and r["planted_stage"] is not None)
        or (r["current_stage"] != 0 and r["planted_stage"] != r["current_stage"])
        for r in rows
    ):
        raise ValueError(
            "Dungeon resource movement lacks its complete pinned obstacle set"
        )
    blocked = {(r["x"], r["y"]) for r in rows if r["current_stage"] != 0}
    current = tuple(request["start_position"][k] for k in ("x", "y", "z"))
    for step in request["steps"]:
        current = tuple(
            current[i] + step["d" + axis] for i, axis in enumerate(("x", "y", "z"))
        )
        if current[:2] in blocked:
            raise ValueError(
                "Destroy the visible resource before crossing its occupied cell"
            )
