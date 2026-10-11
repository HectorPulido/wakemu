"""Persistent ordinary native doors; dungeon progression owns its own gates."""
import hashlib
import math
import struct

from wakfu_server import world_static
from wakfu_server.environment_interactions import _guard, _position
from wakfu_server.inventory_items import _lease


def request(body):
    if type(body) is not bytes or len(body) != 12:
        raise ValueError("Invalid native door request")
    identity, action, parameter = struct.unpack(">qHH", body)
    if identity <= 0 or action not in (17, 18) or parameter:
        raise ValueError("Unsupported ordinary door action")
    return identity, 0 if action == 17 else 1


def _native(map_id, identity):
    return next(
        (
            row
            for row in world_static.objects(map_id)
            if row["id"] == identity and row["type"] == "Door"
        ),
        None,
    )


def _qualified(row, map_id, identity):
    native = _native(map_id, identity)
    if row is None or native is None:
        raise ValueError("Door is not an admitted ordinary public door")
    if (
        row["payload_sha256"]
        != hashlib.sha256(bytes.fromhex(native["payload_hex"])).hexdigest()
    ):
        raise ValueError("Door definition belongs to a different native catalog")
    return dict(row)


def _definition(db, map_id, identity):
    row = db.execute(
        "SELECT * FROM environment_door_definitions WHERE map_id=%s AND object_id=%s",
        (map_id, identity),
    ).fetchone()
    return _qualified(row, map_id, identity)


def definition(store, map_id, identity):
    with store.connection() as db:
        try:
            return _definition(db, map_id, identity)
        except ValueError:
            return None


def state_packet(rule, state):
    if type(state) is not int or state not in (0, 1):
        raise ValueError("Ordinary door cannot change locked or unknown states")
    payload = bytearray.fromhex(rule["state_payload_hex"])
    if len(payload) != 19 or payload[:7] != bytes.fromhex("01020000000602"):
        raise ValueError("Invalid original door synchronization")
    # bEI decodes state, visible/usable, bj, bk, bh, Z, additional actions.
    # bBk.dfi makes bk/bh true only when closed. Retain every unrelated flag.
    payload[7:9] = struct.pack(">h", state)
    payload[12] = payload[13] = state
    return 12344, struct.pack(">qH", rule["object_id"], len(payload)) + payload


def interact(store, account_id, generation, character, body, *, blocked=False):
    identity, desired = request(body)
    if blocked or character.get("instance_id", 0) != 0:
        raise ValueError("Ordinary public door is unavailable in this scene")
    for axis in ("x", "y", "z"):
        value = character[axis]
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("Invalid door interaction position")
    with store.connection() as db:
        _lease(store, db, account_id, generation, character["id"])
        _guard(db, character["id"])
        rule = _definition(db, character["map_id"], identity)
        _position(character, rule)
        db.execute("SELECT pg_advisory_xact_lock(%s,%s)", (rule["map_id"], identity))
        row = db.execute(
            "SELECT state FROM environment_door_states "
            "WHERE map_id=%s AND instance_id=0 AND object_id=%s FOR UPDATE",
            (rule["map_id"], identity),
        ).fetchone()
        current = rule["initial_state"] if row is None else row["state"]
        if current not in (0, 1):
            raise ValueError("Door is locked or owned by another authority")
        # Never close the gate through an actor already standing in its cell.
        if (
            desired == 1
            and db.execute(
                "SELECT 1 FROM characters c JOIN sessions s ON s.character_id=c.id "
                "AND s.account_id=c.account_id WHERE c.map_id=%s AND c.instance_id=0 "
                "AND c.x=%s AND c.y=%s AND c.z=%s AND c.deleted_at IS NULL "
                "AND s.expires_at>%s LIMIT 1",
                (rule["map_id"], rule["x"], rule["y"], rule["z"], store.now()),
            ).fetchone()
        ):
            raise ValueError("Door cell is occupied")
        db.execute(
            "INSERT INTO environment_door_states(map_id,instance_id,object_id,state) "
            "VALUES(%s,0,%s,%s) ON CONFLICT(map_id,instance_id,object_id) "
            "DO UPDATE SET state=EXCLUDED.state",
            (rule["map_id"], identity, desired),
        )
        return {
            "object_id": identity,
            "state": desired,
            "replay": current == desired,
            "packet": state_packet(rule, desired),
        }


def _states(store, map_id, instance_id):
    if type(instance_id) is not int or instance_id != 0:
        return ()
    with store.connection() as db:
        rows = db.execute(
            "SELECT d.*,COALESCE(s.state,d.initial_state) AS current_state "
            "FROM environment_door_definitions d LEFT JOIN environment_door_states s "
            "ON s.map_id=d.map_id AND s.object_id=d.object_id AND s.instance_id=%s "
            "WHERE d.map_id=%s ORDER BY d.object_id",
            (instance_id, map_id),
        ).fetchall()
        return tuple(
            (_qualified(r, map_id, r["object_id"]), r["current_state"]) for r in rows
        )


def snapshots(store, map_id, instance_id, object_ids=None):
    return tuple(
        state_packet(rule, state)
        for rule, state in _states(store, map_id, instance_id)
        if object_ids is None or rule["object_id"] in object_ids
    )


def blocked_cells(store, map_id, instance_id):
    return frozenset(
        (rule["x"], rule["y"], rule["z"])
        for rule, state in _states(store, map_id, instance_id)
        if state == 1
    )


def validate_movement(store, character, movement):
    """Reject ordinary exploration paths crossing a closed native door.

    Existing movement geometry and private dungeon frontier checks retain their
    authority. A diagonal cannot cut a closed doorway through either cardinal
    intermediate cell on the same floor.
    """
    blocked = blocked_cells(store, character["map_id"], character.get("instance_id", 0))
    current = tuple(movement["start_position"][axis] for axis in ("x", "y", "z"))
    # A scene replay or an in-flight route can leave the actor in a newly
    # closed cell. Allow departure; admitting another blocked target is denied.
    for step in movement["steps"]:
        target = tuple(
            current[i] + step["d" + axis] for i, axis in enumerate(("x", "y", "z"))
        )
        if target in blocked:
            raise ValueError("Movement crosses a closed ordinary door")
        if abs(target[0] - current[0]) == 1 and abs(target[1] - current[1]) == 1:
            corners = {(target[0], current[1], z) for z in (current[2], target[2])}
            corners.update((current[0], target[1], z) for z in (current[2], target[2]))
            if corners & blocked:
                raise ValueError("Diagonal movement crosses a closed ordinary door")
        current = target
    return current
