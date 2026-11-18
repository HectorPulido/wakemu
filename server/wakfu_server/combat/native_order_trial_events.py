"""Opt-in classification of actual native pizza outcomes, never client scores.

The304/307 handler witnesses are emitted only after their real successful
native execution. They are reduced in event order after the action completes,
preserving the native ordering of deaths and nested3127 replacement births. Ordinary fights have
no sidecar and do not load or execute this observer.
"""
from contextvars import ContextVar
from hashlib import sha256
import json
from weakref import ref

_CURRENT_BATCH = ContextVar("native_order_trial_action_events", default=())

STATE_ACTIONS = {
    118971: (4535, 3045, "tenderize", None),
    118980: (4538, 3046, "pickup", "tomato"),
    118982: (4538, 3047, "pickup", "cheese"),
    118984: (4538, 3048, "pickup", "pepper"),
    118998: (4537, 3046, "garnish", "tomato"),
    118999: (4537, 3047, "garnish", "cheese"),
    119000: (4537, 3048, "garnish", "pepper"),
}
BAKING_POLICY = {
    "policy": "reviewed-paid-bake-contact-v1",
    "authority": "authorized_wakemu_reconstruction_not_original_server_edge",
    "contact_spell": 4536,
    "contact_effect": 118972,
    "contact_area": 782,
    "native_state": 3123,
    "initial_state_once_per_larva": True,
    "native_terminal_effect": 120461,
    "bare_bake_failure_state": 3124,
    "bare_bake_failure_increment": 1,
    "escape_area": 768,
    "escape_terminal_effect": 118950,
    "escape_failure_state": 3124,
    "escape_failure_increment": 1,
    "escape_authority": "reviewed_server_join_not_original120464_owner_edge",
}
COLORS = {3206: "blue", 3239: "red", 3240: "green"}
SPAWNS = {
    118953: (3044, 3206, "normal"),
    119966: (3044, 3239, "normal"),
    119967: (3044, 3240, "normal"),
    120740: (3044, 3206, "hard"),
    120741: (3044, 3239, "hard"),
    120742: (3044, 3240, "hard"),
    120751: (3127, 3206, "normal"),
    120752: (3127, 3239, "normal"),
    120753: (3127, 3240, "normal"),
    120755: (3127, 3206, "hard"),
    120756: (3127, 3239, "hard"),
    120757: (3127, 3240, "hard"),
    143617: (3127, 3206, "normal"),
    143618: (3127, 3239, "normal"),
    143619: (3127, 3240, "normal"),
}


def _digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


class _NativeOutcome(dict):
    """A fresh handler witness; historical checkpoints retain ordinary JSON."""

    pass


def _proof(fight):
    from wakfu_server import native_order_trial_checkpoint as checkpoint

    document = getattr(fight, checkpoint.FIELD, None)
    if document is None:
        return None
    proof, rules, state = checkpoint.validate(
        document, encounter_id=fight.id, replay=False
    )
    owner = fight.actors.get(proof.owner_id)
    if (
        owner is None
        or owner.owner_id != proof.account_id
        or owner.controlled is not True
    ):
        raise ValueError("Native order event lost its original controlled owner")
    return proof, rules, state


def _owned_summon(fight, actor, owner_id):
    """Follow only actual registered307 ancestry, including retired parents."""
    records = getattr(fight, "native_summon_registrations", {})
    visited = set()
    current = actor
    while current.id != owner_id:
        if current.id in visited or fight.actors.get(current.id) is not current:
            raise ValueError("Order larva has foreign or cyclic native ownership")
        visited.add(current.id)
        row = records.get(current.id)
        source = getattr(current, "native_summon_source", None)
        if (
            not isinstance(row, dict)
            or row.get("actor_id") != current.id
            or not isinstance(source, dict)
            or source.get("native_relation_source")
            != "big.new_bje.fdt_initial_registration"
            or source.get("caster_id") != row.get("caster_id")
            or source.get("controller_id") != row.get("controller_id")
            or source.get("ref") not in COLORS
        ):
            raise ValueError("Order larva lacks its actual native307 source")
        current = fight.actors.get(row["caster_id"])
        if current is None:
            raise ValueError("Order larva caster is absent from its fight")
    return source["ref"] if visited else None


def _publish(fight, kind, **fields):
    original = fight._event(kind, **fields)
    event = _NativeOutcome(original)
    event._origin = ref(fight)
    event._source_digest = _digest(event)
    fight.events[-1] = event
    return event


