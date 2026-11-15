"""Captured Rii training fights have no ordinary monster victory rewards.

All seven official reports keep the same XP/level, and their fight windows
publish no wallet or inventory reward mutations. Quest rewards still belong
to the separate objective-settlement transaction.
"""

from .rii_lesson_spellbook import lesson_contract


def is_owned_training(fight, character_id):
    """Recognize the authenticated owner of a native dojo lesson only."""
    if getattr(fight, "native_fight_model", None) != 14:
        return False
    contract = lesson_contract(fight)
    if contract is None or contract.get("owner") != character_id:
        return False
    actor = fight.actors.get(character_id)
    if actor is None or actor.controlled is not True:
        raise ValueError("Native training reward owner is not a controlled actor")
    orientation = getattr(fight, "rii_orientation_contract", None)
    if contract is not orientation and contract.get("native_lesson") is not True:
        return False
    targets = contract.get("targets", [contract.get("target")])
    if (
        not isinstance(targets, list)
        or not targets
        or len(set(targets)) != len(targets)
        or any(
            type(target) is not int
            or target >= 0
            or target not in fight.actors
            or fight.actors[target].team == actor.team
            for target in targets
        )
    ):
        raise ValueError("Native training rewards lack their owned target roster")
    return True
