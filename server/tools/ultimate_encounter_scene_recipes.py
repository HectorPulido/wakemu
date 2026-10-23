"""Source-bound scene inputs for offline ultimate encounter qualification.

These recipes select existing terrain and identify real producer paths. They
never grant phase states, create replacement terrain, or declare an attack
successful from structural reachability alone.
"""
from collections import defaultdict, deque


def encounter_fixture_factory(
    validator,
    scene,
    *,
    player_level=200,
    player_breed=None,
    player_deck=None,
    character_constructor=None,
    caster_cell=None,
    production_bootstrap=False,
    arena_transform=None,
):
    """Adapt only the existing validation fixture's scene construction inputs.

    Production formation selects the caster unless a reconstruction supplies
    an explicit existing native cell. The existing
    character/NPC constructors, original initial states, paid cast admission
    and transaction paths remain intact. This helper does not execute actions.
    """
    import ast
    import hashlib
    import inspect
    from wakfu_server.dungeon_encounters import enemy_formation
    from wakfu_server.progression import level_xp

    if type(player_level) is not int or not 1 <= player_level <= 245:
        raise ValueError("Invalid native fixture player level")
    if player_breed is not None and (
        type(player_breed) is not int or not 1 <= player_breed <= 18
    ):
        raise ValueError("Invalid native fixture player breed")
    if player_deck is not None and (
        not isinstance(player_deck, (tuple, list))
        or any(type(spell) is not int or spell <= 0 for spell in player_deck)
    ):
        raise ValueError("Invalid native fixture player deck")
    if character_constructor is not None and not callable(character_constructor):
        raise ValueError("Native character constructor must be callable")
    if type(production_bootstrap) is not bool or (
        arena_transform is not None and not callable(arena_transform)
    ):
        raise ValueError("Invalid production scene fixture adapter")
    if production_bootstrap and not scene.get("policy"):
        raise ValueError("Production scene bootstrap requires a declared layout policy")
    geometry = {
        "map_id": scene["map_id"],
        "cells": scene["cells"],
        "edges": scene["edges"],
    }
    if caster_cell is None:
        source = enemy_formation(geometry, scene["anchor"], 1, player_slots=6)[0]
        placement_producer = "wakfu_server.dungeon_encounters.enemy_formation"
    else:
        if (
            not isinstance(caster_cell, (tuple, list))
            or len(caster_cell) != 3
            or any(type(value) is not int for value in caster_cell)
            or tuple(caster_cell) not in {tuple(cell) for cell in scene["cells"]}
        ):
            raise ValueError(
                "Reconstructed caster placement must be an existing native scene cell"
            )
        source = tuple(caster_cell)
        placement_producer = "wakemu.reconstructed.observed-layout.v1"
    original = inspect.getsource(validator.fixture)
    tree = ast.parse(original)
    changes = {"map": 0, "source": 0, "arena": 0, "player_level": 0, "xp": 0}

    class Inputs(ast.NodeTransformer):
        def visit_Constant(self, node):
            if type(node.value) is int and node.value == 1134:
                changes["map"] += 1
                return ast.copy_location(ast.Constant(scene["map_id"]), node)
            return node

        def visit_Assign(self, node):
            self.generic_visit(node)
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id == "source":
                    if ast.literal_eval(node.value) != (-8, -7, -1):
                        raise ValueError("Base validation source placement drifted")
                    node.value = ast.parse(repr(tuple(source)), mode="eval").body
                    changes["source"] += 1
                elif node.targets[0].id == "character_level":
                    if (
                        not isinstance(node.value, ast.IfExp)
                        or ast.literal_eval(node.value.orelse) != 1
                    ):
                        raise ValueError("Base validation default player level drifted")
                    node.value.orelse = ast.Constant(player_level)
                    changes["player_level"] += 1
                elif (
                    node.targets[0].id == "character_breed" and player_breed is not None
                ):
                    if (
                        not isinstance(node.value, ast.IfExp)
                        or ast.literal_eval(node.value.orelse) != 15
                    ):
                        raise ValueError("Base validation default player breed drifted")
                    node.value.orelse = ast.Constant(player_breed)
                    changes["player_breed"] = changes.get("player_breed", 0) + 1
                elif node.targets[0].id == "deck" and player_deck is not None:
                    if not isinstance(node.value, ast.IfExp):
                        raise ValueError(
                            "Base validation default deck construction drifted"
                        )
                    node.value.orelse = ast.Call(
                        func=ast.Name(id="encode_deck", ctx=ast.Load()),
                        args=[ast.Name(id="_encounter_player_deck", ctx=ast.Load())],
                        keywords=[],
                    )
                    changes["player_deck"] = changes.get("player_deck", 0) + 1
            return node

        def visit_Call(self, node):
            self.generic_visit(node)
            if isinstance(node.func, ast.Name) and node.func.id == "local_arena":
                node.func.id = "_encounter_native_arena"
                if production_bootstrap:
                    node.keywords.append(
                        ast.keyword(
                            arg="encounter_reference",
                            value=ast.Name(id="reference", ctx=ast.Load()),
                        )
                    )
                    node.keywords.append(
                        ast.keyword(
                            arg="encounter_character",
                            value=ast.Name(id="character", ctx=ast.Load()),
                        )
                    )
                    node.keywords.append(
                        ast.keyword(
                            arg="encounter_monster",
                            value=ast.Name(id="monster", ctx=ast.Load()),
                        )
                    )
                changes["arena"] += 1
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "effective_character"
                and character_constructor is not None
            ):
                node.func.id = "_encounter_character_constructor"
                changes["character_constructor"] = (
                    changes.get("character_constructor", 0) + 1
                )
            if isinstance(node.func, ast.Name) and node.func.id == "dict":
                keys = {keyword.arg for keyword in node.keywords}
                if {"account_id", "inventory_items", "breed", "level"} <= keys:
                    node.keywords.append(
                        ast.keyword(
                            arg="xp",
                            value=ast.Call(
                                func=ast.Name(
                                    id="_encounter_native_xp", ctx=ast.Load()
                                ),
                                args=[ast.Name(id="character_level", ctx=ast.Load())],
                                keywords=[],
                            ),
                        )
                    )
                    changes["xp"] += 1
            return node

    tree = Inputs().visit(tree)
    ast.fix_missing_locations(tree)
    expected_changes = {"map": 6, "source": 1, "arena": 1, "player_level": 1, "xp": 1}
    expected_changes.update(
        {
            key: 1
            for key, enabled in (
                ("player_breed", player_breed is not None),
                ("player_deck", player_deck is not None),
                ("character_constructor", character_constructor is not None),
            )
            if enabled
        }
    )
    if changes != expected_changes:
        raise ValueError("Base validation encounter inputs drifted: " + repr(changes))

    selected_arenas = []

    def actual_arena(
        *args,
        encounter_reference=None,
        encounter_character=None,
        encounter_monster=None,
        **kwargs,
    ):
        from wakfu_server.combat_terrain import local_arena

        if not production_bootstrap:
            return local_arena(
                *args, **dict(kwargs, compact=False, allowed_cells=scene["cells"])
            )
        from wakfu_server.combat_encounter_scene_layout import prepare_encounter_scene

        map_id, instance_id, player_origin, npc_origin = args[:4]
        character = encounter_character
        member = encounter_monster
        selected = prepare_encounter_scene(
            character,
            [member],
            dict(map_id=map_id, instance_id=instance_id),
            layout=scene,
        )
        if arena_transform is not None:
            selected = arena_transform(character, [member], selected)
        selected_arenas.append(selected)
        return selected

    namespace = dict(validator.fixture.__globals__)
    namespace.update(
        _encounter_native_arena=actual_arena, _encounter_native_xp=level_xp
    )
    if player_deck is not None:
        namespace["_encounter_player_deck"] = tuple(player_deck)
    if character_constructor is not None:
        namespace["_encounter_character_constructor"] = character_constructor
    code = ast.unparse(tree)
    exec(compile(tree, "<source-bound-ultimate-encounter-fixture>", "exec"), namespace)
    receipt = {
        "map_id": scene["map_id"],
        "route_key": scene["route_key"],
        "source": tuple(source),
        "placement_producer": placement_producer,
        "player_level": player_level,
        "player_breed_override": player_breed,
        "player_deck_override": player_deck,
        "base_fixture_sha256": hashlib.sha256(original.encode()).hexdigest(),
        "adapted_fixture_sha256": hashlib.sha256(code.encode()).hexdigest(),
        "changed_inputs": changes,
        "phase_or_resource_grants": False,
        "production_bootstrap": production_bootstrap,
    }
    if not production_bootstrap:
        return namespace["fixture"], receipt

    def production_fixture(*args, **kwargs):
        from wakfu_server.combat_bootstrap import (
            create_placement,
            placement_messages,
            player_payload,
        )
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.equipment_stats import combat_resources
        from wakfu_server.combat_actor import actual_monster_actor_stats, actor_effects

        lifecycle = kwargs.pop("native_lifecycle", False)
        if type(lifecycle) is not bool:
            raise ValueError("Explicit native fixture lifecycle mode must be boolean")
        _discarded, character, monsters, deck = namespace["fixture"](
            *args, **dict(kwargs, native_lifecycle=False)
        )
        selected = selected_arenas[-1]
        resources = combat_resources(character)
        fight, packets = create_placement(
            character,
            list(monsters.values()),
            selected,
            fight_id=78,
            player_ap=resources["ap"],
            player_mp=resources["mp"],
            player_wp=resources["wp"],
            player_initiative=resources["initiative"],
            terrain_effect_id=selected.get("terrain_effect_id", 46),
            terrain_instance_id=780000001,
        )
        initialize_fight_snapshots(
            fight,
            characters={character["id"]: character},
            monsters=monsters,
            wp_resources={
                character["id"]: (resources["wp"], resources["wp"]),
                **{
                    identity: (row["wp"], row["wp"])
                    for identity, row in monsters.items()
                },
            },
            running_effects={identity: () for identity in fight.actors},
            initial_effect_uid=1,
        )
        player = fight.actors[character["id"]]
        payloads = {
            player.id: player_payload(
                character, player, fight.id, wp=player.effect_stats[4]
            )
        }
        for identity, row in monsters.items():
            actor = fight.actors[identity]
            payloads[identity] = (
                actual_monster_actor_stats(
                    row,
                    actor,
                    fight.id,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=actor.effect_maxima[4],
                    fight=fight,
                ),
                actor_effects(),
            )
        leaders = {player.team: player.id}
        for identity in monsters:
            leaders.setdefault(fight.actors[identity].team, identity)
        packets = placement_messages(
            fight,
            selected,
            payloads,
            terrain_effect_id=selected.get("terrain_effect_id", 46),
            terrain_instance_id=780000001,
            leaders=leaders,
            viewer_id=player.id,
        )
        from wakfu_server.combat_wire import decode_bootstrap

        wire = decode_bootstrap(
            next(payload for opcode, payload in packets if opcode == 12847)
        )
        receipt["bootstrap_native_actor_wire"] = {
            actor["actor_id"]: dict(
                format=actor["myE"][0],
                stats_bytes=len(actor["myE"]),
                effects_bytes=len(actor["myF"]),
                direction=actor["myE"][19] if actor["myE"][0] == 2 else None,
            )
            for actor in wire["participants"]
        }
        receipt["bootstrap_packets"] = [
            (opcode, len(payload)) for opcode, payload in packets
        ]
        receipt["bootstrap_scene_metadata"] = fight.native_encounter_scene_layout
        receipt["bootstrap_terrain_effect_id"] = selected.get("terrain_effect_id", 46)
        receipt["bootstrap_native_border_constructor"] = getattr(
            fight, "native_border_constructor", None
        )
        fight.ready(character["account_id"])
        if lifecycle:
            from native_monster_creator_witness import (
                initialize_native_creator_lifecycle,
            )

            fight = initialize_native_creator_lifecycle(
                fight, character, monsters, deck
            )
        return fight, character, monsters, deck

    return production_fixture, receipt


