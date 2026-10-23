"""Executable native retained-group replay over one transaction preview.

Event production and clone guards/criteria are supplied by the authority for
an actual source running effect. This module never invents an event ID.
"""
from dataclasses import dataclass, asdict, replace
from contextvars import ContextVar
from .combat_effect_dispatch import EffectInvocation
from .combat_native_events import (
    subscription_selection,
    subscription_actor_ids,
    activation_order_key,
)


@dataclass(frozen=True)
class NativeEventSource:
    uid: int
    generic_effect: int
    value: int
    caster_id: int | None
    target_id: int | None
    cell: tuple[int, int, int]
    event_ids: tuple[int, ...]
    channel: int
    manager_actor_id: int
    source_parent_uid: int | None
    suppresses_level_one: bool
    suppresses_all: bool
    suppressed: bool
    native_events_verified: bool
    cost_source: dict | None = None
    native_container: dict | None = None
    effect_action_id: int | None = None
    zone_trigger_policy: dict | None = None
    effect_flags: tuple[int, ...] | None = None  # Actual source PK/eVn REP flags.
    native_definition_present: bool | None = None
    native_definition_variant: int | None = None  # Actual PK.dd(1) source value.
    native_execution_status: int | None = None  # Actual eZR.cYh when observed.
    native_execution_blocked: bool | None = None  # Proven cYh()==7 predicate.
    final_modifier: object = (
        None  # Transient live faq accumulator; never retained on Fight.
    )
    runner_modifier: object = (
        None  # Transient live Qe amount, excluded from descriptors.
    )

    def validate(self):
        from .combat_movement_payment_events import valid_movement_descriptor

        movement_payment = valid_movement_descriptor(
            self.cost_source, caster_id=self.caster_id, target_id=self.target_id
        )
        if movement_payment:
            costs = self.cost_source["action_costs"]
            hour_wp = (
                self.cost_source["movement_payment_policy"].get("payment_phase")
                == "hour_wp"
            )
            identifiers = (
                (0, 60, 2263)
                if hour_wp
                else tuple(
                    sorted(
                        {0, 74}
                        | ({65} if costs["mp"] else set())
                        | ({55} if costs["ap"] else set())
                        | ({60} if costs["wp"] else set())
                    )
                )
            )
            if (
                self.event_ids != identifiers
                or self.value != costs["ap"] | (costs["mp"] << 8) | (costs["wp"] << 16)
                or self.channel not in (3, 4, 30, 40, 31, 41)
            ):
                raise ValueError("Movement eWf source differs from its payment")
        synthetic_payment = (
            self.uid == -1
            and self.generic_effect == -1
            and self.native_definition_present is False
            and self.native_container == {"present": False}
            and self.effect_action_id is None
            and self.effect_flags is None
            and self.native_execution_status == -1
            and isinstance(self.cost_source, dict)
            and self.cost_source.get("runner_class") == "eWf"
            and self.cost_source.get("spell_context") == {"present": False}
            and (
                (
                    self.cost_source.get("paid_ability_policy") is None
                    and self.cost_source.get("movement_payment_policy") is None
                )
                or movement_payment
                or self.cost_source.get("paid_ability_policy")
                == {"payer_id": self.caster_id, "mi": True, "mh": False}
                and self.cost_source.get("movement_payment_policy") is None
                and self.caster_id == self.target_id
            )
            and isinstance(self.cost_source.get("action_costs"), dict)
            and set(self.cost_source["action_costs"]) == {"ap", "mp", "wp"}
            and all(
                type(v) is int and -128 <= v <= 127
                for v in self.cost_source["action_costs"].values()
            )
        )
        from .combat_breeze_payment_events import valid_fad_source

        synthetic_breeze = (
            self.uid == -1
            and self.generic_effect == -1
            and self.native_definition_present is False
            and self.native_container == {"present": False}
            and self.effect_action_id is None
            and self.effect_flags is None
            and self.native_execution_status == -1
            and valid_fad_source(self.cost_source)
            and self.caster_id == self.target_id == self.cost_source["payer_id"]
            and self.value == self.cost_source["requested_delta"]
            and tuple(self.event_ids) == (0, 2246)
        )
        if (
            self.native_events_verified is not True
            or type(self.uid) is not int
            or not (0 < self.uid < (1 << 63) or synthetic_payment or synthetic_breeze)
        ):
            raise ValueError("Verified native running-effect event source required")
        if (
            type(self.generic_effect) is not int
            or len(self.cell) != 3
            or any(type(v) is not int for v in self.cell)
        ):
            raise ValueError("Native source identity and cell required")
        if type(self.value) is not int or not -(1 << 31) <= self.value < (1 << 31):
            raise ValueError("Native source running-effect value required")
        if type(self.manager_actor_id) is not int or self.manager_actor_id == 0:
            raise ValueError("Actual native recipient manager actor required")
        if any(
            type(v) is not bool
            for v in (self.suppresses_level_one, self.suppresses_all, self.suppressed)
        ):
            raise ValueError("Native source suppression flags required")
        if not isinstance(self.event_ids, tuple) or any(
            type(v) is not int or v < 0 for v in self.event_ids
        ):
            raise ValueError("Native source event IDs required")

        for observed in (self.native_definition_present, self.native_execution_blocked):
            if observed is not None and type(observed) is not bool:
                raise ValueError("Invalid native source predicate observation")
        if self.native_definition_variant is not None and (
            type(self.native_definition_variant) is not int
            or not -(1 << 63) <= self.native_definition_variant < (1 << 63)
        ):
            raise ValueError("Invalid native source PK variant")
        if self.native_execution_status is not None and (
            type(self.native_execution_status) is not int
            or not -128 <= self.native_execution_status <= 127
        ):
            raise ValueError("Invalid native source execution status")
        if (
            self.native_execution_status is not None
            and self.native_execution_blocked is not None
            and self.native_execution_blocked != (self.native_execution_status == 7)
        ):
            raise ValueError("Inconsistent native source blocked observation")

        if self.final_modifier is not None:
            from .combat_final_modifier import NativeFinalModifier

            if not isinstance(self.final_modifier, NativeFinalModifier):
                raise ValueError("Missing native faq source descriptor")
            self.final_modifier.validate()
            if (
                self.final_modifier.uid != self.uid
                or self.final_modifier.family != self.effect_action_id
            ):
                raise ValueError("Native faq source descriptor identity mismatch")


