"""Qualified actions for the reconstructed Rii state lesson.

The installed state descriptions identify the four conditions. The order is
observed in one official run; alternative original sequences are unknown.
The caller provides encounter-owned coloured cells.
Only a server-owned combat producer may call these helpers.
"""
from copy import deepcopy

from wakfu_server.combat_casting_eligibility import native_casting_distance


# Order observed in the official Rii capture: native effects remove states
# 8015, 8016 and 8013 in sequence, followed by the final distant-turn reaction.
STATES = (8015, 8016, 8013, 8014)
REQUIRED = len(STATES)


def observe(
    state,
    *,
    owner_id,
    target_id,
    actor_id,
    target_actor_id,
    event,
    actor_xy,
    target_xy,
    green,
    red,
    spell_id=None
):
    """Return a new four-stage state after an authenticated turn or hit.

    The stage is server-owned. Coordinates must be captured from the combat
    actors at the instant of the action; green/red are encounter-owned cells,
    never coordinates or a state identifier supplied in a network request.
    """
    if (
        not isinstance(state, dict)
        or set(state) != {"hits"}
        or type(state["hits"]) is not int
        or not 0 <= state["hits"] <= REQUIRED
        or type(owner_id) is not int
        or owner_id <= 0
        or type(target_id) is not int
        or target_id == 0
        or type(actor_id) is not int
        or type(target_actor_id) is not int
        or event not in ("turn_end", "hit")
        or any(
            not isinstance(cell, tuple)
            or len(cell) != 2
            or any(type(value) is not int for value in cell)
            for cell in (actor_xy, target_xy, green, red)
        )
        or green == red
    ):
        raise ValueError("Invalid state lesson action")
    result = deepcopy(state)
    if (
        result["hits"] == REQUIRED
        or actor_id != owner_id
        or target_actor_id != target_id
    ):
        return result
    active = STATES[result["hits"]]
    distance = native_casting_distance(actor_xy, target_xy)
    if active == 8014:
        qualifies = event == "turn_end" and distance >= 6
    elif active == 8013:
        qualifies = event == "turn_end" and distance == 1
    elif active == 8015:
        qualifies = event == "hit" and spell_id == 7967 and actor_xy == green
    else:
        qualifies = event == "hit" and spell_id == 7967 and actor_xy == red
    if qualifies:
        result["hits"] += 1
    return result
