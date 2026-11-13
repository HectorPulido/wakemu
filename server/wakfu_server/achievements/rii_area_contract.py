"""Server-bound mechanics for the reconstructed four-sack area lesson.

This is not yet connected to combat: the producer must supply a single cast's
server-selected, actually hit actors and relocate the sacks after each success.
"""
from .lesson_area import observe


def initialize(fight, packets, *, action_id):
    """Grant only the three native area spells in an owned fight preview."""
    contract = getattr(fight, "rii_area_lesson_contract", None)
    if contract is None:
        return False
    if (
        not isinstance(contract, dict)
        or fight.phase != "active"
        or contract.get("initialized") is not None
    ):
        raise ValueError("Invalid area lesson start")
    owner, targets = contract.get("owner"), contract.get("targets")
    if (
        owner not in fight.actors
        or not isinstance(targets, list)
        or len(targets) != 4
        or len(set(targets)) != 4
        or any(
            type(target) is not int
            or target >= 0
            or target not in fight.actors
            or fight.actors[owner].team == fight.actors[target].team
            for target in targets
        )
    ):
        raise ValueError("Invalid area lesson combatants")
    from wakfu_server.rii_lesson_grants import install

    contract["grant_uids"] = install(
        fight,
        owner,
        packets,
        action_id=action_id,
        allocate_uid=fight.allocate_effect_uid,
        lesson="area",
    )
    contract["initialized"] = True
    return True


def complete_cast(fight, *, action_id, source_id, effect_reference, hit_ids):
    """Record a complete server-observed cast in a combat preview.

    The producer must call this exactly once after all individual native
    effects of that cast succeed. It is an error to supply client target data
    or to publish this candidate before the combat transaction commits.
    """
    contract = getattr(fight, "rii_area_lesson_contract", None)
    if not isinstance(contract, dict) or contract.get("initialized") is not True:
        return False
    before = contract.get("hits", 0)
    state = observe(
        {"hits": before, "actions": contract.get("actions", [])},
        owner_id=contract["owner"],
        source_id=source_id,
        target_ids=contract["targets"],
        hit_ids=hit_ids,
        effect_reference=effect_reference,
        action_id=action_id,
    )
    contract.update(state)
    return state["hits"] > before
