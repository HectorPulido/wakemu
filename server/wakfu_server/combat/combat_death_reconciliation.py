"""Owned death settlement planning, distinct from HP mutation and death delivery."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DeathReconciliationPlan:
    original_order: tuple[int, ...]
    current_id: int
    current_index: int
    surviving_order: tuple[int, ...]
    alive_teams: frozenset[int]


def prepare_death_reconciliation(fight):
    """Resolve native participation; HP alone never replaces in-play authority."""
    old_order = tuple(fight.order)
    current_id = old_order[fight.turn_index]
    participating = {
        actor.id for actor in fight.actors.values() if fight._in_play(actor)
    }
    return DeathReconciliationPlan(
        old_order,
        current_id,
        fight.turn_index,
        tuple(uid for uid in old_order if uid in participating),
        frozenset(
            actor.team for actor in fight.actors.values() if actor.id in participating
        ),
    )


def apply_death_reconciliation(fight, plan):
    """Preserve wave deferral, victory settlement and successor turn ordering."""
    alive = set(plan.alive_teams)
    if getattr(fight, "rift_wave_state", None) is not None:
        from .rift_combat_adapter import finish_defeat

        if finish_defeat(fight, alive):
            fight.order = list(plan.surviving_order)
            return
    defer_victory = False
    if getattr(fight, "rift_wave_state", None) is not None:
        from .rift_combat_adapter import defer_wave_victory

        defer_victory = defer_wave_victory(fight, alive)
    if len(alive) < 2 and not defer_victory:
        fight.order = list(plan.surviving_order)
        fight.phase = "finished"
        fight.winner = next(iter(alive), None)
        fight._event("finished", winner=fight.winner)
    elif plan.current_id in plan.surviving_order:
        fight.order = list(plan.surviving_order)
        # Native additional turns deliberately repeat identities. Filtering
        # preserves the current occurrence, not the first equal actor ID.
        surviving = set(plan.surviving_order)
        fight.turn_index = sum(
            identity in surviving
            for identity in plan.original_order[: plan.current_index]
        )
    else:
        successor_slot = next(
            (plan.current_index + offset) % len(plan.original_order)
            for offset in range(1, len(plan.original_order) + 1)
            if plan.original_order[
                (plan.current_index + offset) % len(plan.original_order)
            ]
            in plan.surviving_order
        )
        wrapped = successor_slot <= plan.current_index
        if wrapped:
            from .combat_round_boundary import complete_round

            # Observe the actual ending actor and original SU occurrence
            # before filtering, including an inactive tail skipped by death.
            if not complete_round(fight):
                fight.order = list(plan.surviving_order)
            fight.turn_index = 0
        else:
            fight.order = list(plan.surviving_order)
            surviving = set(plan.surviving_order)
            fight.turn_index = sum(
                identity in surviving
                for identity in plan.original_order[:successor_slot]
            )
        fight.turn_id += 1
        if wrapped:
            from .combat_round_boundary import finish_turn_budget

            if finish_turn_budget(fight):
                return
        fight._begin_turn()


def settle_deaths_shared(fight):
    """Remove inactive timeline entries, settle summons, then reconcile once."""
    from .combat_summon_retirement import settle_summon_retirements
    from .combat_timeline_snapshot import remove
    from .combat_summon_owner_death import settle as settle_owner_deaths

    settle_owner_deaths(fight)

    for identity in tuple(dict.fromkeys(fight.order)):
        if not fight._in_play(fight.actors[identity]):
            remove(fight, identity)
    settle_summon_retirements(fight)
    plan = prepare_death_reconciliation(fight)
    apply_death_reconciliation(fight, plan)
