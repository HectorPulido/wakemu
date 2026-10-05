"""eZL430 modifies its triggering Qe and suppresses its own PR notification."""
from .combat_parameters import parameter_value
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload
from .combat_trigger_value_modifier import mutate_triggering_runner
from .combat_value_transfer import apply_context_value


class NativeTriggerValueHandler:
    def __init__(self, fight, *, allocate_uid, context):
        self.fight, self.allocate_uid, self.context = fight, allocate_uid, context

    def __call__(self, effect, values, invocation):
        if (
            effect["effect_class"] != 430
            or self.fight.phase != "active"
            or invocation.caster_id not in self.fight.actors
            or invocation.target_id not in self.fight.actors
        ):
            raise ValueError("Native eZL requires authoritative ordinary actors")
        raw = effect["parameters"]
        if len(raw) < 6 or len(raw) % 2:
            raise ValueError("Missing native eZL parameter pairs")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Missing native eZL execution/timing authority")
        if not context.executable:
            return False
        mode = parameter_value(raw, 0, invocation.level)
        value = apply_context_value(
            parameter_value(raw, 1, invocation.level),
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        replace = parameter_value(raw, 2, invocation.level) != 0
        mutate_triggering_runner(mode, value, replace)
        uid = invocation.native_running_uid or self.allocate_uid()
        if context.retained and invocation.native_running_uid is None:
            payload = owned_effect_payload(
                uid=uid,
                base_uid=invocation.base_uid,
                generic_effect=invocation.reference,
                caster_id=invocation.caster_id,
                target_id=invocation.target_id,
                value=value,
                timing_payload=context.timing_payload,
            )
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=invocation.target_id,
                caster_id=invocation.caster_id,
                effect_class=430,
                family="eZL",
                stat_id=None,
                actual=value,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        # eZL.c always mu(true): Qe/PT continues, PR.b/d is suppressed.
        return True
