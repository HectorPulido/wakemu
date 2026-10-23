"""Native eZi321 decurse;315 is eYQ area creation and is not a removal.

Runs only inside the enclosing spell transaction preview. Reapplication is an
explicit audited callback, preserving the native decurse source rather than
silently reusing the original caster/UID or child magnitudes.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
from dataclasses import replace
from wakfu_server.paths import DATA_ROOT
from .combat_effect_dispatch import UnsupportedEffectExecution
from .combat_effect_removal import running_effect_removal

RULES = protocol_catalog.load(DATA_ROOT / "state-decurse-rules.json")


class NativeStateDecurseHandler:
    def __init__(
        self,
        fight,
        packets,
        catalog,
        *,
        action_id,
        state_handler,
        reapply_state=None,
        allocate_uid=None,
        rng=None,
        event_lifecycle=None,
    ):
        self.fight, self.packets, self.catalog = fight, packets, catalog
        self.action_id, self.state_handler, self.reapply_state = (
            action_id,
            state_handler,
            reapply_state,
        )
        if state_handler.fight is not fight:
            raise ValueError("State handler belongs to another preview")
        self.allocate_uid = allocate_uid
        self.rng = rng
        self.event_lifecycle = event_lifecycle
        self.prepared = {}

    def _parameters(self, effect, values):
        from .combat_state_decurse_parameters import state_decurse_parameters

        return state_decurse_parameters(effect, values)

    def _phase(self, effect, invocation, runner, channel):
        masks = effect.get("target_masks")
        if not isinstance(masks, (tuple, list)) or len(masks) != 7:
            raise ValueError("Missing native eZi produced event masks")
        # eZi.bbx inherits eZR/Qe events and adds2225; PK.aZO supplies
        # definition-specific events, including Cra state reduction2288.
        self.event_lifecycle.phase(
            effect,
            invocation,
            uid=runner.uid,
            value=runner.value,
            channel=channel,
            runner_modifier=runner,
            _event_ids=tuple(sorted({0, 2225, *(masks[6] or ())})),
        )

    def _prepare(self, effect, values, invocation, *, clone_uid=None):
        parameters = self._parameters(effect, values)
        if self.event_lifecycle is None or invocation.target_id is None:
            return invocation
        if not self.native_eligibility(effect, invocation):
            return invocation
        from .combat_trigger_value_modifier import NativeRunnerAmount
        from .combat_value_transfer import apply_context_value

        if clone_uid is None and not callable(self.allocate_uid):
            raise ValueError("Missing native eZi UID allocator")
        uid = self.allocate_uid() if clone_uid is None else clone_uid
        selected = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, 321, rng=self.rng)
        self.prepared[uid] = runner
        try:
            # Qe.d(Collection) emits L1 before C; Qe.k(source) calculates
            # the clone before L1. C writes state reference to aSg.
            if clone_uid is None:
                self._phase(effect, selected, runner, 1)
            runner.set_calculated(
                apply_context_value(
                    parameters[0],
                    None
                    if selected.native_context_hex is None
                    else bytes.fromhex(selected.native_context_hex),
                )
            )
            if clone_uid is not None:
                self._phase(effect, selected, runner, 1)
            return selected
        except Exception:
            self.cancel_prepared(selected)
            raise

    def prepare(self, effect, values, invocation):
        if invocation.native_delayed_uid is not None:
            from .combat_native_delayed_effects import scope_for
            from .combat_trigger_value_modifier import NativeRunnerAmount

            scope = scope_for(effect)
            uid = invocation.native_delayed_uid
            source = self.fight.native_owned_group_effects.get(uid)
            if (
                scope is None
                or scope["mode"] != "delivery"
                or scope["uid"] != uid
                or source is None
                or source.get("effect_class") != 321
                or source.get("native_delayed") is not True
                or source.get("invocation") != vars(invocation)
                or invocation.native_running_uid != uid
            ):
                raise ValueError("Missing actual delayed eZi calculation source")
            from .combat_effect_removal import _identity_fields

            fields = _identity_fields(
                bytes.fromhex(source["payload"]), integer_fields=(1, 3, 4)
            )
            value = ((fields.get(4, 0) + 2**31) % 2**32) - 2**31
            if (
                fields.get(1) != uid
                or fields.get(3) != invocation.reference
                or value != source["native_delayed_value"]
            ):
                raise ValueError("Delayed eZi value differs from owned Qe payload")
            runner = NativeRunnerAmount(uid, 321, rng=self.rng, value=value)
            self.prepared[uid] = runner
            return invocation
        return self._prepare(effect, values, invocation)

    def prepare_delayed(self, effect, values, invocation):
        """Qe.d runs L1/C once before Tu; retain its calculated state reference."""
        selected = self._prepare(effect, values, invocation)
        runner = self.prepared.pop(selected.native_running_uid, None)
        if runner is None:
            raise ValueError("Missing delayed eZi initial calculation")
        return selected, runner.value

    def prepare_activation(self, effect, values, invocation, *, clone_uid):
        return self._prepare(effect, values, invocation, clone_uid=clone_uid)

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)

    def native_eligibility(self, effect, invocation):
        target = self.fight.actors.get(invocation.target_id)
        if target is None or target.hp > 0:
            return True
        from .combat_runner_target_life import runner_target_life_eligible

        return runner_target_life_eligible(
            self.fight, target, effect, invocation=invocation
        )

    def __call__(self, effect, values, invocation):
        try:
            return self._apply(effect, values, invocation)
        finally:
            self.cancel_prepared(invocation)

    def _apply(self, effect, values, invocation):
        parameters = self._parameters(effect, values)
        if not self.native_eligibility(effect, invocation):
            return False
        reference = parameters[0]
        target = self.fight.actors.get(invocation.target_id)
        if target is None:
            return False
        runner = None
        if self.event_lifecycle is not None:
            if invocation.native_running_uid is None:
                invocation = self.prepare(effect, values, invocation)
            runner = self.prepared.pop(invocation.native_running_uid, None)
            if runner is None:
                raise ValueError("Missing prepared native eZi runner")
            self._phase(effect, invocation, runner, 2)
            reference = runner.value
        eligible = tuple(
            entry
            for entry in target.state_ledger.entries
            if entry.reference == reference
            and (
                not (
                    self.catalog["states"][str(reference)]["protected"]
                    if entry.protected is None
                    else entry.protected
                )
                or reference in RULES["protected_whitelist"]
            )
        )
        if not eligible:
            # eZi.c calls fRS to suppress PR only. eZR.a still executes
            # Qe.a -> L3/L4 with the actual runner and produced event mask.
            if runner is not None:
                runner.finish_application()
                for channel in (3, 4):
                    self._phase(effect, invocation, runner, channel)
            return False
        remainder = eligible[-1].level - parameters[1] if len(parameters) == 2 else 0
        # Native casts resulting level to signed short when constructing fyW.
        remainder = ((remainder + 32768) % 65536) - 32768
        if remainder > 0 and reference in RULES["selective_child_states"]:
            raise UnsupportedEffectExecution(
                "Selective native state children require owned beneficial classification"
            )
        if remainder > 0 and not callable(self.reapply_state):
            raise UnsupportedEffectExecution(
                "Reduced state requires audited carrier reapplication"
            )
        for entry in eligible:
            if entry.uid not in self.fight.state_wire_payloads:
                raise UnsupportedEffectExecution(
                    "Missing owned state payload for decurse"
                )
        from .combat_consumable_counter import capture, reconcile

        counter_evidence = capture(
            self.fight, invocation, eligible, reference, parameters
        )
        for entry in eligible:
            payload = bytes.fromhex(self.fight.state_wire_payloads[entry.uid])
            self.state_handler.remove_state_children(entry.uid)
            target.state_ledger.remove(entry.uid)
            del self.fight.state_wire_payloads[entry.uid]
            self.packets.append(
                (
                    13560,
                    running_effect_removal(
                        self.fight.id,
                        self.action_id,
                        effect_class=310,
                        target_id=entry.target_id,
                        uid=entry.uid,
                        running_effect_payload=payload,
                    ),
                )
            )
            self.fight._event(
                "state_removed",
                actor_id=entry.target_id,
                uid=entry.uid,
                reference=entry.reference,
                source="decurse321",
            )
        if remainder > 0:
            previous_uids = {entry.uid for entry in target.state_ledger.entries}
            self.reapply_state(effect, reference, remainder, invocation)
            reconcile(self.fight, counter_evidence, previous_uids, remainder)
        if runner is not None:
            runner.finish_application()
            for channel in (3, 4):
                self._phase(effect, invocation, runner, channel)
        return True