def record_state_application(handler, effect, invocation, entry, *, change=None):
    """Called only at NativeStateHandler's successful actual304 boundary."""
    fight = handler.fight
    if getattr(fight, "native_order_trial", None) is None:
        return None
    if invocation.reference == 120460:
        return _record_baking_growth(handler, effect, invocation, entry, change=change)
    if invocation.reference == 120464:
        return _record_failure_application(
            handler, effect, invocation, entry, change=change
        )
    if invocation.reference not in STATE_ACTIONS:
        return None
    from .combat_state_handler import NativeStateHandler
    from .combat_state_ledger import RunningState, StateChange
    from .combat_effect_dispatch import EffectInvocation
    from .combat_active_spell import active_spell_id
    from .combat_effect_removal import _identity_fields
    from .combat_state_parameters import pack_state_identity

    proof, _, _ = _proof(fight)
    spell, state_ref, action, ingredient = STATE_ACTIONS[invocation.reference]
    uid = invocation.native_running_uid
    # Legacy direct handlers do not establish an applicator runner identity.
    if uid is None:
        return None
    if type(entry) is not RunningState:
        raise ValueError("Order304 requires the actual RunningState carrier")
    actor = fight.actors.get(entry.target_id)
    payload = getattr(fight, "state_wire_payloads", {}).get(entry.uid)
    if (
        not isinstance(handler, NativeStateHandler)
        or type(invocation) is not EffectInvocation
        or effect.get("effect_class") != 304
        or entry.reference != state_ref
        or active_spell_id(fight) != spell
        or invocation.caster_id != proof.owner_id
        or type(uid) is not int
        or uid <= 0
        or uid == entry.uid
        or type(entry) is not RunningState
        or actor is None
        or not any(row is entry for row in actor.state_ledger.entries)
        or entry.caster_id != proof.owner_id
        or entry.target_id != invocation.target_id
        or not isinstance(payload, str)
    ):
        raise ValueError("Order304 witness lacks an actual native carrier/action")
    wire = _identity_fields(bytes.fromhex(payload))
    if any(
        wire.get(key) != value
        for key, value in {
            1: entry.uid,
            4: pack_state_identity(entry.reference, entry.level),
            6: entry.caster_id & ((1 << 64) - 1),
            7: entry.target_id & ((1 << 64) - 1),
        }.items()
    ):
        raise ValueError("Order304 carrier UID or native payload differs")
    if action == "pickup":
        if (
            actor.id != proof.owner_id
            or type(change) is not StateChange
            or change.applied is not entry
        ):
            raise ValueError("Order pickup needs its real owned StateChange")
    else:
        _owned_summon(fight, actor, proof.owner_id)
    previous = [
        old
        for old in (() if change is None else change.removed)
        if old.reference == state_ref and old.target_id == entry.target_id
    ]
    if len(previous) > 1:
        raise ValueError("Order304 has multiple replaced same-state carriers")
    return _publish(
        fight,
        "native_order_state_applied",
        effect_reference=invocation.reference,
        action_id=handler.action_id,
        spell_id=spell,
        runner_uid=uid,
        carrier_uid=entry.uid,
        caster_id=entry.caster_id,
        target_id=entry.target_id,
        state_reference=state_ref,
        before_level=previous[0].level if previous else 0,
        after_level=entry.level,
        carrier_sha256=sha256(bytes.fromhex(payload)).hexdigest(),
        ingredient=ingredient,
    )


def record_spawn(handler, effect, invocation, actor, *, runner_uid):
    """Called after a successful native307 registration and initialization."""
    fight = handler.fight
    if (
        getattr(fight, "native_order_trial", None) is None
        or invocation.reference not in SPAWNS
    ):
        return None
    from .combat_summon_handler import NativeSummonHandler
    from .combat_effect_dispatch import EffectInvocation
    from .combat_native_container import resolve_state_container

    proof, _, _ = _proof(fight)
    parent_ref, breed, mode = SPAWNS[invocation.reference]
    if (
        not isinstance(handler, NativeSummonHandler)
        or type(invocation) is not EffectInvocation
        or effect.get("effect_class") != 307
        or mode != proof.mode
        or fight.actors.get(actor.id) is not actor
        or type(runner_uid) is not int
        or runner_uid <= 0
        or type(invocation.state_uid) is not int
    ):
        raise ValueError("Order307 witness lacks its actual native birth source")
    parent = resolve_state_container(fight, invocation.state_uid)
    if parent is None or parent.reference != parent_ref:
        raise ValueError("Order307 birth has the wrong native constructor state")
    _owned_summon(fight, actor, proof.owner_id)
    source = actor.native_summon_source
    if source["ref"] != breed or source["caster_id"] != invocation.caster_id:
        raise ValueError("Order307 birth breed/caster differs from original program")
    table = getattr(fight, "native_timeline_round", None)
    if type(table) is not int or table < 1:
        raise ValueError("Order307 birth has no actual native table")
    return _publish(
        fight,
        "native_order_spawned",
        effect_reference=invocation.reference,
        runner_uid=runner_uid,
        constructor_uid=invocation.state_uid,
        constructor_state=parent_ref,
        actor_id=actor.id,
        caster_id=invocation.caster_id,
        reference=breed,
        native_table=table,
    )


def _classification(action, arguments, source):
    return dict(action=action, arguments=arguments, source=source)


