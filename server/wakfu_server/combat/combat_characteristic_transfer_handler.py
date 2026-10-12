"""Native eWj1070 retained characteristic observer and wire ownership."""
from dataclasses import replace
from .combat_characteristic_transfer import (
    transfer_parameters,
    attach_transfer,
    detach_transfer,
    transfer_additional_payload,
)
from .combat_stat_handler import StatExecutionContext
from .combat_parameters import parameter_value
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_effect_removal import running_effect_removal
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_value_transfer import apply_context_value


class NativeCharacteristicTransferHandler:
    native_runner_value_verified = True

    def __init__(self, fight, packets, *, action_id, allocate_uid, context, rng):
        self.fight, self.packets, self.action_id = fight, packets, action_id
        self.allocate_uid, self.context, self.rng = allocate_uid, context, rng
        self.event_lifecycle = None
        self.prepared = {}

    def native_eligibility(self, effect, invocation):
        from .combat_summon_initialization import registered_or_detached_actor
        from .combat_runner_target_life import runner_target_life_eligible

        actor = registered_or_detached_actor(self.fight, invocation.target_id)
        if actor is None:
            raise ValueError("Missing actual native eWj target life authority")
        return runner_target_life_eligible(
            self.fight, actor, effect, invocation=invocation
        )

    def _context(self, effect, invocation):
        if effect.get("effect_class") != 1070 or len(
            effect.get("parameters", ())
        ) not in (4, 6, 8, 10, 12):
            raise ValueError("Missing native eWj definition")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
        ):
            raise ValueError("Missing native eWj execution authority")
        return context

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            masks = effect.get("target_masks")
            if not isinstance(masks, (list, tuple)) or len(masks) != 7:
                raise ValueError("Missing native eWj event masks")
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
        self._context(effect, invocation)
        uid = invocation.native_running_uid or self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, 1070, rng=self.rng)
        self._phase(effect, invocation, runner, 1)
        specification = transfer_parameters(effect["parameters"], invocation.level)
        runner.set_calculated(
            apply_context_value(
                parameter_value(effect["parameters"], 0, invocation.level),
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
        )
        self.prepared[uid] = runner, specification
        return invocation

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)

    def __call__(self, effect, values, invocation):
        context = self._context(effect, invocation)
        if not context.executable or not self.native_eligibility(effect, invocation):
            self.cancel_prepared(invocation)
            return False
        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        item = self.prepared.pop(invocation.native_running_uid, None)
        if item is None:
            raise ValueError("Missing prepared native eWj runner")
        runner, specification = item
        self._phase(effect, invocation, runner, 2)
        context = self._context(effect, invocation)
        if not context.executable:
            return False
        specification = dict(
            specification, source_stat=((runner.value + 128) % 256) - 128
        )
        actor = self.fight.actors.get(invocation.target_id)
        if actor is None:
            raise ValueError("Missing actual native eWj target PA authority")
        if not context.retained:
            raise ValueError("Native eWj requires retained listener ownership")
        source_id, destination_id = (
            (invocation.caster_id, invocation.target_id)
            if specification["caster_to_target"]
            else (invocation.target_id, invocation.caster_id)
        )
        listener = attach_transfer(
            self.fight,
            uid=runner.uid,
            source_id=source_id,
            destination_id=destination_id,
            caster_id=invocation.caster_id,
            specification=specification,
        )
        runner.finish_application()
        payload = owned_effect_payload(
            uid=runner.uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=actor.id,
            value=runner.value,
            timing_payload=context.timing_payload,
        ) + transfer_additional_payload(specification)
        if context.retained:
            self.fight.owned_stat_effects[runner.uid] = dict(
                uid=runner.uid,
                effect_class=1070,
                family="eWj",
                stat_id=None,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                actual=runner.value,
                native_transfer_uid=listener["uid"],
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        self.packets.append(
            (
                13497,
                owned_effect_application(
                    self.fight.id,
                    self.action_id,
                    effect_class=1070,
                    target_id=actor.id,
                    uid=runner.uid,
                    running_effect_payload=payload,
                ),
            )
        )
        if context.retained and self.event_lifecycle is not None:
            register = getattr(self.event_lifecycle, "register_applied", None)
            if callable(register):
                register(effect, invocation, runner.uid)
        for channel in (3, 4):
            self._phase(effect, invocation, runner, channel)
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, runner.value)
        return True


def remove_characteristic_transfer(handler, uid):
    row = handler.fight.owned_stat_effects[uid]
    if row.get("effect_class") != 1070 or row.get("family") != "eWj":
        raise ValueError("Missing retained native eWj identity")
    detach_transfer(handler.fight, uid)
    handler.packets.append(
        (
            13560,
            running_effect_removal(
                handler.fight.id,
                handler.action_id,
                effect_class=1070,
                target_id=row["target_id"],
                uid=uid,
                running_effect_payload=bytes.fromhex(row["payload"]),
            ),
        )
    )
    del handler.fight.owned_stat_effects[uid]
