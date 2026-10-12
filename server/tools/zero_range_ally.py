"""Private witness proposal; native casting still decides occupied-cell legality."""
from wakfu_server.combat_effect_targets import native_selector_policy


def propose(reference, level, capability, root_effects, native_profiles):
    """Return a constructor recipe only for exact ally-only zero-range roots."""
    if type(reference) is not int or type(level) is not int or level <= 0:
        raise ValueError("Invalid actual native descriptor")
    profile = native_profiles.get(str(reference))
    if profile is None or profile.get("ref") != reference:
        raise ValueError("Missing exact native roster authority")
    if not profile["min_level"] <= level <= profile["max_level"]:
        raise ValueError("Level outside actual native descriptor")
    if capability.get("minimum") != 0 or capability.get("maximum") != 0:
        return None
    if not root_effects:
        return None
    policies = [native_selector_policy(effect) for effect in root_effects]
    if not all(
        p["relations"] == frozenset({"ally"}) and not p["in_area"] for p in policies
    ):
        return None
    return dict(
        kind="native_opponent",
        opponent=dict(reference=reference, level=level, team=1),
        discovery="native_zero_range_ally_population_private_v1",
    )


def extra_cell_request(fight, recipe):
    """Request the actual caster cell without mislabelling an ally as self.

    An occupied cell may still resolve to the caster in the native casting
    oracle. Such a rejection is authoritative, never a reason to bypass it.
    """
    caster = fight.current
    if (
        caster is None
        or recipe.get("discovery") != "native_zero_range_ally_population_private_v1"
    ):
        return []
    return [(tuple(caster.position), None)]