def classify(candidate, event):
    """Classify only actual candidate events under the frozen mode/owner."""
    proof_value = _proof(candidate)
    if proof_value is None:
        return None
    proof, _, state = proof_value
    from wakfu_server.native_order_trial_checkpoint import event_index

    index = event_index(candidate, event)
    kind = event.get("kind")
    if kind in (
        "native_order_state_applied",
        "native_order_spawned",
        "native_order_failure_applied",
        "native_order_baking_contact",
        "native_order_baking_completed",
    ):
        origin = getattr(event, "_origin", None)
        if (
            type(event) is not _NativeOutcome
            or not callable(origin)
            or origin() is not candidate
            or getattr(event, "_source_digest", None) != _digest(event)
        ):
            raise ValueError("Order native outcome is forged, changed or foreign")
        if kind in (
            "native_order_failure_applied",
            "native_order_baking_contact",
            "native_order_baking_completed",
        ):
            return None  # Corroborating witnesses never award a recipe on their own.
        if kind == "native_order_spawned":
            parent, breed, mode = SPAWNS[event["effect_reference"]]
            if (
                mode != proof.mode
                or event["reference"] != breed
                or event["constructor_state"] != parent
            ):
                raise ValueError("Order native birth changed its source program")
            table = event["native_table"]
            limit = 2 if parent == 3127 else 1 if table < 6 else 2 if table < 10 else 3
            return _classification(
                "spawn",
                dict(
                    target_id=event["actor_id"],
                    color=COLORS[breed],
                    population_limit=limit,
                ),
                f"Original state{parent}/307 root{event['effect_reference']} runner{event['runner_uid']}",
            )
        spell, state_ref, action, ingredient = STATE_ACTIONS[event["effect_reference"]]
        if (
            event["spell_id"] != spell
            or event["state_reference"] != state_ref
            or event["caster_id"] != proof.owner_id
        ):
            raise ValueError("Order native state changed its spell/owner")
        if action == "garnish" and state.ingredient != ingredient:
            raise ValueError("Native garnish ingredient differs from the earned pickup")
        args = (
            dict(ingredient=ingredient, charges_after=event["after_level"])
            if action == "pickup"
            else dict(target_id=event["target_id"])
        )
        return _classification(
            action,
            args,
            f"Original spell{spell}/304 root{event['effect_reference']} runner{event['runner_uid']} carrier{event['carrier_uid']}",
        )
    if kind == "kill_hp_minimum_update":
        if event.get("generic_effect") not in (118950, 118970, 120461):
            return None
        target = candidate.actors.get(event.get("target_id"))
        if target is None or not any(row.actor_id == target.id for row in state.larvae):
            return None
        if (
            event.get("effect_class") != 28
            or event.get("minimum") != 0
            or event.get("hp") != 0
            or type(event.get("uid")) is not int
            or event["uid"] <= 0
        ):
            return None
        following = (
            candidate.events[index + 1] if index + 1 < len(candidate.events) else {}
        )
        if (
            following.get("kind") != "death"
            or following.get("actor_id") != target.id
            or following.get("sequence") != event.get("sequence", 0) + 1
        ):
            return None
        from .combat_ordinary_death import registered_ordinary_death

        if not registered_ordinary_death(candidate, target):
            return None
        if (
            event.get("generic_effect") == 118970
            and event.get("source_id") == proof.owner_id
        ):
            larva = next(row for row in state.larvae if row.actor_id == target.id)
            if not larva.tenderized:
                raise ValueError(
                    "Native second tenderize has no prior earned first application"
                )
            return _classification(
                "destroy_tenderized",
                dict(target_id=target.id),
                f"Original4535 second tenderize native28/118970 UID{event['uid']}",
            )
        if event.get("generic_effect") == 120461:
            grant = getattr(candidate, "native_order_baking_grants", {}).get(target.id)
            container = event.get("native_container") or {}
            if (
                isinstance(grant, dict)
                and grant.get("policy_sha256") == _digest(BAKING_POLICY)
                and getattr(candidate, "native_order_baking_policy", None)
                == BAKING_POLICY
                and grant.get("level") == 3
                and container.get("present") is True
                and container.get("type") == 1
                and container.get("is_state") is True
                and container.get("state_id") == 3123
                and event.get("source_id") == proof.owner_id
            ):
                completion = (
                    candidate.events[index + 2]
                    if index + 2 < len(candidate.events)
                    else {}
                )
                origin = getattr(completion, "_origin", None)
                if (
                    type(completion) is not _NativeOutcome
                    or not callable(origin)
                    or origin() is not candidate
                    or getattr(completion, "_source_digest", None)
                    != _digest(completion)
                    or completion.get("kind") != "native_order_baking_completed"
                    or completion.get("native_kill_uid") != event["uid"]
                    or completion.get("baking_carrier_uid") != grant.get("carrier_uid")
                    or completion.get("target_id") != target.id
                    or completion.get("policy_sha256") != _digest(BAKING_POLICY)
                ):
                    raise ValueError(
                        "Baking lacks its actual native terminal carrier witness"
                    )
                larva = next(row for row in state.larvae if row.actor_id == target.id)
                if larva.ingredient is None:
                    failure = getattr(
                        candidate, "native_order_bare_bake_failures", {}
                    ).get(target.id)
                    if (
                        not isinstance(failure, dict)
                        or failure.get("native_kill_uid") != event["uid"]
                        or failure.get("baking_carrier_uid") != grant.get("carrier_uid")
                        or failure.get("before_level") != state.strikes
                        or failure.get("after_level") != state.strikes + 1
                        or failure.get("policy_sha256") != _digest(BAKING_POLICY)
                    ):
                        raise ValueError(
                            "Bare baking lacks its actual reviewed native Failure grant"
                        )
                return _classification(
                    "bake",
                    dict(target_id=target.id),
                    f"Reviewed782 contact grant; actual3123 native120461 UID{event['uid']}",
                )
        if event.get("generic_effect") == 118950:
            failure = _matching_failure(candidate, event, proof, state)
            if failure is not None:
                publisher = (
                    "original120464"
                    if failure["effect_reference"] == 120464
                    else "reviewed direct-state2226"
                )
                return _classification(
                    "escape",
                    dict(target_id=target.id),
                    f"Original768 kill118950 UID{event['uid']}; {publisher} owner Failure3124 carrier{failure['carrier_uid']}",
                )
    if kind == "turn_started" and event.get("actor_id") == proof.owner_id:
        if event.get("actor_turn") == state.turn + 1:
            return _classification(
                "turn_end",
                {},
                "Actual original owner's next native turn_started boundary",
            )
    # Movement to a reviewed endpoint alone proves neither an original escape
    # effect nor a strike. Generic finished/death/score/UI callbacks never count.
    return None