@dataclass(frozen=True)
class NativeExternalEvent:
    """Server external delivery with native null source; no running-effect UID."""

    manager_actor_id: int
    event_ids: tuple[int, ...]
    channel: int
    # These fields let native selection reuse its source-absent branch.
    uid: None = None
    source_parent_uid: None = None
    caster_id: None = None
    target_id: None = None
    suppresses_level_one: bool = False
    suppresses_all: bool = False
    suppressed: bool = False
    cast_boundary_context: dict | None = None
    turn_boundary_context: dict | None = None
    movement_boundary_context: dict | None = None

    def validate(self):
        if self.movement_boundary_context is not None:
            from .combat_external_movement_recipient import (
                validate_movement_boundary_context,
            )

            validate_movement_boundary_context(self.movement_boundary_context)
            if (
                self.event_ids != (1005,)
                or self.turn_boundary_context is not None
                or self.cast_boundary_context is not None
            ):
                raise ValueError(
                    "Movement facts require one matching external boundary"
                )
        if self.turn_boundary_context is not None:
            from .combat_turn_events import validate_turn_boundary_context

            validate_turn_boundary_context(self.turn_boundary_context)
            if self.event_ids != (self.turn_boundary_context["event_id"],):
                raise ValueError("Turn boundary facts require matching external event")
            if self.cast_boundary_context is not None:
                raise ValueError("External event cannot combine cast and turn facts")
        if self.cast_boundary_context is not None:
            from .combat_cast_events import validate_cast_boundary_context

            validate_cast_boundary_context(self.cast_boundary_context)
            if self.event_ids not in ((1024,), (1025,)):
                raise ValueError("Cast boundary facts require external cast event")
        if (
            type(self.manager_actor_id) is not int
            or self.manager_actor_id == 0
            or type(self.channel) is not int
            or not isinstance(self.event_ids, tuple)
            or any(type(v) is not int or v < 0 for v in self.event_ids)
            or any(
                getattr(self, name) is not None
                for name in ("uid", "source_parent_uid", "caster_id", "target_id")
            )
            or self.suppresses_level_one
            or self.suppresses_all
            or self.suppressed
        ):
            raise ValueError("Native external null-source event required")


