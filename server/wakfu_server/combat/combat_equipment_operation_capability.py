"""Executable, per-operation capability checks for equipment-owned graphs.

This module describes what the current native runner adapters can parse. It does
not make a catalog effect executable by itself: every effect also needs a live
runtime binding and an explicit capability-provider approval for its metadata,
criteria and actor/event context.
"""
from collections.abc import Mapping
from dataclasses import dataclass
import math
from types import MappingProxyType

from .combat_definitions import effect_profile, state_profile
from .combat_effect_groups import decode_group_mode
from .combat_operation_registry import assess_operation


@dataclass(frozen=True)
class OperationCapability:
    status: str
    operation_id: str | None
    family: int | None
    level: int | None
    parameters: tuple = ()
    dependencies: tuple = ()
    requires_context: tuple = ()
    reasons: tuple = ()


@dataclass(frozen=True)
class FactoryOperationRoute:
    """Side-effect-free declaration of a route installed by one runtime factory.

    ``handler_type`` is the route constructor recorded by the production
    factory. The live dispatcher still verifies the instantiated binding at
    initialization; this declaration only permits pre-pin admission.
    """

    family: int
    contract: object
    handler_type: type
    factory: object
    inline: bool = False

    @property
    def handler(self):
        return self.handler_type


@dataclass(frozen=True)
class FactoryOperationRoutes:
    factory: object
    routes: object

    @classmethod
    def create(cls, factory, routes):
        checked = {}
        for family, route in routes.items():
            if (
                type(family) is not int
                or type(route) is not FactoryOperationRoute
                or route.factory is not factory
                or route.family != family
                or not callable(route.handler_type)
            ):
                raise ValueError("Malformed native factory operation route")
            checked[family] = route
        return cls(factory, MappingProxyType(checked))


def _result(
    status,
    family=None,
    level=None,
    *,
    operation_id=None,
    parameters=(),
    dependencies=(),
    requires_context=(),
    reasons=()
):
    return OperationCapability(
        status=status,
        operation_id=operation_id,
        family=family,
        level=level,
        parameters=tuple(parameters),
        dependencies=tuple(dependencies),
        requires_context=tuple(sorted(set(requires_context))),
        reasons=tuple(reasons),
    )


def _binding(runtime_bindings, family):
    if type(runtime_bindings) is FactoryOperationRoutes:
        value = runtime_bindings.routes.get(family)
        if (
            type(value) is FactoryOperationRoute
            and value.factory is runtime_bindings.factory
            and value.family == family
            and callable(value.handler_type)
        ):
            return value
        return None
    if not isinstance(runtime_bindings, Mapping):
        return None
    value = runtime_bindings.get(family, runtime_bindings.get(str(family)))
    if value is None:
        return None
    # Only the runtime factory's frozen route is authority. A placeholder,
    # generic object, or standalone callable supplied by a caller is not.
    from .combat_operation_registry import RuntimeOperationBinding

    if not isinstance(value, RuntimeOperationBinding):
        return None
    if (
        type(value.family) is not int
        or value.family != family
        or not callable(value.handler)
    ):
        return None
    return value


def _provider_accepts(
    provider, *, kind, effect, level, operation_id, requires_context=(), detail=None
):
    if not callable(provider):
        return None
    try:
        result = provider(
            kind=kind,
            effect=effect,
            level=level,
            operation_id=operation_id,
            requires_context=tuple(sorted(set(requires_context))),
            detail=detail,
        )
    except (KeyError, TypeError, ValueError):
        return False
    if result is True:
        return True
    # `None` is an explicit deferral from a typed provider: the descriptor
    # parsed, but this factory cannot attest the required runtime context.
    # Preserve that distinction so legacy-qualified routes can still be
    # considered without treating missing authority as a rejection.
    if result is None:
        return None
    if isinstance(result, Mapping):
        return result.get("status") == "supported" and result.get("accepted") is True
    return False


