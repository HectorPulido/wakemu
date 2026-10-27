"""Pure native449/844/1093 adapters; context proof never executes an effect.

These are operators over world-property counters, a real triggering Qe, and
first-matching native state level. They are not characteristic-registry rows.
"""
from collections.abc import Mapping
from dataclasses import dataclass


FAMILIES = frozenset((449, 844, 1093))
OPERATION_IDS = {
    449: "world.property",
    844: "effect.group",
    1093: "effect.triggering_final_modifier",
}


@dataclass(frozen=True)
class NativeStateLevelDomain:
    mode: object
    state_id: int
    maximum_state_level: int
    child_levels: tuple


def state_level_domain(effect, profile, parent_level, state_catalog):
    from wakfu_server.combat_effect_groups import decode_group_mode
    from wakfu_server.combat_state_level_group import level_from_state
    from wakfu_server.combat_equipment_dynamic_levels import UnknownDynamicLevel

    parameters = profile["parameters"]
    if not 7 <= len(parameters) <= 10:
        raise ValueError("Unknown native844 parameter count")
    if not isinstance(state_catalog, Mapping) or not isinstance(
        state_catalog.get("states"), Mapping
    ):
        raise UnknownDynamicLevel("Missing immutable native state-level catalog")
    state_id = parameters[6]
    if type(state_id) is not int or state_id <= 0:
        raise ValueError("Invalid native844 state operand")
    definition = state_catalog["states"].get(str(state_id))
    maximum = (
        None if not isinstance(definition, Mapping) else definition.get("maximum_level")
    )
    if type(maximum) is not int or not 0 <= maximum <= 32767:
        raise UnknownDynamicLevel("Missing finite native844 state-level bound")
    mode = decode_group_mode(
        parameters[:6], raw_target_parameter=effect["parameters"][4]
    )
    # Null PV keeps the parent level. A valid PV without the requested state
    # uses the native constant/sentinel branch. Presence covers every level of
    # that native state, never an unrelated 65,536-value integer scan.
    levels = {parent_level, level_from_state(effect, parameters, parent_level, None)}
    levels.update(
        level_from_state(effect, parameters, parent_level, level)
        for level in range(maximum + 1)
    )
    # A state carrier can now retain a signed negative grade. For the native
    # unit affine form, negative inputs either remain ineligible for every
    # child, hit SP(-1), or produce the finite nonnegative prefix below the
    # constant. No scan over the 32,768 negative input grades is necessary.
    from .combat_state_level_group import float_parameter

    factor = (
        float_parameter(effect["parameters"], 8, parent_level)
        if len(parameters) >= 9
        else 1.0
    )
    constant = parameters[9] if len(parameters) >= 10 else 0
    effects = state_catalog.get("effects")
    if (
        factor != 1.0
        or type(constant) is not int
        or not 0 <= constant <= 32767
        or not isinstance(effects, Mapping)
    ):
        raise UnknownDynamicLevel("Signed native844 needs an affine child-domain proof")
    for child_id in effect.get("children", ()):
        child = effects.get(str(child_id))
        if (
            not isinstance(child, Mapping)
            or type(child.get("minimum_level")) is not int
            or child["minimum_level"] < 0
        ):
            raise UnknownDynamicLevel(
                "Signed native844 children need a negative-level proof"
            )
    # Exact float32 integer addition on this bounded interval cannot overflow
    # or wrap positive. SP(-1) uses the already included parent level.
    levels.update(range(constant))
    return NativeStateLevelDomain(mode, state_id, maximum, tuple(sorted(levels)))


def parse(effect, profile, level, *, state_catalog=None):
    """Return parsed operand/domain, required context and dependencies or error."""
    from wakfu_server.combat_equipment_dynamic_levels import UnknownDynamicLevel

    family = effect.get("effect_class")
    try:
        parameters = profile["parameters"]
        if family == 844:
            parsed = state_level_domain(effect, profile, level, state_catalog)
            requirements = {"native_state_level_group", "native_runner_lifecycle"}
            if parsed.mode.relative_probability:
                requirements.update(("relative_group_candidates", "native_group_rng"))
            if not parsed.mode.on_target:
                requirements.add("native_group_cell_targets")
            if parsed.mode.actor_rebind:
                requirements.add("native_group_actor_rebinding")
            return parsed, tuple(sorted(requirements)), (), None
        if family not in (449, 1093) or len(parameters) != 1:
            raise ValueError("Native operator requires one parameter pair")
        value = parameters[0]
        if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
            raise ValueError("Native operator operand must be signed32")
        if family == 449:
            from wakfu_server.combat_world_properties import registry

            row = registry().get(str(value))
            if not isinstance(row, Mapping):
                raise ValueError("Unknown original world-property enum")
            parsed = dict(
                property_id=value, mapped_fight_property=row["fight_property"]
            )
            requirements = ("native_world_property_context", "native_runner_lifecycle")
        else:
            if set(effect.get("native_effect_flags", ())) - {1, 3, 14, 16, 17, 26}:
                raise ValueError("Unaudited native eZJ flags")
            parsed = dict(amount=value)
            requirements = (
                "native_triggering_final_modifier",
                "native_runner_lifecycle",
            )
    except UnknownDynamicLevel:
        raise
    except (KeyError, IndexError, TypeError, ValueError, OverflowError) as error:
        return None, (), (), "invalid native world/final/state operator: " + str(error)
    return parsed, requirements, (), None


