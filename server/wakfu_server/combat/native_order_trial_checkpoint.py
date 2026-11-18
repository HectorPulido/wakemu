"""Optional JSON-only order-trial sidecar inside the accepted fight checkpoint.

No packet or generic combat win is a score producer. A future native event
classifier must observe the real candidate event before staging a reducer
action. This module provides atomic storage and replay validation; it does not
classify pizza gameplay, choose scoring weights, or enable an arcade.
"""

from dataclasses import asdict
from hashlib import sha256
import json

from wakfu_server.achievements import native_order_trials as kernel

FIELD = "native_order_trial"
SCHEMA = "native-order-trial-checkpoint-v1"


def _plain(value):
    return json.loads(json.dumps(value, allow_nan=False))


def _digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _rules(document):
    if (
        type(document) is not dict
        or set(document)
        != {
            "weights",
            "score_threshold",
            "strike_limit",
            "ingredient_batch",
            "ingredient_capacity",
            "provenance",
        }
        or type(document["weights"]) is not list
        or any(type(row) is not list or len(row) != 3 for row in document["weights"])
        or type(document["provenance"]) is not dict
        or set(document["provenance"]) != {"kind", "evidence"}
        or document["provenance"]["kind"] not in ("native", "reviewed_reconstruction")
        or type(document["provenance"]["evidence"]) is not str
        or not document["provenance"]["evidence"].strip()
    ):
        raise ValueError("Order checkpoint requires explicit frozen scoring provenance")
    return kernel.OrderRules(
        tuple(((row[0], row[1]), row[2]) for row in document["weights"]),
        document["score_threshold"],
        document["strike_limit"],
        document["ingredient_batch"],
        document["ingredient_capacity"],
    )


def _event_identity(event, previous_sequence):
    if type(event) is not dict or set(event) != {
        "native_event",
        "classification",
        "receipt",
        "result_sha256",
    }:
        raise ValueError("Malformed committed order observation")
    native = event["native_event"]
    classification = event["classification"]
    if (
        type(native) is not dict
        or type(native.get("sequence")) is not int
        or native["sequence"] <= previous_sequence
        or type(native.get("kind")) is not str
        or not native["kind"]
        or event["receipt"] != f"event:{native['sequence']}:{_digest(native)}"
        or type(classification) is not dict
        or set(classification) != {"action", "arguments", "source"}
        or type(classification["source"]) is not str
        or not classification["source"]
        or type(classification["arguments"]) is not dict
        or set(classification["arguments"])
        - {
            "target_id",
            "color",
            "ingredient",
            "next_orders",
            "population_limit",
            "charges_after",
        }
    ):
        raise ValueError("Order observation lacks an actual native event identity")
    return native, classification