class NativeFactoryEquipmentCapability:
    """Read-only capability provider tied to a configured production factory.

    It inspects callback availability and statically validates criterion
    syntax. It never invokes targeting, state, stat, RNG, UID, or effect
    handlers. Dynamic branch truth remains the dispatcher’s responsibility.
    """

    def __init__(self, factory, routes):
        from .combat_effect_runtime import NativeEffectRuntimeFactory

        if (
            type(factory) is not NativeEffectRuntimeFactory
            or type(routes) is not FactoryOperationRoutes
            or routes.factory is not factory
        ):
            raise ValueError(
                "Equipment capability requires the configured native factory"
            )
        self.factory = factory
        self.routes = routes

    def _callbacks(self, *names):
        contexts = self.factory.contexts
        return all(callable(getattr(contexts, name, None)) for name in names)

    def __call__(
        self, *, kind, effect, level, operation_id, requires_context=(), detail=None
    ):
        from .combat_operation_registry import RuntimeOperationBinding

        if kind == "criterion":
            if not self._callbacks("condition"):
                return None
            from .combat_conditions import (
                ConditionContext,
                UnknownCondition,
                evaluate_condition,
            )

            expression = (
                detail.get("expression") if isinstance(detail, Mapping) else None
            )
            if not isinstance(expression, str):
                return None
            try:
                evaluate_condition(
                    expression, ConditionContext(actors={}), validate_only=True
                )
            except UnknownCondition:
                return False
            import ast
            from .combat_conditions import _condition_root

            if any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id.lower() == "isprotectorinfight"
                for node in ast.walk(_condition_root(expression))
            ):
                from .combat_protector_fight_condition import (
                    protector_condition_capability,
                )

                return protector_condition_capability(self.factory)
            return True

        if kind == "context":
            # Graph validation passes structured native state profile details
            # separately from the capability name. Read the name only from
            # the explicit requirement tuple so a profile dict can never be
            # mistaken for an authority or used as a mapping key.
            requirement = (
                requires_context[0]
                if len(requires_context) == 1
                else detail
                if isinstance(detail, str)
                else None
            )
            if requirement == "native_existing_primitive_execution":
                from .combat_equipment_native_primitive_capability import (
                    context_capability,
                )

                return context_capability(self.factory, self.routes, effect, detail)
            base = {
                "native_target_selection": self._callbacks(
                    "actor_candidates", "resolution", "native_targets", "cell_eligible"
                ),
                "native_effect_variant_and_flags": True,
                "native_source_guards": self._callbacks("condition"),
                "native_probability_execution": self._callbacks("probability"),
                "native_timing_and_expiration": (
                    isinstance(effect, Mapping)
                    and bool(effect.get("native_timing_definition"))
                ),
                "owned_spellbook_state_level": self._callbacks("state_spell_level"),
                "native_state_level_multiplier": self._callbacks("state_random"),
                "native_state_chance_rng": self._callbacks("state_random"),
                "live_state_resistance": self._callbacks("state", "state_random"),
                "native_state_timer_and_expiration": (
                    isinstance(effect, Mapping)
                    and isinstance(effect.get("native_timing_definition"), Mapping)
                ),
                "native_state_stack_policy": 304 in self.routes.routes,
                "live_target_maximum": self._callbacks("stat"),
                "native_target_life_guard": self._callbacks("stat"),
                "native_group_cell_targets": self._callbacks("group_cells"),
            }
            if isinstance(requirement, str) and requirement.startswith(
                "native_state_clock:"
            ):
                state_clock = requirement.partition(":")[2]
                return state_clock in ("caster", "target") and 304 in self.routes.routes
            if requirement == "native_runner_lifecycle":
                container = (
                    detail.get("retained_container")
                    if isinstance(detail, Mapping)
                    else None
                )
                if container is None:
                    # A stand-alone operation assessment has no source/container
                    # authority yet. Defer it; an explicitly malformed or
                    # unsupported container is a known rejection below.
                    return None
                from .combat_equipment_retained_lifecycle import preflight

                return preflight(self.factory, container)
            if requirement == "owned_state_removal_and_reapplication":
                from .combat_state_decurse import NativeStateDecurseHandler
                from .combat_state_handler import NativeStateHandler

                catalog = self.factory.state_catalog
                if (
                    304 not in self.routes.routes
                    or 321 not in self.routes.routes
                    or not self._callbacks("state", "healing_events", "rounding")
                    or not isinstance(catalog, Mapping)
                    or not isinstance(catalog.get("states"), Mapping)
                    or not isinstance(catalog.get("effects"), Mapping)
                ):
                    return None
                return bool(
                    self.routes.routes[304].handler_type is NativeStateHandler
                    and self.routes.routes[321].handler_type
                    is NativeStateDecurseHandler
                )
            if requirement == "native_dispel_retention":
                from .combat_dispel import NativeDispelHandler

                if (
                    304 not in self.routes.routes
                    or 421 not in self.routes.routes
                    or not self._callbacks("healing_events", "rounding")
                ):
                    return None
                return self.routes.routes[421].handler_type is NativeDispelHandler
            if requirement in (
                "native_world_property_context",
                "native_triggering_final_modifier",
                "native_state_level_group",
            ):
                from .combat_equipment_world_final_state_capability import (
                    context_capability,
                )

                return context_capability(
                    self.factory, self.routes, requirement, effect, level, detail
                )
            if requirement in (
                "native_damage_execution",
                "native_damage_hp_and_rounding",
            ):
                from .combat_equipment_damage_capability import execution_context

                return execution_context(self.factory, self.routes.routes.get(1))
            if requirement == "native_damage_ordering_identity":
                return None  # Identity-bound target ordering is separately proven.
            if requirement in (
                "native_hp_group_pa",
                "native_selected_characteristic_pa",
                "native_characteristic_child_level_domain",
            ) or (
                requirement == "native_dynamic_child_level"
                and effect.get("effect_class") in (913, 1047)
            ):
                from .combat_effect_dispatch import EffectDispatcher
                from .combat_equipment_retained_lifecycle import preflight
                from .combat_group_pv import group_pa, scoped_group_actors

                parsed = detail.get("parsed") if isinstance(detail, Mapping) else None
                container = (
                    detail.get("retained_container")
                    if isinstance(detail, Mapping)
                    else None
                )
                family = effect.get("effect_class")
                route = self.routes.routes.get(family)
                if (
                    not isinstance(parsed, Mapping)
                    or route is None
                    or not route.inline
                    or route.handler_type is not EffectDispatcher
                    or not preflight(self.factory, container)
                    or not callable(group_pa)
                    or not callable(scoped_group_actors)
                ):
                    return None
                if family == 1047:
                    # All currently registered Qq constructors have original
                    # HP/virtual-HP presence or null authority. Other fallback
                    # PA selectors remain unproved, rather than guessed zero.
                    return True if parsed.get("inherited_stat") in (1, 92) else None
                if family == 913:
                    if (
                        parsed.get("stat_id") in (None, 1, 92)
                        or parsed.get("owned_caster_pa") is True
                    ):
                        return True
                    from .combat_equipment_selected_level_domain import (
                        characteristic_context_preflight,
                    )

                    return (
                        True
                        if characteristic_context_preflight(
                            self.factory, container, parsed
                        )
                        else None
                    )
                return None
            if requirement.startswith("native_morph_"):
                from .combat_equipment_morph_capability import preflight
                from .combat_morph_handler import NativeMorphHandler

                parsed = detail.get("parsed") if isinstance(detail, Mapping) else None
                container = (
                    detail.get("retained_container")
                    if isinstance(detail, Mapping)
                    else None
                )
                route = self.routes.routes.get(933)
                if (
                    route is None
                    or route.handler_type is not NativeMorphHandler
                    or not isinstance(parsed, Mapping)
                ):
                    return None
                if requirement in (
                    "native_morph_value_context",
                    "native_morph_actor_level",
                ):
                    # A real phase-1/2 subscriber may replace eWG's profile
                    # value. Original books alone cannot prove that domain.
                    return None
                return preflight(self.factory, container, parsed)
            if (
                requirement == "native_selected_actor_level_domain"
                or requirement == "native_dynamic_child_level"
                and effect.get("effect_class") == 999
                and isinstance(detail, Mapping)
                and isinstance(detail.get("parsed"), Mapping)
                and detail["parsed"].get("child_level_domain") == (-32768, 32767)
            ):
                from .combat_effect_dispatch import EffectDispatcher
                from .combat_equipment_retained_lifecycle import preflight
                from .combat_level_group import runtime_group_level

                route = self.routes.routes.get(999)
                container = (
                    detail.get("retained_container")
                    if isinstance(detail, Mapping)
                    else None
                )
                return bool(
                    route is not None
                    and route.inline
                    and route.handler_type is EffectDispatcher
                    and callable(runtime_group_level)
                    and preflight(self.factory, container)
                )
            if requirement in (
                "native_owned_actor_level",
                "native_dynamic_child_level",
            ):
                from .combat_equipment_dynamic_levels import (
                    CompanionCustodyLevelFacts,
                    OwnerLevelFacts,
                )
                from .combat_effect_dispatch import EffectDispatcher

                facts = (
                    detail.get("owner_level_facts")
                    if isinstance(detail, Mapping)
                    else None
                )
                family = effect.get("effect_class")
                route = self.routes.routes.get(family)
                if (
                    type(facts) not in (OwnerLevelFacts, CompanionCustodyLevelFacts)
                    or route is None
                ):
                    return None
                return bool(
                    route.inline
                    and route.handler_type is EffectDispatcher
                    and family in (999, 913)
                )
            if requirement == "native_cost_group_level":
                from .combat_equipment_cost_level_domain import preflight

                container = (
                    detail.get("retained_container")
                    if isinstance(detail, Mapping)
                    else None
                )
                return True if preflight(self.factory, self.routes, container) else None
            if requirement == "native_trigger_group_level":
                from .combat_effect_dispatch import EffectDispatcher
                from .combat_equipment_retained_lifecycle import preflight
                from .combat_trigger_level_group import runtime_group_level

                route = self.routes.routes.get(1020)
                container = (
                    detail.get("retained_container")
                    if isinstance(detail, Mapping)
                    else None
                )
                if (
                    route is None
                    or not route.inline
                    or route.handler_type is not EffectDispatcher
                    or not callable(runtime_group_level)
                ):
                    return False
                # Every possible signed-short descendant level is separately
                # proved. This verifies the existing replay/retained owner;
                # it does not supply a dummy triggering value at Ready.
                return preflight(self.factory, container)
            if requirement == "native_healing_hp_and_rounding":
                from .combat_healing_handler import NativeHealingHandler

                if 25 not in self.routes.routes or not self._callbacks(
                    "healing", "stat", "rounding"
                ):
                    return None
                return self.routes.routes[25].handler_type is NativeHealingHandler
            if requirement == "native_healing_execution":
                from .combat_healing_handler import NativeHealingHandler

                if 25 not in self.routes.routes or not self._callbacks(
                    "healing", "stat", "rounding"
                ):
                    return None
                if self.routes.routes[25].handler_type is not NativeHealingHandler:
                    return False
                flags = effect.get("native_effect_flags")
                if (
                    not isinstance(flags, (tuple, list))
                    or any(type(flag) is not int for flag in flags)
                    or len(set(flags)) != len(flags)
                ):
                    return False
                if 8 in flags:
                    # The target-order validator is identity-bound to the
                    # native effect reference, which is not part of a profile
                    # alone. Keep this graph unknown until that identity is
                    # carried by the capability input.
                    return None
                allowed = {2, 3, 4, 5, 6, 15, 17, 22, 23, 24, 28, 33, 34}
                if effect.get("effect_class") == 24:
                    allowed.add(
                        29
                    )  # Native LIFE_STEAL_HEAL_EFFECT, not ordinary healing.
                return not (set(flags) - allowed)
            if requirement == "native_trigger_value_lifecycle":
                from .combat_event_replay import NativeEventReplay, NativeEventSource
                from .combat_final_modifier import (
                    final_modifier_source,
                    triggering_runner_source,
                )
                from .combat_trigger_value_handler import NativeTriggerValueHandler
                from .combat_trigger_value_modifier import NativeRunnerAmount, _OWNERS

                route = self.routes.routes.get(430)
                if route is None or route.handler_type is not NativeTriggerValueHandler:
                    return False
                if not self._callbacks("stat"):
                    return None
                # eZL does not manufacture a Qe. It mutates only the current
                # NativeEventReplay source scope; a direct initial execution
                # without such a scope is the native no-op path. Event replay
                # validates actual sources before installing this ContextVar.
                if not (
                    callable(final_modifier_source)
                    and callable(triggering_runner_source)
                    and callable(getattr(NativeEventSource, "validate", None))
                    and callable(getattr(NativeEventReplay, "__call__", None))
                    and isinstance(_OWNERS, Mapping)
                    and bool(_OWNERS)
                    and all(
                        isinstance(row, Mapping) and isinstance(row.get("owner"), str)
                        for row in _OWNERS.values()
                    )
                    and callable(getattr(NativeRunnerAmount, "mutate", None))
                ):
                    return None
                return True
            if requirement == "native_null_execution_context":
                from .combat_stat_handler import NativeStatHandler

                route = self.routes.routes.get(effect.get("effect_class"))
                row = self.factory.characteristic_registry.get(
                    "effects", self.factory.characteristic_registry
                ).get(str(effect.get("effect_class")))
                return bool(
                    isinstance(row, Mapping)
                    and row.get("runner") == "eXE"
                    and route is not None
                    and route.handler_type is NativeStatHandler
                    and self._callbacks("stat")
                )
            if requirement == "native_fight_property_context":
                from .combat_fight_property import (
                    NativeFightPropertyHandler,
                    property_registry,
                )
                from .combat_ordinary_authority import OrdinaryActorAuthority
                from .combat_summon import RegisteredSummonAuthority

                route = self.routes.routes.get(447)
                authority = self.factory.displacement_authority
                if (
                    route is None
                    or route.handler_type is not NativeFightPropertyHandler
                ):
                    return False
                # The handler asks eGj for the actual recipient and performs
                # the property enum lookup at invocation. Pre-pin proof is
                # limited to the exact production actor authority and the
                # published enum row; it never predicts a target or runs the
                # property callback.
                if type(authority) is OrdinaryActorAuthority:
                    property_counts = OrdinaryActorAuthority.property_counts
                elif (
                    type(authority) is RegisteredSummonAuthority
                    and type(authority.ordinary) is OrdinaryActorAuthority
                ):
                    property_counts = RegisteredSummonAuthority.property_counts
                else:
                    return None
                if not callable(property_counts):
                    return None
                try:
                    from .combat_parameters import parameter_value

                    identity = parameter_value(effect.get("parameters", ()), 0, level)
                    row = property_registry().get(identity)
                except (KeyError, OSError, RuntimeError, TypeError, ValueError):
                    return None
                if not isinstance(row, Mapping):
                    return False
                branch = row.get("application_branch")
                if branch == "counter":
                    return True
                if branch in {
                    "set_ap_minimum",
                    "set_mp_minimum",
                    "timeline_recalculate",
                    "insert_extra_turn_current_round",
                    "notify_wp_listeners",
                    "occupancy_and_position",
                }:
                    # These branches need transaction state (resource minima,
                    # timeline cursor/policy, numeric observers, or position
                    # ownership). A callable on the authority proves only
                    # that an executor exists; it does not prove that the
                    # current fight has the exact inputs that executor guards.
                    # Defer until the pre-pin capability carries that typed
                    # transaction context.
                    return None
                return None
            if requirement == "native_group_actor_rebinding":
                from .combat_equipment_selected_level_domain import (
                    group_rebinding_preflight,
                )

                container = (
                    detail.get("retained_container")
                    if isinstance(detail, Mapping)
                    else None
                )
                parsed = detail.get("parsed") if isinstance(detail, Mapping) else None
                return (
                    True
                    if group_rebinding_preflight(
                        self.factory,
                        container,
                        parsed,
                        route=self.routes.routes.get(effect.get("effect_class")),
                    )
                    else None
                )
            # These contexts need live triggering/event/stack authorities that
            # are not exposed as a typed static capability by this factory.
            if requirement in {
                "native_trigger_context",
                "same-action_owned_effect_stack",
            }:
                return None
            if requirement == "native_explicit_self_state_root":
                selector = effect.get("native_target_selector")
                return bool(
                    effect.get("effect_class") == 304
                    and isinstance(selector, Mapping)
                    and selector.get("class") == "fcE"
                    and type(selector.get("mask")) is int
                    and selector["mask"] & 2
                )
            if requirement == "relative_group_candidates":
                return callable(self.factory.relative_group_children)
            if requirement == "native_group_rng":
                authority = self.factory.relative_group_children
                return bool(
                    authority is not None
                    and callable(getattr(authority, "draw_integer", None))
                    and callable(getattr(authority, "draw_fraction", None))
                )
            if requirement == "native_event_scope":
                from .combat_equipment_event_scope import assess

                container = (
                    detail.get("retained_container")
                    if isinstance(detail, Mapping)
                    else None
                )
                return assess(self.factory, effect, container, routes=self.routes)
            return base.get(requirement)

        if kind == "operation":
            route = detail.get("binding") if isinstance(detail, Mapping) else None
            if (
                type(route) is not FactoryOperationRoute
                or route.factory is not self.factory
                or self.routes.routes.get(route.family) is not route
                or route.family != effect.get("effect_class")
            ):
                return False
            if route.inline:
                from .combat_effect_dispatch import EffectDispatcher

                return (
                    route.family in (330, 844, 912, 913, 999, 1020, 1047)
                    and route.handler_type is EffectDispatcher
                )
            return True
        return None


