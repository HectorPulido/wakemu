"""Native-PV operands required by guaranteed direct NPC point consumption.

This is explicit Wakemu decision admission, not recovered original server AI.
The producer is deliberately bounded. Optional, delayed, grouped and area-wide
operations remain subject to their original native execution rules.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RequiredRecipientRequirement:
    effect_reference: int
    level: int
    minimum_count: int = 1
    provenance: str = "wakemu.npc.direct-point-consumption-operand-v1"
    source_effects: object = field(default=None, repr=False, compare=False)


def required_recipient_requirements(
    plan, roots, effects, *, direct_target_policies=None
):
    """Describe mandatory PV operands, never infer dependencies from siblings."""
    from .combat_effect_targets import native_selector_policy, area_offsets
    from .combat_kill import kill_parameters
    from .combat_native_timing_context import native_definition_timing
    from .combat_effect_resolver import variant_accepts

    level = plan.get("evaluation_level")
    if (
        type(level) is not int
        or effects is None
        or not isinstance(roots, (tuple, list))
    ):
        return ()
    result = []
    for reference in roots:
        effect = effects.get(str(reference))
        if (
            not isinstance(effect, dict)
            or effect.get("effect_class") != 28
            or effect.get("children")
            or effect.get("native_active_effect") is False
            or effect.get("application_flag") != "NONE"
            or effect.get("removal_flag") != "NONE"
            or type(effect.get("criteria")) is not str
            or effect["criteria"].strip()
            or effect.get("probability_base") != 100
            or effect.get("probability_per_level") != 0
            or type(effect.get("minimum_level")) is not int
            or type(effect.get("maximum_level")) is not int
            or not effect["minimum_level"] <= level <= effect["maximum_level"]
            or (effect.get("area_class"), effect.get("area_native")) != ("anD", "point")
            or effect.get("native_execution_mode") != 2
        ):
            continue
        masks = effect.get("target_masks")
        if not isinstance(masks, (tuple, list)) or len(masks) != 7 or any(masks):
            continue
        try:
            # Both authoritative NPC and oracle factories use critical=False.
            # A dormant critical consumer must not constrain the normal cast.
            if not variant_accepts(effect, "EFFECTS_ONLY"):
                continue
            if direct_target_policies is None:
                from .combat_direct_target import native_direct_target_policies

                direct_target_policies = native_direct_target_policies()
            direct = direct_target_policies.get(str(reference))
            if (
                not isinstance(direct, (tuple, list))
                or len(direct) != 3
                or direct[0] != 28
                or any(type(value) is not bool for value in direct[1:])
                or direct[2] is not False
            ):
                # A caster-bound direct route needs its own operand producer;
                # do not substitute point selection for the native binding.
                continue
            policy = native_selector_policy(effect)
            if not policy["in_area"] or not policy["relations"]:
                continue
            if area_offsets(effect) != {(0, 0)}:
                continue
            timing = native_definition_timing(effect, level)
            if timing["delay"] or timing["duration"] != 0:
                continue
            # The returned bit controls permanent KO handling, not whether
            # eXc assigns HP to its minimum. Validate every supported count.
            kill_parameters(effect, level)
        except (ValueError, KeyError, TypeError, OverflowError):
            # Unknown shapes need source review; never invent a new mandatory
            # operand for another native branch merely to make it executable.
            continue
        result.append(
            RequiredRecipientRequirement(reference, level, source_effects=effects)
        )
    return tuple(result)


def selected_native_recipients(fight, plan, factory, reference, level):
    """Use exactly the normal resolver's candidate and native-PV producers."""
    from .combat_effect_dispatch import EffectInvocation
    from .combat_effect_targets import (
        select_native_effect_targets,
        select_effect_targets,
        native_selector_policy,
    )
    from .combat_effect_area_targets import (
        area_targets,
        area_target_context,
        retained_area_source_target,
    )
    from .combat_native_actor_lookup import native_actor

    effect = factory.effects[str(reference)]
    invocation = EffectInvocation(
        reference, level, plan["actor_id"], plan.get("target_id"), plan["target"]
    )
    contexts = factory.contexts
    candidates = tuple(
        actor
        for actor in contexts.actor_candidates(fight, plan, effect, invocation)
        if not getattr(actor, "pve_withdrawn", False)
    )
    if any(native_actor(fight, actor.id) is not actor for actor in candidates):
        raise ValueError("NPC operand candidates differ from their native preview")
    areas = area_targets(fight)
    population = candidates + areas
    identities = tuple(actor.id for actor in population)
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate runtime actor identities")
    from .combat_runtime_adapter import native_point_target_projection

    projection = native_point_target_projection(contexts.native_targets)
    policy = native_selector_policy(effect)
    if (
        projection is None
        or not policy["in_area"]
        or effect.get("native_target_selector") is None
        or (effect.get("area_class"), effect.get("area_native")) != ("anD", "point")
    ):
        native = contexts.native_targets(fight, plan, effect, invocation)
    else:
        selected_geometry = select_effect_targets(
            effect,
            fight.actors[plan["actor_id"]],
            plan["target"],
            population,
            relations=policy["relations"],
            native_radius=True,
            available=lambda _actor: True,
        )
        native = projection(fight, plan, effect, invocation, selected_geometry)
    source = retained_area_source_target(fight, invocation.caster_id)
    if source is not None:
        native = {**native, source.id: area_target_context(source)}
    native = {**native, **{area.id: area_target_context(area) for area in areas}}
    return select_native_effect_targets(
        effect,
        fight.actors[plan["actor_id"]],
        plan["target"],
        population,
        native_context=native,
    )


