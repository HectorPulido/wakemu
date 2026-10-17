"""Separate native turn phases, with explicit emulated-server delivery policy.

Installed effect descriptions197715/339741 identify1001 as start;343079/339766
identify1002 as end. No client server-producer callsite is claimed. Null source,
channels and the timing relative to expiration are server policy; Qf retains
its native priority, masks and criteria. Each owned boundary is delivered once.
"""
from .combat_event_replay import NativeExternalEvent


TURN_BOUNDARY_POLICY = "wakemu.owned-turn-boundary-facts-v1"


def validate_turn_boundary_context(context, *, fight=None):
    """Validate owned server facts while preserving the native null Qe source."""
    events = {"start": 1001, "end": 1002, "regeneration": 1037}
    if (
        not isinstance(context, dict)
        or set(context) != {"policy", "actor_id", "turn_id", "phase", "event_id"}
        or context.get("policy") != TURN_BOUNDARY_POLICY
        or type(context.get("actor_id")) is not int
        or context["actor_id"] == 0
        or type(context.get("turn_id")) is not int
        or type(context.get("event_id")) is not int
        or type(context.get("phase")) is not str
        or context["phase"] not in events
        or events[context["phase"]] != context["event_id"]
    ):
        raise ValueError("Invalid owned turn boundary facts")
    if fight is not None and (
        fight.phase != "active"
        or fight.current is None
        or fight.current.id != context["actor_id"]
        or fight.turn_id != context["turn_id"]
    ):
        raise ValueError("Owned turn boundary facts differ from active turn")
    return context


def _deliver(dispatcher, *, actor_id, phase, event_id, suppression_phase=None):
    fight = dispatcher.native_retention.fight
    from .combat_turn_boundary import prepare_turn_delivery, execute_turn_delivery

    plan = prepare_turn_delivery(
        fight,
        actor_id=actor_id,
        phase=phase,
        event_id=event_id,
        suppression_phase=suppression_phase,
    )
    return execute_turn_delivery(dispatcher, plan)


def deliver_turn_start(dispatcher, *, actor_id):
    return _deliver(dispatcher, actor_id=actor_id, phase="start", event_id=1001)


def deliver_turn_end(dispatcher, *, actor_id):
    return _deliver(dispatcher, actor_id=actor_id, phase="end", event_id=1002)


def deliver_turn_regeneration(dispatcher, *, actor_id):
    """Replay native1037 regeneration at the owned end boundary.

    Installed343565 and6935 descriptions place natural regeneration at end
    of turn;343570 subscribes1037 and its child343571 gains current WP.
    Delivery after1002 and before expiry is explicit server ordering policy;
    no original client producer or direct resource refill is asserted.
    """
    return _deliver(
        dispatcher,
        actor_id=actor_id,
        phase="regeneration",
        event_id=1037,
        suppression_phase="end",
    )