@dataclass(frozen=True)
class NativeCloneAuthority:
    executable: object  # (effect, invocation, source) -> bool; eZR.i corpse/context guards
    condition_context: object  # (effect, invocation, source) -> current native criterion context


_ACTIVE_TRIGGER_KEYS = ContextVar("native_qj_active_trigger_keys", default=frozenset())


class NativeTriggerHistory:
    """Qj.b/a/bcm tracks active (generic,caster,target) triples, not all past executions."""

    @property
    def active(self):
        # Qj is thread-local, shared by nested runtime/replay instances.
        # Immutable values also isolate copied asynchronous contexts.
        return set(_ACTIVE_TRIGGER_KEYS.get())

    def enter(self, generic, caster, target):
        key = (
            generic,
            0 if caster is None else caster,
            0 if target is None else target,
        )
        if key in self.active:
            return None
        _ACTIVE_TRIGGER_KEYS.set(_ACTIVE_TRIGGER_KEYS.get() | {key})
        return key

    def leave(self, key):
        active = _ACTIVE_TRIGGER_KEYS.get()
        if key not in active:
            raise ValueError("Native trigger history scope is not active")
        _ACTIVE_TRIGGER_KEYS.set(active - {key})


class NativeEventReplay:
    def __init__(self, dispatcher, retention):
        self.dispatcher, self.retention = dispatcher, retention
        self.history = NativeTriggerHistory()

    def __call__(self, source, *, authority, eligible_uids=None):
        if not isinstance(
            source, (NativeEventSource, NativeExternalEvent)
        ) or not isinstance(authority, NativeCloneAuthority):
            raise ValueError("Native event source and clone authority required")
        source.validate()
        if eligible_uids is not None and (
            not isinstance(eligible_uids, frozenset)
            or any(type(uid) is not int or uid <= 0 for uid in eligible_uids)
        ):
            raise ValueError("Explicit retained UID scope required")
        if not callable(authority.executable) or not callable(
            authority.condition_context
        ):
            raise ValueError("Native clone callbacks required")
        view = self.retention.view()
        queued = []
        remove = []
        for entry in view.entries:
            if eligible_uids is not None and entry.uid not in eligible_uids:
                continue
            if entry.manager_id != source.manager_actor_id:
                continue
            row = self.retention.fight.native_owned_group_effects.get(entry.uid)
            if row is None:
                definition = self.retention.metadata["effects"].get(
                    str(entry.generic_effect)
                )
                if definition is not None and definition["subscription"]:
                    raise ValueError(
                        "Subscribed retained family has no native replay runner "
                        f"(uid={entry.uid}, reference={entry.generic_effect}, "
                        f"family={entry.effect_class}, manager={entry.manager_id})"
                    )
                continue
            definition = self.retention.metadata["effects"][
                str(row["invocation"]["reference"])
            ]
            action = subscription_selection(
                masks=row["native_subscription_masks"],
                event_ids=source.event_ids,
                channel=source.channel,
                global_subscription=definition["event_global_subscription"],
                reversed_subscription=definition["event_reverse_subscription"],
                flags=row["native_effect_flags"],
                source_present=isinstance(source, NativeEventSource),
                source_suppresses_level_one=source.suppresses_level_one,
                source_suppresses_all=source.suppresses_all,
                source_suppressed=source.suppressed,
                source_is_self=source.uid == entry.uid,
                source_parent_is_self=source.source_parent_uid == entry.uid,
            )
            if action == "remove":
                remove.append(entry.uid)
            elif action == "activate":
                queued.append((entry, row, definition))
        # Native eZX.a removes queued listeners before sorting/activating survivors.
        if remove:
            self.retention.removal(view).remove(remove)
        queued.sort(
            key=lambda item: activation_order_key(
                priority=item[2]["event_priority"],
                generic_effect=item[0].generic_effect,
                uid=item[0].uid,
            )
        )
        outcomes = []
        for entry, row, definition in queued:
            if (
                isinstance(source, NativeEventSource)
                and source.runner_modifier is not None
            ):
                from .combat_trigger_value_modifier import NativeRunnerAmount

                runner = source.runner_modifier
                if (
                    not isinstance(runner, NativeRunnerAmount)
                    or runner.uid != source.uid
                    or runner.family != source.effect_action_id
                ):
                    raise ValueError("Native source runner amount identity mismatch")
                from .combat_runner_target import current_runner_target

                source = replace(
                    source,
                    value=runner.value,
                    target_id=current_runner_target(runner, source.target_id),
                )
            if entry.uid not in self.retention.fight.native_owned_group_effects:
                continue
            count = row.get("execution_count")
            if type(count) is not int or not -2147483648 <= count <= 2147483647:
                raise ValueError("Missing native retained listener execution count")
            original = EffectInvocation(
                **dict(
                    row["invocation"],
                    cell=tuple(row["invocation"]["cell"]),
                    native_value_scope=None,
                )
            )
            retained_container = self.retention.replay_container(row, entry, original)
            if retained_container is not None:
                # Replay runs under a fight-scoped dispatcher, not the
                # original spell's runtime plan. Restore the exact container
                # snapshot captured when this listener was registered.
                original = replace(
                    original,
                    native_retained_container=dict(retained_container),
                )
            caster, target = subscription_actor_ids(
                target_code=definition["event_target_code"],
                caster_code=definition["event_caster_code"],
                original_caster=original.caster_id,
                original_target=original.target_id,
                manager_actor=entry.manager_id,
                source_caster=source.caster_id,
                source_target=source.target_id,
                source_present=isinstance(source, NativeEventSource),
            )
            from .combat_encounter_owned_start_binding import owned_start_caster

            reconstructed_caster = owned_start_caster(
                self.retention.fight,
                source,
                entry=entry,
                original=original,
                definition=definition,
                effect=self.dispatcher.effects[str(original.reference)],
            )
            if reconstructed_caster is not None:
                caster = reconstructed_caster
            from .combat_encounter_movement_binding import movement_caster

            committed_caster = movement_caster(
                self.retention.fight,
                source,
                entry=entry,
                original=original,
                definition=definition,
                effect=self.dispatcher.effects[str(original.reference)],
            )
            if committed_caster is not None:
                caster = committed_caster
            from .combat_encounter_npc_start_binding import npc_start_caster

            npc_caster = npc_start_caster(
                self.retention.fight,
                source,
                entry=entry,
                original=original,
                definition=definition,
                effect=self.dispatcher.effects[str(original.reference)],
            )
            if npc_caster is not None:
                caster = npc_caster
            from .combat_external_turn_recipient import external_turn_recipient

            target = external_turn_recipient(
                self.retention.fight,
                source,
                target_code=definition["event_target_code"],
                original_target=target,
            )
            from .combat_external_turn_recipient import external_movement_recipient

            target = external_movement_recipient(
                self.retention.fight,
                source,
                target_code=definition["event_target_code"],
                original_target=target,
            )
            if caster is None:
                raise ValueError("Native group clone requires caster actor")
            from .combat_state_managers import registered_area_pv

            target_manager = (
                (
                    self.retention.fight.actors.get(target)
                    or registered_area_pv(self.retention.fight, target)
                )
                if target is not None
                else None
            )
            if target is not None and target_manager is None:
                raise ValueError("Native group clone target manager absent")
            cell = (
                target_manager.position
                if target is not None
                else (
                    source.cell
                    if isinstance(source, NativeEventSource)
                    else original.cell
                )
            )
            if (
                target is None
                and isinstance(source, NativeExternalEvent)
                and source.cast_boundary_context is not None
            ):
                # Wakemu cast policy supplies the validated cast anchor for
                # null-PV cell groups. It does not fabricate a native Qe source
                # or replace an explicitly selected actor recipient.
                from .combat_cast_events import validate_cast_boundary_context

                context = validate_cast_boundary_context(source.cast_boundary_context)
                cell = tuple(context["target_cell"])
            source_context = (
                asdict(replace(source, final_modifier=None, runner_modifier=None))
                if isinstance(source, NativeEventSource)
                else None
            )
            if source_context is not None:
                from .combat_state_runner import NativeRunnerStateLevel

                if isinstance(source.runner_modifier, NativeRunnerStateLevel):
                    source_context[
                        "native_apply_state_reference"
                    ] = source.runner_modifier.reference
                    source_context["native_source_is_eWu"] = True
                elif source.runner_modifier is not None:
                    source_context["native_source_is_eWu"] = False
                source_context.pop("final_modifier", None)
                source_context.pop("runner_modifier", None)
            invocation = replace(
                original,
                caster_id=caster,
                target_id=target,
                cell=cell,
                base_uid=entry.uid,
                wakemu_fresh_child_selection=False,
                native_trigger_context=(source_context),
                native_turn_boundary_context=(
                    source.turn_boundary_context
                    if isinstance(source, NativeExternalEvent)
                    else None
                ),
                native_movement_boundary_context=(
                    source.movement_boundary_context
                    if isinstance(source, NativeExternalEvent)
                    else None
                ),
                native_cast_boundary_context=(
                    source.cast_boundary_context
                    if isinstance(source, NativeExternalEvent)
                    else None
                ),
            )
            key = self.history.enter(entry.generic_effect, caster, target)
            if key is None:
                continue
            try:
                effect = self.dispatcher.effects[str(invocation.reference)]
                executable = authority.executable(effect, invocation, source)
                accepted = False

                def allocate_clone():
                    nonlocal accepted
                    uid = self.retention.fight.allocate_effect_uid()
                    accepted = True
                    return uid

                from .combat_final_modifier import final_modifier_source

                from contextlib import nullcontext

                # Native clones keep their actual PL pointer for all children,
                # including siblings after another child removes its Qf carrier.
                # Scope ends with this activation; it does not revive the state.
                owner_scope = nullcontext()
                if original.state_uid is not None:
                    owner_scope = self.retention.container_scope(original)
                with final_modifier_source(source), owner_scope:
                    outcomes.append(
                        self.dispatcher.execute_activation(
                            invocation,
                            source=source,
                            condition_context=authority.condition_context,
                            executable=executable,
                            allocate_uid=allocate_clone,
                        )
                    )
                # Qe.k decrements the original listener after an accepted clone,
                # independently of whether any child reported success.
                if (
                    accepted
                    and entry.uid in self.retention.fight.native_owned_group_effects
                    and count >= 0
                ):
                    count = max(0, count - 1)
                    row["execution_count"] = count
                    if count == 0:
                        self.retention.remove_group(entry.uid)
            finally:
                self.history.leave(key)
        return tuple(outcomes)