def observe_pending(candidate, *, events):
    """Reduce actual outcomes in source event order after native resolution."""
    if getattr(candidate, "native_order_trial", None) is None:
        return 0
    from wakfu_server import native_order_trial_checkpoint as checkpoint

    total = 0
    if not isinstance(events, (tuple, list)):
        raise ValueError("Order observer requires this native action event batch")
    token = _CURRENT_BATCH.set(tuple(events))
    try:
        for event in tuple(events):
            total += checkpoint.observe(candidate, event, classify=classify)
    finally:
        _CURRENT_BATCH.reset(token)
    return total


def adopt_witnesses(destination, candidate, *, previous_sequence):
    """Rebind fresh witnesses only after actual owned fight adoption.

    Merely matching fight IDs or serialized bytes is insufficient. The real
    adopt_fight operation installs these exact list/sidecar objects before
    calling this function. Its caller captures the old destination sequence.
    """
    if getattr(candidate, "native_order_trial", None) is None:
        return 0
    if (
        destination is candidate
        or destination.id != candidate.id
        or destination.events is not candidate.events
        or destination.native_order_trial is not candidate.native_order_trial
        or type(previous_sequence) is not int
        or previous_sequence < 0
        or previous_sequence > candidate.sequence
    ):
        raise ValueError("Order witness transfer requires actual owned adoption")
    total = 0
    for event in reversed(candidate.events):
        if event.get("sequence", 0) <= previous_sequence:
            break
        if event.get("kind") not in (
            "native_order_state_applied",
            "native_order_spawned",
            "native_order_failure_applied",
            "native_order_baking_contact",
            "native_order_baking_completed",
        ):
            continue
        origin = getattr(event, "_origin", None)
        if (
            type(event) is not _NativeOutcome
            or not callable(origin)
            or origin() is not candidate
            or getattr(event, "_source_digest", None) != _digest(event)
        ):
            raise ValueError("Fresh order witness changed before owned adoption")
        event._origin = ref(destination)
        total += 1
    return total


