"""Ordered fcj eligibility, without resource, deck or effect execution checks.

Hooks consume actual native snapshots. A missing hook is unknown, never an
accepted empty cell or a null fighter. Native fyJ names are retained so the
caller can distinguish rejection from missing authority.
"""
from dataclasses import dataclass

from wakfu_server.combat_casting_range import int32
from wakfu_server.combat_conditions import UnknownCondition


def _call(hooks, name, *args):
    callback = getattr(hooks, name, None)
    if not callable(callback):
        raise UnknownCondition("Missing native casting authority: " + name)
    return callback(*args)


def _boolean(hooks, name, *args):
    value = _call(hooks, name, *args)
    if type(value) is not bool:
        raise UnknownCondition("Invalid native casting boolean: " + name)
    return value


def _java_abs(value):
    return value if value == -(1 << 31) else abs(value)


def native_casting_distance(source_xy, target_xy):
    """fcj range overload: Java int subtraction, abs and sum all wrap."""
    for position in (source_xy, target_xy):
        if (
            not isinstance(position, (tuple, list))
            or len(position) != 2
            or any(
                type(v) is not int or not -(1 << 31) <= v < (1 << 31) for v in position
            )
        ):
            raise UnknownCondition("Missing native casting range coordinates")
    return int32(sum(_java_abs(int32(t - s)) for s, t in zip(source_xy, target_xy)))


def native_pv_cell_distance(position, radius, cell):
    """ala.a(alb,x,y): signed radius subtraction and clipped axis distances."""
    if type(radius) is not int or not -128 <= radius <= 127:
        raise UnknownCondition("Missing actual native casting PV radius")
    # Validate XY with the same native coordinate bounds.
    native_casting_distance(position[:2], cell[:2])
    return int32(
        sum(
            max(0, int32(_java_abs(int32(s - t)) - radius))
            for s, t in zip(position[:2], cell[:2])
        )
    )


@dataclass(frozen=True)
class NativeCastingFlags:
    check_turn: bool = True
    evaluate_exempt_fighters: bool = True
    line_of_sight: bool = False
    free_cell: bool = False
    forbid_qi_p: bool = False
    allow_self: bool = False

    def __post_init__(self):
        if any(type(value) is not bool for value in self.__dict__.values()):
            raise ValueError("Native casting flags must be selected booleans")


def _native_casting_eligibility(hooks, flags):
    """Return fcj's fyJ result, preserving its ordered short circuits.

    The hooks object owns the actual caster/container/cell/QI identities.
    resolve_target_fighter must bind fbX.dC's result, including proven null;
    criterion_objects must preserve fbX.a's native order. roots must preserve
    eVo.iterator order. No hook may execute an effect or recursively prepare
    a cast. root_has_shape/root_has_selector describe native null presence.
    """
    if not isinstance(flags, NativeCastingFlags):
        raise ValueError("Missing selected native casting flags")
    if not _boolean(hooks, "container_present"):
        return "twF"
    if flags.check_turn and not _boolean(hooks, "current_turn_matches"):
        return "twY"
    minimum, maximum = _call(hooks, "effective_range")
    if any(type(value) is not int for value in (minimum, maximum)):
        raise UnknownCondition("Invalid native casting effective range")
    if minimum > maximum:
        return "twI"
    if _boolean(hooks, "cell_and_qi_present"):
        _call(hooks, "resolve_target_fighter")
        if callable(getattr(hooks, "range_accepts", None)):
            in_range = _boolean(
                hooks, "range_accepts", minimum, maximum, flags.allow_self
            )
        else:
            distance = _call(hooks, "range_distance")
            if type(distance) is not int:
                raise UnknownCondition("Invalid native casting distance")
            in_range = (
                minimum <= distance <= maximum or distance == 0 and flags.allow_self
            )
        if not in_range:
            return "twI"
        if not _boolean(hooks, "qi_in_bounds"):
            return "twH"
        if flags.forbid_qi_p and _boolean(hooks, "qi_p"):
            return "twH"
        if not _boolean(hooks, "qi_r"):
            return "twH"
        geometry = "native_los" if flags.line_of_sight else "qi_j"
        if not _boolean(hooks, geometry):
            return "twG"
        criterion_present = _boolean(hooks, "criterion_present")
        if criterion_present and not _boolean(hooks, "criterion_cell"):
            return "twV"
        objects = _call(hooks, "criterion_objects")
        if not isinstance(objects, (tuple, list)):
            raise UnknownCondition("Missing ordered casting criterion objects")
        if criterion_present and objects:
            accepted = False
            for obj in objects:
                if not flags.evaluate_exempt_fighters and _boolean(
                    hooks, "criterion_fighter_exempt", obj
                ):
                    accepted = True
                    break
                if _boolean(hooks, "criterion_object", obj):
                    accepted = True
                    break
            if not accepted:
                return "twV"
        roots = _call(hooks, "roots")
        if not isinstance(roots, (tuple, list)):
            raise UnknownCondition("Missing ordered native casting roots")
        for root in roots:
            if (
                _boolean(hooks, "root_has_shape", root)
                and _boolean(hooks, "root_has_selector", root)
                and not _boolean(hooks, "root_collision_clear", root)
            ):
                return "twX"
        if flags.free_cell and _boolean(hooks, "qi_g"):
            return "twT"
        if _boolean(hooks, "target_fighter_present"):
            if _boolean(hooks, "target_sd_r_other"):
                return "twV"
            if _boolean(hooks, "caster_sd_g_lower_level"):
                return "twV"
            accepted = False
            # fcj creates a second iterator; selector acceptance has no shape
            # requirement and a null selector accepts immediately.
            for root in roots:
                if not _boolean(hooks, "root_has_selector", root):
                    accepted = True
                    break
                if _boolean(hooks, "root_selector_accepts", root):
                    accepted = True
            if not accepted:
                return "twE"
    elif _boolean(hooks, "criterion_present") and not _boolean(hooks, "criterion_cell"):
        return "twV"
    return "twD"


def native_casting_eligibility(hooks, flags, *, trace=None):
    """Optionally capture consumed native hooks, without replaying a query."""
    if trace is None:
        return _native_casting_eligibility(hooks, flags)
    if not isinstance(trace, list):
        raise ValueError("Native casting trace must be a list")

    class TracedHooks:
        def __getattr__(self, name):
            callback = getattr(hooks, name, None)
            if not callable(callback):
                return callback

            def consumed(*args):
                row = dict(stage=name, arguments=list(args))
                trace.append(row)
                try:
                    value = callback(*args)
                except ValueError as error:
                    row["error"] = str(error)
                    raise
                row["value"] = value
                return value

            return consumed

    try:
        result = _native_casting_eligibility(TracedHooks(), flags)
    except ValueError as error:
        error.native_casting_trace = trace
        raise
    trace.append(dict(stage="result", value=result))
    return result


def native_use_gate_effect(eligibility_query, alignment_query):
    """ePI evaluates both calls, then returns !(fcj == twD && alignment)."""
    if not callable(eligibility_query) or not callable(alignment_query):
        raise UnknownCondition("Missing native UseGateEffect casting queries")
    result = eligibility_query()
    alignment = alignment_query()
    if (
        result
        not in {"twD", "twE", "twF", "twG", "twH", "twI", "twT", "twV", "twX", "twY"}
        or type(alignment) is not bool
    ):
        raise UnknownCondition("Invalid native UseGateEffect casting results")
    return not (result == "twD" and alignment)
