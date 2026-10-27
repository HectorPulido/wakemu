"""Persist actual opponent artifact choices onto fresh ordinary Rift waves.

This is an explicit Wakemu server producer, not a synthetic summon2130 event.
The accepted choice receipt and its original faM/304 graph supply each incoming
grant. Native state application owns merging, caps, child effects and packets;
an old NPC's post-merge grade or unrelated innate state is never copied.
"""
from collections.abc import Mapping

POLICY = "wakemu.rift.observed-artifact-choice-inheritance.v1"


def _original_grant(dispatcher, reference, level):
    from wakfu_server.combat_effect_area import native_effect_areas
    from wakfu_server.combat_definitions import effect_profile
    from wakfu_server.combat_state_parameters import interpret_state_parameters

    area = native_effect_areas().get(str(reference))
    if (
        not isinstance(area, Mapping)
        or 2243 not in area.get("entry_masks", ())
        or type(level) is not int
        or not 0 <= level <= 32767
    ):
        raise ValueError("Artifact inheritance requires its original faM activation")
    pending, seen, grants = list(area["effect_ids"]), set(), []
    while pending:
        identity = pending.pop()
        if identity in seen:
            continue
        seen.add(identity)
        effect = dispatcher.effects.get(str(identity))
        if not isinstance(effect, Mapping):
            raise ValueError("Original artifact grant graph is incomplete")
        minimum, maximum = effect.get("minimum_level"), effect.get("maximum_level")
        if type(minimum) is not int or type(maximum) is not int or minimum > maximum:
            raise ValueError("Original artifact grant level window is invalid")
        if not minimum <= level <= maximum:
            continue
        if effect.get("effect_class") == 304:
            values = effect_profile(effect, level)["parameters"]
            if (
                len(values) != 3
                or effect.get("probability_base") != 100
                or effect.get("probability_per_level") != 0
            ):
                raise ValueError(
                    "Artifact inheritance needs a deterministic original state grant"
                )
            parsed = interpret_state_parameters(values, allow_signed_calculation=True)
            if parsed["level"] < 1 or parsed["chance_parameter"] not in (-1, 100):
                raise ValueError(
                    "Original artifact grant needs another inheritance contract"
                )
            grants.append((identity, parsed["reference"], parsed["level"]))
            # State children are passive reactions, not additional pickup grants.
        else:
            pending.extend(effect.get("children", ()))
    if len(grants) != 1:
        raise ValueError(
            "Artifact inheritance requires one unambiguous original304 grant"
        )
    return grants[0]


def _history(dispatcher, wave, npc_team):
    fight = dispatcher.native_retention.fight
    receipts = getattr(fight, "native_artifact_activation_receipts", {})
    grants, seen = [], set()
    for key, group in sorted(
        fight.rift_wave_state.get("native_artifact_groups", {}).items(),
        key=lambda item: int(item[0]),
    ):
        if int(key) >= wave:
            continue
        for assignment in group["assignments"]:
            # A just-distributed leftover has already granted this new roster.
            if assignment.get("before_wave", 0) >= wave:
                continue
            uid, recipient = assignment["opponent"], assignment["recipient"]
            if (
                assignment.get("kind") not in ("contact_pair", "automatic_pair")
                or type(uid) is not int
                or uid <= 0
                or uid in seen
                or type(recipient) is not int
                or recipient >= 0
            ):
                raise ValueError(
                    "Artifact inheritance opponent history is inconsistent"
                )
            seen.add(uid)
            receipt = receipts.get(str(uid))
            if (
                not isinstance(receipt, Mapping)
                or receipt.get("complete") is not True
                or receipt.get("origin") != "assignment"
                or receipt.get("actor_id") != recipient
                or type(receipt.get("recipient_team")) is not int
                or receipt.get("recipient_team") != npc_team
                or receipt.get("reference") != group["original"].get(str(uid))
                or receipt.get("area_uid") != uid
                or receipt.get("source_kind") != "observed_original_artifact_activation"
                or not isinstance(receipt.get("observed_state_changes"), (tuple, list))
                or uid in fight.native_effect_areas
            ):
                raise ValueError(
                    "Artifact inheritance lacks a completed original opponent choice"
                )
            applicator, state, grade = _original_grant(
                dispatcher, receipt["reference"], receipt.get("area_level")
            )
            _validate_observations(dispatcher, receipt, state, receipts)
            # The level above is the original incoming304 value. In particular,
            # an observation of6→12 does not cause an incoming grant of12.
            # A completed choice may have no ledger delta when a species
            # already carries that exact innate. Its consumed faM and unique
            # deterministic304 still identify the acquired artifact correctly.
            grants.append(
                dict(
                    artifact_uid=uid,
                    artifact_reference=receipt["reference"],
                    source_recipient=recipient,
                    source_wave=int(key),
                    applicator=applicator,
                    applicator_level=receipt["area_level"],
                    state=state,
                    incoming_grade=grade,
                )
            )
    return grants