def _record_failure_application(handler, effect, invocation, entry, *, change):
    """The original768 callback really applied3124 to this admitted owner."""
    from .combat_state_handler import NativeStateHandler
    from .combat_state_ledger import RunningState, StateChange
    from .combat_effect_dispatch import EffectInvocation
    from .combat_effect_removal import _identity_fields
    from .combat_state_parameters import pack_state_identity

    fight = handler.fight
    proof, _, _ = _proof(fight)
    if invocation.target_id != proof.owner_id:
        return None  # A different positive eGj recipient is not this owner's strike.
    container = invocation.native_retained_container or {}
    area = getattr(fight, "native_effect_areas", {}).get(container.get("id"))
    if invocation.native_running_uid is None:
        return None
    if (
        not isinstance(handler, NativeStateHandler)
        or type(invocation) is not EffectInvocation
        or effect.get("effect_class") != 304
        or type(entry) is not RunningState
        or entry.reference != 3124
        or type(change) is not StateChange
        or change.applied is not entry
        or entry.target_id != proof.owner_id
        or entry.caster_id != invocation.caster_id
        or container.get("type") != 3
        or container.get("native_kind") != "effect_area"
        or area is None
        or area.get("reference") != 768
        or area.get("uid") != container.get("id")
        or invocation.caster_id not in (area.get("uid"), area.get("owner_id"))
        or type(invocation.native_running_uid) is not int
        or invocation.native_running_uid <= 0
    ):
        raise ValueError("Order Failure3124 lacks its actual768 native callback")
    payload = getattr(fight, "state_wire_payloads", {}).get(entry.uid)
    if not isinstance(payload, str):
        raise ValueError("Order Failure3124 has no actual carrier payload")
    wire = _identity_fields(bytes.fromhex(payload))
    if any(
        wire.get(key) != value
        for key, value in {
            1: entry.uid,
            4: pack_state_identity(3124, entry.level),
            6: entry.caster_id & ((1 << 64) - 1),
            7: entry.target_id & ((1 << 64) - 1),
        }.items()
    ):
        raise ValueError("Order Failure3124 carrier differs from native application")
    previous = [
        old
        for old in change.removed
        if old.reference == 3124 and old.target_id == entry.target_id
    ]
    before = previous[0].level if len(previous) == 1 else 0
    if len(previous) > 1 or not 0 <= before < 3 or entry.level != before + 1:
        raise ValueError("Order Failure3124 is not one actual additive strike")
    return _publish(
        fight,
        "native_order_failure_applied",
        effect_reference=120464,
        runner_uid=invocation.native_running_uid,
        carrier_uid=entry.uid,
        caster_id=entry.caster_id,
        target_id=entry.target_id,
        before_level=before,
        after_level=entry.level,
        area_uid=area["uid"],
        area_reference=768,
        carrier_sha256=sha256(bytes.fromhex(payload)).hexdigest(),
    )


def _matching_failure(candidate, kill, proof, state):
    """Pair one actual768 death with its subsequent actual owner strike."""
    container = kill.get("native_container") or {}
    if container.get("type") != 3 or container.get("native_kind") != "effect_area":
        return None
    area = getattr(candidate, "native_effect_areas", {}).get(container.get("id"))
    if (
        area is None
        or area.get("reference") != 768
        or kill.get("source_id") not in (area.get("uid"), area.get("owner_id"))
    ):
        return None
    seen_kill = False
    for row in _CURRENT_BATCH.get():
        if row is kill:
            seen_kill = True
            continue
        if not seen_kill:
            continue
        if (
            row.get("kind") == "kill_hp_minimum_update"
            and row.get("generic_effect") == 118950
            and (row.get("native_container") or {}).get("id") == area["uid"]
        ):
            break  # A later activation cannot supply this death's missing strike.
        if (
            row.get("kind") != "native_order_failure_applied"
            or row.get("area_uid") != area["uid"]
        ):
            continue
        origin = getattr(row, "_origin", None)
        if (
            type(row) is not _NativeOutcome
            or not callable(origin)
            or origin() is not candidate
            or getattr(row, "_source_digest", None) != _digest(row)
            or row.get("target_id") != proof.owner_id
            or not (
                row.get("effect_reference") == 120464
                or row.get("effect_reference") == 2226
                and row.get("policy_sha256") == _digest(BAKING_POLICY)
                and row.get("authority") == BAKING_POLICY["escape_authority"]
                and row.get("native_kill_uid") == kill.get("uid")
            )
            or row.get("before_level") != state.strikes
            or row.get("after_level") != row.get("before_level", -2) + 1
        ):
            raise ValueError("Order escape has a forged or foreign Failure3124 witness")
        return row
    return None


def record_displacement(handler, effect, invocation, *, uid, positions_before, changed):
    """Witness paid4536 contact; initial3123 is separate reviewed server policy.

    An inert782 marker never awards a recipe. This records only an actual
    successful original118972 push into its registered native footprint.
    """
    fight = handler.fight
    if (
        getattr(fight, "native_order_trial", None) is None
        or invocation.reference != 118972
    ):
        return None
    from .combat_displacement import NativeDisplacementHandler
    from .combat_effect_dispatch import EffectInvocation
    from .combat_active_spell import active_spell_id
    from .combat_effect_area_geometry import contains_area_cell
    from .combat_environment_glyphs import verify_environment_glyph

    proof, _, state = _proof(fight)
    if (
        not isinstance(handler, NativeDisplacementHandler)
        or type(invocation) is not EffectInvocation
        or effect.get("effect_class") != 300
        or active_spell_id(fight) != 4536
        or invocation.caster_id != proof.owner_id
        or type(uid) is not int
        or uid <= 0
    ):
        raise ValueError("Order baking contact lacks the actual4536 native push")
    emitted = []
    for actor, destination in changed:
        if actor.id != invocation.target_id:
            continue
        if fight.actors.get(actor.id) is not actor:
            raise ValueError("Order baking contact has a foreign moved actor")
        before = positions_before.get(actor.id)
        after = tuple(actor.position)
        if before is None or tuple(destination) != after or tuple(before) == after:
            continue
        if not any(row.actor_id == actor.id for row in state.larvae):
            continue
        _owned_summon(fight, actor, proof.owner_id)
        for area in getattr(fight, "native_effect_areas", {}).values():
            if area.get("reference") != 782:
                continue
            if contains_area_cell(area, before) or not contains_area_cell(area, after):
                continue
            verify_environment_glyph(fight, area)
            witness = _publish(
                fight,
                "native_order_baking_contact",
                effect_reference=118972,
                spell_id=4536,
                runner_uid=uid,
                caster_id=proof.owner_id,
                target_id=actor.id,
                from_cell=tuple(before),
                to_cell=after,
                area_uid=area["uid"],
                area_reference=782,
            )
            _grant_baking(handler, witness)
            emitted.append(witness)
    return tuple(emitted)


