"""Original119018/341 selections, witnessed after actual native304 success.

Initialization timing is a reviewed server join. The lottery, eligibility,
children and native carriers remain original; hard refills use real1001.
"""

from contextvars import ContextVar
from hashlib import sha256
import json
from weakref import ref

from .native_order_trial_presentation import RECIPES

_BY_STATE = {value: key for key, value in RECIPES.items()}
_CHILDREN = dict(zip(range(119019, 119028), RECIPES.values()))
_initial = ContextVar("native_order_initial_lottery", default=None)
LOTTERY_SHA256 = "c557fbae37917190aec94a807216000808939f90fa52058fed6107bddc661bc5"


class _Selection(dict):
    pass


def _digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def placement_authorized(fight, source, target, reference, level):
    scope = _initial.get()
    if (
        scope is None
        or scope[0] is not fight
        or source != target
        or source != scope[2].owner_id
    ):
        return False
    dispatcher = scope[1]
    ancestors = dispatcher._active_ancestors
    return (
        fight.phase == "placement"
        and level == 1
        and len(ancestors) >= 2
        and ancestors[-2] == 119018
        and _CHILDREN.get(ancestors[-1]) == reference
    )


def placement_stat_context(fight, invocation):
    scope = _initial.get()
    if scope is None or scope[0] is not fight:
        return False
    if (
        invocation.caster_id != invocation.target_id
        or invocation.target_id != scope[2].owner_id
    ):
        return False
    ancestors = scope[1]._active_ancestors
    if not ancestors or ancestors[0] != 119018 or invocation.level != 1:
        return False
    if invocation.reference in (119018, *_CHILDREN):
        return True
    if (
        len(ancestors) < 3
        or ancestors[1] not in _CHILDREN
        or invocation.state_uid is None
    ):
        return False
    from .combat_native_container import resolve_state_container
    from .native_order_trial_presentation import ROOTS

    parent = resolve_state_container(fight, invocation.state_uid)
    return (
        parent.reference == _CHILDREN[ancestors[1]]
        and parent.level == 1
        and parent.target_id == scope[2].owner_id
        and invocation.reference == ROOTS[parent.reference]
    )


def record_state(handler, effect, invocation, entry, *, change):
    if (
        effect is None
        or effect.get("effect_class") != 304
        or invocation.reference not in _CHILDREN
    ):
        return None
    from .combat_state_handler import NativeStateHandler
    from .native_order_trial_encounter import policy_for
    from .combat_turn_events import validate_turn_boundary_context
    from .combat_native_container import resolve_state_container

    fight = handler.fight
    policy = policy_for(fight)
    dispatcher = getattr(handler, "native_order_selection_dispatcher", None)
    if policy is None or dispatcher is None:
        return None
    if invocation.target_id != policy.owner_id:
        return None  # Preserve other native recipients without quest authority.
    initial = _initial.get()
    initializing = (
        initial is not None and initial[0] is fight and initial[1] is dispatcher
    )
    if not initializing:
        if getattr(fight, "native_order_trial", None) is None or policy.mode != "hard":
            return None
        boundary = invocation.native_turn_boundary_context
        if boundary is None:
            return None
        validate_turn_boundary_context(boundary, fight=fight)
        if boundary["event_id"] != 1001 or boundary["actor_id"] != policy.owner_id:
            return None
        parent = resolve_state_container(fight, invocation.state_uid)
        if parent.reference != 3052 or parent.target_id != policy.owner_id:
            raise ValueError("Recipe selection lost original3052 source")
    ancestors = dispatcher._active_ancestors
    owner = fight.actors[policy.owner_id]
    if (
        type(handler) is not NativeStateHandler
        or dispatcher.native_state_handler is not handler
        or change.applied is not entry
        or not any(item is entry for item in owner.state_ledger.entries)
        or invocation.caster_id != invocation.target_id
        or invocation.target_id != owner.id
        or entry.reference != _CHILDREN[invocation.reference]
        or entry.level != 1
        or type(invocation.native_running_uid) is not int
        or len(ancestors) < 2
        or ancestors[-2:] != (119018, invocation.reference)
    ):
        raise ValueError("Recipe selection lacks its actual native341 child")
    original = fight._event(
        "native_order_recipe_selected",
        actor_id=owner.id,
        effect_reference=invocation.reference,
        native_uid=invocation.native_running_uid,
        carrier_uid=entry.uid,
        state_reference=entry.reference,
        source_state_uid=invocation.state_uid,
        initialization=initializing,
        turn_id=fight.turn_id,
    )
    witness = _Selection(original)
    witness._origin = ref(fight)
    witness._digest = _digest(witness)
    fight.events[-1] = witness
    return witness


