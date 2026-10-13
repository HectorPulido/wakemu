"""Prioritize real empty anchors for nonspatial caster-only roots; never certify casts."""


def prefer_caster_empty_anchors(
    fight,
    source,
    minimum,
    maximum,
    casting,
    root_ids,
    effects,
    casting_roots,
    *,
    enumerate_empty=None
):
    if not caster_empty_root_policy(
        minimum, maximum, casting, root_ids, effects, casting_roots
    ):
        return None
    if enumerate_empty is None:
        from monster_pending_scenarios import bounded_empty_targets

        enumerate_empty = bounded_empty_targets
    # Reuse the existing two ordinary empty-anchor slots; do not raise caps.
    candidates = enumerate_empty(
        fight,
        source,
        minimum,
        maximum,
        limit=12,
        prefer_linear=casting.get("linear") is True,
        prefer_diagonal=casting.get("diagonal") is True,
    )
    if casting.get("linear") is True:
        candidates = [p for p in candidates if p[0] == source[0] or p[1] == source[1]]
    if casting.get("diagonal") is True:
        candidates = [
            p for p in candidates if abs(p[0] - source[0]) == abs(p[1] - source[1])
        ]
    return candidates[:2]


def spatial_enemy_descendants(root_ids, effects):
    """Read bounded direct group geometry; unknown ancestry never becomes proof."""
    from wakfu_server.combat_effect_targets import native_selector_policy
    from wakfu_server.combat_area_geometry import native_area_shape

    visited = set()
    active = set()
    found = []

    def visit(identity):
        if identity in active or len(visited) >= 128:
            raise ValueError("Unbounded native group ancestry")
        if identity in visited:
            return
        effect = effects.get(str(identity))
        if not isinstance(effect, dict):
            raise ValueError("Missing native group descendant")
        active.add(identity)
        visited.add(identity)
        if effect.get("effect_class") in (330, 331):
            children = effect.get("children")
            if not isinstance(children, list):
                raise ValueError("Missing native group children")
            for child in children:
                visit(child)
        else:
            policy = native_selector_policy(effect)
            if policy["in_area"] and policy["relations"] == frozenset({"enemy"}):
                if native_area_shape(effect) is None:
                    raise ValueError("Unknown native descendant geometry")
                found.append(effect)
        active.remove(identity)

    try:
        for identity in root_ids:
            visit(identity)
    except ValueError:
        return None
    return found


def rank_empty_geometry(source, anchors, enemies, effects):
    """Rank existing cells only; native targeting and execution remain authoritative."""
    from wakfu_server.combat_area_geometry import native_area_contains

    def score(anchor):
        return sum(
            native_area_contains(
                effect, origin=anchor, reference=source, point=enemy, radius=0
            )
            for effect in effects
            for enemy in enemies
        )

    return sorted(anchors, key=lambda anchor: -score(anchor))


def rank_enemy_geometry(source, enemies, anchors, effects, minimum, maximum, casting):
    """Prefer real opponent cells admitting an empty native descendant-area anchor."""
    from wakfu_server.combat_area_geometry import native_area_contains

    usable = [
        anchor
        for anchor in anchors
        if anchor != source
        and minimum
        <= abs(anchor[0] - source[0]) + abs(anchor[1] - source[1])
        <= maximum
        and (
            casting.get("linear") is not True
            or anchor[0] == source[0]
            or anchor[1] == source[1]
        )
        and (
            casting.get("diagonal") is not True
            or abs(anchor[0] - source[0]) == abs(anchor[1] - source[1])
        )
    ]

    def score(enemy):
        return sum(
            any(
                native_area_contains(
                    effect, origin=anchor, reference=source, point=enemy, radius=0
                )
                for effect in effects
            )
            for anchor in usable
            if anchor != enemy
        )

    return sorted(enemies, key=lambda enemy: -score(enemy))


def caster_centered_enemy_cells(source, direction, root_ids, effects, destinations):
    """eYg actor branch centers children on selected self, not requested anchor."""
    from wakfu_server.combat_effect_groups import native_group_route
    from wakfu_server.combat_area_geometry import (
        native_area_contains,
        native_area_shape,
    )
    from wakfu_server.combat_effect_targets import native_selector_policy

    if type(direction) is not int or not 0 <= direction < 8:
        return []
    descendants = []
    for identity in root_ids:
        root = effects.get(str(identity), {})
        # No actor-rebind or nested group inference: those require their own
        # exact context propagation. The direct native default is on-target.
        count = root.get("parameter_count")
        if (
            root.get("effect_class") != 330
            or type(count) is not int
            or not 0 <= count < 6
        ):
            return []
        try:
            if native_group_route(root) != "actors":
                return []
        except ValueError:
            return []
        children = root.get("children")
        if not isinstance(children, list) or len(children) > 128:
            return []
        for child_id in children:
            child = effects.get(str(child_id))
            if not isinstance(child, dict):
                return []
            try:
                policy = native_selector_policy(child)
                if policy["in_area"] and policy["relations"] == frozenset({"enemy"}):
                    if native_area_shape(child) is None:
                        return []
                    # Qe.a resolves this immediate recipient before its runner
                    # executes. Child865/330 may later change context; do not
                    # project their descendants onto the caster's origin.
                    descendants.append(child)
            except ValueError:
                return []
    if not descendants:
        return []
    return [
        cell
        for cell in destinations
        if cell != source
        and any(
            native_area_contains(
                effect,
                origin=source,
                reference=source,
                point=cell,
                direction=direction,
                radius=0,
            )
            for effect in descendants
        )
    ]


def caster_empty_root_policy(
    minimum, maximum, casting, root_ids, effects, casting_roots
):
    from wakfu_server.combat_effect_targets import native_selector_policy

    if (
        type(minimum) is not int
        or type(maximum) is not int
        or minimum < 1
        or maximum < minimum
        or not root_ids
        or casting.get("free_cell") is True
    ):
        return False
    for reference in root_ids:
        effect = effects.get(str(reference))
        metadata = casting_roots.get(str(reference))
        if not isinstance(effect, dict) or not isinstance(metadata, dict):
            return False
        if (
            "native_casting_collision_area" not in metadata
            or metadata["native_casting_collision_area"] is not None
            or metadata.get("native_selector_present") is not True
            or metadata.get("native_target_selector")
            != effect.get("native_target_selector")
        ):
            return False
        policy = native_selector_policy(effect)
        if policy["in_area"] or policy["relations"] != frozenset({"self"}):
            return False
    return True
