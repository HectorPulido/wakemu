"""eYV1030 changes actual bcM affiliation and restores its saved signed byte."""
from dataclasses import replace
from .combat_parameters import parameter_value
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_value_transfer import apply_context_value
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_delivery
from .combat_effect_removal import running_effect_removal


def signed_affiliation(value):
    if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
        raise ValueError("Missing native eYV signed amount")
    return ((value + 128) % 256) - 128


class NativeAffiliationHandler:
    native_runner_value_verified = True

    def __init__(
        self, fight, packets, *, action_id, allocate_uid, context, rng, authority
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.rng, self.authority = context, rng, authority
        self.event_lifecycle, self.prepared = None, {}

    def _context(self, effect, invocation):
        if (
            effect["effect_class"] != 1030
            or self.fight.phase != "active"
            or invocation.caster_id not in self.fight.actors
            or invocation.target_id not in self.fight.actors
        ):
            raise ValueError("Native eYV requires actual fighters")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Missing native eYV execution authority")
        return context

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            masks = effect.get("target_masks")
            if not isinstance(masks, (list, tuple)) or len(masks) != 7:
                raise ValueError("Missing native eYV event masks")
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                _event_ids=tuple(sorted({0, *(masks[6] or ())})),
                runner_modifier=runner,
            )

    def prepare(self, effect, values, invocation):
        self._context(effect, invocation)
        uid = invocation.native_running_uid or self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, 1030, rng=self.rng)
        self._phase(effect, invocation, runner, 1)
        amount = parameter_value(effect["parameters"], 0, invocation.level)
        runner.set_calculated(
            apply_context_value(
                amount,
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
        )
        self.prepared[uid] = runner
        return invocation

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)

    def __call__(self, effect, values, invocation):
        context = self._context(effect, invocation)
        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        runner = self.prepared.pop(invocation.native_running_uid, None)
        if runner is None:
            raise ValueError("Missing prepared native eYV runner")
        if not context.executable:
            return False
        self._phase(effect, invocation, runner, 2)
        context = self._context(effect, invocation)
        if not context.executable or runner.value == -1:
            return False
        actor = self.fight.actors[invocation.target_id]
        if self.authority(self.fight, actor).targeting.get("is_amO") is not True:
            return False
        old = getattr(actor, "native_fight_affiliation", actor.team)
        if type(old) is not int or not -128 <= old < 128:
            raise ValueError("Missing actual saved eYV bcM affiliation")
        actor.native_fight_affiliation = signed_affiliation(runner.value)

        def payload_for(value):
            return owned_effect_payload(
                uid=runner.uid,
                base_uid=invocation.base_uid,
                generic_effect=invocation.reference,
                caster_id=invocation.caster_id,
                target_id=actor.id,
                value=value,
                timing_payload=context.timing_payload,
            )

        payload = payload_for(runner.value)
        if context.retained:
            self.fight.owned_stat_effects[runner.uid] = dict(
                uid=runner.uid,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                effect_class=1030,
                family="eYV",
                stat_id=None,
                actual=runner.value,
                saved_affiliation=old,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        self.packets.append(
            owned_effect_delivery(
                self.fight.id,
                self.action_id,
                effect_class=1030,
                target_id=actor.id,
                uid=runner.uid,
                running_effect_payload=payload,
            )
        )
        if context.retained and self.event_lifecycle is not None:
            self.event_lifecycle.register_applied(effect, invocation, runner.uid)
        runner.finish_application()
        for channel in (3, 4):
            self._phase(effect, invocation, runner, channel)
        if context.retained:
            row = self.fight.owned_stat_effects[runner.uid]
            row["actual"], row["payload"] = (
                runner.value,
                payload_for(runner.value).hex(),
            )
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, runner.value)
        return True


def remove_affiliation(handler, uid):
    row = handler.fight.owned_stat_effects[uid]
    if row["family"] != "eYV":
        raise ValueError("Not an owned native affiliation effect")
    actor = handler.fight.actors[row["target_id"]]
    old = row["saved_affiliation"]
    if type(old) is not int or not -128 <= old < 128:
        raise ValueError("Missing saved native affiliation")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=1030,
        target_id=actor.id,
        uid=uid,
        running_effect_payload=bytes.fromhex(row["payload"]),
    )
    actor.native_fight_affiliation = old
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
