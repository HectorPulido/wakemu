"""Complete native child-output domains, independent of future target identity.

Native eYm resolves the selected real eGj at execution; null and Qq preserve
parent level. Other overrides are signed-short before descendant dispatch.
A whole-domain descendant proof therefore never substitutes an owner's level
for an unknown or rebound target and never predicts a future actor roster.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SelectedChildLevels:
    mode: object
    levels: tuple = ()
    requires_context: tuple = (
        "native_selected_actor_level_domain",
        "native_dynamic_child_level",
    )
    child_level_domain: tuple = (-32768, 32767)


def child_domain_witnesses(effect, effects, states, *, registry=None):
    """Every reachable child level must pass the existing typed leaf proof."""
    from .combat_equipment_hp_group_parser import child_domain_witnesses as prove

    return prove(effect, effects, states, registry=registry)


def owned_characteristic_domain(parsed, facts):
    """Prove the selected PV is the actual owned fighter, not an area PA.

    The existing production group_pa reader supplies its current and maximum
    anew at execution. The complete signed-short child proof is independent of
    that future numeric PA value; missing PA fields still fail at the reader.
    """
    from .combat_equipment_dynamic_levels import OwnerLevelFacts

    return (
        type(facts) is OwnerLevelFacts
        and parsed["select_caster"] is True
        and not parsed["group_mode"].actor_rebind
    )


def characteristic_context_preflight(factory, retained_container, parsed):
    """Prove the existing selected-PV reader, without predicting its PA value.

    Both selected and rebound actors use their actual complete ActorSnapshot.
    Registered areas keep group_pa's concrete native presence/null contract;
    incomplete PA pairs and unknown constructor contracts still reject at execution.
    Neither owner level nor zero is substituted for an unknown selected PV.
    Descendant admission separately requires the complete signed-short proof.
    """
    from collections.abc import Mapping
    from .combat_effect_groups import EffectGroupMode
    from .combat_equipment_retained_lifecycle import preflight
    from .combat_characteristic_level_group import runtime_group_level
    from . import combat_effect_runtime, combat_group_pv

    if (
        not isinstance(parsed, Mapping)
        or type(parsed.get("stat_id")) is not int
        or not 0 <= parsed["stat_id"] <= 255
        or type(parsed.get("select_caster")) is not bool
        or type(parsed.get("group_mode")) is not EffectGroupMode
        or parsed["group_mode"].actor_rebind not in (0, 1, 2)
        or parsed.get("child_level_domain") != (-32768, 32767)
    ):
        return False
    return (
        preflight(factory, retained_container)
        and combat_effect_runtime.native_characteristic_group_level
        is runtime_group_level
        and callable(combat_group_pv.group_pa)
        and callable(combat_group_pv.scoped_group_actors)
        and callable(combat_group_pv.resolve_group_level_pv)
    )


def group_rebinding_preflight(factory, retained_container, parsed, *, route):
    """Prove the production group executor supports native caster rebinding.

    The selected target remains a live invocation operand. This proves only
    that the inline native group routes use the existing ordered executor;
    it does not identify a future target or transfer owner-level facts to it.
    """
    from collections.abc import Mapping
    from .combat_effect_groups import EffectGroupMode, execute_ordered_group
    from .combat_effect_dispatch import EffectDispatcher
    from .combat_equipment_operation_capability import FactoryOperationRoute
    from .combat_equipment_retained_lifecycle import preflight
    from . import combat_effect_dispatch

    mode = (
        parsed.get("group_mode")
        if isinstance(parsed, Mapping)
        else parsed
        if type(parsed) is EffectGroupMode
        else getattr(parsed, "mode", None)
    )
    return bool(
        type(mode) is EffectGroupMode
        and type(mode.actor_rebind) is int
        and mode.actor_rebind in (1, 2)
        and type(route) is FactoryOperationRoute
        and route.factory is factory
        and route.family in (330, 844, 912, 913, 999, 1020, 1047)
        and route.inline is True
        and route.handler_type is EffectDispatcher
        and combat_effect_dispatch.execute_ordered_group is execute_ordered_group
        and preflight(factory, retained_container)
    )
