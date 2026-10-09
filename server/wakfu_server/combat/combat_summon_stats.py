"""Native eHj fighter data for registered positive-ID class summons."""
import struct

from .combat_snapshot_wire import snapshot_characteristics


def registered_summon_stats(actor, fight, map_id):
    """Serialize the actual registered summon without a player/database lookup."""
    row = getattr(fight, "native_summon_registrations", {}).get(actor.id)
    source = getattr(actor, "native_summon_source", None)
    authority = row.get("authority") if isinstance(row, dict) else None
    if (
        fight.actors.get(actor.id) is not actor
        or not isinstance(source, dict)
        or not isinstance(authority, dict)
        or source.get("native_relation_source")
        != "big.new_bje.fdt_initial_registration"
        or row.get("actor_id") != actor.id
        or authority.get("is_summon") is not True
        or authority.get("is_player") is not False
        or authority.get("breed_id") != source.get("ref")
        or authority.get("native_real_level") != source.get("level")
        or row.get("controller_id") != source.get("controller_id")
        or row.get("controller_id") != getattr(actor, "native_controller_id", None)
        or authority.get("native_controller_id") != row.get("controller_id")
        or row.get("caster_id") != source.get("caster_id")
    ):
        raise ValueError("Missing registered native summon stats source")
    reference, level = source["ref"], source["level"]
    direction = getattr(actor, "direction", None)
    obstacle = actor.native_obstacle_id
    if obstacle == -1:
        from .combat_summon_retirement import retired_summon_ids

        # QI.g calls QK.M(-1), retaining the OUT_OF_PLAY fighter object.
        # Only a fully validated retirement checkpoint authorizes this byte.
        valid_obstacle = actor.id in retired_summon_ids(fight)
    else:
        valid_obstacle = type(obstacle) is int and 0 <= obstacle <= 126
    if (
        type(actor.id) is not int
        or not 0 < actor.id < 1 << 63
        or type(fight.id) is not int
        or not 0 < fight.id < 1 << 31
        or type(map_id) is not int
        or not -(1 << 63) <= map_id < 1 << 63
        or type(reference) is not int
        or not 0 < reference < 32768
        or type(level) is not int
        or not 0 <= level < 32768
        or type(direction) is not int
        or not 0 <= direction < 8
        or type(obstacle) is not int
        or not valid_obstacle
    ):
        raise ValueError("Invalid registered native summon wire identity")
    stats = snapshot_characteristics(actor)
    controlled_by_ai = getattr(actor, "native_controlled_by_ai", None)
    if type(controlled_by_ai) is not bool:
        raise ValueError("Missing actual registered summon po.SX control authority")
    position = struct.pack(
        ">iihqBB",
        *actor.position,
        map_id,
        direction,
        0,
    )
    return (
        b"\x02"
        + position
        # pW.Uh is applied by eGn.zm through eGj.ly: it must preserve dTE.
        + struct.pack(
            ">iBBBBbB", fight.id, 0, 0, int(authority["is_summon"]), 0, obstacle, 0
        )
        + stats
        + bytes((int(controlled_by_ai),))
        + struct.pack(">hB", reference, 1)
        + struct.pack(">hH", level, 0)
        + struct.pack(">qBqBh", actor.id, 1, -1, 0, 0)
    )
