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
    # eYg.bbA compares So(2) with1, it does not validate a0/1 enum.
    # Other values have bbA=false/bbB=false: fresh Qe selection remains
    # blocked by native_group_route, but an already-bound state listener
    # still runs eYg.a's non-bbA (cell) child branch.
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
    # eYg.fPP logs a null bfs and keeps the original actors. Its target
    # iterator subsequently returns without executing children; a cell branch
    # still uses the original caster and selected cells.
    if mode.actor_rebind == 1 and target_id is not None:
        caster_id = target_id
    elif mode.actor_rebind == 2 and target_id is not None:
        if mode.on_target and caster_cell is None:
            raise UnsupportedEffectGroup(
                "Actor swapping requires native caster position"
            )
        caster_id, target_id = target_id, caster_id
        if mode.on_target:
            target_cell = caster_cell
    if mode.on_target and target_id is None:
        return ()
    if not mode.on_target and cell_targets is None:
        raise UnsupportedEffectGroup("Cell class330 requires the native parent area")
    from .combat_random_group import NativeRandomProbabilityExhausted
    import logging

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
            try:
                applied = execute_child(invocation)
            except NativeRandomProbabilityExhausted as error:
                # Original eYg catches child.a exceptions, logs and returns.
                # Keep native random rejection; never swallow authority errors.
                logging.getLogger(__name__).error(
                    "Native ordered group stopped at child %s: %s", child_id, error
                )
                return tuple(calls)
            successes += int(bool(applied))
            calls.append(invocation)
    return tuple(calls)


NATIVE_CELL_GROUP_FAMILIES = frozenset((330, 844, 910, 912, 913, 999, 1020, 1047, 1103))


def native_group_route(effect):
    """Actual inherited eYg.bbA/bbB, including neither-flag values.

    Qe.a fresh targeting does not execute when both flags are false. A bound
    carrier uses Qe.d separately; this helper does not invent its actor scope.
    """
    if effect.get("effect_class") == 1080:
        return "cell"  # eYi inherits literal eWd.bbA=false, bbB=true.
    if effect.get("effect_class") == 341:
        # eXR inherits eYg's owner predicates with So(1): bbA is true for 1,
        # bbB for 0, and both flags are true when the parameter is absent.
        count = effect.get("parameter_count")
        if type(count) is not int or count < 0:
            raise UnsupportedEffectGroup("Missing native eXR parameter count")
        if count < 2:
            return "actors"
        parameters = effect.get("parameters")
        if not isinstance(parameters, (tuple, list)) or len(parameters) < 2:
            raise UnsupportedEffectGroup("Missing raw native eXR So(1)")
        raw = parameters[1]
        if type(raw) not in (int, float):
            raise UnsupportedEffectGroup("Invalid raw native eXR So(1)")
        return "actors" if raw == 1 else "cell" if raw == 0 else "none"
    if effect.get("effect_class") == 349:
        count = effect.get("parameter_count")
        if type(count) is not int or count < 0:
            raise UnsupportedEffectGroup("Missing native eXR parameter count")
        if count < 2:
            return "actors"
        parameters = effect.get("parameters")
        if not isinstance(parameters, (tuple, list)) or len(parameters) < 3:
            raise UnsupportedEffectGroup("Missing raw native eXR So(1)")
        raw = parameters[2]
        return "cell" if raw == 0 else "actors" if raw == 1 else "none"
    if effect.get("effect_class") in (1100, 1101):
        return "actors"  # eYo.bbA=true / bbB=false, independent of parameters.
    if effect.get("effect_class") in (345, 352):
        return "cell"  # eYA.bbA=false / bbB=true, independent of So(2).
    if effect.get("effect_class") not in NATIVE_CELL_GROUP_FAMILIES:
        return None
    count = effect.get("parameter_count")
    if type(count) is not int or count < 0:
        raise UnsupportedEffectGroup("Missing native group parameter count")
    if count < 3:
        return "actors"
    parameters = effect.get("parameters")
    if not isinstance(parameters, (tuple, list)) or len(parameters) < 5:
        raise UnsupportedEffectGroup("Missing raw native group So(2)")
    raw = parameters[4]
    return "cell" if raw == 0 else "actors" if raw == 1 else "none"


def native_group_cell_mode(effect):
    return native_group_route(effect) == "cell"
