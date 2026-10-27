"""Native eYt912 parsing and conservative signed-byte cost level proofs.

Execution remains in combat_cost_level_group. Its source is the actual eWf
paid action descriptor; absent and non-eWf sources inherit the parent level.
No equipment level substitutes for a future action's AP, MP or WP payment.
"""
from collections.abc import Mapping
from itertools import product
import math

from .combat_equipment_dynamic_levels import UnknownDynamicLevel


MAX_EXPLICIT_DOMAIN = 512


def parse(effect, profile, level):
    from .combat_effect_groups import decode_group_mode
    from .combat_level_group import _native_float_parameter
    from .combat_native_events import validate_group_registration_flags

    raw = effect.get("parameters")
    values = profile.get("parameters")
    if (
        effect.get("effect_class") != 912
        or effect.get("parameter_count") != 9
        or not isinstance(raw, (tuple, list))
        or len(raw) != 18
        or any(
            type(value) not in (int, float) or not math.isfinite(value) for value in raw
        )
        or type(level) is not int
        or not -32768 <= level <= 32767
        or not isinstance(values, (tuple, list))
        or len(values) != 9
        or any(type(value) is not int for value in values)
    ):
        raise ValueError("Invalid native eYt912 cost group definition")
    flags = effect.get("native_effect_flags")
    if not isinstance(flags, (tuple, list)):
        raise ValueError("Missing native cost group registration flags")
    validate_group_registration_flags(
        flags,
        active=False,
        constructor=True,
        effect=effect,
        reference=effect.get("_capability_reference"),
    )
    weights = tuple(_native_float_parameter(raw, index, level) for index in (6, 7, 8))
    if any(not math.isfinite(weight) for weight in weights):
        raise UnknownDynamicLevel(
            "Non-finite native eYt cost weights need a separate proof"
        )
    return dict(
        group_mode=decode_group_mode(values[:6], raw_target_parameter=raw[4]),
        cost_weights=weights,
        child_levels=_cost_levels(weights, level),
        cost_source="native_eWf_signed_byte_payment",
    )


def _cost_levels(weights, inherited_level):
    from .combat_cost_level_group import weighted_cost_level
    from .combat_parameters import _float32

    # Sequential native float32 multiplication/addition is monotone in each
    # operand for fixed finite weights. All eight corners bound every signed
    # byte combination, including negative/refunded action amounts. The dense
    # integer interval is an intentional conservative superset, not a guess
    # that a large weighted sum has no gaps.
    corners = []
    for amounts in product((-128, 127), repeat=3):
        products = tuple(
            _float32(_float32(value) * weight)
            for value, weight in zip(amounts, weights)
        )
        partial = _float32(products[0] + products[1])
        total = _float32(partial + products[2])
        if any(not math.isfinite(value) for value in (*products, partial, total)):
            raise UnknownDynamicLevel("Native cost float32 interval overflows")
        corners.append(
            weighted_cost_level(weights, dict(zip(("ap", "mp", "wp"), amounts)))
        )
    active = tuple(index for index, weight in enumerate(weights) if weight != 0)
    if len(active) <= 1:
        # A level-scaled single payment can have a large bounding interval
        # while retaining only 256 actual signed-byte inputs. Evaluate those
        # original inputs, including Java rounding, rather than inventing the
        # intermediate integer costs or increasing the dense-domain bound.
        overrides = set()
        for payment in range(-128, 128) if active else (0,):
            amounts = [0, 0, 0]
            if active:
                amounts[active[0]] = payment
            overrides.add(
                weighted_cost_level(weights, dict(zip(("ap", "mp", "wp"), amounts)))
            )
    else:
        low, high = min(corners), max(corners)
        if high - low + 1 > MAX_EXPLICIT_DOMAIN:
            raise UnknownDynamicLevel(
                "Native cost child domain needs an interval proof"
            )
        overrides = range(low, high + 1)
    levels = {inherited_level}
    for override in overrides:
        # eYt's native -1 sentinel preserves the parent's level before the
        # dynamic child signed-short cast; other negative levels are real.
        if override != -1:
            levels.add(((override + 32768) % 65536) - 32768)
    return tuple(sorted(levels))


def child_domain_witnesses(effect, effects, states=None, *, registry=None, level):
    """Assess every reachable bounded child level, including nested groups.

    The caller must enqueue these witnesses through ordinary typed graph
    validation. Nested subscriptions and changing state/group parameters are
    consequently checked at every level; endpoint equivalence is not assumed.
    """
    from .combat_definitions import effect_profile

    parsed = parse(effect, effect_profile(effect, level), level)
    children = effect.get("children")
    if (
        not isinstance(children, (tuple, list))
        or not children
        or any(type(child) is not int or child <= 0 for child in children)
        or not isinstance(effects, Mapping)
    ):
        raise UnknownDynamicLevel(
            "Missing complete native cost group child definitions"
        )
    witnesses = []
    for child in dict.fromkeys(children):
        definition = effects.get(str(child))
        if not isinstance(definition, Mapping):
            raise UnknownDynamicLevel("Missing compiled native cost group child")
        low, high = definition.get("minimum_level"), definition.get("maximum_level")
        if type(low) is not int or type(high) is not int or low > high:
            raise ValueError("Invalid native cost group child level bounds")
        witnesses.extend(
            (child, value) for value in parsed["child_levels"] if low <= value <= high
        )
    return tuple(witnesses)


def preflight(factory, routes, retained_container):
    from . import combat_effect_runtime
    from .combat_cost_level_group import runtime_group_level
    from .combat_effect_dispatch import EffectDispatcher
    from .combat_equipment_operation_capability import FactoryOperationRoutes
    from .combat_equipment_retained_lifecycle import _native_factory
    from .combat_equipment_retained_lifecycle import preflight as retained

    runtime = _native_factory(factory)
    if (
        runtime is None
        or type(routes) is not FactoryOperationRoutes
        or routes.factory is not runtime
        or not retained(factory, retained_container)
    ):
        return False
    route = routes.routes.get(912)
    return (
        route is not None
        and route.factory is runtime
        and route.family == 912
        and route.inline is True
        and route.handler_type is EffectDispatcher
        and combat_effect_runtime.native_cost_group_level is runtime_group_level
    )
