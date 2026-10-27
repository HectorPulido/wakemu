"""Native faM assignment through original children, with owned pickup receipts.

The contact-to2243 producer is explicit Wakemu policy. Assignment supplies a
real recipient to the same faM.c(amP) consumer; it never grants states directly.
"""
from copy import deepcopy


# A server-assigned artifact is not a physical pickup. Scope its native area
# identity so only that source's instant full-MP pickup toll is waived.
from contextvars import ContextVar

_ASSIGNMENT_AREA = ContextVar("automatic_artifact_assignment_area", default=None)


def automatic_pickup_toll(effect, invocation):
    """Wakemu assignment policy; ordinary contact and state costs stay native."""
    area_uid = _ASSIGNMENT_AREA.get()
    container = invocation.native_retained_container
    if (
        area_uid is None
        or not isinstance(container, dict)
        or container.get("present") is not True
        or container.get("type") != 3
        or container.get("id") != area_uid
        or container.get("native_kind") != "effect_area"
        or effect.get("effect_class") != 48
        or not {19, 30}.issubset(effect.get("native_effect_flags", ()))
    ):
        return False
    from .combat_parameters import parameter_value

    parameters = effect.get("parameters", ())
    return (
        len(parameters) == 2 and parameter_value(parameters, 0, invocation.level) == 100
    )


def _receipts(fight):
    return getattr(fight, "native_artifact_activation_receipts", {})


def prior_activation(fight, row, actor_id, origin):
    receipt = _receipts(fight).get(str(row["uid"]))
    if receipt is None:
        return False
    if (
        receipt.get("reference") != row["reference"]
        or receipt.get("actor_id") != actor_id
        or receipt.get("origin") != origin
        or receipt.get("complete") is not True
    ):
        raise ValueError("Artifact activation differs from its original receipt")
    return True


def state_observations(fight):
    """Observe actual registered actor carriers without inferring any grant."""
    return {
        (actor.id, entry.uid): dict(
            actor_id=actor.id,
            uid=entry.uid,
            reference=entry.reference,
            level=entry.level,
            caster_id=entry.caster_id,
            target_id=entry.target_id,
            target_team=actor.team,
        )
        for actor in fight.actors.values()
        for entry in actor.state_ledger.entries
    }


def complete_activation(
    runtime, row, definition, target, *, origin, successful, before_states
):
    """Notify only after original successful children consumed this actual Qq."""
    from .combat_artifact_area import verify_artifact_area

    verify_artifact_area(row, definition)
    if origin not in ("contact", "assignment") or target is None:
        raise ValueError("Actual artifact activation recipient and origin required")
    if not successful or runtime.fight.native_effect_areas.get(row["uid"]) is row:
        return False  # A rejected criterion is not a pickup or an assignment.
    if prior_activation(runtime.fight, row, target.id, origin):
        return True
    current = runtime.fight.native_effect_areas.get(row["uid"])
    if current is not None:
        raise ValueError("Consumed artifact UID was replaced during activation")
    receipts = getattr(runtime.fight, "native_artifact_activation_receipts", None)
    if receipts is None:
        receipts = runtime.fight.native_artifact_activation_receipts = {}
    after_states = state_observations(runtime.fight)
    changes = [
        record
        for key, record in sorted(after_states.items())
        if key not in before_states or before_states[key]["level"] != record["level"]
    ]
    for record in changes:
        uid = record["uid"]
        # Actual carrier PL/UID bytes, not a guessed applicator reference.
        record["retained_record"] = deepcopy(
            runtime.fight.native_retained_records.get(uid)
        )
        record["wire_payload"] = runtime.fight.state_wire_payloads.get(uid)
    receipt = dict(
        reference=row["reference"],
        area_uid=row["uid"],
        area_level=row["level"],
        actor_id=target.id,
        owner_id=row["owner_id"],
        recipient_team=target.team,
        origin=origin,
        complete=False,
        source_kind="observed_original_artifact_activation",
        observed_state_changes=changes,
    )
    receipts[str(row["uid"])] = receipt
    if origin == "contact" and runtime.artifact_collected is not None:
        if not callable(runtime.artifact_collected):
            raise ValueError("Invalid artifact post-contact callback")
        runtime.artifact_collected(area_row=row, actor_id=target.id)
    receipt["complete"] = True
    return True


def assign_artifact(runtime, area_uid, recipient_id):
    """Assign one genuine live artifact, without movement or recursive pairing."""
    if (
        type(area_uid) is not int
        or area_uid <= 0
        or type(recipient_id) is not int
        or recipient_id == 0
    ):
        raise ValueError("Actual artifact and recipient identities required")
    fight = runtime.fight
    receipt = _receipts(fight).get(str(area_uid))
    if receipt is not None:
        if (
            receipt.get("origin") != "assignment"
            or receipt.get("actor_id") != recipient_id
            or receipt.get("complete") is not True
        ):
            raise ValueError("Artifact assignment conflicts with its original receipt")
        if area_uid in fight.native_effect_areas:
            raise ValueError("Consumed artifact assignment is still registered")
        return True  # Replay does not execute original children again.
    row = fight.native_effect_areas.get(area_uid)
    target = fight.actors.get(recipient_id)
    if row is None or target is None or not fight._in_play(target):
        raise ValueError("Artifact assignment requires its live Qq and recipient")
    definition = runtime._definition(row)
    from .combat_artifact_area import verify_artifact_area

    verify_artifact_area(row, definition)
    if 2243 not in definition["entry_masks"]:
        raise ValueError("Artifact lacks its native2243 activation subscription")
    token = _ASSIGNMENT_AREA.set(area_uid)
    try:
        runtime._deliver_event(
            row, definition, target, 2243, artifact_origin="assignment"
        )
    finally:
        _ASSIGNMENT_AREA.reset(token)
    return prior_activation(fight, row, recipient_id, "assignment")


def artifact_assignment_eligible(runtime, area_uid, recipient_id):
    """Query original grant criteria without charges, handlers or RNG draws."""
    from .combat_artifact_area import verify_artifact_area

    if (
        type(area_uid) is not int
        or area_uid <= 0
        or type(recipient_id) is not int
        or recipient_id == 0
    ):
        raise ValueError("Actual artifact and recipient identities required")
    row = runtime.fight.native_effect_areas.get(area_uid)
    if row is None:
        raise ValueError("Artifact eligibility requires its actual live Qq")
    definition = runtime._definition(row)
    verify_artifact_area(row, definition)
    if 2243 not in definition["entry_masks"]:
        raise ValueError("Artifact lacks its native2243 activation subscription")
    target = runtime.fight.actors.get(recipient_id)
    if target is None or not runtime.fight._in_play(target):
        return False
    return runtime._artifact_criterion_probe(row, definition, target)