def _effect_metadata(effect, level, *, explicit_self_state_root=False):
    """Validate common native descriptor completeness; return errors/needs."""
    required = (
        "parameter_count",
        "parameters",
        "minimum_level",
        "maximum_level",
        "variant",
        "native_execution_mode",
        "native_definition_class",
        "native_target_selector",
        "area_native",
        "area_class",
        "target_masks",
        "native_effect_flags",
        "native_timing_definition",
        "native_hmi_actions",
        "application_flag",
        "removal_flag",
        "probability_base",
        "probability_per_level",
        "criteria",
    )
    if any(key not in effect for key in required):
        return None, (), "missing native operation metadata"
    raw_parameters = effect["parameters"]
    if (
        type(effect["parameter_count"]) is not int
        or not isinstance(raw_parameters, (tuple, list))
        or len(raw_parameters) % 2
        or effect["parameter_count"] != len(raw_parameters) // 2
        or any(type(value) not in (int, float) for value in raw_parameters)
        or any(
            type(value) is float and not math.isfinite(value)
            for value in raw_parameters
        )
        or type(effect["minimum_level"]) is not int
        or type(effect["maximum_level"]) is not int
        or effect["minimum_level"] > effect["maximum_level"]
        or level < effect["minimum_level"]
        or level > effect["maximum_level"]
        or type(effect["variant"]) is not int
        or type(effect["native_execution_mode"]) is not int
        or not isinstance(effect["native_definition_class"], str)
        or not isinstance(effect["native_target_selector"], Mapping)
        or not isinstance(effect["area_native"], str)
        or not isinstance(effect["area_class"], str)
        or not isinstance(effect["target_masks"], (tuple, list))
        or len(effect["target_masks"]) != 7
        or not isinstance(effect["native_effect_flags"], (tuple, list))
        or any(type(flag) is not int for flag in effect["native_effect_flags"])
        or not isinstance(effect["native_timing_definition"], Mapping)
        or not isinstance(effect["native_hmi_actions"], Mapping)
        or not isinstance(effect["application_flag"], str)
        or not isinstance(effect["removal_flag"], str)
        or not isinstance(effect["criteria"], str)
    ):
        return None, (), "malformed native operation metadata"
    selector = effect["native_target_selector"]
    if (
        not isinstance(selector.get("class"), str)
        or type(selector.get("mask")) is not int
    ):
        return None, (), "malformed native target selector"
    # Reuse the same fcE parser and area adapter used by the live resolver.
    # A selector with its area bit clear does not traverse geometry at runtime;
    # when the bit is set, validate only that the shared geometry adapter can
    # interpret this native area descriptor. Runtime coordinates and actor
    # properties remain invocation data and are never guessed here.
    from .combat_effect_targets import (
        UnsupportedTargetSelector,
        area_offsets,
        native_selector_policy,
    )

    try:
        target_policy = native_selector_policy(effect)
        if target_policy["in_area"]:
            area_offsets(effect, origin=(0, 0), reference=(0, 0), direction=7)
    except (UnsupportedTargetSelector, TypeError, ValueError, KeyError) as error:
        return (
            None,
            (),
            "native target/area adapter cannot parse descriptor: " + str(error),
        )
    masks = effect["target_masks"]
    if any(
        mask is not None
        and (
            not isinstance(mask, (tuple, list))
            or any(type(event) is not int for event in mask)
        )
        for mask in masks
    ):
        return None, (), "malformed native event masks"
    try:
        profile = effect_profile(effect, level)
    except (KeyError, TypeError, ValueError, OverflowError):
        return None, (), "invalid native effect profile"
    requirements = {
        "native_target_selection",
        "native_effect_variant_and_flags",
        "native_source_guards",
    }
    if profile["probability"] != 100:
        requirements.add("native_probability_execution")
    if any(masks[index] for index in range(6)):
        requirements.add("native_event_scope")
    if masks[6]:
        requirements.add("native_event_scope")
    if (
        not math.isfinite(profile["probability"])
        or not 0 <= profile["probability"] <= 100
    ):
        return None, (), "native operation probability is outside [0, 100]"
    timing = effect["native_timing_definition"]
    if any(type(value) not in (bool, int, float) for value in timing.values()):
        return None, (), "malformed native operation timing"
    if any(
        type(value) in (int, float) and not math.isfinite(value)
        for value in timing.values()
    ):
        return None, (), "non-finite native operation timing"
    if timing:
        requirements.add("native_timing_and_expiration")
    if (
        explicit_self_state_root
        and effect.get("effect_class") == 304
        and selector["mask"] & 2
    ):
        requirements.add("native_explicit_self_state_root")
    return profile, tuple(sorted(requirements)), None


