"""Source-backed1032 dodger/locker roles after a real paid fei departure.

Native non-reversed subscriptions belong to the dodger (channel6); reversed
subscriptions belong to actual locking opponents (channel60). The original
server callsite is absent. This declared Wakemu join uses the existing native
loss computation and its actual paid commit; no adjacency or item whitelist
is inferred after movement.
"""
from contextlib import contextmanager
from contextvars import ContextVar

POLICY = "wakemu.equipment.paid-native-fei-departure-v1"
_ACTIVE = ContextVar("wakemu_equipment_paid_tackle", default=None)


@contextmanager
def committed_tackle_departure(fight, receipt):
    """Scope exact pre-departure causers on the caller's accepted step preview."""
    if receipt is None or not (receipt["ap"] or receipt["mp"]):
        yield
        return
    actor = fight.actors.get(receipt["actor_id"])
    causers = tuple(receipt["causer_ids"])
    if (
        actor is None
        or actor is not fight.current
        or fight.phase != "active"
        or tuple(actor.position) != tuple(receipt["to_cell"])
        or not causers
        or len(causers) != len(set(causers))
        or any(uid not in fight.actors or uid == actor.id for uid in causers)
        or any(
            type(receipt[key]) is not int or receipt[key] < 0 for key in ("ap", "mp")
        )
    ):
        raise ValueError("Native tackle commit differs from its captured departure")
    previous = _ACTIVE.get()
    if previous is not None:
        raise ValueError("Nested native tackle departure publication")
    scope = dict(fight=fight, receipt=receipt, delivered=False, turn_id=fight.turn_id)
    token = _ACTIVE.set(scope)
    try:
        yield
    finally:
        _ACTIVE.reset(token)


@contextmanager
def tackle_departure_preview(source_fight, preview, payment):
    """Bind the paid departure to its one unpublished area-callback preview.

    Area movement copies the already moved fight before native callbacks. Its
    consumed step-payment witness authenticates this transfer; matching fight
    IDs alone never authorize a different dispatcher population.
    """
    scope = _ACTIVE.get()
    if scope is None:
        yield
        return
    from .combat_movement_payment_events import WakemuMovementPolicy

    receipt = scope["receipt"]
    actor_id = receipt["actor_id"]
    actor = preview.actors.get(actor_id)
    if (
        scope["fight"] is not source_fight
        or scope["delivered"]
        or not isinstance(payment, WakemuMovementPolicy)
        or payment.source_fight is not source_fight
        or payment.publication
        or preview is source_fight
        or preview.id != source_fight.id
        or scope["turn_id"] != source_fight.turn_id
        or preview.turn_id != scope["turn_id"]
        or preview.phase != "active"
        or actor is None
        or preview.current is not actor
        or actor is source_fight.actors.get(actor_id)
        or tuple(actor.position) != tuple(receipt["to_cell"])
        or payment.payer_id != actor_id
        or payment.receipt["origin"] != tuple(receipt["from_cell"])
        or payment.receipt["destination"] != tuple(receipt["to_cell"])
        or payment.receipt["turn_id"] != scope["turn_id"]
        or receipt["ap"] > payment.receipt["ap_paid"]
        or receipt["mp"] > payment.receipt["mp_paid"]
    ):
        raise ValueError("Native tackle preview lacks its consumed departure payment")
    published = dict(scope, fight=preview)
    token = _ACTIVE.set(published)
    try:
        yield
    finally:
        scope["delivered"] = published["delivered"]
        _ACTIVE.reset(token)


def deliver_tackle_boundary(dispatcher, *, actor_id, from_cell, to_cell, action_id):
    """Publish only actual positive-tax participant roles, once per paid step."""
    scope = _ACTIVE.get()
    if scope is None:
        return ()
    fight = dispatcher.native_retention.fight
    receipt = scope["receipt"]
    if (
        scope["fight"] is not fight
        or scope["turn_id"] != fight.turn_id
        or receipt["actor_id"] != actor_id
        or tuple(receipt["from_cell"]) != tuple(from_cell)
        or tuple(receipt["to_cell"]) != tuple(to_cell)
        or actor_id not in fight.actors
        or tuple(fight.actors[actor_id].position) != tuple(to_cell)
        or type(action_id) is not int
        or action_id <= 0
    ):
        raise ValueError("Native tackle event has no matching accepted departure")
    if scope["delivered"]:
        return ()
    scope["delivered"] = True
    from .combat_equipment_external_events import deliver_scoped_pairs

    recipients = ((actor_id, 6),) + tuple((uid, 60) for uid in receipt["causer_ids"])
    return deliver_scoped_pairs(dispatcher, event_id=1032, recipients=recipients)
