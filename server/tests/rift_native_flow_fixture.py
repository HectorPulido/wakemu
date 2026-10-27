"""Native constructor fixture shared by the three-Rift lifecycle component.

Terrain, directed edges and QI surface indices come from the original published
map. Deterministic participant selection is a component placement policy.
Actor characteristics, ordinary sources, initial states and role records come
from the pinned published dataset and the SQL-declared frozen Rift policy.
"""
from copy import deepcopy
from collections import deque
import random
from types import SimpleNamespace


def _native_positions(map_id, quantity, *, minimum_separation=3):
    """Select real mutually reachable cells, never synthetic grid neighbors."""
    from wakfu_server.combat_geometry import published_geometry, encounter_component

    geometry = published_geometry(map_id)
    for origin in sorted(
        geometry.cells,
        key=lambda cell: (abs(cell[0]) + abs(cell[1]), abs(cell[2]), cell),
    ):
        try:
            component, _ = encounter_component(geometry, origin)
        except ValueError:
            continue
        distances, pending = {origin: 0}, deque([origin])
        while pending:
            current = pending.popleft()
            for target in geometry.outgoing.get(current, ()):
                if target in component and target not in distances:
                    distances[target] = distances[current] + 1
                    pending.append(target)
        # Component placement chooses native free cells before any Actor
        # exists; it never relocates initialized combatants.
        candidates = sorted(
            (
                cell
                for cell, distance in distances.items()
                if distance >= minimum_separation
                and abs(cell[0] - origin[0]) + abs(cell[1] - origin[1])
                >= minimum_separation
            ),
            key=lambda cell: (distances[cell], cell),
        )
        if len(candidates) >= quantity:
            return origin, tuple(candidates[:quantity])
    raise ValueError("Published Rift geometry lacks the required native formation")


