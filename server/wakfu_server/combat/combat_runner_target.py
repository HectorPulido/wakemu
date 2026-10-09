"""Execution-local Qe.bfs target storage; Qe.f does not alter bft or caster."""
from dataclasses import dataclass, replace
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_runner_cell import bind_runner_cell, runner_cell_invocation


@dataclass
class NativeRunnerTarget:
    uid: int
    family: int
    target_id: int | None


def bind_runner_target(runner, invocation):
    if not isinstance(runner, NativeRunnerAmount):
        raise ValueError("Missing actual native runner target owner")
    bind_runner_cell(runner, invocation)
    existing = getattr(runner, "native_target_binding", None)
    if existing is None:
        runner.native_target_binding = NativeRunnerTarget(
            runner.uid, runner.family, invocation.target_id
        )
    else:
        current_runner_target(runner, invocation.target_id)
    return runner.native_target_binding


def current_runner_target(runner, original_target):
    binding = getattr(runner, "native_target_binding", None)
    if binding is None:
        return original_target
    if (
        not isinstance(binding, NativeRunnerTarget)
        or binding.uid != runner.uid
        or binding.family != runner.family
        or binding.target_id is not None
        and type(binding.target_id) is not int
    ):
        raise ValueError("Invalid live native Qe target binding")
    return binding.target_id


def runner_target_invocation(runner, invocation):
    return runner_cell_invocation(
        runner,
        replace(
            invocation, target_id=current_runner_target(runner, invocation.target_id)
        ),
    )


def redirect_source_runner(fight, invocation, ratio, on_target):
    from .combat_final_modifier import triggering_runner_source
    from .combat_native_actor_lookup import native_actor
    from .combat_state_managers import registered_area_pv

    source = triggering_runner_source()
    if source is None:
        if invocation.native_trigger_context is not None:
            raise ValueError("Missing actual direct-trigger/PS.fLP source runner")
        return False  # Original eZR.J(null) can return null.
    if (
        invocation.native_trigger_context is not None
        and invocation.native_trigger_context.get("uid") != source.uid
    ):
        raise ValueError("Stale native redirection source UID")
    runner = source.runner_modifier
    if (
        not isinstance(runner, NativeRunnerAmount)
        or runner.uid != source.uid
        or runner.family != source.effect_action_id
    ):
        raise ValueError("Missing actual live source runner target/amount authority")
    binding = getattr(runner, "native_target_binding", None)
    if not isinstance(binding, NativeRunnerTarget):
        raise ValueError("Native source runner target consumption is unaudited")
    current_runner_target(runner, source.target_id)
    target = invocation.target_id if on_target else invocation.caster_id
    if (
        target is not None
        and native_actor(fight, target) is None
        and registered_area_pv(fight, target) is None
    ):
        raise ValueError("Missing actual redirection target PV")
    if ratio == -2:
        raise ValueError(
            "Native source n(null) modifier replay requires recalculation authority"
        )
    binding.target_id = target
    if ratio > 0:
        runner.mutate(0, ratio, True)
    return True