HEALING_ELEMENT_EVENT_IDS = {25: 17, 251: 16, 253: 15, 258: 13, 259: 14, 1084: 30}


def healing_event_source(
    effect,
    invocation,
    packet,
    *,
    channel,
    manager_actor_id,
    source_suppressed,
    definition_suppresses_level_one,
    extra_dynamic_event_ids,
):
    """Build source from an actual eXs application packet and audited event production.

    eXs.bbx emits0/1; eZR.bby emits the registry's element event. Extra runtime
    events must be supplied explicitly (empty when authoritatively absent).
    """
    import struct
    from .combat_effect_removal import _identity_fields

    if not isinstance(packet, bytes) or len(packet) < 19:
        raise ValueError("Owned native healing packet required")
    fight, action, sequence, reserved, kind, size = struct.unpack(
        ">iiiBih", packet[:19]
    )
    if (
        kind != effect["effect_class"]
        or kind not in HEALING_ELEMENT_EVENT_IDS
        or len(packet) != 19 + size
    ):
        raise ValueError("Native healing source packet family/size mismatch")
    fields = _identity_fields(packet[19:])
    expected = (invocation.reference, invocation.caster_id, invocation.target_id)
    signed = lambda v: v - (1 << 64) if v >= (1 << 63) else v
    if (fields.get(3), signed(fields.get(6, 0)), signed(fields.get(7, 0))) != expected:
        raise ValueError("Native healing source identity mismatch")
    if (
        type(source_suppressed) is not bool
        or type(definition_suppresses_level_one) is not bool
    ):
        raise ValueError("Explicit native source suppression required")
    if not isinstance(extra_dynamic_event_ids, tuple) or any(
        type(v) is not int or v < 0 for v in extra_dynamic_event_ids
    ):
        raise ValueError("Explicit native dynamic event IDs required")
    masks = effect["target_masks"]
    flags = effect["native_effect_flags"]
    emitted = {
        0,
        1,
        HEALING_ELEMENT_EVENT_IDS[kind],
        *(masks[6] or ()),
        *extra_dynamic_event_ids,
    }
    parent = (
        None
        if invocation.native_trigger_context is None
        else invocation.native_trigger_context["uid"]
    )
    return NativeEventSource(
        fields[1],
        invocation.reference,
        signed(fields.get(4, 0)),
        invocation.caster_id,
        invocation.target_id,
        invocation.cell,
        tuple(sorted(emitted)),
        channel,
        manager_actor_id,
        parent,
        source_suppressed or definition_suppresses_level_one or 5 in flags,
        6 in flags,
        source_suppressed,
        True,
    )


