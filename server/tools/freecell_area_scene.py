"""Rank existing native free-cell cast witnesses; never certify eligibility."""


def direct_enemy_areas(casting, roots):
    from wakfu_server.combat_area_geometry import native_area_shape

    if casting.get("free_cell") is not True:
        return []
    from wakfu_server.combat_effect_targets import native_selector_policy

    areas = []
    for root in roots:
        if root.get("criteria"):
            continue
        try:
            policy = native_selector_policy(root)
        except ValueError:
            continue
        if (
            policy["in_area"]
            and "enemy" in policy["relations"]
            and native_area_shape(root) is not None
        ):
            areas.append(root)
    # This is advisory geometry only. Full fcE actor predicates (including
    # bit50's actual bcN) remain authoritative during the normal native cast.
    return areas


def rank_recipients(source, enemies, anchors, roots, casting, minimum, maximum):
    from caster_empty_anchor import rank_enemy_geometry

    areas = direct_enemy_areas(casting, roots)
    if not areas:
        return enemies
    return rank_enemy_geometry(
        source, enemies, anchors, areas, minimum, maximum, casting
    )


def rank_anchors(source, anchors, enemies, roots, casting):
    from caster_empty_anchor import rank_empty_geometry

    areas = direct_enemy_areas(casting, roots)
    return rank_empty_geometry(source, anchors, enemies, areas) if areas else anchors


def rank_scenarios(scenarios, roots, casting):
    """Try an unoccupied ordinary arena before optional supportive companions.

    Explicit owned prerequisites keep their position. The automatically
    suggested ally can occupy the only legal free-cell anchor, so it follows
    the existing ordinary scene when unconditional hostile area roots exist.
    """
    if not direct_enemy_areas(casting, roots) or None not in scenarios:
        return scenarios
    optional = [
        scene
        for scene in scenarios
        if isinstance(scene, dict)
        and scene.get("discovery") == "ordinary_same_species_ally_v1"
    ]
    if not optional:
        return scenarios
    return [scene for scene in scenarios if scene not in optional] + optional
