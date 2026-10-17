"""Current-client fight actor serialization from local authoritative values."""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
import struct
from wakfu_server.progression import character_xp

EMPTY_EFFECTS = bytes(2)  # eZV.a: signed i16 running-effect count.


def _ai_control_byte(enabled):
    if type(enabled) is not bool:
        raise ValueError("Missing actual native po.SX control authority")
    return bytes((int(enabled),))


def characteristics(
    character, *, wp, ap=6, mp=3, max_ap=None, max_mp=None, max_wp=None
):
    """pl/tA: u16 count, then (PC.aKg byte,current,min,max,bonus)."""
    maximum = character["max_hp"]
    current = character["hp"]
    if not 0 <= current <= maximum < (1 << 31):
        raise ValueError("Invalid fight HP")
    values = (
        (1, current, maximum),
        (2, ap, ap if max_ap is None else max_ap),
        (3, mp, mp if max_mp is None else max_mp),
        (4, wp, wp if max_wp is None else max_wp),
    )
    if any(current > maximum for _, current, maximum in values):
        raise ValueError("Current resource exceeds maximum")
    if any(
        type(value) is not int or not 0 <= value < (1 << 31)
        for _, current, maximum in values
        for value in (current, maximum)
    ):
        raise ValueError("Invalid fight characteristics")
    return struct.pack(">H", len(values)) + b"".join(
        struct.pack(">Biiii", identity, current, 0, maximum, 0)
        for identity, current, maximum in values
    )


def actor_stats(
    character,
    fight_id,
    team=0,
    *,
    wp,
    obstacle_id=None,
    native_qi_retired=False,
    ap=6,
    mp=3,
    direction=0,
    initiative=0,
    max_ap=None,
    max_mp=None,
    max_wp=None,
    characteristics_payload=None,
    native_controlled_by_ai=False,
):
    """myE/Mn: eHf.FIGHTER_DATAS_WITH_XP (3), read by big.ev/eHd.ew.

    The client binds this blob to the outer actor ID before deserialization.
    Its ID and account identity also match the local actor, never a capture.
    """
    if type(fight_id) is not int or not 0 < fight_id < (1 << 31):
        raise ValueError("Invalid fight identity")
    if type(team) is not int or not 0 <= team < 128:
        raise ValueError("Invalid fight team")
    if type(direction) is not int or not 0 <= direction < 8:
        raise ValueError("Invalid fight direction")
    if not 1 <= character["level"] <= MAX_CHARACTER_LEVEL:
        raise ValueError("Invalid fight level")
    if not 0 < character["id"] < (1 << 63) or not 0 < character["account_id"] < (
        1 << 63
    ):
        raise ValueError("Invalid actor identity")
    if characteristics_payload is None:
        stats = characteristics(
            character, ap=ap, mp=mp, wp=wp, max_ap=max_ap, max_mp=max_mp, max_wp=max_wp
        )
        if type(initiative) is not int or not -(1 << 31) <= initiative < (1 << 31):
            raise ValueError("Invalid fight initiative")
        from wakfu_server.equipment_stats import bonuses

        extra = {
            identity: value
            for identity, value in bonuses(character)["stats"].items()
            if identity not in (1, 2, 3, 4, 35) and value != 0
        }
        if any(
            not 0 <= identity <= 255 or not -(1 << 31) <= value < (1 << 31)
            for identity, value in extra.items()
        ):
            raise ValueError("Invalid equipment characteristic")
        stats = (
            struct.pack(">H", 5 + len(extra))
            + stats[2:]
            + struct.pack(">Biiii", 35, initiative, -(1 << 31), (1 << 31) - 1, 0)
        )
        stats += b"".join(
            struct.pack(">Biiii", identity, value, -(1 << 31), (1 << 31) - 1, 0)
            for identity, value in sorted(extra.items())
        )
    else:
        stats = characteristics_payload
    from .combat_characteristic_order import health_dependency_order

    stats = health_dependency_order(stats)
    position = struct.pack(
        ">iihqBB",
        character["x"],
        character["y"],
        character["z"],
        character["map_id"],
        direction,
        0,
    )
    obstacle = team if obstacle_id is None else obstacle_id
    if type(obstacle) is not int or not (
        0 <= obstacle <= 126 or native_qi_retired is True and obstacle == -1
    ):
        raise ValueError("Invalid native obstacle byte")
    fight = struct.pack(">iBBBBbB", fight_id, 0, 0, 0, 0, obstacle, 0)
    return (
        b"\x03"
        + struct.pack(">q", character_xp(character))
        + position
        + fight
        + stats
        + _ai_control_byte(native_controlled_by_ai)
        + struct.pack(">hB", character["breed"], 0)
        + stats
        + struct.pack(
            ">qBqBh", character["id"], 0, character["account_id"], 0, character["level"]
        )
    )


def actor_effects():
    """myF/Mo: start with no remote running effects."""
    return EMPTY_EFFECTS


