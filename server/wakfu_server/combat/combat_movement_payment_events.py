"""Explicit Wakemu caller policy for paid, committed voluntary movement.

Installed6269/339726 tooltips specify damage after own-turn movement; native
listeners subscribe to channel3/event74. eWf.bbx emits74 when mh is true.
The original server caller is unavailable. This module supplies that caller
policy from an actual step-payment witness, never from an arbitrary spell.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

_POLICY = "wakemu.committed-step-eWf.v1"
_WP_POLICY = "wakemu.committed-step-eWf.v2"
_step_payment = ContextVar("committed_step_payment", default=None)


def _raw_resources(actor):
    if getattr(actor, "effect_resource_raw_currents", None) is not None:
        from .combat_resource_pa_notifications import resource_raw_current

        return (resource_raw_current(actor, 2), resource_raw_current(actor, 3))
    return (actor.ap, actor.mp)


@contextmanager
def committed_step_payment(
    fight,
    actor,
    *,
    origin,
    destination,
    index,
    ap_before,
    mp_before,
    ap_paid,
    mp_paid,
    ap_after=None,
    mp_after=None,
    wp_before=None,
    wp_after=None,
    wp_paid=0,
):
    """Only execute_steps calls this after its actual resource debit and QI move."""
    actual_after = _raw_resources(actor)
    if ap_after is None:
        ap_after = actual_after[0]
    if mp_after is None:
        mp_after = actual_after[1]
    if (
        fight.phase != "active"
        or fight.current is not actor
        or fight.actors.get(actor.id) is not actor
        or actor.position != destination
        or origin == destination
        or type(index) is not int
        or index < 0
        or any(
            type(v) is not int or v < 0
            for v in (ap_before, mp_before, ap_paid, mp_paid)
        )
        or ap_before - ap_after != ap_paid
        or mp_before - mp_after != mp_paid
        or ap_paid > 127
        or mp_paid > 127
    ):
        raise ValueError("Missing actual committed movement payment witness")
    receipt = dict(
        fight=fight,
        fight_id=fight.id,
        actor_id=actor.id,
        turn_id=fight.turn_id,
        origin=tuple(origin),
        destination=tuple(destination),
        index=index,
        ap_before=ap_before,
        mp_before=mp_before,
        ap_after=ap_after,
        mp_after=mp_after,
        ap_effective_after=actor.ap,
        mp_effective_after=actor.mp,
        ap_raw_post=actual_after[0],
        mp_raw_post=actual_after[1],
        ap_paid=ap_paid,
        mp_paid=mp_paid,
        consumed=False,
    )
    if wp_before is not None or wp_after is not None or wp_paid != 0:
        wp_current = (actor.effect_stats or {}).get(4)
        if (
            any(
                type(value) is not int or value < 0
                for value in (wp_before, wp_after, wp_paid, wp_current)
            )
            or wp_before - wp_after != wp_paid
            or wp_paid != 1
            or wp_current != wp_after
        ):
            raise ValueError("Missing actual committed movement WP payment witness")
        from .combat_hour_travel import current_hour_movement_boundary

        hour = current_hour_movement_boundary(fight, actor.id, origin, destination)
        if hour is None:
            raise ValueError("Movement WP payment lacks its actual HOUR boundary")
        receipt.update(
            wp_before=wp_before,
            wp_after=wp_after,
            wp_paid=wp_paid,
            wp_effective_after=wp_current,
            hour_boundary=dict(hour),
        )
    token = _step_payment.set(receipt)
    try:
        yield
    finally:
        _step_payment.reset(token)


def consume_step_payment(fight, *, actor_id, origin, path):
    receipt = _step_payment.get()
    if receipt is None:
        return None  # Direct/forced/legacy callbacks have no payment authority.
    actor = fight.actors.get(actor_id)
    if (
        actor is None
        or fight.phase != "active"
        or receipt["consumed"]
        or receipt["fight"] is not fight
        or receipt["actor_id"] != actor_id
        or receipt["turn_id"] != fight.turn_id
        or receipt["origin"] != tuple(origin)
        or tuple(path) != (receipt["destination"],)
        or fight.current is not actor
        or actor.position != receipt["destination"]
        or (actor.ap, actor.mp)
        != (receipt["ap_effective_after"], receipt["mp_effective_after"])
        or _raw_resources(actor) != (receipt["ap_raw_post"], receipt["mp_raw_post"])
        or "wp_paid" in receipt
        and (actor.effect_stats or {}).get(4) != receipt["wp_effective_after"]
    ):
        raise ValueError("Movement payment receipt does not own this callback")
    receipt["consumed"] = True
    return WakemuMovementPolicy(
        {k: v for k, v in receipt.items() if k not in ("fight", "consumed")}, fight
    )


def valid_movement_descriptor(descriptor, *, caster_id, target_id):
    if not isinstance(descriptor, dict) or set(descriptor) != {
        "runner_class",
        "action_costs",
        "spell_context",
        "movement_payment_policy",
    }:
        return False
    policy = descriptor["movement_payment_policy"]
    if not isinstance(policy, dict):
        return False
    wp_fields = {
        "wp_before",
        "wp_after",
        "wp_paid",
        "wp_effective_after",
        "hour_boundary",
        "payment_phase",
    }
    has_wp = bool(set(policy) & wp_fields)
    if set(policy) != {
        "policy",
        "fight_id",
        "actor_id",
        "turn_id",
        "origin",
        "destination",
        "index",
        "ap_before",
        "mp_before",
        "ap_after",
        "mp_after",
        "ap_paid",
        "mp_paid",
        "ap_effective_after",
        "mp_effective_after",
        "ap_raw_post",
        "mp_raw_post",
        "mi",
        "mh",
    } | (wp_fields if has_wp else set()):
        return False
    if has_wp and (
        any(
            type(policy[key]) is not int or policy[key] < 0
            for key in ("wp_before", "wp_after", "wp_paid", "wp_effective_after")
        )
        or policy["wp_paid"] != 1
        or policy["wp_effective_after"] != policy["wp_after"]
        or policy["wp_before"] - policy["wp_after"] != policy["wp_paid"]
        or policy["payment_phase"] not in ("movement", "hour_wp")
    ):
        return False
    hour_wp = has_wp and policy["payment_phase"] == "hour_wp"
    for key in ("origin", "destination"):
        if (
            not isinstance(policy[key], (tuple, list))
            or len(policy[key]) != 3
            or any(type(v) is not int for v in policy[key])
        ):
            return False
    if has_wp:
        from .combat_hour_travel import validate_hour_boundary_facts

        try:
            hour = validate_hour_boundary_facts(policy["hour_boundary"])
        except ValueError:
            return False
        if (
            hour["actor_id"] != policy["actor_id"]
            or hour["turn_id"] != policy["turn_id"]
            or tuple(hour["from_cell"]) != tuple(policy["origin"])
            or tuple(hour["to_cell"]) != tuple(policy["destination"])
        ):
            return False
    expected_costs = (
        {"ap": 0, "mp": 0, "wp": 1}
        if hour_wp
        else {"ap": policy["ap_paid"], "mp": policy["mp_paid"], "wp": 0}
    )
    if (
        descriptor["runner_class"] != "eWf"
        or descriptor["spell_context"] != {"present": False}
        or policy["policy"] != (_WP_POLICY if has_wp else _POLICY)
        or policy["mi"] is not hour_wp
        or policy["mh"] is not (not hour_wp)
        or type(policy["fight_id"]) is not int
        or not 0 < policy["fight_id"] < (1 << 31)
        or type(policy["actor_id"]) is not int
        or policy["actor_id"] == 0
        or caster_id != target_id
        or caster_id != policy["actor_id"]
        or any(
            type(policy[k]) is not int or policy[k] < 0
            for k in (
                "turn_id",
                "index",
                "ap_before",
                "mp_before",
                "ap_after",
                "mp_after",
                "ap_paid",
                "mp_paid",
                "ap_effective_after",
                "mp_effective_after",
                "ap_raw_post",
                "mp_raw_post",
            )
        )
        or not 0 <= policy["mp_paid"] <= 127
        or policy["ap_paid"] > 127
        or policy["ap_before"] - policy["ap_after"] != policy["ap_paid"]
        or policy["mp_before"] - policy["mp_after"] != policy["mp_paid"]
        or descriptor["action_costs"] != expected_costs
    ):
        return False
    return tuple(policy["origin"]) != tuple(policy["destination"])


@dataclass(frozen=True)
class WakemuMovementPolicy:
    receipt: dict
    source_fight: object = field(compare=False, repr=False)
    publication: list = field(default_factory=list, compare=False, repr=False)

    @property
    def payer_id(self):
        return self.receipt["actor_id"]

    def descriptor(self, costs):
        has_wp = "wp_paid" in self.receipt
        hour_wp = has_wp and costs == {"ap": 0, "mp": 0, "wp": 1}
        fields = dict(self.receipt)
        if has_wp:
            fields["payment_phase"] = "hour_wp" if hour_wp else "movement"
        result = dict(
            runner_class="eWf",
            action_costs=dict(costs),
            spell_context={"present": False},
            movement_payment_policy=dict(
                fields,
                policy=_WP_POLICY if has_wp else _POLICY,
                mi=hour_wp,
                mh=not hour_wp,
            ),
        )
        if not valid_movement_descriptor(
            result, caster_id=self.payer_id, target_id=self.payer_id
        ):
            raise ValueError("Invalid committed movement eWf descriptor")
        return result


def replay_movement_payment(dispatcher, policy):
    """Publish actual paid MP once, without paying again or changing spell policy."""
    if policy is None:
        return ()
    fight = dispatcher.native_retention.fight
    actor = fight.actors.get(policy.payer_id)
    receipt = policy.receipt
    if (
        actor is None
        or fight.phase != "active"
        or fight is policy.source_fight
        or policy.publication
        or fight.id != receipt["fight_id"]
        or fight.current is not actor
        or fight.turn_id != receipt["turn_id"]
        or actor.position != receipt["destination"]
        or (actor.ap, actor.mp)
        != (receipt["ap_effective_after"], receipt["mp_effective_after"])
        or _raw_resources(actor) != (receipt["ap_raw_post"], receipt["mp_raw_post"])
        or "wp_paid" in receipt
        and (actor.effect_stats or {}).get(4) != receipt["wp_effective_after"]
    ):
        raise ValueError("Movement payment differs from unpublished preview")
    from .combat_effect_dispatch import EffectInvocation
    from .combat_cost_payment_events import payment_event_ids

    phases = [dict(ap=receipt["ap_paid"], mp=receipt["mp_paid"], wp=0)]
    if "wp_paid" in receipt:
        phases.insert(0, dict(ap=0, mp=0, wp=receipt["wp_paid"]))
    for costs in phases:
        policy.descriptor(costs)
    policy.publication.append(True)
    events = dispatcher.native_cost_payment_events_factory()
    invocation = EffectInvocation(
        -1,
        -1,
        actor.id,
        actor.id,
        actor.position,
        native_retained_container={"present": False},
    )
    outcomes = []
    # Actual hour WP is a paid non-spell action. Installed314228 subscribes
    # to2263 and excludes only Dial5345; original313167/313252 tooltips specify
    # each WP used. Keep tackle AP/MP away from all special ability events.
    for costs in phases:
        hour_wp = costs["wp"] > 0
        definition = dict(
            effect_class=30,
            native_effect_flags=[],
            native_costs=costs,
            native_movement_payment_policy=policy,
        )
        identifiers = (
            payment_event_ids(costs, special=True)
            if hour_wp
            else tuple(sorted({*payment_event_ids(costs), 74}))
        )
        packed = costs["ap"] | (costs["mp"] << 8) | (costs["wp"] << 16)
        for channel in (3, 4):
            outcomes.extend(
                events.phase(
                    definition,
                    invocation,
                    uid=-1,
                    value=packed,
                    channel=channel,
                    _event_ids=identifiers,
                )
                or ()
            )
    return tuple(outcomes)
