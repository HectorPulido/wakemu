"""Transaction-owned mechanics for the reconstructed elemental lesson.

This module does not create encounters, mutate player decks, or publish world
actors. A producer must first bind the owner and the target from an owned
encounter receipt. The native combat transaction owns the returned changes.
"""
from .lesson_elements import observe, resistance_profile


SPELL_EFFECTS = {361189: 2, 361190: 4, 361191: 3, 361192: 5}
WEAKNESSES = (2, 4, 3, 5)
# The official capture has three 7963 casts followed by 7966 during one turn.
# Keep a weakness stable for repeated hits, then project a different one; the
# original server's random selection policy remains unknown.
HIT_WEAKNESSES = (2, 2, 5, 4)


def begin_turn(fight):
    """Rotate resistance only at a new owner turn, after actor initialization.

    Caller must publish the changed characteristic snapshot in the same
    combat transaction. The order is a local reconstruction; the original
    server's selection policy was not captured.
    """
    contract = getattr(fight, "rii_element_lesson_contract", None)
    if not isinstance(contract, dict) or fight.current is None:
        return False
    if fight.current.id != contract.get("owner"):
        return False
    turn = fight.turn_id
    if type(turn) is not int or turn <= 0:
        raise ValueError("Invalid elemental lesson turn")
    if contract.get("profile_turn") == turn:
        return False
    target = fight.actors.get(contract.get("target"))
    if target is None or not isinstance(target.effect_stats, dict):
        raise ValueError("Missing elemental lesson target characteristics")
    index = contract.get("profile_index", -1)
    if type(index) is not int or not -1 <= index < len(WEAKNESSES):
        raise ValueError("Invalid elemental lesson weakness index")
    index = (index + 1) % len(WEAKNESSES)
    profile = resistance_profile(WEAKNESSES[index])
    if (
        not isinstance(target.effect_minima, dict)
        or not isinstance(target.effect_maxima, dict)
        or any(
            type(target.effect_minima.get(stat)) is not int
            or type(target.effect_maxima.get(stat)) is not int
            or not target.effect_minima[stat] <= value <= target.effect_maxima[stat]
            for stat, value in profile.items()
        )
    ):
        raise ValueError("Elemental lesson resistance is outside native bounds")
    target.effect_stats.update(profile)
    contract["profile_index"] = index
    contract["profile_turn"] = turn
    return True


def initialize(fight, packets, *, action_id):
    """Initialize an owned active lesson after native actor snapshots exist."""
    contract = getattr(fight, "rii_element_lesson_contract", None)
    if contract is None:
        return False
    if not isinstance(contract, dict) or fight.phase != "active":
        raise ValueError("Invalid elemental lesson start")
    owner = contract.get("owner")
    target = fight.actors.get(contract.get("target"))
    if (
        owner not in fight.actors
        or target is None
        or fight.actors[owner].team == target.team
    ):
        raise ValueError("Invalid elemental lesson participants")
    if contract.get("initialized") is not None:
        raise ValueError("Elemental lesson already initialized")
    # The target can have the first turn; prepare the first profile regardless.
    # Its owner turn advances the index to 0 exactly once when it arrives.
    original = fight.current
    if original is None:
        raise ValueError("Missing initial elemental lesson turn")
    if original.id != owner:
        # Do not mutate the timeline merely to initialize target stats.
        profile = resistance_profile(WEAKNESSES[0])
        if (
            not isinstance(target.effect_stats, dict)
            or not isinstance(target.effect_minima, dict)
            or not isinstance(target.effect_maxima, dict)
            or any(
                type(target.effect_minima.get(stat)) is not int
                or type(target.effect_maxima.get(stat)) is not int
                or not target.effect_minima[stat] <= value <= target.effect_maxima[stat]
                for stat, value in profile.items()
            )
        ):
            raise ValueError("Elemental lesson resistance is outside native bounds")
        target.effect_stats.update(profile)
    else:
        begin_turn(fight)
    from wakfu_server.rii_lesson_grants import install

    contract["grant_uids"] = install(
        fight,
        owner,
        packets,
        action_id=action_id,
        allocate_uid=fight.allocate_effect_uid,
    )
    contract["initialized"] = True
    return True


def hit(fight, *, source_id, target_id, effect_reference, damage):
    """Return reconstructed tutorial HP damage, recording an authentic hit.

    Only the four specified native effects can count; the damage caller must
    use the returned amount for both native mutation and packet generation.
    This narrowly scoped rule keeps the 100-HP sack alive until four valid
    hits even when a player's level or mastery would otherwise one-shot it.
    """
    contract = getattr(fight, "rii_element_lesson_contract", None)
    if not isinstance(contract, dict) or target_id != contract.get("target"):
        return None
    element = SPELL_EFFECTS.get(effect_reference)
    if element is None or source_id != contract.get("owner") or damage <= 0:
        return 0
    target = fight.actors.get(target_id)
    if target is None or not isinstance(target.effect_stats, dict):
        raise ValueError("Missing elemental lesson target characteristics")
    previous = {"hits": contract.get("hits", 0), "last_turn": contract.get("last_turn")}
    updated = observe(
        previous,
        owner_id=contract["owner"],
        target_id=target_id,
        source_id=source_id,
        hit_target_id=target_id,
        element=element,
        resistances=target.effect_stats,
        turn_serial=fight.turn_id,
        damage=damage,
    )
    contract.update(updated)
    if updated["hits"] > previous["hits"] and updated["hits"] < 4:
        weakness = HIT_WEAKNESSES[updated["hits"] - 1]
        profile = resistance_profile(weakness)
        if (
            not isinstance(target.effect_minima, dict)
            or not isinstance(target.effect_maxima, dict)
            or any(
                type(target.effect_minima.get(stat)) is not int
                or type(target.effect_maxima.get(stat)) is not int
                or not target.effect_minima[stat] <= value <= target.effect_maxima[stat]
                for stat, value in profile.items()
            )
        ):
            raise ValueError("Elemental lesson resistance is outside native bounds")
        target.effect_stats.update(profile)
    return 25 if updated["hits"] > previous["hits"] else 0
