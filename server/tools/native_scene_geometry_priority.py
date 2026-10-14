"""Prefer existing native witness cells; never certify geometry or eligibility."""


def native_identity_spare_priority(scenario, source, target, candidate):
    if (
        not isinstance(scenario, dict)
        or scenario.get("discovery") != "positive_native_target_identity_v1"
        or scenario.get("kind") != "native_opponent"
        or scenario.get("opponent", {}).get("team", 0) != 0
    ):
        return 0
    # A side participant between endpoints can block a legitimate native ray.
    # This is ordering only: registered footprints and actual LOS still decide.
    inside = min(source[0], target[0]) <= candidate[0] <= max(
        source[0], target[0]
    ) and min(source[1], target[1]) <= candidate[1] <= max(source[1], target[1])
    return int(inside)


def zero_range_hostile_scene_priority(scenarios, roots, minimum, maximum):
    if (
        type(minimum) is not int
        or type(maximum) is not int
        or minimum != 0
        or maximum != 0
        or None not in scenarios
    ):
        return scenarios
    from wakfu_server.combat_effect_targets import native_selector_policy, area_offsets

    hostile_area = False
    for root in roots:
        if root.get("effect_class") not in (1, 2, 3, 4, 5) or root.get("criteria"):
            continue
        try:
            policy = native_selector_policy(root)
            offsets = area_offsets(root)
        except ValueError:
            continue
        if (
            policy["in_area"]
            and "enemy" in policy["relations"]
            and any(tuple(point) != (0, 0) for point in offsets)
        ):
            hostile_area = True
            break
    if not hostile_area:
        return scenarios
    optional = [
        s
        for s in scenarios
        if isinstance(s, dict) and s.get("discovery") == "ordinary_same_species_ally_v1"
    ]
    return (
        [s for s in scenarios if s not in optional] + optional
        if optional
        else scenarios
    )
