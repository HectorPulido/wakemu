"""Owned death settlement planning, distinct from HP mutation and death delivery."""
from dataclasses import dataclass


@dataclass(frozen=True)
class DeathReconciliationPlan:
    original_order: tuple[int, ...]
    current_id: int
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
        tuple(uid for uid in old_order if uid in participating),
        frozenset(
            actor.team for actor in fight.actors.values() if actor.id in participating
        ),
    )


def apply_death_reconciliation(fight, plan):
    """Preserve wave deferral, victory settlement and successor turn ordering."""
    fight.order = list(plan.surviving_order)
    alive = set(plan.alive_teams)
    defer_victory = False
    if getattr(fight, "rift_wave_state", None) is not None:
        from .rift_combat_adapter import defer_wave_victory

        defer_victory = defer_wave_victory(fight, alive)
    if len(alive) < 2 and not defer_victory:
        fight.phase = "finished"
        fight.winner = next(iter(alive), None)
        fight._event("finished", winner=fight.winner)
    elif plan.current_id in fight.order:
        fight.turn_index = fight.order.index(plan.current_id)
    else:
        start = plan.original_order.index(plan.current_id)
        next_id = next(
            plan.original_order[(start + offset) % len(plan.original_order)]
            for offset in range(1, len(plan.original_order) + 1)
            if plan.original_order[(start + offset) % len(plan.original_order)]
            in fight.order
        )
        fight.turn_index = fight.order.index(next_id)
        fight.turn_id += 1
        fight._begin_turn()


def settle_deaths_shared(fight):
    """Remove inactive timeline entries, settle summons, then reconcile once."""
    from .combat_summon_retirement import settle_summon_retirements
    from .combat_timeline_snapshot import remove

    for identity in tuple(dict.fromkeys(fight.order)):
        if not fight._in_play(fight.actors[identity]):
            remove(fight, identity)
    settle_summon_retirements(fight)
    plan = prepare_death_reconciliation(fight)
    apply_death_reconciliation(fight, plan)