def room_scene(configuration, geometry, reference, *, room_order=1):
    """Bind a frozen roster to its exact map and exported walkable room."""
    route = configuration["route"]
    topology = configuration["topology"]
    map_id = geometry["map_id"]
    if map_id != route["start_map_id"] or map_id != topology["asset_map_id"]:
        raise ValueError("Encounter route and native geometry identities differ")
    rooms = [
        r for r in configuration["compiled_plan"]["rooms"] if r["order"] == room_order
    ]
    sections = [r for r in topology["rooms"] if r["order"] == room_order]
    if len(rooms) != 1 or len(sections) != 1:
        raise ValueError("Encounter room is absent or ambiguous")
    entries = [m for m in rooms[0]["monsters"] if m["ref_id"] == reference]
    if len(entries) != 1 or entries[0]["count"] != 1:
        raise ValueError("Requested singleton boss is absent from the frozen roster")
    cells = frozenset(map(tuple, sections[0]["cells"]))
    native_cells = frozenset(map(tuple, geometry["cells"]))
    anchor = tuple(sections[0]["anchor"])
    if not cells or not cells <= native_cells or anchor not in cells:
        raise ValueError("Encounter room or anchor leaves published native terrain")
    edges = tuple(
        (tuple(start), tuple(end))
        for start, end in geometry["edges"]
        if tuple(start) in cells and tuple(end) in cells
    )
    return {
        "route_key": route["key"],
        "reference": reference,
        "map_id": map_id,
        "anchor": anchor,
        "cells": cells,
        "edges": edges,
        "level": entries[0]["native_min_level"],
        "provenance": configuration["provenance"],
    }