def _grant_baking(displacement, contact):
    """Reviewed server program, not an asserted missing native304 root."""
    from .combat_definitions import state_profile
    from .combat_effect_dispatch import EffectInvocation
    from .combat_state_handler import StateCarrierContext
    from .combat_native_timing_context import native_time_payload
    from .combat_encounter_scene_states import native_state_source_digest

    fight = displacement.fight
    if getattr(fight, "native_order_baking_policy", None) != BAKING_POLICY:
        raise ValueError("Reviewed initial baking program was not explicitly frozen")
    runtime = getattr(displacement, "native_order_state_runtime", None)
    if not isinstance(runtime, tuple) or len(runtime) != 2:
        raise ValueError(
            "Reviewed baking requires the actual transaction state runtime"
        )
    handler, retention = runtime
    if handler.fight is not fight or retention.fight is not fight:
        raise ValueError("Reviewed baking changed native transaction ownership")
    actor = fight.actors[contact["target_id"]]
    grants = dict(getattr(fight, "native_order_baking_grants", {}))
    existing = [
        entry for entry in actor.state_ledger.entries if entry.reference == 3123
    ]
    if actor.id in grants:
        previous = grants[actor.id]
        if (
            previous.get("policy_sha256") != _digest(BAKING_POLICY)
            or len(existing) != 1
            or existing[0].uid != previous.get("carrier_uid")
            or existing[0].level != previous.get("level")
        ):
            raise ValueError("Reviewed baking lost its existing native carrier")
        return False  # A later valid push cannot restart or accelerate cooking.
    if existing:
        raise ValueError("Reviewed baking cannot adopt an unearned initial carrier")
    profile = state_profile(handler.catalog, 3123, 1)
    if tuple(handler.catalog["states"]["3123"]["effect_ids"]) != (
        120457,
        120458,
        120459,
        120461,
    ):
        raise ValueError("Original baking native roots changed")
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
    # 2226 is the existing direct-state convention; it is not a pizza source edge.
    if not retention.apply_state_reference(
        handler,
        EffectInvocation(
            2226,
            1,
            contact["caster_id"],
            actor.id,
            actor.position,
            native_retained_container={"present": False},
        ),
        3123,
        1,
        carrier_context=carrier,
    ):
        raise ValueError("Reviewed baking native initial state rejected")
    entries = [entry for entry in actor.state_ledger.entries if entry.reference == 3123]
    if len(entries) != 1 or entries[0].level != 1:
        raise ValueError("Reviewed baking lost its original native carrier")
    grants[actor.id] = dict(
        policy=BAKING_POLICY["policy"],
        authority=BAKING_POLICY["authority"],
        policy_sha256=_digest(BAKING_POLICY),
        contact_sequence=contact["sequence"],
        contact_sha256=_digest(contact),
        area_uid=contact["area_uid"],
        carrier_uid=entries[0].uid,
        level=1,
        source_sha256=native_state_source_digest(handler.catalog, 3123),
    )
    fight.native_order_baking_grants = grants


def _record_baking_growth(handler, effect, invocation, entry, *, change):
    from .combat_state_handler import NativeStateHandler
    from .combat_effect_dispatch import EffectInvocation
    from .combat_state_ledger import RunningState, StateChange

    fight = handler.fight
    grant = getattr(fight, "native_order_baking_grants", {}).get(invocation.target_id)
    if grant is None:
        return None  # Unrelated native3123 is not this reviewed recipe.
    if (
        not isinstance(handler, NativeStateHandler)
        or type(invocation) is not EffectInvocation
        or getattr(fight, "native_order_baking_policy", None) != BAKING_POLICY
        or grant.get("policy_sha256") != _digest(BAKING_POLICY)
        or type(entry) is not RunningState
        or type(change) is not StateChange
        or change.applied is not entry
        or entry.reference != 3123
        or effect.get("effect_class") != 304
        or invocation.state_uid != grant["carrier_uid"]
        or entry.level != grant["level"] + 1
        or entry.level > 3
        or len([old for old in change.removed if old.uid == grant["carrier_uid"]]) != 1
    ):
        raise ValueError("Reviewed baking lost its actual additive native lineage")
    grants = dict(fight.native_order_baking_grants)
    grants[entry.target_id] = dict(grant, carrier_uid=entry.uid, level=entry.level)
    fight.native_order_baking_grants = grants
    return None


