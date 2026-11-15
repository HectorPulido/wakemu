"""Server-owned spell book for the native Rii training fights.

The first lesson uses a class attack to teach facing. The next six switch to
the native lesson morphology, which owns their temporary spells. A bound
lesson accepts that actual book instead of the visitor's saved class deck.
Callers retain casting authority; this module never grants or hides spells.
"""

LESSON_CONTRACTS = (
    "rii_orientation_contract",
    "rii_element_lesson_contract",
    "rii_distance_lesson_contract",
    "rii_los_lesson_contract",
    "rii_area_lesson_contract",
    "rii_movement_lesson_contract",
    "rii_states_lesson_contract",
)


def lesson_contract(fight):
    """Return the single bound training contract of a fight, if any."""
    active = [
        name
        for name in LESSON_CONTRACTS
        if isinstance(getattr(fight, name, None), dict)
    ]
    if len(active) > 1:
        raise ValueError("A training fight cannot bind multiple lessons")
    return getattr(fight, active[0]) if active else None


def lesson_spells(fight):
    """Return the lesson's active spells, or None for an unchanged class book."""
    contract = lesson_contract(fight)
    if contract is None:
        return None
    if isinstance(getattr(fight, "rii_orientation_contract", None), dict):
        # The first lesson teaches facing with the visitor's own first class
        # attack (5562 in the captured Huppermage run). It has no morphology.
        return None
    from .combat_spell_grant import granted_spells
    from .combat_morph_spellbook import morph_record

    owner = contract.get("owner")
    if type(owner) is not int:
        return set()
    allowed = set(granted_spells(fight, owner))
    morph = morph_record(fight, owner)
    if morph is not None:
        allowed.update(set(morph["levels"]) - morph["removed_raw_uids"])
    return allowed


def accepts(fight, actor_id, spell_id):
    """True when the fight is open to this actor's spell, lesson rule included."""
    allowed = lesson_spells(fight)
    if allowed is None:
        return True
    contract = lesson_contract(fight)
    if contract is not None and contract.get("owner") == actor_id:
        return spell_id in allowed
    return True
