"""Immutable expiration selection; removal callbacks retain their native owners."""
from dataclasses import dataclass
from .combat_state_timing import StateTimer
from .combat_state_managers import state_managers


@dataclass(frozen=True)
class ExpirationPlan:
    entries: tuple[tuple[int, str, int], ...]


def collect_expiration_due(preview, *, actor_id, round_number, phase, round_cleanup):
    from .combat_timed_expiration import _due

    due = []
    for actor in state_managers(preview):
        for entry in actor.state_ledger.entries:
            if _due(entry.timer, actor_id, round_number, phase, round_cleanup):
                due.append((entry.uid, "state", actor.id))
    for uid, entry in preview.owned_stat_effects.items():
        timer = entry.get("timer")
        if timer is not None:
            timer = StateTimer(**timer)
            if (
                type(timer.actor_id) is not int
                or timer.actor_id not in preview.actors
                or type(timer.expiration_round) is not int
                or not -32768 <= timer.expiration_round <= 32767
                or timer.phase not in ("start", "end")
            ):
                raise ValueError("Invalid owned native effect timer")
            if _due(timer, actor_id, round_number, phase, round_cleanup):
                due.append((uid, "stat", entry["target_id"]))
    for uid, entry in preview.native_owned_group_effects.items():
        timer = entry.get("timer")
        if timer is not None and _due(
            StateTimer(**timer), actor_id, round_number, phase, round_cleanup
        ):
            due.append((uid, "group", entry["target_id"]))
    for uid, entry in getattr(preview, "native_owned_area_effects", {}).items():
        raw = entry.get("timer")
        if raw is None:
            continue
        timer = StateTimer(**raw)
        if (
            type(timer.actor_id) is not int
            or timer.actor_id not in preview.actors
            or type(timer.expiration_round) is not int
            or not -32768 <= timer.expiration_round <= 32767
            or timer.phase not in ("start", "end")
        ):
            raise ValueError("Invalid owned native area timer")
        if _due(timer, actor_id, round_number, phase, round_cleanup):
            due.append((uid, "area", entry["target_id"]))
    return tuple(due)


def order_expiration_due(preview, due):
    order = {uid: index for index, uid in enumerate(preview.native_retained_order)}
    ordered = (
        sorted(due, key=lambda item: order.get(item[0], item[0]))
        if preview.native_retained_tracking and order
        else sorted(due)
    )
    return ExpirationPlan(tuple(ordered))


def prepare_expiration_order(preview, **clock):
    """Offline planner; runtime enters effect resolution before ordering."""
    return order_expiration_due(preview, collect_expiration_due(preview, **clock))
