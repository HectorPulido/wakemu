"""Native participant roster and area identity for the Rii LOS lesson.

Official fight snapshots contain one player and one sack. Native fake-fighter
areas (1808), not monster actors, provide the dynamic LOS obstacles. Their
creation is owned by the original state/effect runner.
"""

from .rii_los_encounter import LOS

AREA_REFERENCE = 1808
SACK_STATE = 8005
OWNER_STATE = 8003
TURN_STATE = 8017


def retire_before_cast(
    fight, dispatcher, packets, *, actor_id, spell_id, target, action_id
):
    """Retire this lesson's previous obstacles before an observed valid shot.

    The native effect tree generates the next obstacles during the same cast.
    Scope the removal to the authenticated owner, target and area reference.
    """
    contract = getattr(fight, "rii_los_lesson_contract", None)
    if isinstance(contract, dict) and contract.get("native_lesson") is True:
        return 0
    if (
        not isinstance(contract, dict)
        or contract.get("native_los_areas") is not True
        or actor_id != contract.get("owner")
        or spell_id != 7968
    ):
        return 0
    sack = fight.actors.get(contract.get("target"))
    if sack is None or tuple(target) != tuple(sack.position) or sack.hp <= 25:
        return 0
    from wakfu_server.combat_effect_area import remove_owned_hour_area
    from wakfu_server.combat_effect_area_codec import area_retirement

    areas = getattr(fight, "native_effect_areas", {})
    uids = sorted(
        uid
        for uid, row in areas.items()
        if row.get("owner_id") == actor_id and row.get("reference") == AREA_REFERENCE
    )
    callbacks = getattr(dispatcher, "native_area_events", None)
    for uid in uids:
        remove_owned_hour_area(fight, uid, callbacks=callbacks)
        if not callable(getattr(callbacks, "area_removed", None)):
            packets.append(area_retirement(fight.id, action_id, uid))
    return len(uids)


def bind(db, owner, monsters):
    """Bind only a one-sack roster with the caller's exact durable receipt."""
    if (
        not isinstance(monsters, (list, tuple))
        or len(monsters) != 1
        or not isinstance(monsters[0], dict)
        or monsters[0].get("ref") != LOS.reference
    ):
        return None
    from .rii_owned_lesson import bind as bind_owned

    contract = bind_owned(db, LOS, owner, monsters)
    if contract is None:
        return None
    contract["native_los_areas"] = True
    return contract


def spawn(store, groups, account_id, generation, character, *, repeat=False):
    """Use the shared owner-scoped single-sack producer; do not create rocks."""
    from .rii_owned_lesson import spawn as spawn_owned

    return spawn_owned(
        store, groups, account_id, generation, character, LOS, repeat=repeat
    )
