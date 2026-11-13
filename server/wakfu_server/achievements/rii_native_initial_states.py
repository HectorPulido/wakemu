"""Captured state carriers for explicitly admitted native Rii encounters.

Applications use the retained-effect engine so the original subscriptions and
effect trees remain authoritative.  A caller must discard its preview on error.
"""


def install(dispatcher):
    """Install the observed LOS participants' carriers before fight-start events."""
    fight = dispatcher.native_retention.fight
    contract = getattr(fight, "rii_los_lesson_contract", None)
    if not isinstance(contract, dict) or contract.get("native_los_areas") is not True:
        return False
    owner, target = contract.get("owner"), contract.get("target")
    if (
        type(owner) is not int
        or owner <= 0
        or type(target) is not int
        or target >= 0
        or owner not in fight.actors
        or target not in fight.actors
        or fight.actors[owner].team == fight.actors[target].team
    ):
        raise ValueError("Invalid native Rii LOS state participants")
    from wakfu_server.rift_native_gameplay import apply_native_carrier

    # The original capture applies 8005 to the sack, then 8003 to the player.
    apply_native_carrier(dispatcher, actor_id=target, reference=8005, grade=1)
    apply_native_carrier(dispatcher, actor_id=owner, reference=8003, grade=1)
    return True
