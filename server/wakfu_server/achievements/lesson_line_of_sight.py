"""Qualified native line-of-sight lesson hit candidates.

The client identifies spell 7968 and its 25-damage effect. A guide describes
moving rocks and at least four cells of range. Four hits are a reconstruction
from that effect and the observed 100-HP sack, not an original server trace.
This pure helper is intentionally not an encounter or a quest event producer.
"""
from copy import deepcopy

from wakfu_server.combat_casting_eligibility import native_casting_distance


SPELL = 7968
DAMAGE_EFFECT = 361213
REQUIRED_HITS = 4
MIN_RANGE = 4


def observe(
    state,
    *,
    owner_id,
    target_id,
    source_id,
    hit_target_id,
    spell_id,
    effect_reference,
    source_xy,
    target_xy,
    damage,
    casting_los
):
    """Count one qualified cast, using server-owned positions and native ray.

    The caller must only pass the real cast authorization's ray result from
    the current fight, never a client-supplied flag. The normal casting engine
    still owns permission, range, and obstacle checks. No rewards are granted.
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
        or any(
            type(value) is not int
            for value in (source_id, hit_target_id, spell_id, effect_reference, damage)
        )
        or damage < 0
        or type(casting_los) is not bool
    ):
        raise ValueError("Invalid line-of-sight lesson event")
    candidate = deepcopy(state)
    if (
        candidate["hits"] == REQUIRED_HITS
        or source_id != owner_id
        or hit_target_id != target_id
        or spell_id != SPELL
        or effect_reference != DAMAGE_EFFECT
        or not casting_los
        or damage == 0
    ):
        return candidate
    if native_casting_distance(source_xy, target_xy) >= MIN_RANGE:
        candidate["hits"] += 1
    return candidate
