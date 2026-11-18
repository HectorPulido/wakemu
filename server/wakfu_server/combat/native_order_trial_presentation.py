"""Reviewed server projection of earned order state through native retention.

Original marker profiles are unchanged. This is not an original missing server
callback: only the authenticated optional trial checkpoint supplies its values.
"""

import struct

RECIPES = {
    ("blue", "tomato"): 3051,
    ("blue", "cheese"): 3053,
    ("blue", "pepper"): 3054,
    ("red", "tomato"): 3055,
    ("red", "cheese"): 3056,
    ("red", "pepper"): 3057,
    ("green", "tomato"): 3058,
    ("green", "cheese"): 3059,
    ("green", "pepper"): 3060,
}
ROOTS = dict(zip(RECIPES.values(), range(119009, 119018)))
ROOTS[3050] = 119003
POLICY = "wakemu.order-trial.native-marker-projection.v1"


def desired(fight):
    from .native_order_trial_checkpoint import validate

    document = getattr(fight, "native_order_trial", None)
    if document is None:
        return None
    _proof, _rules, state = validate(document, encounter_id=fight.id, replay=False)
    actor = fight.actors.get(state.owner_id)
    if (
        actor is None
        or not actor.controlled
        or actor.owner_id != document["admission"]["account_id"]
    ):
        raise ValueError("Order marker projection lost its admitted player")
    if state.score % 5 or state.score_state_level > 5000:
        raise ValueError("Earned order score exceeds its original native marker")
    return actor, {
        3050: state.score_state_level,
        **{RECIPES[tuple(recipe)]: 1 for recipe in state.orders},
    }


def synchronize(fight, dispatcher):
    """Apply/remove original carriers on the same private native dispatcher."""
    selection = desired(fight)
    if selection is None:
        return False
    actor, markers = selection
    handler, retention = dispatcher.native_state_handler, dispatcher.native_retention
    if handler.fight is not fight or retention.fight is not fight:
        raise ValueError("Order markers require the current native candidate")
    from .combat_definitions import state_profile
    from .combat_effect_dispatch import EffectInvocation
    from .combat_state_handler import StateCarrierContext
    from .combat_native_timing_context import native_time_payload

    changed = False
    for reference, root in ROOTS.items():
        entries = [e for e in actor.state_ledger.entries if e.reference == reference]
        if len(entries) > 1:
            raise ValueError("Order marker has ambiguous native carrier ownership")
        level = markers.get(reference)
        if entries and level is not None and entries[0].level == level:
            continue
        profile = state_profile(handler.catalog, reference, level or 0)
        if (
            tuple(profile["effects"]) != (root,)
            or profile["duration"] != -1
            or level is not None
            and profile["level"] != level
        ):
            raise ValueError("Original order marker program changed")
        if entries:
            retention.removal(retention.view()).remove((entries[0].uid,))
            changed = True
        if level is None:
            continue
        carrier = StateCarrierContext(
            profile["duration"],
            profile["realtime_duration"],
            False,
            None,
            None,
            False,
            False,
            False,
            0,
            native_time_payload(realtime_remaining=profile["realtime_duration"]),
        )
        if not retention.apply_state_reference(
            handler,
            EffectInvocation(2226, level, actor.id, actor.id, actor.position),
            reference,
            level,
            carrier_context=carrier,
        ):
            raise ValueError("Native order marker application was rejected")
        changed = True
    present = [e for e in actor.state_ledger.entries if e.reference in ROOTS]
    actual = {e.reference: e.level for e in present}
    if len(present) != len(actual) or actual != markers:
        raise ValueError("Native order markers differ from their earned checkpoint")
    return changed


def prepare(fight, runtime, packets):
    """Join a fresh native delivery block without renumbering accepted packets."""
    selection = desired(fight)
    if selection is None:
        return packets
    actor, markers = selection
    if actor.hp <= 0 and fight.native_order_trial["state"]["finished"] is True:
        # An authenticated terminal score is durable, but native state grants
        # must not be forced onto the dead owner after final strike cleanup.
        return packets
    present = [e for e in actor.state_ledger.entries if e.reference in ROOTS]
    current = {e.reference: e.level for e in present}
    if len(present) != len(current):
        raise ValueError("Order marker has ambiguous native carrier ownership")
    if current == markers:
        return packets
    from .combat_runtime_messages import RuntimeMessages

    if (
        type(runtime) is not RuntimeMessages
        or runtime.fight is not fight
        or not callable(runtime.expiration_runtime_factory)
    ):
        raise ValueError("Order marker delivery requires its actual native runtime")
    factory = runtime.expiration_runtime_factory(action_id=runtime.action_id + 1)
    dispatcher, outbox = factory(
        fight, {"native_retained_container": {"present": False}}
    )
    synchronize(fight, dispatcher)
    prefix_actions = tuple(runtime.last_native_delivery)
    fresh = runtime.prepare_delivery(
        tuple(outbox) + ((13420, struct.pack(">i", fight.id)),)
    )
    runtime.last_native_delivery = prefix_actions + tuple(fresh.native_actions)
    return tuple(packets) + tuple(fresh)
