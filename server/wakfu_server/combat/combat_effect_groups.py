"""Verified ordered class330/eYg branch; relative probability remains unknown.

Native eYg.C reads limit/success/relative/transmit/rebind from evaluated
parameters 0/1/3/4/5. bbA reads RAW So(2), unlike those evaluated values.
eYg.a(iterator,eVt) counts calls and successful PT.bas()>0 results separately.
Cell mode expands the parent's native area per child, not a flat child list.
"""
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence


class UnsupportedEffectGroup(ValueError):
    pass


@dataclass(frozen=True)
class EffectGroupMode:
    limit: int = 0
    count_successes: bool = False
    on_target: bool = True
    relative_probability: bool = False
    transmit_target: bool = True
    actor_rebind: int = 0


def decode_group_mode(
    parameters: Sequence[int], *, raw_target_parameter: float | None = None
) -> EffectGroupMode:
    """Input parameters are native eVn.a(index,level,rpA) results."""
    if len(parameters) > 6:
        raise UnsupportedEffectGroup("Unknown class330 parameter variant")
    if len(parameters) >= 3 and raw_target_parameter is None:
        raise UnsupportedEffectGroup("class330 target/cell mode requires raw So(2)")
    if raw_target_parameter is not None and raw_target_parameter not in (0, 1):
        raise UnsupportedEffectGroup("Unknown class330 target mode")
    rebind = ((parameters[5] + 128) % 256) - 128 if len(parameters) >= 6 else 0
    # fPP only recognizes1/2; other native bytes leave actors unchanged.
    return EffectGroupMode(
        limit=parameters[0] if parameters else 0,
        count_successes=len(parameters) >= 2 and parameters[1] == 1,
        on_target=len(parameters) < 3 or raw_target_parameter == 1,
        relative_probability=len(parameters) >= 4 and parameters[3] == 1,
        transmit_target=len(parameters) < 5 or parameters[4] == 1,
        actor_rebind=rebind if rebind in (1, 2) else 0,
    )


@dataclass(frozen=True)
class GroupInvocation:
    child_id: int
    caster_id: int
    target_id: int | None
    cell: tuple[int, int, int]


def execute_ordered_group(
    mode: EffectGroupMode,
    children: Iterable[int],
    *,
    caster_id: int,
    target_id: int | None,
    target_cell: tuple[int, int, int],
    execute_child: Callable[[GroupInvocation], bool],
    cell_targets: Sequence[tuple[int, int, int]] | None = None,
    caster_cell: tuple[int, int, int] | None = None,
) -> tuple[GroupInvocation, ...]:
    """Run native ordered calls; callback returns whether PT.bas()>0.

    Child criteria, level, probability and application remain callback duties.
    In cell mode cell_targets must be the parent's native area after QI.R,
    valid-height and QI.aK filtering; no guessed area expansion is performed.
    Calls count even when the child rejects eligibility or has no success.
    """
    if mode.relative_probability:
        raise UnsupportedEffectGroup(
            "Relative class330 probability requires native candidate targeting and RNG"
        )
    if mode.actor_rebind and target_id is None:
        raise UnsupportedEffectGroup("Actor rebinding requires an authoritative target")
    if mode.actor_rebind == 1:
        caster_id = target_id
    elif mode.actor_rebind == 2:
        if mode.on_target and caster_cell is None:
            raise UnsupportedEffectGroup(
                "Actor swapping requires native caster position"
            )
        caster_id, target_id = target_id, caster_id
        if mode.on_target:
            target_cell = caster_cell
    if mode.on_target and target_id is None:
        raise UnsupportedEffectGroup("Target class330 requires a target actor")
    if not mode.on_target and cell_targets is None:
        raise UnsupportedEffectGroup("Cell class330 requires the native parent area")
    calls = []
    successes = 0
    for child_id in children:
        if (
            mode.limit > 0
            and (successes if mode.count_successes else len(calls)) >= mode.limit
        ):
            break
        positions = (target_cell,) if mode.on_target else cell_targets
        for cell in positions:
            if (
                mode.limit > 0
                and (successes if mode.count_successes else len(calls)) >= mode.limit
            ):
                break
            invocation = GroupInvocation(
                child_id,
                caster_id,
                target_id if mode.on_target and mode.transmit_target else None,
                cell,
            )
            successes += int(bool(execute_child(invocation)))
            calls.append(invocation)
    return tuple(calls)