def validate(document, *, encounter_id, replay=True):
    """Replay untrusted recovery; trusted candidates validate only state and head."""
    from wakfu_server import native_order_trial_admission as admission

    if (
        type(document) is not dict
        or set(document)
        != {"schema", "admission", "capability", "rules", "initial", "state", "events"}
        or document["schema"] != SCHEMA
        or type(document["admission"]) is not dict
        or set(document["admission"]) != set(admission.Admission.__dataclass_fields__)
        or type(document["events"]) is not list
    ):
        raise ValueError("Malformed order checkpoint envelope")
    capability = admission.validate(document["capability"])
    proof = admission.Admission(**document["admission"])
    if (
        capability["enabled"] is not True
        or proof.profile_id != capability["id"]
        or proof.profile_sha256 != admission.digest(capability)
        or proof.mode not in ("normal", "hard")
        or proof.hard_mode is not (proof.mode == "hard")
        or type(proof.owner_id) is not int
        or proof.owner_id <= 0
        or type(proof.account_id) is not int
        or proof.account_id <= 0
        or type(proof.instance_id) is not int
        or proof.instance_id <= 0
        or type(proof.generation) is not str
        or not proof.generation
    ):
        raise ValueError("Order checkpoint lost its frozen selected mode")
    source = capability["sources"][proof.mode]
    effects = [
        e
        for g in source["descriptor"]["groups"]
        for a in g["actions"]
        for e in a["effects"]
    ]
    if (
        proof.source_id != source["object_id"]
        or proof.source_map_id != source["map_id"]
        or proof.descriptor_sha256 != source["descriptor_sha256"]
        or len(effects) != 1
        or proof.effect_reference != effects[0]["action_reference"]
    ):
        raise ValueError("Order checkpoint changed its original native mode source")
    rules = _rules(document["rules"])
    initial = kernel.restore(
        document["initial"], rules, owner_id=proof.owner_id, encounter_id=encounter_id
    )
    if (
        initial.hard_mode is not proof.hard_mode
        or initial.receipts
        or initial.score
        or initial.strikes
        or initial.finished
        or initial.larvae
        or initial.turn != 1
        or initial.ingredient is not None
        or initial.charges
    ):
        raise ValueError("Order checkpoint initial state is not a fresh native attempt")
    if not replay:
        final = kernel.restore(
            document["state"], rules, owner_id=proof.owner_id, encounter_id=encounter_id
        )
        if final.hard_mode is not proof.hard_mode or len(final.receipts) != len(
            document["events"]
        ):
            raise ValueError("Order checkpoint changed its mode or receipt count")
        if not document["events"]:
            if final != initial:
                raise ValueError(
                    "Order checkpoint changed without a native observation"
                )
        else:
            previous_sequence = 0
            if len(document["events"]) > 1:
                previous = document["events"][-2]
                if (
                    type(previous) is not dict
                    or type(previous.get("native_event")) is not dict
                    or type(previous["native_event"].get("sequence")) is not int
                ):
                    raise ValueError("Malformed prior native observation head")
                previous_sequence = previous["native_event"]["sequence"]
            head = document["events"][-1]
            _event_identity(head, previous_sequence)
            if head["receipt"] not in final.receipts or head[
                "result_sha256"
            ] != _digest(kernel.snapshot(final, rules)):
                raise ValueError(
                    "Order checkpoint current state differs from its observation head"
                )
        return proof, rules, final
    state = initial
    previous_sequence = 0
    for event in document["events"]:
        native, classification = _event_identity(event, previous_sequence)
        previous_sequence = native["sequence"]
        state = kernel.apply(
            state,
            rules,
            owner_id=proof.owner_id,
            encounter_id=encounter_id,
            receipt=event["receipt"],
            action=classification["action"],
            **classification["arguments"],
        )
        if (
            event["receipt"] not in state.receipts
            or _digest(kernel.snapshot(state, rules)) != event["result_sha256"]
        ):
            raise ValueError(
                "Order observation disagrees with its committed reducer result"
            )
    final = kernel.restore(
        document["state"], rules, owner_id=proof.owner_id, encounter_id=encounter_id
    )
    if final != state:
        raise ValueError(
            "Order checkpoint score or receipts differ from native observations"
        )
    return proof, rules, final


def install(fight, proof, state, rules, *, provenance, capability=None):
    """Install only after genuine mode admission and native form construction."""
    from wakfu_server import native_order_trial_admission as admission
    from .combat_morph_spellbook import morph_record
    from .native_order_trial_form import SPELLS

    capability = (
        admission.document() if capability is None else admission.validate(capability)
    )
    if capability["enabled"] is not True or not isinstance(proof, admission.Admission):
        raise ValueError("Order checkpoint capability is disabled")
    actor = fight.actors.get(proof.owner_id)
    current = morph_record(fight, proof.owner_id)
    if (
        actor is None
        or actor.owner_id != proof.account_id
        or actor.controlled is not True
        or fight.phase not in ("placement", "active")
        or state.encounter_id != fight.id
        or state.owner_id != proof.owner_id
        or current is None
        or current["profile_id"] != 3217
        or tuple(current["levels"].items()) != tuple((ref, 1) for ref in SPELLS)
    ):
        raise ValueError(
            "Order checkpoint requires its actual native form and fight owner"
        )
    rule_document = dict(
        weights=[
            [color, ingredient, weight] for (color, ingredient), weight in rules.weights
        ],
        score_threshold=rules.score_threshold,
        strike_limit=rules.strike_limit,
        ingredient_batch=rules.ingredient_batch,
        ingredient_capacity=rules.ingredient_capacity,
        provenance=provenance,
    )
    document = _plain(
        dict(
            schema=SCHEMA,
            admission=asdict(proof),
            capability=capability,
            rules=rule_document,
            initial=kernel.snapshot(state, rules),
            state=kernel.snapshot(state, rules),
            events=[],
        )
    )
    validate(document, encounter_id=fight.id, replay=False)
    previous = getattr(fight, FIELD, None)
    if previous is not None:
        validate(previous, encounter_id=fight.id, replay=False)
        if any(
            previous[key] != document[key]
            for key in ("admission", "capability", "rules", "initial")
        ):
            raise ValueError(
                "Order checkpoint cannot reset or change an admitted attempt"
            )
        return False
    setattr(fight, FIELD, document)
    return True