def _parse_operation(
    effect, profile, registry, *, owner_level_facts=None, state_catalog=None
):
    family = effect["effect_class"]
    values = tuple(profile["parameters"])
    requirements = set()
    dependencies = []

    if family == 304:
        from .combat_state_parameters import interpret_state_parameters

        try:
            parsed = interpret_state_parameters(values, allow_signed_calculation=True)
        except (TypeError, ValueError) as error:
            return None, (), (), "invalid native state-apply parameters: " + str(error)
        if len(values) in (4, 5):
            requirements.add("owned_spellbook_state_level")
            if len(values) == 5:
                requirements.add("native_state_level_multiplier")
        if parsed["chance_parameter"] not in (-1, 100):
            requirements.update(("live_state_resistance", "native_state_chance_rng"))
        dependencies.append(("state", parsed["reference"], parsed["level"]))
        return parsed, tuple(requirements), tuple(dependencies), None

    if family == 912:
        from .combat_equipment_cost_level_domain import parse

        parsed = parse(effect, profile, effect_level(effect))
        requirements.update(("native_cost_group_level", "native_runner_lifecycle"))
        mode = parsed["group_mode"]
        if mode.actor_rebind:
            requirements.add("native_group_actor_rebinding")
        if mode.relative_probability:
            requirements.update(("relative_group_candidates", "native_group_rng"))
        if not mode.on_target:
            requirements.add("native_group_cell_targets")
        return parsed, tuple(requirements), (), None

    if family == 999:
        from .combat_equipment_dynamic_levels import group_child_levels

        proof = group_child_levels(effect, effect_level(effect), owner_level_facts)
        requirements.update(proof.requires_context)
        requirements.add("native_runner_lifecycle")
        if proof.mode.actor_rebind:
            requirements.add("native_group_actor_rebinding")
        if proof.mode.relative_probability:
            requirements.update(("relative_group_candidates", "native_group_rng"))
        if not proof.mode.on_target:
            requirements.add("native_group_cell_targets")
        parsed = dict(group_mode=proof.mode, child_levels=proof.levels)
        if getattr(proof, "child_level_domain", None) is not None:
            parsed["child_level_domain"] = proof.child_level_domain
        return parsed, tuple(requirements), (), None

    if family in (449, 844, 1093):
        from .combat_equipment_world_final_state_capability import parse

        if family == 844:
            from .combat_native_events import validate_group_registration_flags

            validate_group_registration_flags(
                effect.get("native_effect_flags"),
                active=False,
                constructor=True,
                effect=effect,
                reference=effect.get("_capability_reference"),
            )
        return parse(effect, profile, effect_level(effect), state_catalog=state_catalog)

    if family in (913, 1047):
        if family == 913:
            from .combat_equipment_characteristic_group_parser import (
                parse,
                required_context,
            )
            from .combat_native_events import validate_group_registration_flags

            validate_group_registration_flags(
                effect.get("native_effect_flags"),
                active=False,
                constructor=True,
                effect=effect,
                reference=effect.get("_capability_reference"),
            )
            parsed = parse(effect, profile)
            from .combat_equipment_selected_level_domain import (
                owned_characteristic_domain,
            )

            parsed["owned_caster_pa"] = owned_characteristic_domain(
                parsed, owner_level_facts
            )
            if parsed["owned_caster_pa"]:
                requirements.add("native_owned_actor_level")
            requirements.update(required_context(parsed))
        else:
            from .combat_equipment_hp_group_parser import parse

            parsed = parse(effect, profile, effect_level(effect))
            requirements.update(
                (
                    "native_hp_group_pa",
                    "native_dynamic_child_level",
                    "native_runner_lifecycle",
                )
            )
            mode = parsed["group_mode"]
            if mode.relative_probability:
                requirements.update(("relative_group_candidates", "native_group_rng"))
            if not mode.on_target:
                requirements.add("native_group_cell_targets")
            if mode.actor_rebind:
                requirements.add("native_group_actor_rebinding")
        return parsed, tuple(requirements), (), None

    if family == 933:
        from .combat_equipment_dynamic_levels import UnknownDynamicLevel
        from .combat_equipment_morph_parser import (
            parse,
            required_context,
            MissingNativeMorphProfile,
        )
        from .combat_equipment_morph_capability import (
            dependency_witnesses,
            UnknownMorphDependency,
        )

        try:
            parsed = parse(effect, profile)
            dependencies = tuple(
                ("effect", reference, level)
                for reference, level in dependency_witnesses(parsed)
            )
        except (MissingNativeMorphProfile, UnknownMorphDependency) as missing:
            raise UnknownDynamicLevel(str(missing)) from missing
        return parsed, required_context(parsed), dependencies, None

    if family == 1020:
        from .combat_equipment_trigger_level_domain import trigger_group_mode

        mode = trigger_group_mode(effect, effect_level(effect))
        requirements.update(("native_trigger_group_level", "native_runner_lifecycle"))
        if mode.relative_probability:
            requirements.update(("relative_group_candidates", "native_group_rng"))
        if not mode.on_target:
            requirements.add("native_group_cell_targets")
        if mode.actor_rebind:
            requirements.add("native_group_actor_rebinding")
        return (
            dict(group_mode=mode, child_domain="native_signed_short"),
            tuple(requirements),
            (),
            None,
        )

    if family == 330:
        raw_target = effect["parameters"][4] if len(values) >= 3 else None
        try:
            mode = decode_group_mode(values, raw_target_parameter=raw_target)
        except (TypeError, ValueError) as error:
            return (
                None,
                (),
                (),
                "invalid native ordered-group parameters: " + str(error),
            )
        if mode.relative_probability:
            requirements.update(("relative_group_candidates", "native_group_rng"))
        if not mode.on_target:
            requirements.add("native_group_cell_targets")
        if mode.actor_rebind:
            requirements.add("native_group_actor_rebinding")
        return mode, tuple(requirements), (), None

    if family == 447:
        from .combat_equipment_fight_property_parser import parse

        try:
            parsed = parse(effect, profile, effect_level(effect))
        except (TypeError, ValueError) as error:
            return None, (), (), "invalid native eWt property parameters: " + str(error)
        requirements.update(
            ("native_fight_property_context", "native_runner_lifecycle")
        )
        return parsed, tuple(requirements), (), None

    if family == 430:
        from .combat_equipment_trigger_value_parser import parse

        try:
            parsed = parse(effect, profile, effect_level(effect))
        except (TypeError, ValueError) as error:
            return (
                None,
                (),
                (),
                "invalid native eZL trigger-value parameters: " + str(error),
            )
        requirements.update(
            ("native_trigger_value_lifecycle", "native_runner_lifecycle")
        )
        return parsed, tuple(requirements), (), None

    from .combat_maximum_resource import FAMILIES as MAXIMUM_FAMILIES

    if family in MAXIMUM_FAMILIES:
        if len(effect.get("parameters", ())) != 6 or len(values) != 3:
            return None, (), (), "eWN maximum-resource operation requires three values"
        from .combat_parameters import parameter_value

        amount = parameter_value(effect["parameters"], 0, effect_level(effect))
        apply_current = parameter_value(effect["parameters"], 1, effect_level(effect))
        remove_current = parameter_value(effect["parameters"], 2, effect_level(effect))
        if amount in (-1, -2):
            requirements.add("native_trigger_context")
        return (
            dict(
                stat_id=MAXIMUM_FAMILIES[family][0],
                amount=amount,
                apply_current=apply_current == 1,
                remove_current=remove_current == 1,
            ),
            tuple(requirements),
            (),
            None,
        )

    from .combat_maximum_resource import REDUCTION_FAMILIES

    if family in REDUCTION_FAMILIES:
        return _parse_eWO(effect, profile, stat=REDUCTION_FAMILIES[family])

    # eXE has no stat mutation, but it is a real NativeStatHandler operation:
    # it creates/removes the native retained carrier and carries its execution
    # status through the ordinary lifecycle. Admit only the exact registry
    # contract consumed by null_execution_status; this does not bless other
    # family-400/world-property shapes.
    rows = registry.get("effects", registry) if isinstance(registry, Mapping) else None
    row = rows.get(str(family)) if isinstance(rows, Mapping) else None
    if isinstance(row, Mapping) and row.get("runner") == "eXE":
        contract = row.get("parameter_contract")
        if (
            row.get("effect_class") != family
            or row.get("operation") != "none"
            or row.get("dynamic_stat") is not False
            or row.get("fixed_stat_id") is not None
            or row.get("additional_fields") != {}
            or not isinstance(contract, Mapping)
            or contract.get("current_stat_change") is not False
            or type(contract.get("evaluation_level")) is not int
            or contract.get("evaluation_level") != 0
            or type(contract.get("parameterless_status")) is not int
            or contract.get("parameterless_status") != -1
            or contract.get("parameterless_status_policy") != "preserve_existing_status"
            or contract.get("signed_byte_cast") is not True
            or type(contract.get("status_parameter_index")) is not int
            or contract.get("status_parameter_index") != 0
        ):
            return None, (), (), "incomplete native eXE null-execution contract"
        from .combat_stat_effects import null_execution_status

        try:
            status = null_execution_status(effect.get("parameters", ()))
        except (TypeError, ValueError) as error:
            return None, (), (), "invalid native eXE parameters: " + str(error)
        requirements.update(
            (
                "native_null_execution_context",
                "native_runner_lifecycle",
                "native_target_life_guard",
            )
        )
        return (
            dict(runner="eXE", execution_status=status),
            tuple(requirements),
            (),
            None,
        )

    from .combat_equipment_owned_operation_parsers import (
        FAMILIES as OWNED_PARSER_FAMILIES,
    )

    if family in OWNED_PARSER_FAMILIES:
        from .combat_equipment_owned_operation_parsers import (
            parse as parse_owned_operation,
        )

        return parse_owned_operation(effect, profile, registry)

    from .combat_equipment_native_primitive_capability import (
        FAMILIES as PRIMITIVE_FAMILIES,
    )

    if family in PRIMITIVE_FAMILIES:
        from .combat_equipment_native_primitive_capability import (
            parse as parse_primitive,
        )

        return parse_primitive(effect, profile)

    # Generic registry-backed eWQ/eWR family. The operation registry identifies
    # its fixed or dynamic native stat; stat_parameters remains the sole parser.
    rows = registry.get("effects", registry) if isinstance(registry, Mapping) else None
    row = rows.get(str(family)) if isinstance(rows, Mapping) else None
    if row is None or row.get("runner") not in ("eWQ", "eWR"):
        return None, (), (), "no native eWQ/eWR registry binding"
    parameter_contract = row.get("parameter_contract")
    if not isinstance(parameter_contract, Mapping):
        return None, (), (), "incomplete native eWQ/eWR parameter contract"
    supported_counts = parameter_contract.get("supported_counts")
    fixed_stat = row.get("fixed_stat_id")
    if (
        type(row.get("percent_default")) is not bool
        or row.get("limit_policy") not in ("NORMAL", "RESISTANCE_CAP")
        or type(row.get("zero_initial_amount_rejected")) is not bool
        or not isinstance(supported_counts, (tuple, list))
        or not supported_counts
        or any(
            type(count) is not int or count not in (1, 2, 3)
            for count in supported_counts
        )
        or fixed_stat is not None
        and (type(fixed_stat) is not int or not 0 <= fixed_stat <= 255)
    ):
        return None, (), (), "incomplete native eWQ/eWR parameter contract"
    from .combat_current_stat_parameters import stat_parameters
    from .combat_parameters import parameter_value

    try:
        # Zero is a parse-only stand-in. The context requirement below ensures
        # a real eWv value is supplied when native C uses its -1 sentinel.
        raw_requested = parameter_value(effect["parameters"], 0, effect_level(effect))
        parsed = stat_parameters(
            effect["parameters"],
            effect_level(effect),
            registered_stat_id=row.get("fixed_stat_id"),
            percent_default=row["percent_default"],
            trigger_value=0,
        )
    except (TypeError, ValueError) as error:
        return None, (), (), "invalid native eWQ/eWR parameters: " + str(error)
    if raw_requested == -1:
        requirements.add("native_trigger_context")
    if parsed["percent"]:
        requirements.add("live_target_maximum")
    if row["limit_policy"] == "RESISTANCE_CAP":
        requirements.add("same-action_owned_effect_stack")
    if row["runner"] == "eWR":
        requirements.add("native_target_life_guard")
    parsed.update(
        runner=row["runner"],
        limit_policy=row["limit_policy"],
        zero_initial_amount_rejected=row["zero_initial_amount_rejected"],
    )
    return parsed, tuple(requirements), (), None


