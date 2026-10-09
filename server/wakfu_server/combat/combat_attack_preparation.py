"""Explicit Wakemu first-attack preparation policy, using a real damage Qe.

The original event-500 publisher is unavailable. Preparation's native reverse
subscription must run before damage L1 so its damage listener observes that
same attack. Its eYv consumer requires the actual triggering spell container.
"""
from contextlib import contextmanager
from contextvars import ContextVar


_scope = ContextVar("wakemu_attack_preparation", default=None)


@contextmanager
def attack_preparation_scope(fight, actor_id):
    token = _scope.set(dict(fight=fight, actor_id=actor_id, delivered=False))
    try:
        yield
    finally:
        _scope.reset(token)


def deliver_attack_preparation(
    lifecycle, effect, invocation, *, uid, final_modifier, runner_modifier
):
    scope = _scope.get()
    if scope is None or scope["delivered"]:
        return False
    if (
        lifecycle.preview is not scope["fight"]
        or invocation.caster_id != scope["actor_id"]
    ):
        return False
    from .combat_ordinary_authority import ordinary_container_type

    if ordinary_container_type(lifecycle.preview, lifecycle.plan, invocation) not in (
        11,
        12,
    ):
        return False
    # Mark before replay: reactive children are not another primary attack.
    scope["delivered"] = True
    from .combat_ordinary_events import OrdinaryHealingEvents

    OrdinaryHealingEvents.phase(
        lifecycle,
        effect,
        invocation,
        uid=uid,
        value=0,
        channel=1,
        _event_ids=(500,),
        final_modifier=final_modifier,
        runner_modifier=runner_modifier,
    )
    return True