@dataclass(frozen=True)
class NativeHealingEventAuthority:
    """Authority returns ordered real Qf deliveries for this source application.

    sources(preview, plan, effect, invocation, packet) must return validated
    NativeEventSource objects. It owns Qe.a routing (caster30, target3, globals31),
    suppression and dynamic events; they cannot be inferred from a heal packet.
    """

    sources: object
    clone: NativeCloneAuthority


class NativeHealingEventEmitter:
    def __init__(self, replay, authority, *, preview, plan):
        if not isinstance(authority, NativeHealingEventAuthority) or not callable(
            authority.sources
        ):
            raise ValueError("Authoritative native healing deliveries required")
        if not isinstance(authority.clone, NativeCloneAuthority):
            raise ValueError("Authoritative native clone context required")
        self.replay, self.authority, self.preview, self.plan = (
            replay,
            authority,
            preview,
            plan,
        )

    def __call__(self, effect, invocation, packet):
        # Materialize/validate all routes before replay mutates the same preview.
        sources = tuple(
            self.authority.sources(self.preview, self.plan, effect, invocation, packet)
        )
        from .combat_effect_removal import _identity_fields
        import struct

        fight, action = struct.unpack(">ii", packet[:8])
        fields = _identity_fields(packet[19:])
        if fight != self.preview.id:
            raise ValueError("Native healing event belongs to a different fight")
        for source in sources:
            if not isinstance(source, (NativeEventSource, NativeExternalEvent)):
                raise ValueError("Native healing event source required")
            source.validate()
            if (
                source.uid,
                source.generic_effect,
                source.value,
                source.caster_id,
                source.target_id,
            ) != (
                fields[1],
                invocation.reference,
                fields.get(4, 0),
                invocation.caster_id,
                invocation.target_id,
            ):
                raise ValueError(
                    "Native delivery does not belong to the applied healing effect"
                )
            if source.manager_actor_id not in self.preview.actors:
                raise ValueError("Native event recipient is absent from this preview")
        return tuple(
            self.replay(source, authority=self.authority.clone) for source in sources
        )