def monster_actor_stats(
    actor,
    fight_id,
    team=None,
    direction=0,
    *,
    characteristics_payload=None,
    obstacle_id=None,
    native_controlled_by_ai=False,
    native_qi_retired=False,
    fight_property_counts=None,
):
    """NPC eHj format2; public stats use sP, not the player's pl section."""
    identity = actor["id"]
    team = actor["team"] if team is None else team
    if type(identity) is not int or not -(1 << 63) < identity < 0:
        raise ValueError("Invalid NPC identity")
    if not 0 < fight_id < (1 << 31) or team not in (0, 1) or not 0 <= direction < 8:
        raise ValueError("Invalid NPC fight")
    if characteristics_payload is None:
        stats = characteristics(
            actor,
            ap=actor["ap"],
            mp=actor["mp"],
            wp=actor["wp"],
            max_ap=actor.get("max_ap"),
            max_mp=actor.get("max_mp"),
            max_wp=actor.get("max_wp"),
        )
        # Include initiative35 as an owned stat for authoritative turn ordering.
        statcount = struct.unpack_from(">H", stats)[0]
        stats = (
            struct.pack(">H", statcount + 1)
            + stats[2:]
            + struct.pack(
                ">Biiii", 35, actor["initiative"], -(1 << 31), (1 << 31) - 1, 0
            )
        )
    else:
        stats = characteristics_payload
    from .combat_characteristic_order import health_dependency_order

    stats = health_dependency_order(stats)
    position = struct.pack(
        ">iihqBB", actor["x"], actor["y"], actor["z"], actor["map_id"], direction, 0
    )
    obstacle = team if obstacle_id is None else obstacle_id
    if type(obstacle) is not int or not (
        0 <= obstacle <= 126 or native_qi_retired is True and obstacle == -1
    ):
        raise ValueError("Invalid native obstacle byte")
    from .combat_property_wire import (
        fight_property_payload,
        ordinary_monster_property_counts,
    )

    # The native rK component follows fight characteristics, separately from
    # pW's optional descriptor flag. Null rK clears the client's PB.
    counts = (
        ordinary_monster_property_counts(actor)
        if fight_property_counts is None
        else fight_property_counts
    )
    fight = struct.pack(">iBBBBbB", fight_id, 0, 0, 0, 0, obstacle, 0)
    return (
        b"\x02"
        + position
        + fight
        + stats
        + fight_property_payload(counts)
        + struct.pack(">h", actor["ref"])
        + _ai_control_byte(native_controlled_by_ai)
        + struct.pack(">hH", actor["level"], 0)
        + struct.pack(">qBqBh", identity, 1, -1, 0, 0)
    )


def _forced_qi_retired(fight, actor, fight_id):
    """Only an actual completed934 transition authorizes the signed absent byte."""
    if fight is None:
        return False
    if fight.id != fight_id or fight.actors.get(actor.id) is not actor:
        raise ValueError("Mismatched actual retirement serialization context")
    from .combat_forced_retirement import retired_forced_fighter_ids
    from .combat_qi_fight import current_registry

    retired = retired_forced_fighter_ids(fight)
    if actor.id not in retired:
        return False
    # Validate complete actual spatial population, not just a copied receipt.
    current_registry(fight)
    return True


def actual_actor_stats(
    character, actor, fight_id, *, wp_current, wp_maximum, direction=0, fight=None
):
    """PC snapshot after movement/cast; resources remain current/max distinct."""
    if (
        getattr(actor, "native_summon_source", None) is not None
        or getattr(actor, "is_summon", False) is True
    ):
        raise ValueError("Summon stats require current native registration")
    if actor.id != character["id"] or not actor.controlled:
        raise ValueError("Runtime actor does not match owned player")
    current = dict(
        character,
        hp=actor.hp,
        max_hp=actor.max_hp,
        x=actor.position[0],
        y=actor.position[1],
        z=actor.position[2],
    )
    from .combat_snapshot_wire import snapshot_characteristics

    snapshot = (
        snapshot_characteristics(actor)
        if getattr(actor, "effect_stats", None) is not None
        else None
    )
    return actor_stats(
        current,
        fight_id,
        team=actor.team,
        obstacle_id=actor.native_obstacle_id,
        native_qi_retired=_forced_qi_retired(fight, actor, fight_id),
        characteristics_payload=snapshot,
        ap=actor.ap,
        mp=actor.mp,
        max_ap=actor.max_ap,
        max_mp=actor.max_mp,
        wp=wp_current,
        max_wp=wp_maximum,
        initiative=actor.initiative,
        direction=getattr(actor, "direction", direction),
        native_controlled_by_ai=getattr(actor, "native_controlled_by_ai", None),
    )


def actual_monster_actor_stats(
    monster, actor, fight_id, *, wp_current, wp_maximum, direction=0, fight=None
):
    """NPC snapshot from live fight resources, preserving its native reference."""
    from .combat_property_wire import ordinary_monster_property_counts

    if (
        getattr(actor, "native_summon_source", None) is not None
        or getattr(actor, "is_summon", False) is True
    ):
        raise ValueError("Summon stats require current native registration")
    if actor.id != monster["id"] or actor.controlled:
        raise ValueError("Runtime actor does not match owned monster")
    current = dict(
        monster,
        hp=actor.hp,
        max_hp=actor.max_hp,
        ap=actor.ap,
        max_ap=actor.max_ap,
        mp=actor.mp,
        max_mp=actor.max_mp,
        wp=wp_current,
        max_wp=wp_maximum,
        initiative=actor.initiative,
        team=actor.team,
        x=actor.position[0],
        y=actor.position[1],
        z=actor.position[2],
    )
    from .combat_snapshot_wire import snapshot_characteristics

    snapshot = (
        snapshot_characteristics(actor)
        if getattr(actor, "effect_stats", None) is not None
        else None
    )
    return monster_actor_stats(
        current,
        fight_id,
        obstacle_id=actor.native_obstacle_id,
        direction=getattr(actor, "direction", direction),
        characteristics_payload=snapshot,
        native_controlled_by_ai=getattr(actor, "native_controlled_by_ai", None),
        native_qi_retired=(
            _forced_qi_retired(fight, actor, fight_id)
            or getattr(actor, "native_ordinary_qi_retirement", {}).get("source")
            == "wakemu.owned-npc-state2-qi-completion-v1"
        ),
        fight_property_counts=ordinary_monster_property_counts(monster, actor),
    )
