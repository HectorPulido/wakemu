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
