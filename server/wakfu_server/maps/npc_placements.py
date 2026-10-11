"""Accredited original NPC positions, independent of dialogue availability.

These actors have no combat registration or server interaction handler. Native
collection actions are explicitly disabled until their own contracts exist.
"""
import re
import struct


def validate(row):
    integers = (
        "actor_id",
        "reference_id",
        "map_id",
        "instance_id",
        "x",
        "y",
        "z",
        "direction",
        "level",
        "visual_id",
    )
    if any(type(row.get(key)) is not int for key in integers):
        raise ValueError("Invalid native NPC position fields")
    if not (
        -9007199254740991 <= row["actor_id"] < 0
        and 0 < row["reference_id"] < 32768
        and 0 < row["map_id"] < 2**31
        and row["instance_id"] == 0
        and all(-(2**31) <= row[k] < 2**31 for k in ("x", "y"))
        and -32768 <= row["z"] < 32768
        and 0 <= row["direction"] < 8
        and 0 < row["level"] < 32768
        and row["visual_id"] > 0
    ):
        raise ValueError("Invalid native NPC position contract")
    if not isinstance(row.get("source_sha256"), str) or not re.fullmatch(
        r"[a-f0-9]{64}", row["source_sha256"]
    ):
        raise ValueError("Missing native NPC source authority")
    name = row.get("name_es")
    if not isinstance(name, str) or not name or len(name.encode("utf-8")) > 65535:
        raise ValueError("Invalid original NPC name")
    actions = row.get("native_action_ids")
    if (
        not isinstance(actions, list)
        or len(actions) > 65535
        or any(type(a) is not int or not 0 < a < 2**31 for a in actions)
        or len(set(actions)) != len(actions)
    ):
        raise ValueError("Invalid native NPC action mask")
    return row


def load_scene(db, map_id, instance_id):
    if instance_id != 0:
        return ()
    rows = db.execute(
        "SELECT npc.* FROM world_native_npc_placements npc "
        "WHERE npc.enabled AND npc.map_id=%s AND npc.instance_id=%s "
        "AND NOT EXISTS (SELECT 1 FROM world_dialogue_npcs dialog WHERE dialog.actor_id=npc.actor_id) "
        "ORDER BY npc.actor_id",
        (map_id, instance_id),
    ).fetchall()
    return tuple(validate(row) for row in rows)


def spawn(row):
    """Publish native format11 with every original collection action masked."""
    validate(row)
    name = row["name_es"].encode("utf-8")
    out = (
        b"\x0b"
        + struct.pack(">qBqH", row["actor_id"], 1, -1, len(name))
        + name
        + struct.pack(">h", row["reference_id"])
    )
    out += struct.pack(
        ">iihqBB", row["x"], row["y"], row["z"], row["map_id"], row["direction"], 0
    )
    out += b"\x01" + struct.pack(">hH", row["level"], 0)
    out += b"\x00" + struct.pack(">iBBBBbB", -1, 0, 0, 0, 0, -1, 0)
    out += b"\x00" + struct.pack(
        ">qHhh", -row["actor_id"], 1, row["reference_id"], row["level"]
    )
    actions = row["native_action_ids"]
    out += struct.pack(">hhH", -1, -1, len(actions)) + b"".join(
        struct.pack(">i", action) for action in actions
    )
    out += bytes(2) + bytes(16) + bytes(3)
    return 12608, b"\x00\x01" + struct.pack(">BqH", 1, row["actor_id"], len(out)) + out