def record_baking_death(kill_handler, effect, invocation, *, uid):
    """Seal actual120461 completion and reviewed bare failure before delivery."""
    fight = kill_handler.fight
    if (
        getattr(fight, "native_order_trial", None) is None
        or invocation.reference != 120461
    ):
        return None
    from .combat_native_container import resolve_state_container
    from .combat_kill import NativeKillHandler
    from .combat_definitions import state_profile
    from .combat_effect_dispatch import EffectInvocation
    from .combat_state_handler import StateCarrierContext
    from .combat_native_timing_context import native_time_payload

    proof, _, state = _proof(fight)
    death = fight.events[-1] if fight.events else {}
    kill = fight.events[-2] if len(fight.events) >= 2 else {}
    if (
        death.get("kind") != "death"
        or death.get("actor_id") != invocation.target_id
        or kill.get("kind") != "kill_hp_minimum_update"
        or kill.get("uid") != uid
        or kill.get("generic_effect") != 120461
        or kill.get("target_id") != invocation.target_id
        or not kill.get("hp_before", 0) > 0
        or kill.get("hp") != 0
    ):
        return None
    grant = getattr(fight, "native_order_baking_grants", {}).get(invocation.target_id)
    if grant is None:
        return None
    larva = next(
        (row for row in state.larvae if row.actor_id == invocation.target_id), None
    )
    if larva is None:
        return None
    entry = resolve_state_container(fight, invocation.state_uid)
    actor = fight.actors.get(invocation.target_id)
    if (
        not isinstance(kill_handler, NativeKillHandler)
        or type(invocation) is not EffectInvocation
        or getattr(fight, "native_order_baking_policy", None) != BAKING_POLICY
        or grant.get("policy_sha256") != _digest(BAKING_POLICY)
        or effect.get("effect_class") != 28
        or invocation.caster_id != proof.owner_id
        or entry is None
        or entry.reference != 3123
        or entry.level != 3
        or entry.target_id != invocation.target_id
        or entry.caster_id != proof.owner_id
        or grant.get("level") != 2
        or actor is None
        or actor.hp != 0
        or type(uid) is not int
        or uid <= 0
    ):
        raise ValueError("Baking completion lacks its actual native120461 source")
    _owned_summon(fight, actor, proof.owner_id)
    completion = _publish(
        fight,
        "native_order_baking_completed",
        native_kill_uid=uid,
        baking_carrier_uid=entry.uid,
        prior_carrier_uid=grant["carrier_uid"],
        target_id=actor.id,
        caster_id=proof.owner_id,
        policy_sha256=_digest(BAKING_POLICY),
        contact_sequence=grant["contact_sequence"],
    )
    if larva.ingredient is not None or any(
        row.reference in (3046, 3047, 3048) for row in actor.state_ledger.entries
    ):
        return completion  # Actual garnish forbids the reviewed bare-pizza strike.
    old = dict(getattr(fight, "native_order_bare_bake_failures", {}))
    if actor.id in old:
        return None
    runtime = getattr(kill_handler, "native_order_state_runtime", None)
    if not isinstance(runtime, tuple) or len(runtime) != 2:
        raise ValueError("Bare baking requires its actual transaction state runtime")
    handler, retention = runtime
    if handler.fight is not fight or retention.fight is not fight:
        raise ValueError("Bare baking changed its native transaction ownership")
    owner = fight.actors[proof.owner_id]
    before = [row for row in owner.state_ledger.entries if row.reference == 3124]
    if len(before) > 1 or (before[0].level if before else 0) != state.strikes:
        raise ValueError("Bare baking native Failure differs from earned strikes")
    profile = state_profile(handler.catalog, 3124, 1)
    if tuple(handler.catalog["states"]["3124"]["effect_ids"]) != (120462, 120463):
        raise ValueError("Bare baking native Failure roots changed")
    context = StateCarrierContext(
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
        EffectInvocation(
            2226,
            1,
            proof.owner_id,
            proof.owner_id,
            owner.position,
            native_retained_container={"present": False},
        ),
        3124,
        1,
        carrier_context=context,
    ):
        raise ValueError("Bare baking native Failure application rejected")
    after = [row for row in owner.state_ledger.entries if row.reference == 3124]
    if len(after) != 1 or after[0].level != state.strikes + 1:
        raise ValueError("Bare baking lost its actual additive Failure carrier")
    old[actor.id] = dict(
        policy_sha256=_digest(BAKING_POLICY),
        source="reviewed_bare_bake_failure_not_native304_edge",
        native_kill_uid=uid,
        baking_carrier_uid=entry.uid,
        failure_carrier_uid=after[0].uid,
        before_level=state.strikes,
        after_level=after[0].level,
    )
    fight.native_order_bare_bake_failures = old
    return old[actor.id]


