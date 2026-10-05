"""Native apply-state304 -> owned carrier310 and nested effects.

Use only on a spell transaction preview. Clock/flags must come from an audited
runtime context, not a guessed duration. The ledger retains subscribed roots
for later event delivery; this handler executes only immediate roots.
"""
from .combat_state_managers import state_manager
from dataclasses import dataclass, replace
from contextlib import nullcontext
from .combat_state_carrier import (
    state_carrier_payload,
    state_carrier_application,
    STATE_CARRIER_APPLICATION_OPCODE,
)
from .combat_effect_removal import running_effect_removal
from .combat_effect_dispatch import UnsupportedEffectExecution
from .combat_state_parameters import interpret_state_parameters
from .combat_subscription_runners import SUBSCRIPTION_FAMILIES


@dataclass(frozen=True)
class StateCarrierContext:
    native_turn_clock: int
    native_realtime_remaining: int
    applying_effect_has_delay: bool
    timeline: object
    parent_uid: int | None
    critical: bool
    flag17: bool
    flag18: bool
    related_uid: int
    timing_payload: bytes | None


class NativeStateHandler:
    def __init__(
        self,
        fight,
        packets,
        catalog,
        *,
        action_id,
        allocate_uid,
        context,
        execute_child,
        remove_child_effect=None,
        register_subscription=None,
        applied_state_scope=None,
        rng=None,
    ):
        self.fight, self.packets, self.catalog = fight, packets, catalog
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.execute_child = context, execute_child
        self.remove_child_effect = remove_child_effect
        self.register_subscription = register_subscription
        self.applied_state_scope = applied_state_scope
        self.rng = rng
        self.event_lifecycle = None
        self.prepared_runners = {}

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            # eWu inherits Qe.bbw: fresh bfA includes0, plus PK.aZO.
            masks = effect.get("target_masks")
            if masks is None or len(masks) != 7:
                raise ValueError("Missing native eWu produced event masks")
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                runner_modifier=runner,
                _event_ids=tuple(sorted({0, *(masks[6] or ())})),
            )

    def prepare(self, effect, values, invocation):
        if self.event_lifecycle is None:
            return invocation
        from .combat_state_runner import NativeRunnerStateLevel

        runner = NativeRunnerStateLevel(self.allocate_uid(), rng=self.rng)
        invocation = replace(invocation, native_running_uid=runner.uid)
        # Ordinary Qe.d(Collection): L1 precedes C and its level reseeding.
        self._phase(effect, invocation, runner, 1)
        parameters = interpret_state_parameters(values["parameters"])
        runner.seed(parameters["reference"], parameters["level"])
        from .combat_value_transfer import apply_context_value

        runner.set_calculated(
            apply_context_value(
                0,
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
        )
        self.prepared_runners[runner.uid] = runner
        return invocation

    def remove_state_children(self, state_uid):
        """Undo retained current-stat effects before their owned carrier.

        Bind remove_child_effect to NativeStatHandler.remove on this same
        transaction preview. Ownership uses the carrier UID, not the state ID,
        parent applicator UID or caster; multiple instances remain distinct.
        """
        if type(state_uid) is not int or not 0 < state_uid < (1 << 63):
            raise UnsupportedEffectExecution(
                "Missing owned state carrier UID for child removal"
            )
        children = tuple(
            uid
            for uid, child in self.fight.owned_stat_effects.items()
            if child.get("state_uid") == state_uid
        )
        if not children:
            return
        if not callable(self.remove_child_effect):
            raise UnsupportedEffectExecution(
                "Retained state children require an explicit removal callback"
            )
        owner = getattr(self.remove_child_effect, "__self__", None)
        if owner is not None and getattr(owner, "fight", self.fight) is not self.fight:
            raise UnsupportedEffectExecution(
                "State child removal callback belongs to another fight preview"
            )
        for uid in children:
            self.remove_child_effect(uid)
            if uid in self.fight.owned_stat_effects:
                raise UnsupportedEffectExecution(
                    "State child removal callback did not remove the owned effect"
                )

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 304:
            raise UnsupportedEffectExecution(
                "Unsupported native state applicator parameters"
            )
        try:
            parameters = interpret_state_parameters(values["parameters"])
        except ValueError as error:
            raise UnsupportedEffectExecution(str(error)) from error
        runner = None
        if self.event_lifecycle is not None:
            if invocation.native_running_uid is not None:
                runner = self.prepared_runners.pop(invocation.native_running_uid, None)
                if runner is None:
                    raise ValueError("Missing prepared native eWu applicator")
            else:
                # Qe.k replay: C precedes L1/L2; mutations now survive.
                from .combat_state_runner import NativeRunnerStateLevel

                runner = NativeRunnerStateLevel(
                    self.allocate_uid(),
                    rng=self.rng,
                    reference=parameters["reference"],
                    level=parameters["level"],
                )
                from .combat_value_transfer import apply_context_value

                runner.set_calculated(
                    apply_context_value(
                        0,
                        None
                        if invocation.native_context_hex is None
                        else bytes.fromhex(invocation.native_context_hex),
                    )
                )
                self._phase(effect, invocation, runner, 1)
            self._phase(effect, invocation, runner, 2)
        result = self.apply_reference(
            effect,
            invocation,
            parameters["reference"] if runner is None else runner.reference,
            parameters["level"] if runner is None else runner.pending_level,
        )
        if runner is not None:
            runner.finish_application()
            self._phase(effect, invocation, runner, 3)
            self._phase(effect, invocation, runner, 4)
            from .combat_runner_callbacks import notify_runner_value

            notify_runner_value(invocation, runner.value)
        return result

    def apply_reference(
        self,
        effect,
        invocation,
        reference,
        level,
        *,
        carrier_context=None,
        protected=None,
    ):
        """Apply a native carrier from an already interpreted reference/level.

        304's separate chance gate belongs to its parameter interpreter;321
        reapplication has no invented304 parameters and uses its own context.
        """
        context = (
            self.context(effect, invocation)
            if carrier_context is None
            else carrier_context
        )
        if not isinstance(context, StateCarrierContext):
            raise ValueError("Missing audited native state carrier context")
        uid = self.allocate_uid()
        change = self.fight.apply_state(
            invocation.caster_id,
            invocation.target_id,
            reference,
            level,
            uid=uid,
            catalog=self.catalog,
            applying_effect_has_delay=context.applying_effect_has_delay,
            timeline=context.timeline,
            protected=protected,
        )
        entry = change.applied
        if entry is None:
            return False
        for old in change.removed:
            original = self.fight.state_wire_payloads.get(old.uid)
            if original is None:
                raise UnsupportedEffectExecution(
                    "Missing owned payload for replaced state"
                )
            packet = running_effect_removal(
                self.fight.id,
                self.action_id,
                effect_class=310,
                target_id=old.target_id,
                uid=old.uid,
                running_effect_payload=bytes.fromhex(original),
            )
            self.remove_state_children(old.uid)
            self.packets.append((13560, packet))
            del self.fight.state_wire_payloads[old.uid]
        if entry.retained:
            payload = state_carrier_payload(
                uid=uid,
                base_uid=context.parent_uid,
                caster_id=entry.caster_id,
                target_id=entry.target_id,
                state_id=entry.reference,
                level=entry.level,
                native_turn_clock=context.native_turn_clock,
                native_realtime_remaining=context.native_realtime_remaining,
                critical=context.critical,
                flag17=context.flag17,
                flag18=context.flag18,
                related_uid=context.related_uid,
                timing_payload=context.timing_payload,
            )
            packet = state_carrier_application(
                self.fight.id,
                self.action_id,
                uid=uid,
                target_id=entry.target_id,
                running_effect_payload=payload,
            )
            self.fight.state_wire_payloads[uid] = payload.hex()
            self.packets.append((STATE_CARRIER_APPLICATION_OPCODE, packet))
        scope = (
            nullcontext()
            if self.applied_state_scope is None
            else self.applied_state_scope(entry)
        )
        with scope:
            for child_id in entry.effect_ids:
                child = self.catalog["effects"][str(child_id)]
                masks = child.get("target_masks")
                if masks is None or len(masks) != 7:
                    raise UnsupportedEffectExecution(
                        "Missing nested state's native trigger masks"
                    )
                # Removal-only masks (index2) still execute at installation.
                if any(masks[index] for index in (0, 1, 3, 4, 5)):
                    if not entry.retained:
                        raise UnsupportedEffectExecution(
                            "Instant state cannot retain event subscriptions"
                        )
                    if self.register_subscription is not None:
                        if child["effect_class"] not in SUBSCRIPTION_FAMILIES:
                            error = UnsupportedEffectExecution(
                                f"Subscribed state child family {child['effect_class']} reference {child_id} has no central registration machinery"
                            )
                            error.audit_reference = child_id
                            error.audit_level = entry.level
                            raise error
                        self.register_subscription(
                            replace(
                                invocation,
                                reference=child_id,
                                level=entry.level,
                                caster_id=entry.caster_id,
                                target_id=entry.target_id,
                                cell=state_manager(
                                    self.fight, entry.target_id
                                ).position,
                                base_uid=None,
                                native_running_uid=None,
                                state_uid=uid,
                                native_context_hex="0801100020ffffffffffffffffff0128013000380040004800",
                                native_value_scope=None,
                                native_explicit_target=False,
                            )
                        )
                    continue  # Unbound legacy paths retain subscriptions only in ledger.effect_ids.
                self.execute_child(
                    replace(
                        invocation,
                        reference=child_id,
                        level=entry.level,
                        caster_id=entry.caster_id,
                        target_id=entry.target_id,
                        cell=state_manager(self.fight, entry.target_id).position,
                        base_uid=None,
                        native_running_uid=None,
                        state_uid=uid,
                        native_context_hex="0801100020ffffffffffffffffff0128013000380040004800"
                        if self.register_subscription is not None
                        else invocation.native_context_hex,
                        native_value_scope=None
                        if self.register_subscription is not None
                        else invocation.native_value_scope,
                        native_explicit_target=False,
                    )
                )
        return True