def context_capability(factory, routes, requirement, effect, level, detail):
    """Typed pre-pin production wiring, not a live recipient or fake callback."""
    from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
    from wakfu_server.combat_equipment_retained_lifecycle import preflight

    if type(factory) is not NativeEffectRuntimeFactory:
        return None
    family = effect.get("effect_class")
    route = routes.routes.get(family)
    container = (
        detail.get("retained_container") if isinstance(detail, Mapping) else None
    )
    if route is None or not preflight(factory, container):
        return None
    if not callable(getattr(factory.contexts, "stat", None)):
        return None
    if requirement == "native_world_property_context":
        from wakfu_server.combat_world_property_handler import (
            NativeWorldPropertyHandler,
        )
        from wakfu_server.combat_summon import RegisteredSummonAuthority
        from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority
        from wakfu_server.combat_world_properties import registry
        from wakfu_server.combat_parameters import parameter_value

        if family != 449 or route.handler_type is not NativeWorldPropertyHandler:
            return False
        authority = factory.displacement_authority
        if (
            not (
                type(authority) is OrdinaryActorAuthority
                or (
                    type(authority) is RegisteredSummonAuthority
                    and type(authority.ordinary) is OrdinaryActorAuthority
                )
            )
            or not callable(getattr(type(authority), "world_property_counts", None))
            or not callable(getattr(type(authority), "property_counts", None))
        ):
            return None
        return isinstance(
            registry().get(str(parameter_value(effect["parameters"], 0, level))),
            Mapping,
        )
    if requirement == "native_triggering_final_modifier":
        from wakfu_server.combat_final_modifier import (
            NativeFinalModifierHandler,
            final_modifier_source,
            triggering_runner_source,
            FAQ_FAMILIES,
        )

        if family != 1093 or route.handler_type is not NativeFinalModifierHandler:
            return False
        from wakfu_server.combat_native_timing_context import native_definition_timing

        try:
            timing = native_definition_timing(effect, level)
        except (KeyError, TypeError, ValueError):
            return None
        if timing["retained"]:
            from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
            from wakfu_server.combat_stat_handler import NativeStatHandler

            # eZJ has no inverse of faq.SX: the triggering runner owns that
            # accumulator, not the retained recipient. Its stat_id=None row
            # uses ordinary retained ownership and payload-only removal.
            if not callable(
                NativeRetainedRuntime.register_applied_stat
            ) or not callable(NativeStatHandler.remove):
                return None
        # The exact NativeEventReplay scopes its actual Qe with this context
        # manager; the handler checks source UID/family/faq identity at runtime.
        from wakfu_server.combat_event_replay import (
            NativeEventReplay,
            NativeEventSource,
        )

        return bool(
            FAQ_FAMILIES
            and callable(final_modifier_source)
            and callable(triggering_runner_source)
            and callable(getattr(NativeEventSource, "validate", None))
            and callable(getattr(NativeEventReplay, "__call__", None))
        )
    if requirement == "native_state_level_group":
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_state_level_group import runtime_child_level
        from wakfu_server.combat_effect_runtime import native_state_group_level

        parsed = detail.get("parsed") if isinstance(detail, Mapping) else None
        if (
            family != 844
            or not route.inline
            or route.handler_type is not EffectDispatcher
            or native_state_group_level is not runtime_child_level
            or type(parsed) is not NativeStateLevelDomain
        ):
            return None
        states = factory.state_catalog.get("states")
        row = states.get(str(parsed.state_id)) if isinstance(states, Mapping) else None
        return (
            isinstance(row, Mapping)
            and row.get("maximum_level") == parsed.maximum_state_level
        )
    return None
