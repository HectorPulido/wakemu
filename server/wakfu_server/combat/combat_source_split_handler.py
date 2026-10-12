"""eZh401 lifecycle using the same native PR/retention seam as eWK."""
from wakfu_server.combat_redirect_runner import NativeRedirectRunnerHandler
from wakfu_server.combat_parameters import parameter_value
from wakfu_server.combat_value_transfer import apply_context_value
from .combat_source_split import split_actual_source


class NativeSourceSplitRunnerHandler(NativeRedirectRunnerHandler):
    effect_family = 401
    runner_name = "eZh"

    def _calculate(self, effect, invocation):
        if effect["effect_class"] != 401:
            raise ValueError("Wrong native split family")
        count = effect["parameter_count"]
        raw = effect["parameters"]
        ratio = (
            min(parameter_value(raw, 0, invocation.level), 100) if count >= 1 else 100
        )
        cap = parameter_value(raw, 1, invocation.level) if count >= 2 else 0
        ratio = apply_context_value(
            ratio,
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        return ratio, cap

    def _redirect(self, effect, invocation, runner, cap):
        if self.event_lifecycle is None:
            raise ValueError("Actual eZh source definition/lifecycle required")
        definition = self.event_lifecycle.definition(effect, invocation)
        accepted = split_actual_source(
            self.fight,
            invocation,
            runner.value,
            cap,
            caster_code=definition["event_caster_code"],
        )
        if not accepted:
            runner.notification_suppressed = True  # Native fRS/rIW.
        return accepted
