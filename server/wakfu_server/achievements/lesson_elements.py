"""Validate elemental-weakness lessons from authenticated combat facts.

The caller owns the encounter and produces the hit element, current target
resistances and turn serial from the server's combat transaction.  Neither a
client-selected element nor a spell icon is sufficient evidence for a hit.
This planning primitive does not create encounters or grant quest progress.
"""
from copy import deepcopy
from math import isfinite


# Native combat effect element identifiers and target resistance stat IDs.
ELEMENT_RESISTANCE = {2: 28, 4: 29, 3: 30, 5: 31}


def resistance_profile(weakness):
    """Return the reconstructed lesson sack's four authoritative resistances.

    The client screenshot shows 32000 for the other three and zero for the
    weakness. The caller must project this snapshot to every fight viewer.
    """
    if type(weakness) is not int or weakness not in ELEMENT_RESISTANCE:
        raise ValueError("Invalid elemental lesson weakness")
    return {
        stat: 0 if element == weakness else 32000
        for element, stat in ELEMENT_RESISTANCE.items()
    }


def observe(
    state,
    *,
    owner_id,
    target_id,
    source_id,
    hit_target_id,
    element,
    resistances,
    turn_serial,
    damage
):
    """Count positive hits against a lowest resistance, including the same turn.

    The returned state is JSON-serializable and belongs to a single identified
    encounter. The caller must retain it with the combat snapshot and settle
    the quest only after the required count. Equal minimum resistances qualify.
    """
    if (
        not isinstance(state, dict)
        or set(state) != {"hits", "last_turn"}
        or type(state["hits"]) is not int
        or not 0 <= state["hits"] <= 4
        or (
            state["last_turn"] is not None
            and (type(state["last_turn"]) is not int or state["last_turn"] < 0)
        )
        or type(owner_id) is not int
        or owner_id <= 0
        or type(target_id) is not int
        or target_id == 0
        or type(source_id) is not int
        or type(hit_target_id) is not int
        or type(element) is not int
        or type(turn_serial) is not int
        or turn_serial < 0
        or type(damage) is not int
        or damage < 0
    ):
        raise ValueError("Invalid elemental lesson event")
    if not isinstance(resistances, dict) or any(
        type(resistances.get(stat)) not in (int, float)
        or not isfinite(resistances[stat])
        for stat in ELEMENT_RESISTANCE.values()
    ):
        raise ValueError("Incomplete elemental resistance snapshot")
    candidate = deepcopy(state)
    if (
        candidate["hits"] == 4
        or source_id != owner_id
        or hit_target_id != target_id
        or damage == 0
        or element not in ELEMENT_RESISTANCE
        or (candidate["last_turn"] is not None and turn_serial < candidate["last_turn"])
    ):
        return candidate
    values = [resistances[stat] for stat in ELEMENT_RESISTANCE.values()]
    if resistances[ELEMENT_RESISTANCE[element]] == min(values):
        candidate["hits"] += 1
        candidate["last_turn"] = turn_serial
    return candidate