def validate_required_recipients(fight, plan, factory, requirements):
    """Require operands, preserving native corpse and no-HP-area eligibility.

    Call on the existing private preview: anchored area queries may refresh
    geometry. No root, probability draw, stat mutation or payment runs here.
    """
    selections = []
    for requirement in requirements:
        if (
            type(requirement) is not RequiredRecipientRequirement
            or requirement.source_effects is not factory.effects
            or requirement.level != plan["evaluation_level"]
            or type(requirement.minimum_count) is not int
            or requirement.minimum_count < 1
        ):
            raise ValueError("Invalid native NPC operand admission requirement")
        selected = selected_native_recipients(
            fight, plan, factory, requirement.effect_reference, requirement.level
        )
        identities = tuple(actor.id for actor in selected)
        if len(identities) < requirement.minimum_count:
            raise ValueError("NPC point consumption requires a native recipient")
        selections.append((requirement.effect_reference, identities))
    return tuple(selections)


def validate_npc_consumption_recipients(fight, plan, roots, factory):
    requirements = required_recipient_requirements(
        plan, roots, getattr(factory, "effects", None)
    )
    return validate_required_recipients(fight, plan, factory, requirements)


# Cache only neutral contracts from sealed published definitions. A caller's
# factory mapping is rebound on every return; no Fight/PV/callback is retained.
from collections import OrderedDict
from threading import RLock
from . import combat_published_catalogs as _published_contracts
from . import combat_direct_target as _direct_contracts
from . import combat_effect_targets as _target_contracts
from . import combat_native_timing_context as _timing_contracts
from . import combat_kill as _kill_contracts
from . import combat_effect_resolver as _variant_contracts

_CONTRACT_CACHE_LIMIT = 512
_CONTRACT_CACHE_LOCK = RLock()
_CONTRACT_CACHE_MISSING = object()
_POINT_CONTRACT_CACHE = OrderedDict()
_SOURCE_STATIC_DESCRIPTOR = _published_contracts.static_catalog_descriptor
_SOURCE_DIRECT_GETTER = _direct_contracts.native_direct_target_policies
_POINT_SOURCES = (
    _target_contracts.native_selector_policy,
    _target_contracts.area_offsets,
    _timing_contracts.native_definition_timing,
    _kill_contracts.kill_parameters,
    _variant_contracts.variant_accepts,
)


def published_contract_key(effects, roots, level):
    if (
        _published_contracts.static_catalog_descriptor is not _SOURCE_STATIC_DESCRIPTOR
        or type(roots) not in (tuple, list)
        or any(type(reference) is not int or reference <= 0 for reference in roots)
        or type(level) is not int
    ):
        return None
    descriptor = _SOURCE_STATIC_DESCRIPTOR(effects)
    if descriptor is None or effects.representation != "frozen_effect":
        return None
    return (tuple(sorted(descriptor.items())), tuple(roots), level)


def cached_published_contract(cache, key, build):
    if key is None:
        return build()
    with _CONTRACT_CACHE_LOCK:
        value = cache.get(key, _CONTRACT_CACHE_MISSING)
        if value is not _CONTRACT_CACHE_MISSING:
            cache.move_to_end(key)
            return value
    value = build()
    with _CONTRACT_CACHE_LOCK:
        cache[key] = value
        cache.move_to_end(key)
        while len(cache) > _CONTRACT_CACHE_LIMIT:
            cache.popitem(last=False)
    return value


_uncached_required_recipient_requirements = required_recipient_requirements


def required_recipient_requirements(
    plan, roots, effects, *, direct_target_policies=None
):
    level = plan.get("evaluation_level")
    key = published_contract_key(effects, roots, level)
    current_sources = (
        _target_contracts.native_selector_policy,
        _target_contracts.area_offsets,
        _timing_contracts.native_definition_timing,
        _kill_contracts.kill_parameters,
        _variant_contracts.variant_accepts,
    )
    if (
        direct_target_policies is not None
        or _direct_contracts.native_direct_target_policies is not _SOURCE_DIRECT_GETTER
        or any(
            current is not original
            for current, original in zip(current_sources, _POINT_SOURCES)
        )
    ):
        key = None
    if key is None:
        return _uncached_required_recipient_requirements(
            plan, roots, effects, direct_target_policies=direct_target_policies
        )
    policies = _SOURCE_DIRECT_GETTER()
    descriptor = _SOURCE_STATIC_DESCRIPTOR(policies)
    if (
        descriptor is None
        or descriptor["revision"] != dict(key[0])["revision"]
        or policies.representation != "native_json"
    ):
        return _uncached_required_recipient_requirements(
            plan, roots, effects, direct_target_policies=policies
        )
    key = (key, tuple(sorted(descriptor.items())))
    references = cached_published_contract(
        _POINT_CONTRACT_CACHE,
        key,
        lambda: tuple(
            row.effect_reference
            for row in _uncached_required_recipient_requirements(
                plan, roots, effects, direct_target_policies=policies
            )
        ),
    )
    return tuple(
        RequiredRecipientRequirement(ref, level, source_effects=effects)
        for ref in references
    )
