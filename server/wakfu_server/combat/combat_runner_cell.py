"""Execution-local Qe.bft cell identity, independent of Qe.bfs and caster."""
from dataclasses import dataclass, replace
from .combat_trigger_value_modifier import NativeRunnerAmount


@dataclass
class NativeRunnerCell:
    uid: int
    family: int
    cell: tuple[int, int, int]


def _cell(value):
    if (
        type(value) is not tuple
        or len(value) != 3
        or any(type(part) is not int for part in value)
        or not -(1 << 31) <= value[0] < (1 << 31)
        or not -(1 << 31) <= value[1] < (1 << 31)
        or not -32768 <= value[2] <= 32767
    ):
        raise ValueError("Invalid native Qe cell coordinates")
    return value


def bind_runner_cell(runner, invocation):
    if not isinstance(runner, NativeRunnerAmount):
        raise ValueError("Missing actual native runner cell owner")
    if getattr(runner, "native_cell_binding", None) is None:
        runner.native_cell_binding = NativeRunnerCell(
            runner.uid, runner.family, _cell(invocation.cell)
        )
    current_runner_cell(runner, invocation.cell)
    return runner.native_cell_binding


def current_runner_cell(runner, original):
    binding = getattr(runner, "native_cell_binding", None)
    if binding is None:
        return original
    if (
        not isinstance(binding, NativeRunnerCell)
        or binding.uid != runner.uid
        or binding.family != runner.family
    ):
        raise ValueError("Invalid live native Qe cell binding")
    return _cell(binding.cell)


def runner_cell_invocation(runner, invocation):
    return replace(invocation, cell=current_runner_cell(runner, invocation.cell))


def reflect_source_cell(fight, invocation, authority):
    """eZc.c(source,true): write source Qe.c at its own caster's PV cell."""
    from .combat_final_modifier import triggering_runner_source
    from .combat_native_actor_lookup import native_actor

    source = triggering_runner_source()
    if source is None:
        if invocation.native_trigger_context is not None:
            raise ValueError("Missing native reflection source runner")
        return False
    if (
        invocation.native_trigger_context is not None
        and invocation.native_trigger_context.get("uid") != source.uid
    ):
        raise ValueError("Stale native reflection source UID")
    runner = source.runner_modifier
    if (
        not isinstance(runner, NativeRunnerAmount)
        or runner.uid != source.uid
        or runner.family != source.effect_action_id
    ):
        raise ValueError("Missing live native reflection runner")
    binding = getattr(runner, "native_cell_binding", None)
    if not isinstance(binding, NativeRunnerCell):
        raise ValueError("Native source cell consumption is unaudited")
    current_runner_cell(runner, source.cell)
    caster = native_actor(fight, source.caster_id)
    if caster is None:
        raise ValueError("Native reflection non-fighter/null source PV unsupported")
    provider = getattr(authority, "world_properties", None)
    properties = (
        frozenset(provider(fight, caster))
        if callable(provider)
        else getattr(caster, "native_world_properties", None)
    )
    if not isinstance(properties, frozenset):
        raise ValueError("Missing actual source PV world properties")
    if 43 in properties:
        return False  # Actual eHQ.BOSS guard cancels eZc, not the source runner.
    binding.cell = _cell(tuple(caster.position))
    return True