def build_flow_fixture(
    character,
    run,
    fight_id,
    identities,
    references,
    *,
    compiled,
    registry,
    minimum_separation=3,
    additional_player_ids=(),
    additional_player_sources=None,
    ready=True,
):
    from wakfu_server.combat_actor_snapshot import (
        build_player_snapshot,
        build_npc_snapshot,
        native_npc_creation_values,
    )
    from wakfu_server.combat_state import Actor, Fight
    from wakfu_server.combat_encounter_roles import bind_roles
    from wakfu_server.rift_encounter_roles import roles_for_catalog
    from wakfu_server.monsters import owned_instance, reference
    from wakfu_server.equipment_stats import effective_character, combat_resources
    from wakfu_server.combat_geometry_snapshot import freeze_terrain
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.combat_qi_fight import (
        prepare_fresh_actor_slots,
        install_fresh_actor_slots,
    )
    from wakfu_server.combat_global_pv_collections import (
        initialize_global_pv_collections,
    )
    from wakfu_server.combat_server_spell import server_runtime

    roles = roles_for_catalog(
        run["catalog"], run["policy"], monster_references=references
    )
    player_position, monster_positions = _native_positions(
        run["catalog"]["map_id"], len(references), minimum_separation=minimum_separation
    )
    character = effective_character(deepcopy(character))
    character.update(
        map_id=run["catalog"]["map_id"],
        instance_id=run["instance_id"],
        x=player_position[0],
        y=player_position[1],
        z=player_position[2],
    )
    resources = combat_resources(character)
    player = Actor(
        character["id"],
        roles.player_team,
        player_position,
        character["hp"],
        resources["ap"],
        resources["mp"],
        resources["initiative"],
        character["level"],
        owner_id=character["account_id"],
        controlled=True,
        max_hp=character["max_hp"],
    )
    player_snapshot = build_player_snapshot(
        character,
        player,
        wp_current=resources["wp"],
        wp_maximum=resources["wp"],
        running_effects=(),
    )
    actors, monsters, snapshots = [player], {}, {player.id: player_snapshot}
    characters = {player.id: character}
    from wakfu_server.combat_geometry import published_geometry

    geometry = published_geometry(character["map_id"])
    for identity in additional_player_ids:
        occupied = {member.position for member in actors} | set(monster_positions)
        adjacent = sorted(
            cell
            for cell in geometry.outgoing.get(player.position, ())
            if cell not in occupied
            and player.position in geometry.outgoing.get(cell, ())
            and all(
                abs(cell[0] - target[0]) + abs(cell[1] - target[1]) >= 4
                for target in monster_positions
            )
        )
        if not adjacent:
            raise ValueError(
                "No native adjacent company placement outside the boss aura"
            )
        position = adjacent[0]
        from rift_native_gear_fixture import clone_equipment_owner

        hero = (
            effective_character(deepcopy(additional_player_sources[identity]))
            if additional_player_sources is not None
            else clone_equipment_owner(character, identity)
        )
        hero_resources = combat_resources(hero)
        hero.update(map_id=character["map_id"], instance_id=character["instance_id"])
        hero.update(x=position[0], y=position[1], z=position[2])
        hero_actor = Actor(
            identity,
            roles.player_team,
            position,
            hero["hp"],
            hero_resources["ap"],
            hero_resources["mp"],
            hero_resources["initiative"],
            hero["level"],
            owner_id=hero["account_id"],
            controlled=True,
            max_hp=hero["max_hp"],
        )
        characters[identity] = hero
        snapshots[identity] = build_player_snapshot(
            hero,
            hero_actor,
            wp_current=hero_resources["wp"],
            wp_maximum=hero_resources["wp"],
            running_effects=(),
        )
        actors.append(hero_actor)
    for index, (identity, ref) in enumerate(zip(identities, references)):
        level = reference(ref)["min_level"]
        position = monster_positions[index]
        monster = owned_instance(
            ref,
            level,
            identity,
            map_id=character["map_id"],
            instance_id=run["instance_id"],
            x=position[0],
            y=position[1],
            z=position[2],
            team=1,
        )
        values = native_npc_creation_values(ref, level)
        actor = Actor(
            identity,
            roles.npc_team,
            position,
            values[1]["current"],
            values[2]["current"],
            values[3]["current"],
            values[35]["current"],
            level,
            max_hp=values[1]["maximum"],
            direction=3,
        )
        snapshots[identity] = build_npc_snapshot(
            monster,
            actor,
            wp_current=values[4]["current"],
            wp_maximum=values[4]["maximum"],
            running_effects=(),
        )
        actors.append(actor)
        monsters[identity] = monster
    player_actors = [actor for actor in actors if actor.controlled]
    npc_actors = [actor for actor in actors if not actor.controlled]
    terrain = local_arena(
        character["map_id"],
        run["instance_id"],
        player.position,
        [actor.position for actor in actors if actor.id != player.id],
        compact=False,
        relocate_monsters=False,
        player_radius=player_snapshot.physical_radius,
        member_radii=[
            snapshots[actor.id].physical_radius
            for actor in actors
            if actor.id != player.id
        ],
    )
    cells, edges = terrain["validated_cells"], terrain["valid_edges"]
    fight = Fight(
        fight_id,
        actors,
        cells,
        roles.placement_cells(
            [a.position for a in player_actors], [a.position for a in npc_actors]
        ),
        valid_edges=edges,
    )
    for identity, snap in snapshots.items():
        snap.install(fight.actors[identity])
    bind_roles(fight, roles, player_ids=tuple(characters), npc_ids=tuple(monsters))
    fight.native_qi_snapshot = {
        name: deepcopy(terrain[name])
        for name in ("x", "y", "width", "height", "cell_masks")
    }
    fight.native_qi_surface_provenance = dict(terrain["native_qi_surface_provenance"])
    initialize_global_pv_collections(fight, tuple(fight.actors))
    install_fresh_actor_slots(
        fight,
        prepare_fresh_actor_slots(
            fight,
            physical_radii={
                actor.id: snapshots[actor.id].physical_radius for actor in actors
            },
        ),
    )
    freeze_terrain(fight)
    fight.native_effect_uid_next = 1
    fight.native_obstacle_cells = frozenset()
    fight.rift_monsters = deepcopy(monsters)
    fight.rift_wave_state = dict(
        instance_id=run["instance_id"],
        wave=1,
        turn_budget=run["policy"]["turn_budget"],
        wave_actor_ids=list(identities),
        wave_species_refs=list(references),
        catalog=deepcopy(run["catalog"]),
        policy=deepcopy(run["policy"]),
        seed=run["seed"],
        actor_id_pool=[-300, -301, -302, -303],
        world_group_id=fight_id,
    )
    from wakfu_server.rift_npc_creation import initialize_native_wave_actors

    initialize_native_wave_actors(fight, tuple(monsters.values()))
    if ready:
        fight.ready(character["account_id"])
    rng = random.Random(81971)

    def runtime_factory(current, *, action_id):
        build = character["builds"][character.get("active_build_index", 0)]
        deck = bytes.fromhex(build["deck"])
        runtime, _ = server_runtime(
            character,
            current.rift_monsters,
            deck,
            action_id=action_id,
            critical=False,
            rng=rng,
            compiled=compiled,
            player_characters=characters,
            deck_blobs={
                identity: bytes.fromhex(member["builds"][0]["deck"])
                for identity, member in characters.items()
            },
        )
        return runtime

    def factory(current):
        runtime = runtime_factory(current, action_id=1)
        return runtime(current, {"native_retained_container": {"present": False}})

    return SimpleNamespace(
        fight=fight,
        factory=factory,
        runtime_factory=runtime_factory,
        rng=rng,
        character=character,
        characters=characters,
        decks={
            identity: bytes.fromhex(member["builds"][0]["deck"])
            for identity, member in characters.items()
        },
        monsters=monsters,
        roles=roles,
    )