def _validate_observations(dispatcher, receipt, state, receipts):
    """Check real carrier PL/UID evidence without using its grade as grant math."""
    from wakfu_server.combat_effect_removal import _identity_fields

    for observed in receipt["observed_state_changes"]:
        if not isinstance(observed, Mapping) or observed.get("reference") != state:
            continue  # A reactive passive is not this original pickup304.
        if type(observed.get("target_team")) is not int:
            raise ValueError(
                "Artifact observation lacks its actual target constructor side"
            )
        if observed["target_team"] != receipt["recipient_team"]:
            continue  # Do not borrow another side's reactive state carrier.
        retained, wire = observed.get("retained_record"), observed.get("wire_payload")
        if (
            not isinstance(retained, Mapping)
            or type(wire) is not str
            or retained.get("uid") != observed.get("uid")
            or retained.get("effect_class") != 310
            or retained.get("manager_id") != observed.get("target_id")
            or retained.get("container_present") is not True
            or retained.get("container_type") != 3
            or retained.get("container_kind") != "effect_area"
            or retained.get("container_is_spell") is not False
        ):
            raise ValueError(
                "Artifact grant observation lacks its actual native carrier"
            )
        container = retained.get("container_id")
        fields = _identity_fields(bytes.fromhex(wire), integer_fields=(1, 3, 9, 10))
        if (
            fields.get(1) != observed["uid"]
            or fields.get(9) != 3
            or fields.get(10) != container
        ):
            raise ValueError("Artifact observation PL differs from its actual wire")
        if container != receipt["area_uid"]:
            # Native merging may retain the preceding artifact's carrier PL.
            # It must still be a real grant of this same original state kind.
            previous = receipts.get(str(container))
            if (
                not isinstance(previous, Mapping)
                or previous.get("complete") is not True
                or _original_grant(
                    dispatcher, previous["reference"], previous["area_level"]
                )[1]
                != state
            ):
                raise ValueError(
                    "Merged artifact carrier belongs to another native source"
                )


def _apply(dispatcher, actor, grant):
    from wakfu_server.combat_definitions import state_profile
    from wakfu_server.combat_effect_dispatch import EffectInvocation
    from wakfu_server.combat_native_timing_context import native_time_payload
    from wakfu_server.combat_state_handler import StateCarrierContext

    handler = dispatcher.native_state_handler
    profile = state_profile(handler.catalog, grant["state"], grant["incoming_grade"])
    if profile["duration"] != -1 or profile["realtime_duration"] != 0:
        raise ValueError(
            "Artifact inheritance cannot extend a temporary reactive state"
        )
    invocation = EffectInvocation(
        grant["applicator"],
        grant["applicator_level"],
        actor.id,
        actor.id,
        actor.position,
        native_retained_container={"present": False},
    )
    context = StateCarrierContext(
        -1,
        0,
        False,
        None,
        None,
        False,
        False,
        False,
        0,
        native_time_payload(realtime_remaining=0),
    )
    # Unlike a first wave carrier, a selected artifact may merge with a prior
    # choice or a genuine species innate. The original state handler decides
    # that result; no hand-written grade arithmetic is performed here.
    dispatcher.native_retention.apply_state_reference(
        handler,
        invocation,
        grant["state"],
        grant["incoming_grade"],
        carrier_context=context,
    )


def inherit_artifact_grants(dispatcher, *, actor_ids, wave):
    """Apply historical choices once, after6807 and before new leftovers.

    The caller owns an unpublished wave preview/outbox and external RNG
    rollback. Failures discard both native state changes and this receipt.
    """
    from wakfu_server.rift_native_gameplay import policy
    from wakfu_server.combat_encounter_roles import assigned_roles
    from wakfu_server.combat_global_pv_collections import global_fighter_guards

    fight = dispatcher.native_retention.fight
    document = policy(fight)
    if document is None or document.get("artifacts", {}).get("enabled") is not True:
        return False
    roles, ids = assigned_roles(fight), tuple(actor_ids)
    state = fight.rift_wave_state
    if type(wave) is not int or wave < 1 or not ids or len(set(ids)) != len(ids):
        raise ValueError("Artifact inheritance requires the exact fresh native roster")
    for uid in ids:
        actor = fight.actors.get(uid)
        carrier = state.get("native_wave_entries", {}).get(str(uid))
        if (
            type(uid) is not int
            or uid >= 0
            or actor is None
            or actor.controlled
            or actor.team != roles.npc_team
            or not fight._in_play(actor)
            or getattr(actor, "native_summon_source", None) is not None
            or not isinstance(carrier, Mapping)
            or carrier.get("wave") != wave
            or carrier.get("reference") != document["wave_state"]
            or not global_fighter_guards(fight, uid)["baF"]
        ):
            raise ValueError(
                "Artifact inheritance target is not this registered ordinary wave"
            )
    grants = _history(dispatcher, wave, roles.npc_team)
    receipt = dict(policy=POLICY, wave=wave, actors=list(ids), grants=grants)
    records = state.setdefault("native_artifact_inheritance", {})
    previous = records.get(str(wave))
    if previous is not None:
        if previous != dict(receipt, complete=True):
            raise ValueError("Artifact inheritance replay changed its accepted history")
        return False
    records[str(wave)] = dict(receipt, complete=False)
    for grant in grants:
        for uid in ids:
            _apply(dispatcher, fight.actors[uid], grant)
    records[str(wave)]["complete"] = True
    return bool(grants)
