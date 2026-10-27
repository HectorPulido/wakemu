"""Explicit Wakemu paid-weapon boundaries; original server caller unavailable.

1018 arms original listeners before this item's roots, so their event2 eZJ can
modify the actual weapon damage faq. 1015 removes temporary listeners only
following successful roots. This is not a spell cast or a cosmetic finisher.
"""
from contextlib import contextmanager

from .combat_event_replay import NativeExternalEvent

POLICY = "wakemu.paid-weapon-boundaries-v1"


def _validate(dispatcher, plan):
    fight = dispatcher.native_retention.fight
    actor_id = plan.get("actor_id")
    caster = fight.actors.get(actor_id)
    payment = plan.get("native_weapon_payment")
    container = plan.get("native_retained_container")
    if (
        caster is None
        or fight.current is not caster
        or fight.phase != "active"
        or plan.get("slot") != 15
        or type(plan.get("item_uid")) is not int
        or plan["item_uid"] <= 0
        or type(plan.get("item_reference")) is not int
        or plan["item_reference"] <= 0
        or container
        != dict(
            present=True,
            type=12,
            id=plan["item_reference"],
            is_spell=False,
            protected=None,
        )
        or not isinstance(payment, dict)
        or payment.get("policy") != POLICY
        or payment.get("actor_id") != actor_id
        or payment.get("item_uid") != plan["item_uid"]
        or not callable(getattr(dispatcher, "replay_event", None))
        or not hasattr(dispatcher, "native_clone_authority")
    ):
        raise ValueError("Weapon event requires its owned paid item action")
    before, after = payment.get("before"), payment.get("after")
    costs = plan.get("costs")
    if (
        not isinstance(before, tuple)
        or not isinstance(after, tuple)
        or len(before) != 3
        or len(after) != 3
        or not isinstance(costs, dict)
        or any(type(value) is not int for value in (*before, *after))
        or any(
            type(costs.get(key)) is not int or costs[key] < 0
            for key in ("ap", "mp", "wp")
        )
        or tuple(before[i] - costs[key] for i, key in enumerate(("ap", "mp", "wp")))
        != after
        or any(value < 0 for value in after)
        or (caster.ap, caster.mp, caster.effect_stats[4]) != after
    ):
        raise ValueError("Weapon event differs from its actual resource payment")
    from .combat_active_spell import active_spell_container

    if active_spell_container(fight).get("present"):
        raise ValueError("Weapon boundary cannot run inside an active spell")
    return fight, actor_id


@contextmanager
def weapon_event_scope(dispatcher, plan):
    """Wrap one admitted private weapon execution, never a restored listener."""
    if not hasattr(dispatcher, "native_retention"):
        # Custom component dispatchers have no native Qf publication surface.
        yield
        return
    fight, actor_id = _validate(dispatcher, plan)
    from .combat_cast_events import _deliver

    # Native local/reverse/global subscription selection makes these mutually
    # exclusive for each listener. Outer Arma de Luz is reverse60, not local6.
    _deliver(dispatcher, plan, 1018)
    yield
    from .combat_external_event_removal import has_removal_subscription

    if not has_removal_subscription(dispatcher, 1015):
        return
    recipients = [(actor_id, 4), (actor_id, 40)]
    if hasattr(fight, "native_global_pv_collections"):
        from .combat_global_pv_collections import global_pv_iterator

        recipients.extend(
            (identity, 41) for identity in global_pv_iterator(fight, caster_id=actor_id)
        )
    for identity, channel in recipients:
        dispatcher.replay_event(
            NativeExternalEvent(identity, (1015,), channel),
            authority=dispatcher.native_clone_authority,
        )