def begin_area_batch(fight, row, target):
    """Capture the owner counter before this selected native768 root batch."""
    if (
        row.get("reference") != 768
        or getattr(fight, "native_order_trial", None) is None
    ):
        return None
    proof, _, state = _proof(fight)
    if state.finished or fight.actors[proof.owner_id].hp <= 0:
        return None
    if not any(larva.actor_id == target.id for larva in state.larvae):
        return None  # An ordinary NPC is not a trial's registered larva.
    _owned_summon(fight, target, proof.owner_id)
    if getattr(fight, "native_order_baking_policy", None) != BAKING_POLICY:
        raise ValueError("Escape reconstruction policy was not frozen")
    from .combat_environment_glyphs import verify_environment_glyph

    verify_environment_glyph(fight, row)
    entries = [
        entry
        for entry in fight.actors[proof.owner_id].state_ledger.entries
        if entry.reference == 3124
    ]
    if len(entries) > 1:
        raise ValueError("Escape owner has ambiguous native Failure carriers")
    return dict(
        event_start=len(fight.events),
        before_level=entries[0].level if entries else 0,
        owner_id=proof.owner_id,
        target_id=target.id,
        area_uid=row["uid"],
    )


def finish_area_batch(dispatcher, row, target, token):
    """Reviewed escape publisher after original roots; never duplicate120464."""
    if token is None:
        return None
    fight = dispatcher.native_state_handler.fight
    proof, _, _ = _proof(fight)
    if (
        token["owner_id"] != proof.owner_id
        or token["target_id"] != target.id
        or token["area_uid"] != row["uid"]
        or row.get("reference") != 768
    ):
        raise ValueError("Escape batch changed its admitted native recipients")
    from .combat_environment_glyphs import registered_environment_kill_source
    from .combat_ordinary_death import registered_ordinary_death
    from .combat_definitions import state_profile
    from .combat_state_handler import StateCarrierContext
    from .combat_native_timing_context import native_time_payload
    from .combat_effect_dispatch import EffectInvocation

    batch = fight.events[token["event_start"] :]
    kills = [
        event
        for event in batch
        if event.get("kind") == "kill_hp_minimum_update"
        and event.get("generic_effect") == 118950
        and event.get("target_id") == target.id
        and event.get("source_id") == row["uid"]
        and event.get("hp_before", 0) > 0
    ]
    if not kills:
        return None
    if (
        len(kills) != 1
        or not registered_environment_kill_source(fight, kills[0])
        or not registered_ordinary_death(fight, target)
    ):
        raise ValueError("Escape lacks one actual registered768 native death")
    owner = fight.actors[proof.owner_id]
    entries = [entry for entry in owner.state_ledger.entries if entry.reference == 3124]
    after = entries[0].level if len(entries) == 1 else 0
    before = token["before_level"]
    if len(entries) > 1 or before >= 3 or after not in (before, before + 1):
        raise ValueError("Escape native Failure changed by an unsupported amount")
    if after == before + 1:
        witnesses = [
            event
            for event in batch
            if type(event) is _NativeOutcome
            and event.get("kind") == "native_order_failure_applied"
            and event.get("effect_reference") == 120464
            and event.get("target_id") == owner.id
            and event.get("area_uid") == row["uid"]
            and event.get("before_level") == before
            and event.get("after_level") == after
        ]
        if len(witnesses) != 1:
            raise ValueError(
                "Escape owner Failure lacks its actual original120464 witness"
            )
        return witnesses[0]
    handler, retention = dispatcher.native_state_handler, dispatcher.native_retention
    if handler.fight is not fight or retention.fight is not fight:
        raise ValueError("Escape changed its native transaction state runtime")
    profile = state_profile(handler.catalog, 3124, 1)
    if tuple(handler.catalog["states"]["3124"]["effect_ids"]) != (120462, 120463):
        raise ValueError("Escape Failure original state program changed")
    context = StateCarrierContext(
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
        EffectInvocation(
            2226,
            1,
            owner.id,
            owner.id,
            owner.position,
            native_retained_container={"present": False},
        ),
        3124,
        1,
        carrier_context=context,
    ):
        raise ValueError("Reviewed escape native Failure application rejected")
    entries = [entry for entry in owner.state_ledger.entries if entry.reference == 3124]
    if len(entries) != 1 or entries[0].level != before + 1:
        raise ValueError("Reviewed escape lost its actual additive Failure carrier")
    entry = entries[0]
    payload = fight.state_wire_payloads.get(entry.uid)
    if not isinstance(payload, str):
        raise ValueError(
            "Reviewed escape Failure has no original native carrier payload"
        )
    return _publish(
        fight,
        "native_order_failure_applied",
        effect_reference=2226,
        authority=BAKING_POLICY["escape_authority"],
        policy_sha256=_digest(BAKING_POLICY),
        native_kill_uid=kills[0]["uid"],
        carrier_uid=entry.uid,
        caster_id=owner.id,
        target_id=owner.id,
        before_level=before,
        after_level=entry.level,
        area_uid=row["uid"],
        area_reference=768,
        carrier_sha256=sha256(bytes.fromhex(payload)).hexdigest(),
    )
