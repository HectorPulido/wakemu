"""Prioritize actual discovered target identities within unchanged search caps."""


def prioritize_native_identities(scenarios, discovered):
    identities = []
    for recipe in discovered:
        if (
            not isinstance(recipe, dict)
            or recipe.get("discovery") != "positive_native_target_identity_v1"
        ):
            raise ValueError("Expected actual native target identity discovery")
        if recipe not in identities:
            identities.append(recipe)
    conditional = [
        s
        for s in scenarios
        if isinstance(s, dict)
        and s.get("discovery") == "owned_conditional_self_state_v1"
    ]
    return (
        conditional
        + identities
        + [s for s in scenarios if s not in conditional and s not in identities]
    )
