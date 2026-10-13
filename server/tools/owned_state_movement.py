"""Spend actual native MP using normal movement commits, never edit resources."""


def requires_zero_mp_branch(criterion):
    import ast
    from wakfu_server.combat_local_criteria import parse_local_criterion

    if not isinstance(criterion, str) or len(criterion) > 2048:
        return False
    try:
        root = parse_local_criterion(criterion)
    except (ValueError, SyntaxError):
        return False

    def visit(node):
        if isinstance(node, ast.UnaryOp):
            return False
        if isinstance(node, ast.BoolOp):
            return any(visit(value) for value in node.values)
        return (
            isinstance(node, ast.Compare)
            and len(node.ops) == len(node.comparators) == 1
            and isinstance(node.ops[0], ast.Eq)
            and isinstance(node.comparators[0], ast.Constant)
            and type(node.comparators[0].value) is int
            and node.comparators[0].value == 0
            and isinstance(node.left, ast.Call)
            and isinstance(node.left.func, ast.Name)
            and node.left.func.id == "GetCharacteristic"
            and not node.left.keywords
            and len(node.left.args) == 1
            and isinstance(node.left.args[0], ast.Constant)
            and node.left.args[0].value == "MP"
        )

    return visit(root)


def spend_native_movement(
    fight, caster_id, provider, runtime_factory, serialize, *, limit=12
):
    actor = fight.actors[caster_id]
    start = actor.position
    budget = actor.mp
    if type(budget) is not int or budget < 0 or budget > limit or budget % 2:
        raise ValueError("No bounded native return-to-source MP exhaustion path")
    if budget == 0:
        return dict(initial_mp=0, final_mp=0, packets=0, path=[])
    occupied = {
        a.position for uid, a in fight.actors.items() if uid != caster_id and a.hp > 0
    }
    neighbor = next(
        (
            cell
            for cell in sorted(fight.walkable)
            if cell not in occupied
            and cell[2] == start[2]
            and abs(cell[0] - start[0]) + abs(cell[1] - start[1]) == 1
            and (
                getattr(fight, "edges", None) is None
                or (start, cell) in fight.edges
                and (cell, start) in fight.edges
            )
        ),
        None,
    )
    if neighbor is None:
        raise ValueError("No actual free native movement neighbor")
    path = [cell for _ in range(budget // 2) for cell in (neighbor, start)]
    packets = provider.commit(
        runtime_factory(fight),
        dict(type="move", path=[list(c) for c in path]),
        serialize,
    )
    if not packets or actor.position != start or actor.mp != 0 or actor.hp <= 0:
        raise ValueError(
            "Native movement did not exhaust MP and preserve caster placement"
        )
    return dict(
        initial_mp=budget,
        final_mp=actor.mp,
        packets=len(packets),
        path=[list(c) for c in path],
    )


def bind_owned_movement_authority(fight, character, monsters, deck):
    """Replace NPC-constructor scope with the normal full owned runtime scope."""
    from wakfu_server.combat_server_spell import server_runtime
    from wakfu_server.combat_npc_attack import npc_runtime_catalog

    factory, _ = server_runtime(
        character,
        monsters,
        deck,
        action_id=1,
        critical=False,
        compiled=npc_runtime_catalog(),
    )
    authority = factory.native_rail_movement_authority
    if not callable(authority) or not callable(getattr(authority, "properties", None)):
        raise ValueError("Missing canonical owned movement authority")
    # Keep original strict roster/registration/property checks for every actor.
    for actor in fight.actors.values():
        authority(fight, actor)
        authority.properties(fight, actor)
    fight.native_rail_movement_authority = authority
    return sorted(fight.actors)


def prioritized_owned_preparations(recipes):
    """Try genuine prerequisite commits before generic targets consume caps."""
    return [
        recipe
        for recipe in recipes
        if recipe.get("discovery")
        in ("owned_conditional_self_state_v1", "native_zero_mp_lifecycle_v1")
    ]