def event_index(candidate, event):
    """Resolve one actual native event by its contiguous Fight._event sequence."""
    events = candidate.events
    if (
        not isinstance(event, dict)
        or type(event.get("sequence")) is not int
        or not events
        or not isinstance(events[0], dict)
        or type(events[0].get("sequence")) is not int
    ):
        raise ValueError("Order observer requires an actual candidate native event")
    index = event["sequence"] - events[0]["sequence"]
    if not 0 <= index < len(events) or events[index] is not event:
        raise ValueError("Order observer requires an actual candidate native event")
    return index


def observe(candidate, event, *, classify):
    """Stage a future native classifier's result on its actual combat candidate.

    No classifier is supplied by this module. It must validate original native
    action/runner/area authority; client requests and scores are never inputs.
    Rejected candidates retain their own sidecar and cannot mutate the source.
    """
    document = getattr(candidate, FIELD, None)
    if document is None:
        return False
    proof, rules, state = validate(document, encounter_id=candidate.id, replay=False)
    if not callable(classify):
        raise ValueError("Order observer requires an actual candidate native event")
    event_index(candidate, event)
    native = _plain(event)
    receipt = f"event:{native['sequence']}:{_digest(native)}"
    if receipt in state.receipts:
        return False
    classification = classify(candidate, event)
    if classification is None:
        return False
    classification = _plain(classification)
    if type(classification) is not dict or set(classification) != {
        "action",
        "arguments",
        "source",
    }:
        raise ValueError(
            "Order classifier must supply explicit original-source evidence"
        )
    result = kernel.apply(
        state,
        rules,
        owner_id=proof.owner_id,
        encounter_id=candidate.id,
        receipt=receipt,
        action=classification["action"],
        **classification["arguments"],
    )
    if receipt not in result.receipts:
        # Native cleanup/replacement outcomes may follow a true terminal strike
        # in the same accepted action. The reducer deliberately ignores them;
        # an unaccepted receipt must never become checkpoint history.
        return False
    next_document = dict(document)
    next_document["events"] = list(document["events"])
    next_document["state"] = kernel.snapshot(result, rules)
    next_document["events"].append(
        dict(
            native_event=native,
            classification=classification,
            receipt=receipt,
            result_sha256=_digest(next_document["state"]),
        )
    )
    validate(next_document, encounter_id=candidate.id, replay=False)
    setattr(candidate, FIELD, next_document)
    return True


def validate_checkpoint(state, *, expected=None, replay=True):
    """Keep recovery as abort/accounting evidence, never resume a live lease."""
    document = state.get(FIELD)
    if document is None:
        return
    proof, _, _ = validate(document, encounter_id=state["id"], replay=replay)
    actors = state.get("actors", {})
    actor = actors.get(str(proof.owner_id), actors.get(proof.owner_id))
    if (
        not isinstance(actor, dict)
        or actor.get("owner_id") != proof.account_id
        or actor.get("controlled") is not True
    ):
        raise ValueError("Order checkpoint differs from its durable combat owner")
    if expected is not None and document != expected:
        raise ValueError("Order checkpoint differs from its accepted combat candidate")


def validate_fight(fight):
    document = getattr(fight, FIELD, None)
    if document is not None:
        validate_checkpoint(
            dict(
                id=fight.id,
                actors={str(k): vars(v) for k, v in fight.actors.items()},
                **{FIELD: document},
            ),
            replay=False,
        )