def producer_paths(graph, target, owners, *, maximum_nodes=20000):
    """Find positive source paths, excluding criteria-only area references.

    Returned paths end at the requested state/area and begin at a real owned
    spell or initial monster constructor. Runtime eligibility still applies.
    """
    parents = defaultdict(set)
    for edge in graph["edges"]:
        source = edge["source"]
        if source.endswith(":criterion"):
            continue
        parents[edge["kind"] + ":" + str(edge["reference"])].add(source)
    owners = frozenset(owners)
    queue = deque([(target, (target,))])
    seen, paths = {target}, []
    while queue:
        node, path = queue.popleft()
        if node in owners:
            paths.append(tuple(reversed(path)))
            continue
        for source in sorted(parents[node]):
            if source in seen:
                continue
            seen.add(source)
            if len(seen) > maximum_nodes:
                raise ValueError("Encounter producer traversal exceeds its node bound")
            queue.append((source, path + (source,)))
    return tuple(sorted(paths))


def path_guards(graph, path):
    """Retain native eligibility guards instead of treating a graph as a cast."""
    return tuple(
        (node, graph["records"][node]["criteria"])
        for node in path
        if graph.get("records", {}).get(node, {}).get("criteria")
    )


def projected_native_columns(scene, effect, origin, *, direction, reference=None):
    """Join unchanged native point offsets to exact existing room columns."""
    from wakfu_server.combat_area_geometry import oriented_area_offsets

    origin = tuple(origin)
    if origin not in scene["cells"]:
        raise ValueError("Native scene caster is outside the bound encounter room")
    if type(direction) is not int or not 0 <= direction < 8:
        raise ValueError("Native scene requires an explicit genuine facing")
    reference = origin if reference is None else tuple(reference)
    offsets = oriented_area_offsets(
        effect, origin=origin, reference=reference, direction=direction
    )
    columns = defaultdict(list)
    for cell in scene["cells"]:
        columns[cell[:2]].append(cell)
    points = tuple((origin[0] + x, origin[1] + y) for x, y in offsets)
    return {
        "projected": points,
        "existing": tuple(
            columns[point][0] for point in points if len(columns.get(point, ())) == 1
        ),
        "absent": tuple(point for point in points if point not in columns),
        "ambiguous": tuple(
            point for point in points if len(columns.get(point, ())) > 1
        ),
    }
