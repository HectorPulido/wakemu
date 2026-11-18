"""Original341 recipe selection with explicit server admission timing.

Initial execution is a reviewed server join to the original119018 program.
Hard refills are accepted only from its real3052/TURN_START1001 outcomes.
Normal mode finishes after its initial requests; no client recipes are used.
"""

from hashlib import sha256
import json

from wakfu_server.achievements import native_order_trials as kernel

POLICY = {
    "schema": "native341-order-requests-v2",
    "authority": "original119018_algorithm_reviewed_initial_timing",
    "request_count": 3,
    "distinct": True,
    "normal": "reviewed_initial119018_without_hard3052_then_finish",
    "hard": "original3052_turn_start1001_refill_when_all_markers_absent",
}


def _digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def initial(dispatcher, proof):
    """Choose a new attempt's requests after its actual native form exists."""
    from wakfu_server import native_order_trial_admission as admission
    from . import native_order_trial_checkpoint as checkpoint
    from .combat_morph_spellbook import morph_record

    if type(proof) is not admission.Admission or proof.generation is None:
        raise ValueError("Order generation requires its selected native mode")
    fight = dispatcher.native_state_handler.fight
    actor = fight.actors.get(proof.owner_id)
    morph = morph_record(fight, proof.owner_id)
    if (
        dispatcher.native_retention.fight is not fight
        or actor is None
        or actor.owner_id != proof.account_id
        or actor.controlled is not True
        or morph is None
        or morph.get("profile_id") != 3217
        or proof.mode not in ("normal", "hard")
        or proof.hard_mode is not (proof.mode == "hard")
    ):
        raise ValueError("Order generation lost its actual native form or owner")
    previous = getattr(fight, "native_order_request_policy", None)
    if previous is not None and previous != POLICY:
        raise ValueError("Order generation policy changed within an attempt")
    document = getattr(fight, checkpoint.FIELD, None)
    if document is not None:
        existing, rules, _ = checkpoint.validate(
            document, encounter_id=fight.id, replay=False
        )
        if existing != proof:
            raise ValueError("Order generation cannot reroll another admitted attempt")
        state = kernel.restore(
            document["initial"], rules, owner_id=proof.owner_id, encounter_id=fight.id
        )
        return state.orders
    fight.native_order_request_policy = dict(POLICY)
    from .native_order_trial_selection import draw_initial

    return draw_initial(dispatcher, proof)


def advance(candidate, *, events):
    """Refill only after an earned current-action bake emptied the requests.

    The decision is a real server operation recorded in the same candidate and
    checkpoint as its causal native bake. Native marker delivery follows this
    step. The caller owns normal-mode terminal publication after the explicit
    finish receipt; empty opposition by itself is never completion authority.
    """
    if getattr(candidate, "native_order_trial", None) is None:
        return False
    from . import native_order_trial_checkpoint as checkpoint

    proof, rules, state = checkpoint.validate(
        candidate.native_order_trial, encounter_id=candidate.id, replay=False
    )
    if state.finished:
        return False
    if getattr(candidate, "native_order_request_policy", None) != POLICY:
        raise ValueError("Order request refill lost its frozen native policy")
    if state.hard_mode:
        from .native_order_trial_selection import selected

        requests = selected(candidate, events)
        if requests is None:
            return False  # Wait for the next actual original1001 lottery.
        parent = next(
            event
            for event in events
            if event.get("kind") == "native_order_recipe_selected"
        )
        if state.orders:
            history = candidate.native_order_trial["events"]
            head = history[-1] if history else None
            if (
                tuple(state.orders) == tuple(requests)
                and head is not None
                and head["classification"]["action"] == "refill"
                and head["native_event"].get("parent_sequence") == parent["sequence"]
                and head["native_event"].get("policy_sha256") == _digest(POLICY)
            ):
                return False
            raise ValueError(
                "Native lottery refilled before earned requests were empty"
            )
    else:
        if state.orders:
            return False
        requests = ()
        parent = None
        for event in events:
            checkpoint.event_index(candidate, event)
            if (
                event.get("kind") == "kill_hp_minimum_update"
                and event.get("generic_effect") == 120461
                and event.get("source_id") == proof.owner_id
                and f"event:{event['sequence']}:{_digest(event)}" in state.receipts
            ):
                parent = event
        if parent is None:
            raise ValueError("Normal completed requests lack their earned native bake")
    decision = candidate._event(
        "order_requests_refilled" if state.hard_mode else "order_requests_completed",
        actor_id=proof.owner_id,
        owner_id=proof.account_id,
        parent_sequence=parent["sequence"],
        policy_sha256=_digest(POLICY),
        requests=[list(recipe) for recipe in requests],
    )

    def classify(fight, event):
        if fight is not candidate or event is not decision:
            raise ValueError("Order request decision belongs to another action")
        return dict(
            action="refill" if state.hard_mode else "finish",
            arguments=dict(next_orders=requests) if state.hard_mode else {},
            source=(
                "Actual native3052 TURN_START1001 original341 recipe selection"
                if state.hard_mode
                else "Actual normal requested native120461 bake"
            ),
        )

    return checkpoint.observe(candidate, decision, classify=classify)
