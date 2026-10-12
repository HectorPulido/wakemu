"""Native eWK1000 redirects an actual triggering Qe, without changing bft."""
from dataclasses import replace
from .combat_parameters import parameter_value
from .combat_stat_handler import StatExecutionContext
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_runner_target import (
    bind_runner_target,
    runner_target_invocation,
    redirect_source_runner,
)
from .combat_value_transfer import apply_context_value
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_effect_removal import running_effect_removal
from .combat_runner_callbacks import notify_runner_value


class NativeRedirectRunnerHandler:
    native_runner_value_verified = True
    effect_family = 1000
    runner_name = "eWK"

    def _redirect(self, effect, invocation, runner, on_target):
        return redirect_source_runner(self.fight, invocation, runner.value, on_target)

    def __init__(self, fight, packets, *, action_id, allocate_uid, context, rng):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context, self.rng = (
            action_id,
            allocate_uid,
            context,
            rng,
        )
        self.event_lifecycle = None
        self.prepared, self.runners = {}, {}

    def _events(self, effect):
        masks = effect.get("target_masks")
        if not isinstance(masks, (list, tuple)) or len(masks) < 7:
            raise ValueError("Missing native eWK event masks")
        return tuple(sorted({0, *(masks[6] or ())}))

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                _event_ids=self._events(effect),
                runner_modifier=runner,
                _nullable_target=True,
            )

    def _calculate(self, effect, invocation):
        if effect.get("effect_class") != 1000:
            raise ValueError("Wrong native source redirection family")
        count = effect["parameter_count"]
        raw = effect["parameters"]
        ratio = parameter_value(raw, 0, invocation.level) if count >= 1 else -1
        on_target = count >= 2 and parameter_value(raw, 1, invocation.level) == 1
        ratio = apply_context_value(
            ratio,
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        return ratio, on_target

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)
        self.runners.pop(invocation.native_running_uid, None)

    def prepare(self, effect, values, invocation):
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, self.effect_family, rng=self.rng)
        bind_runner_target(runner, invocation)
        self.runners[uid] = runner
        try:
            self._phase(effect, invocation, runner, 1)
            invocation = runner_target_invocation(runner, invocation)
            ratio, on_target = self._calculate(effect, invocation)
            runner.set_calculated(ratio)
            self.prepared[uid] = on_target
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def __call__(self, effect, values, invocation):
        if invocation.native_running_uid is None:
            invocation = replace(invocation, native_running_uid=self.allocate_uid())
        try:
            return self._apply(effect, invocation)
        finally:
            self.cancel_prepared(invocation)

    def _apply(self, effect, invocation):
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
            or type(ctx.retained) is not bool
            or type(ctx.executable) is not bool
        ):
            raise ValueError("Missing native eWK execution/retention guards")
        if not ctx.executable:
            return False
        uid = invocation.native_running_uid or self.allocate_uid()
        runner = self.runners.get(uid)
        if runner is None:
            ratio, on_target = self._calculate(effect, invocation)
            runner = NativeRunnerAmount(
                uid, self.effect_family, rng=self.rng, value=ratio
            )
            bind_runner_target(runner, invocation)
            self.runners[uid] = runner
            self.prepared[uid] = on_target
            self._phase(effect, invocation, runner, 1)
        on_target = self.prepared[uid]
        invocation = runner_target_invocation(runner, invocation)
        self._phase(effect, invocation, runner, 2)
        invocation = runner_target_invocation(runner, invocation)
        self._redirect(effect, invocation, runner, on_target)
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=invocation.target_id,
            value=runner.value,
            timing_payload=ctx.timing_payload,
        )
        if ctx.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                family=self.runner_name,
                effect_class=self.effect_family,
                target_id=invocation.target_id,
                caster_id=invocation.caster_id,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
            )
        if not runner.notification_suppressed:
            self.packets.append(
                (
                    13497,
                    owned_effect_application(
                        self.fight.id,
                        self.action_id,
                        effect_class=self.effect_family,
                        target_id=invocation.target_id,
                        uid=uid,
                        running_effect_payload=payload,
                    ),
                )
            )
        if ctx.retained and self.event_lifecycle is not None:
            self.event_lifecycle.register_applied(effect, invocation, uid)
        runner.finish_application()
        for channel in (3, 4):
            self._phase(effect, invocation, runner, channel)
        notify_runner_value(invocation, runner.value)
        return True


def remove_redirect_runner(handler, uid):
    row = handler.fight.owned_stat_effects[uid]
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=row["effect_class"],
        target_id=row["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(row["payload"]),
    )
    # Native eWK has no inverse source retarget: inherited bbR does not revert it.
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