def selected(fight, events, *, initialization=False):
    from .native_order_trial_checkpoint import event_index
    from .native_order_trial_encounter import policy_for

    policy = policy_for(fight)
    if policy is None:
        raise ValueError("Native recipe selection requires its actual constructor")
    witnesses = [
        event for event in events if event.get("kind") == "native_order_recipe_selected"
    ]
    if not witnesses:
        return None
    if len(witnesses) != 3:
        raise ValueError("Native lottery did not produce exactly three recipes")
    references = []
    owner = fight.actors[policy.owner_id]
    for event in witnesses:
        event_index(fight, event)
        if (
            type(event) is not _Selection
            or not callable(getattr(event, "_origin", None))
            or event._origin() is not fight
            or getattr(event, "_digest", None) != _digest(event)
            or event["initialization"] is not initialization
            or event["actor_id"] != policy.owner_id
        ):
            raise ValueError("Unowned or changed native recipe witness")
        carrier = next(
            (
                entry
                for entry in owner.state_ledger.entries
                if entry.uid == event["carrier_uid"]
            ),
            None,
        )
        if (
            carrier is None
            or carrier.reference != event["state_reference"]
            or carrier.level != 1
        ):
            raise ValueError("Native recipe carrier changed before acceptance")
        references.append(carrier.reference)
    active = [
        entry.reference
        for entry in owner.state_ledger.entries
        if entry.reference in _BY_STATE
    ]
    if len(set(references)) != 3 or len(active) != 3 or set(active) != set(references):
        raise ValueError("Native lottery markers differ from its three real outcomes")
    return tuple(_BY_STATE[reference] for reference in references)


def draw_initial(dispatcher, proof):
    from .native_order_trial_placement import selection_context_authorized
    from .combat_effect_dispatch import EffectDispatcher, EffectInvocation

    from wakfu_server import native_order_trial_admission as admission

    if type(proof) is not admission.Admission:
        raise ValueError("Initial native lottery requires an admitted mode")
    fight = dispatcher.native_state_handler.fight
    if type(dispatcher) is not EffectDispatcher or not selection_context_authorized(
        fight, dispatcher, proof
    ):
        raise ValueError(
            "Initial native lottery requires its checked placement publisher"
        )
    owner = fight.actors[proof.owner_id]
    if any(entry.reference in _BY_STATE for entry in owner.state_ledger.entries):
        raise ValueError("Initial native lottery cannot reroll existing recipes")
    catalog = dispatcher.native_state_handler.catalog["effects"]
    original = {
        str(reference): {
            key: value
            for key, value in catalog[str(reference)].items()
            if key != "native_timing_checks"
        }
        for reference in (119018, *_CHILDREN)
    }
    if _digest(original) != LOTTERY_SHA256:
        raise ValueError("Original native recipe lottery source changed")
    effect = catalog["119018"]
    if (
        effect["effect_class"] != 341
        or tuple(effect["parameters"]) != (3.0, 0.0)
        or tuple(effect["children"]) != tuple(_CHILDREN)
    ):
        raise ValueError("Original native three-recipe lottery changed")
    parent = next(
        (entry.uid for entry in owner.state_ledger.entries if entry.reference == 3052),
        None,
    )
    if proof.hard_mode and parent is None:
        raise ValueError("Hard initial lottery lost original3052 marker")
    before = len(fight.events)
    token = _initial.set((fight, dispatcher, proof))
    try:
        dispatcher.execute(
            EffectInvocation(
                119018,
                1,
                owner.id,
                owner.id,
                owner.position,
                state_uid=parent,
                native_retained_container={"present": False},
            )
        )
    finally:
        _initial.reset(token)
    result = selected(fight, fight.events[before:], initialization=True)
    if result is None:
        raise ValueError("Original native lottery produced no recipes")
    return result


def adopt_witnesses(destination, candidate, *, previous_sequence):
    if (
        destination.id != candidate.id
        or destination.events is not candidate.events
        or destination.native_order_trial is not candidate.native_order_trial
    ):
        raise ValueError("Recipe witnesses require actual native fight adoption")
    for event in reversed(destination.events):
        if event["sequence"] <= previous_sequence:
            break
        if (
            type(event) is _Selection
            and callable(getattr(event, "_origin", None))
            and event._origin() is candidate
        ):
            if getattr(event, "_digest", None) != _digest(event):
                raise ValueError("Native recipe witness changed during adoption")
            event._origin = ref(destination)
