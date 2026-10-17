"""Optional step delivery on an already validated complete movement route.

Callers stage the fight and outgoing packets before publishing this operation.
Whole-route rail eligibility and tackle bookkeeping remain authoritative.
"""


def execute_steps(fight, actor, path, *, on_rails, callback):
    from .combat_rail_movement import movement_cost
    from .combat_tackle_movement import movement_tackle_cost
    from .combat_qi_fight import move_registered_actor

    # Compute all prefixes before callbacks change resources, facing or QI.
    # Off-rail complete routes must never receive a cheaper rail-prefix cost.
    schedule = []
    previous_base = previous_ap = previous_mp = 0
    for index in range(1, len(path) + 1):
        base = movement_cost(fight, actor, path[:index])[0] if on_rails else index
        ap, mp = movement_tackle_cost(fight, actor, path[:index])
        schedule.append(
            (
                base - previous_base + mp - previous_mp,
                ap - previous_ap,
                mp - previous_mp,
            )
        )
        previous_base, previous_ap, previous_mp = base, ap, mp

    executed, total_mp, total_ap, total_tackle = [], 0, 0, 0
    for index, (cell, (mp, ap, tackle)) in enumerate(zip(path, schedule)):
        if actor.mp < mp or actor.ap < ap or actor.hp <= 0 or fight.phase != "active":
            break
        before = actor.position
        if getattr(actor, "effect_resource_raw_currents", None) is not None:
            from .combat_resource_pa_notifications import (
                resource_shift_result,
                shift_resource_current,
                resource_raw_current,
            )

            if ap:
                resource_shift_result(actor, 2, ap, subtract=True)
            resource_shift_result(actor, 3, mp, subtract=True)
            ap_before = resource_raw_current(actor, 2)
            if ap:
                shift_resource_current(fight, actor, 2, ap, subtract=True)
            ap_after = resource_raw_current(actor, 2)
            # AP listeners can mutate MP: witness only the following MP setter.
            mp_before = resource_raw_current(actor, 3)
            shift_resource_current(fight, actor, 3, mp, subtract=True)
            mp_after = resource_raw_current(actor, 3)
        else:
            ap_before, mp_before = actor.ap, actor.mp
            actor.ap -= ap
            actor.mp -= mp
            ap_after, mp_after = actor.ap, actor.mp
        fight._sync_resources(actor)
        move_registered_actor(fight, actor, cell)
        executed.append(cell)
        total_mp += mp
        total_ap += ap
        total_tackle += tackle
        from .combat_movement_payment_events import committed_step_payment

        with committed_step_payment(
            fight,
            actor,
            origin=before,
            destination=cell,
            index=index,
            ap_before=ap_before,
            mp_before=mp_before,
            ap_after=ap_after,
            mp_after=mp_after,
            ap_paid=ap_before - ap_after,
            mp_paid=mp_before - mp_after,
        ):
            callback(fight, actor, before, cell)
        if actor.position != cell:
            break
    if not executed:
        raise ValueError("Native movement has no affordable first step")
    return fight._event(
        "movement",
        actor_id=actor.id,
        path=executed,
        cost=total_mp,
        **(
            {"tackle_ap": total_ap, "tackle_mp": total_tackle}
            if total_ap or total_tackle
            else {}
        ),
        **({"on_rails": True} if on_rails else {}),
    )
