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
        if effect["effect_class"] != 321:
            raise UnsupportedEffectExecution(
                "Only native state decurse321 is supported"
            )
        parameters = values["parameters"]
        if len(parameters) not in (1, 2) or any(type(v) is not int for v in parameters):
            raise UnsupportedEffectExecution("Unsupported native decurse parameters")
        return parameters

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
        return self._prepare(effect, values, invocation)

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
            self.reapply_state(effect, reference, remainder, invocation)
        if runner is not None:
            runner.finish_application()
            for channel in (3, 4):
                self._phase(effect, invocation, runner, channel)
        return True
