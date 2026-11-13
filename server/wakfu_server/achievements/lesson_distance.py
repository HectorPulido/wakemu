"""Reconstructed distance-lesson predicates for authenticated fight events.

The installed text identifies spell 7967 and the guide shows a melee zone
through two cells which changes after each hit. Four alternating hits starting
at melee are a reconstruction consistent with the 25-damage spell and the
observed 100-HP sack; the original server encounter was not captured.

The caller owns a specific encounter, extracts actors and positions from the
server's resolved combat action, and persists the returned state with that
fight. This module does not authorize spells or complete missions.
"""
from copy import deepcopy

from wakfu_server.combat_casting_eligibility import native_casting_distance


SPELL = 7967
REQUIRED_HITS = 4


def observe(
    state,
    *,
    owner_id,
    target_id,
    source_id,
    hit_target_id,
    spell_id,
    source_xy,
    target_xy,
    damage
):
    """Count a qualifying hit in the current reconstructed distance zone.

    Even-numbered hits require melee (one or two cells); odd-numbered hits
    require distance (three or more). An invalid action leaves state intact.
    Positions must be captured at the instant of damage, not supplied by the
    client or reconstructed after an effect may have displaced either actor.
    """
    if (
        not isinstance(state, dict)
        or set(state) != {"hits"}
        or type(state["hits"]) is not int
        or not 0 <= state["hits"] <= REQUIRED_HITS
        or type(owner_id) is not int
        or owner_id <= 0
        or type(target_id) is not int
        or target_id == 0
        or type(source_id) is not int
        or type(hit_target_id) is not int
        or type(spell_id) is not int
        or type(damage) is not int
        or damage < 0
    ):
        raise ValueError("Invalid distance lesson event")
    candidate = deepcopy(state)
    if (
        candidate["hits"] == REQUIRED_HITS
        or source_id != owner_id
        or hit_target_id != target_id
        or spell_id != SPELL
        or damage == 0
    ):
        return candidate
    distance = native_casting_distance(source_xy, target_xy)
    if distance <= 0:
        return candidate
    expects_melee = candidate["hits"] % 2 == 0
    if (distance <= 2) == expects_melee:
        candidate["hits"] += 1
    return candidate