def effect_level(effect):
    """Read a validated signed-short level chosen by the graph caller."""
    value = effect.get("_capability_level")
    if type(value) is not int or not -32768 <= value <= 32767:
        raise ValueError("Missing native capability level")
    return value


def _parse_eWO(effect, profile, *, stat):
    from .combat_parameters import parameter_value

    raw = effect.get("parameters")
    if not isinstance(raw, (tuple, list)) or len(raw) not in (2, 4, 6, 8):
        return None, (), (), "eWO reduction requires one to four native values"
    level = effect_level(effect)
    values = [parameter_value(raw, index, level) for index in range(len(raw) // 2)]
    requirements = set()
    amount = values[0]
    if amount == -1:
        requirements.add("native_trigger_context")
    elif amount == -2:
        requirements.add("live_target_current_resource")
    chance = 100 if len(values) < 2 or values[1] < 0 else min(100, max(0, values[1]))
    if chance < 100:
        requirements.add("native_eWO_probability_rng")
    restore = len(values) < 3 or values[2] == 1
    reduce = len(values) < 4 or values[3] == 1
    return (
        dict(
            stat_id=stat,
            amount=amount,
            chance=chance,
            restore_current=restore,
            reduce_current=reduce,
        ),
        tuple(requirements),
        (),
        None,
    )


def validate_effect(
    effect,
    level,
    registry,
    *,
    runtime_bindings,
    criteria_capability,
    explicit_self_state_root=False,
    retained_container=None,
    owner_level_facts=None,
    state_catalog=None,
    effect_reference=None
):
    """Validate one effect's executable operation shape and dependencies.

    `criteria_capability` is a trusted, read-only provider invoked for the
    operation, each parsed criterion, and each required live context. It must
    explicitly return True (or `{status:'supported', accepted:True}`); an
    `assess_operation(...).status == 'conditional'` alone never suffices.
    """
    if not isinstance(effect, Mapping) or type(effect.get("effect_class")) is not int:
        return _result("unknown", reasons=("missing native effect family",))
    family = effect["effect_class"]
    if type(level) is not int or not -32768 <= level <= 32767:
        return _result(
            "unsupported", family, reasons=("invalid native operation level",)
        )
    profile, common_context, error = _effect_metadata(
        effect, level, explicit_self_state_root=explicit_self_state_root
    )
    if error:
        return _result("unknown", family, level, reasons=(error,))
    from .combat_maximum_resource import (
        FAMILIES as MAXIMUM_FAMILIES,
        REDUCTION_FAMILIES,
    )
    from .combat_equipment_owned_operation_parsers import (
        OPERATION_IDS as OWNED_OPERATION_IDS,
    )
    from .combat_equipment_native_primitive_capability import (
        OPERATION_IDS as PRIMITIVE_OPERATION_IDS,
    )

    op_id = (
        "state.apply"
        if family == 304
        else "effect.group"
        if family in (330, 844, 912, 913, 999, 1020, 1047)
        else (
            "world.property"
            if family == 449
            else "effect.triggering_final_modifier"
            if family == 1093
            else "spellbook.morph"
            if family == 933
            else "fight.property"
            if family == 447
            else "effect.triggering_amount"
            if family == 430
            else "resource.maximum"
            if family in MAXIMUM_FAMILIES
            else "resource.maximum_reduction"
            if family in REDUCTION_FAMILIES
            else OWNED_OPERATION_IDS.get(
                family, PRIMITIVE_OPERATION_IDS.get(family, "resource.current")
            )
        )
    )
    descriptor = dict(effect)
    descriptor["_capability_level"] = level
    descriptor["_capability_reference"] = effect_reference
    from .combat_equipment_dynamic_levels import UnknownDynamicLevel

    try:
        parsed, operation_context, dependencies, error = _parse_operation(
            descriptor,
            profile,
            registry,
            owner_level_facts=owner_level_facts,
            state_catalog=state_catalog,
        )
    except UnknownDynamicLevel as missing:
        return _result(
            "unknown", family, level, operation_id=op_id, reasons=(str(missing),)
        )
    except (TypeError, ValueError) as malformed:
        return _result(
            "unsupported",
            family,
            level,
            operation_id=op_id,
            reasons=("invalid native operation parameters: " + str(malformed),),
        )
    if error:
        rows = (
            registry.get("effects", registry) if isinstance(registry, Mapping) else None
        )
        row = rows.get(str(family)) if isinstance(rows, Mapping) else None
        from .combat_maximum_resource import (
            FAMILIES as MAXIMUM_FAMILIES,
            REDUCTION_FAMILIES,
        )
        from .combat_equipment_owned_operation_parsers import (
            FAMILIES as OWNED_PARSER_FAMILIES,
        )
        from .combat_equipment_native_primitive_capability import (
            FAMILIES as PRIMITIVE_FAMILIES,
        )

        owned_parser = family in (
            *MAXIMUM_FAMILIES,
            *REDUCTION_FAMILIES,
            304,
            330,
            447,
            449,
            844,
            912,
            913,
            933,
            999,
            1020,
            1047,
            1093,
            *OWNED_PARSER_FAMILIES,
            *PRIMITIVE_FAMILIES,
        ) or (isinstance(row, Mapping) and row.get("runner") in ("eWQ", "eWR", "eXE"))
        status = "unsupported" if owned_parser else "unknown"
        return _result(status, family, level, operation_id=op_id, reasons=(error,))
    requirements = set(common_context) | set(operation_context)
    binding = _binding(runtime_bindings, family)
    if binding is None:
        return _result(
            "unknown",
            family,
            level,
            operation_id=op_id,
            parameters=(parsed,),
            dependencies=dependencies,
            requires_context=requirements,
            reasons=("actual RuntimeOperationBinding is missing",),
        )
    from .combat_equipment_native_primitive_capability import SET_CURRENT

    set_rows = None
    if family in SET_CURRENT:
        from .combat_set_current_characteristic import set_current_registry

        set_rows = set_current_registry()
    assessment = assess_operation(
        effect,
        characteristic_registry=registry
        if family
        not in (
            *MAXIMUM_FAMILIES,
            *REDUCTION_FAMILIES,
            304,
            330,
            844,
            913,
            933,
            999,
            1020,
            1047,
        )
        else None,
        runtime_bindings={family: binding},
        set_current_registry=set_rows,
    )
    if assessment.status in ("unknown", "unsupported"):
        return _result(
            assessment.status,
            family,
            level,
            operation_id=op_id,
            parameters=(parsed,),
            dependencies=dependencies,
            requires_context=requirements,
            reasons=assessment.reasons,
        )
    # `conditional` establishes only that static family assessment did not
    # reject this shape; the typed parser below and provider still decide.
    criterion_text = effect.get("criteria", "").strip()
    if criterion_text:
        from .combat_local_criteria import parse_local_criterion

        try:
            criterion = parse_local_criterion(criterion_text)
        except (TypeError, ValueError):
            return _result(
                "unsupported",
                family,
                level,
                operation_id=op_id,
                parameters=(parsed,),
                dependencies=dependencies,
                requires_context=requirements,
                reasons=("unsupported native operation criterion syntax",),
            )
        accepted = _provider_accepts(
            criteria_capability,
            kind="criterion",
            effect=effect,
            level=level,
            operation_id=op_id,
            requires_context=requirements,
            detail=dict(expression=criterion_text, parsed=criterion),
        )
        if accepted is None:
            return _result(
                "unknown",
                family,
                level,
                operation_id=op_id,
                parameters=(parsed,),
                dependencies=dependencies,
                requires_context=requirements,
                reasons=("native criteria capability provider is required",),
            )
        if accepted is not True:
            return _result(
                "unsupported",
                family,
                level,
                operation_id=op_id,
                parameters=(parsed,),
                dependencies=dependencies,
                requires_context=requirements,
                reasons=("criteria capability provider rejected native criterion",),
            )
    for requirement in sorted(requirements):
        accepted = _provider_accepts(
            criteria_capability,
            kind="context",
            effect=effect,
            level=level,
            operation_id=op_id,
            requires_context=(requirement,),
            detail=(
                {
                    "requirement": requirement,
                    "retained_container": retained_container,
                    "parsed": parsed,
                }
                if requirement
                in (
                    "native_runner_lifecycle",
                    "native_event_scope",
                    "native_trigger_group_level",
                    "native_cost_group_level",
                    "native_existing_primitive_execution",
                    "native_world_property_context",
                    "native_triggering_final_modifier",
                    "native_state_level_group",
                    "native_hp_group_pa",
                    "native_selected_characteristic_pa",
                    "native_characteristic_child_level_domain",
                    "native_group_actor_rebinding",
                    "native_morph_execution",
                    "native_morph_profile_dependencies",
                    "native_morph_value_context",
                    "native_morph_actor_level",
                )
                or requirement == "native_dynamic_child_level"
                and (
                    family in (913, 1047)
                    or family == 999
                    and isinstance(parsed, Mapping)
                    and parsed.get("child_level_domain") == (-32768, 32767)
                )
                or requirement == "native_selected_actor_level_domain"
                else {"owner_level_facts": owner_level_facts}
                if requirement
                in ("native_owned_actor_level", "native_dynamic_child_level")
                else requirement
            ),
        )
        if accepted is not True:
            return _result(
                "unknown" if accepted is None else "unsupported",
                family,
                level,
                operation_id=op_id,
                parameters=(parsed,),
                dependencies=dependencies,
                requires_context=requirements,
                reasons=(
                    "native operation context is not explicitly supported: "
                    + requirement,
                ),
            )
    accepted = _provider_accepts(
        criteria_capability,
        kind="operation",
        effect=effect,
        level=level,
        operation_id=op_id,
        requires_context=requirements,
        detail=dict(profile=profile, parsed=parsed, binding=binding),
    )
    if accepted is not True:
        return _result(
            "unknown" if accepted is None else "unsupported",
            family,
            level,
            operation_id=op_id,
            parameters=(parsed,),
            dependencies=dependencies,
            requires_context=requirements,
            reasons=("operation capability provider did not accept native operation",),
        )
    return _result(
        "supported",
        family,
        level,
        operation_id=op_id,
        parameters=(parsed,),
        dependencies=dependencies,
        requires_context=requirements,
    )


def validate_graph(
    source,
    compiled,
    registry,
    *,
    runtime_bindings,
    criteria_capability,
    owner_level_facts=None
):
    """Validate a complete source graph without item/state/effect ID allowlists."""
    if (
        not isinstance(source, Mapping)
        or not isinstance(source.get("roots"), (tuple, list))
        or not source["roots"]
        or source.get("attachment_field") not in (None, 24, 32)
    ):
        return _result(
            "unsupported", reasons=("complete owned equipment source is required",)
        )
    omitted = source.get("unplanned_passive_effect_ids")
    if not isinstance(omitted, (tuple, list)) or omitted:
        return _result(
            "unsupported", reasons=("complete passive-root authority is required",)
        )
    effects = getattr(compiled, "effects", None)
    source_states = getattr(compiled, "source_states", None)
    if not isinstance(effects, Mapping) or not isinstance(source_states, Mapping):
        return _result(
            "unknown", reasons=("compiled native effect/state catalogs are required",)
        )
    states = source_states.get("states")
    if not isinstance(states, Mapping):
        return _result("unknown", reasons=("compiled native state catalog is missing",))
    container = source.get("native_retained_container")
    if not isinstance(container, Mapping):
        return _result("unknown", reasons=("native retained container is missing",))
    root_level = container.get("level")
    if type(root_level) is not int or not -32768 <= root_level <= 32767:
        return _result("unknown", reasons=("native retained level is missing",))
    if any(
        type(reference) is not int or reference <= 0 for reference in source["roots"]
    ):
        return _result("unsupported", reasons=("invalid native graph root reference",))
    queue = [(reference, root_level, True, True) for reference in source["roots"]]
    visited, dependencies, requires_context, parsed = set(), [], set(), []
    expanded_states = set()
    while queue:
        reference, level, is_root, caster_is_owner = queue.pop()
        key = (reference, level, is_root, caster_is_owner)
        if key in visited:
            continue
        visited.add(key)
        effect = effects.get(str(reference))
        if not isinstance(effect, Mapping):
            return _result(
                "unknown", reasons=("compiled native effect definition is missing",)
            )
        minimum, maximum = effect.get("minimum_level"), effect.get("maximum_level")
        if (
            type(minimum) is int
            and type(maximum) is int
            and minimum <= maximum
            and not minimum <= level <= maximum
        ):
            # The real dispatcher skips this invocation before profiling or
            # executing children. Still validate its descriptor; a valid native
            # level window is not malformed operation metadata.
            _, _, error = _effect_metadata(effect, min(max(level, minimum), maximum))
            if error:
                return _result("unknown", reasons=(error,))
            continue
        family = effect.get("effect_class")
        # Direct roots use the same typed operation parser, live route binding,
        # provider checks, and pinning as descendants. No root-family allowlist
        # is added here: a root advances only if its actual operation family is
        # installed and every required execution context is explicitly proven.
        validated = validate_effect(
            effect,
            level,
            registry,
            runtime_bindings=runtime_bindings,
            criteria_capability=criteria_capability,
            explicit_self_state_root=is_root and family == 304,
            retained_container=container,
            owner_level_facts=owner_level_facts if caster_is_owner else None,
            effect_reference=reference,
            state_catalog=source_states,
        )
        if validated.status != "supported":
            return validated
        parsed.extend(validated.parameters)
        dependencies.extend(validated.dependencies)
        requires_context.update(validated.requires_context)
        child_levels = (level,)
        child_caster_is_owner = caster_is_owner
        if family == 999:
            child_levels = validated.parameters[0]["child_levels"]
        elif family == 844:
            child_levels = validated.parameters[0].child_levels
            if validated.parameters[0].mode.actor_rebind:
                child_caster_is_owner = False
        elif (
            family in (912, 913, 1047, 1020)
            and validated.parameters[0]["group_mode"].actor_rebind
        ):
            child_caster_is_owner = False
        elif family == 330 and validated.parameters[0].actor_rebind:
            # A rebound parent can replace the caster with a selected target.
            # Owner-level facts must not stand in for that different actor.
            child_caster_is_owner = False
        if family == 999 and validated.parameters[0].get("child_level_domain") == (
            -32768,
            32767,
        ):
            from .combat_equipment_dynamic_levels import UnknownDynamicLevel
            from .combat_equipment_selected_level_domain import child_domain_witnesses

            if validated.parameters[0]["group_mode"].actor_rebind:
                child_caster_is_owner = False
            try:
                witnesses = child_domain_witnesses(
                    effect, effects, source_states, registry=registry
                )
            except (UnknownDynamicLevel, TypeError, ValueError) as missing:
                return _result(
                    "unknown",
                    family,
                    level,
                    operation_id=validated.operation_id,
                    reasons=(str(missing),),
                )
            for child, child_level in witnesses:
                queue.append((child, child_level, False, child_caster_is_owner))
        elif family in (913, 1047):
            from .combat_equipment_dynamic_levels import UnknownDynamicLevel
            from .combat_equipment_hp_group_parser import child_domain_witnesses

            try:
                witnesses = child_domain_witnesses(
                    effect, effects, source_states, registry=registry
                )
            except (UnknownDynamicLevel, TypeError, ValueError) as missing:
                return _result(
                    "unknown",
                    family,
                    level,
                    operation_id=validated.operation_id,
                    reasons=(str(missing),),
                )
            for child, child_level in witnesses:
                queue.append((child, child_level, False, child_caster_is_owner))
        elif family == 912:
            from .combat_equipment_cost_level_domain import child_domain_witnesses
            from .combat_equipment_dynamic_levels import UnknownDynamicLevel

            try:
                witnesses = child_domain_witnesses(
                    effect, effects, source_states, registry=registry, level=level
                )
            except (UnknownDynamicLevel, TypeError, ValueError) as missing:
                return _result(
                    "unknown",
                    family,
                    level,
                    operation_id=validated.operation_id,
                    reasons=(str(missing),),
                )
            for child, child_level in witnesses:
                queue.append((child, child_level, False, child_caster_is_owner))
        elif family == 1020:
            from .combat_equipment_dynamic_levels import UnknownDynamicLevel
            from .combat_equipment_trigger_level_domain import child_domain_witnesses

            try:
                witnesses = child_domain_witnesses(
                    effect, effects, registry=registry, states=source_states
                )
            except (UnknownDynamicLevel, TypeError, ValueError) as missing:
                return _result(
                    "unknown",
                    family,
                    level,
                    operation_id=validated.operation_id,
                    reasons=(str(missing),),
                )
            for child, child_level in witnesses:
                queue.append((child, child_level, False, child_caster_is_owner))
        else:
            for child in effect.get("children", ()):
                for child_level in child_levels:
                    queue.append((child, child_level, False, child_caster_is_owner))
        for dependency_kind, state_reference, state_level, *_ in validated.dependencies:
            if dependency_kind == "effect":
                queue.append((state_reference, state_level, False, caster_is_owner))
                continue
            if dependency_kind != "state":
                continue
            definition = states.get(str(state_reference))
            if not isinstance(definition, Mapping):
                return _result(
                    "unknown",
                    family,
                    level,
                    operation_id=validated.operation_id,
                    reasons=("referenced native state definition is missing",),
                )
            if type(state_level) is int and state_level < 0:
                children = definition.get("effect_ids")
                if not isinstance(children, (tuple, list)) or any(
                    not isinstance(effects.get(str(child)), Mapping)
                    or type(effects[str(child)].get("minimum_level")) is not int
                    or effects[str(child)]["minimum_level"] < 0
                    for child in children
                ):
                    return _result(
                        "unknown",
                        family,
                        level,
                        operation_id=validated.operation_id,
                        reasons=(
                            "Negative state descendants need a complete domain proof",
                        ),
                    )
            maximum = definition.get("maximum_level")
            if type(maximum) is not int or not 0 <= maximum <= 32767:
                return _result(
                    "unsupported",
                    family,
                    level,
                    operation_id=validated.operation_id,
                    reasons=("invalid native state level domain",),
                )
            expansion = (state_reference, caster_is_owner)
            if expansion in expanded_states:
                continue
            expanded_states.add(expansion)
            for current_level in range(maximum + 1):
                try:
                    state = state_profile(source_states, state_reference, current_level)
                except (KeyError, TypeError, ValueError):
                    return _result(
                        "unknown",
                        family,
                        level,
                        operation_id=validated.operation_id,
                        reasons=("native state profile is incomplete",),
                    )
                state_context = set()
                if state["duration"] != -1 or state["realtime_duration"] > 0:
                    state_context.add("native_state_timer_and_expiration")
                if state["clock_actor"] not in ("caster", "target"):
                    return _result(
                        "unsupported",
                        family,
                        level,
                        operation_id=validated.operation_id,
                        reasons=("unknown native state clock actor",),
                    )
                state_context.add("native_state_clock:" + state["clock_actor"])
                state_context.add("native_state_stack_policy")
                for requirement in sorted(state_context):
                    accepted = _provider_accepts(
                        criteria_capability,
                        kind="context",
                        effect=effect,
                        level=level,
                        operation_id=validated.operation_id,
                        requires_context=(requirement,),
                        detail=dict(
                            state=state,
                            state_level=current_level,
                        ),
                    )
                    if accepted is not True:
                        return _result(
                            "unknown" if accepted is None else "unsupported",
                            family,
                            level,
                            operation_id=validated.operation_id,
                            dependencies=dependencies,
                            requires_context=requires_context | state_context,
                            reasons=(
                                "native state context is not explicitly supported: "
                                + requirement,
                            ),
                        )
                requires_context.update(state_context)
                for child in state["effects"]:
                    queue.append((child, current_level, False, caster_is_owner))
    return _result(
        "supported",
        parameters=parsed,
        dependencies=dependencies,
        requires_context=requires_context,
        operation_id="equipment.effect_graph",
    )
