"""Ordinary reinforcement creation through the installed client's cjs/aVH path.

The world appearance must precede cvg13091: aVH looks up an existing big and
does not construct an NPC. Unlike eZl307 this path never marks a summon and
never resets the fight phase through cvb12847.
"""
from wakfu_server.combat_actor import actor_effects, monster_actor_stats
from wakfu_server.combat_monster_world import spawn_monster
from wakfu_server.combat_multiplayer_wire import added


def initialize_native_wave_actors(fight, monsters):
    """Initialize only fresh reinforcements through ordinary NPC producers.

    The caller owns an unpublished preview. Existing actors' innate states and
    controller changes must never be initialized again at a wave boundary.
    """
    from wakfu_server.combat_npc_ai_initialization import initial_ai_actors
    from wakfu_server.combat_npc_initialization import (
        initial_plans,
        initialize_ordinary_npcs,
    )

    sources = {monster["id"]: monster for monster in monsters}
    from wakfu_server.combat_automatic_npc_turn import (
        initial_root_manifest,
        install_root_manifest,
    )

    root_manifest = initial_root_manifest(fight, sources)
    ai_actors = initial_ai_actors(fight, sources)
    for identity in ai_actors:
        fight.actors[identity].native_controlled_by_ai = True
    fight.native_npc_ai_actors = (
        frozenset(getattr(fight, "native_npc_ai_actors", ())) | ai_actors
    )
    install_root_manifest(fight, root_manifest)
    plans = initial_plans(fight, sources)
    if plans:
        previous = dict(getattr(fight, "native_npc_initialization_receipts", {}))
        if set(previous) & set(plans):
            raise ValueError("Rift NPC initial states were already initialized")
        initialize_ordinary_npcs(fight, sources, plans)
        fight.native_npc_initialization_receipts = {
            **previous,
            **fight.native_npc_initialization_receipts,
        }


def creation_packets(
    monster, fight_id, *, obstacle_id, group_id, direction=3, actor=None, fight=None
):
    """Return ordered appearance and fight admission for an owned ordinary NPC.

    The caller registers the actor and its obstacle in the same authoritative
    fight before publishing these packets. Monster identity/reference and base
    characteristics must come from the existing owned monster catalog.
    """
    direction = direction if actor is None else actor.direction
    appearance = spawn_monster(
        monster,
        group_id=group_id,
        direction=direction,
        fighter=actor,
        fight=fight,
    )
    stats = monster_actor_stats(
        monster,
        fight_id,
        direction=direction,
        obstacle_id=obstacle_id,
    )
    effects = actor_effects()
    if actor is not None:
        from wakfu_server.combat_actor import actual_monster_actor_stats
        from wakfu_server.combat_remote_effects import active_actor_effects

        if (
            fight is None
            or fight.id != fight_id
            or fight.actors.get(actor.id) is not actor
        ):
            raise ValueError("Rift creation snapshot requires its owned actor")
        stats = actual_monster_actor_stats(
            monster,
            actor,
            fight_id,
            wp_current=actor.effect_stats[4],
            wp_maximum=actor.effect_maxima[4],
            direction=direction,
            fight=fight,
        )
        from wakfu_server.combat_input_observation import wall_time_ns

        effects = active_actor_effects(
            fight,
            actor.id,
            now_milliseconds=wall_time_ns("rift.birth.effect_snapshot") // 1000000,
        )
    admission = added(
        fight_id,
        monster["id"],
        actor_type=0,
        team=monster["team"] if actor is None else actor.team,
        stats=stats,
        effects=effects,
        controller=None,
    )
    return ((12608, appearance), admission)


def prepare_wave_npcs(monsters, *, catalog=None, team=1):
    """Prepare exact ordinary NPC resources and snapshots from native curves."""
    from wakfu_server.combat_state import Actor
    from wakfu_server.combat_actor_snapshot import (
        native_npc_creation_values,
        build_npc_snapshot,
    )

    if type(team) is not int or team not in (0, 1):
        raise ValueError("Reviewed ordinary wave constructor team required")
    monsters = list(monsters)
    identities = [monster.get("id") for monster in monsters]
    positions = [
        tuple(monster.get(key) for key in ("x", "y", "z")) for monster in monsters
    ]
    if (
        not monsters
        or len(set(identities)) != len(identities)
        or any(type(uid) is not int or uid >= 0 for uid in identities)
        or len(set(positions)) != len(positions)
        or any(any(type(value) is not int for value in p) for p in positions)
    ):
        raise ValueError("Invalid fresh rift NPC identities or positions")
    from wakfu_server.combat_npc_initialization import (
        initial_property_counts,
        install_initial_properties,
    )

    properties = initial_property_counts(
        {monster["id"]: monster for monster in monsters}
    )
    actors = []
    for monster, position in zip(monsters, positions):
        values = native_npc_creation_values(
            monster["ref"], monster["level"], catalog=catalog
        )
        actor = Actor(
            monster["id"],
            team,
            position,
            values[1]["current"],
            values[2]["current"],
            values[3]["current"],
            values[35]["current"],
            monster["level"],
            max_hp=values[1]["maximum"],
            direction=3,
        )
        build_npc_snapshot(
            monster,
            actor,
            wp_current=values[4]["current"],
            wp_maximum=values[4]["maximum"],
            running_effects=(),
            catalog=catalog,
        ).install(actor)
        install_initial_properties(actor, properties[actor.id])
        actors.append(actor)
    return actors


def install_native_wave(
    fight, monsters, *, initialize_actor, initialize_wave=None, catalog=None
):
    """Install on a detached accepted-command preview; caller discards failures.

    Initializer must preinstall all new ordinary monster sources and run the
    same innate creation path as initial NPCs, returning initialization packets.
    The optional batch initializer runs after every actor is registered, before
    any snapshot is serialized. Its packets follow all birth packets so native
    state applications cannot address an actor the client has not created yet.
    """
    from wakfu_server.combat_qi_fight import current_registry
    from wakfu_server.combat_global_pv_collections import register_global_fighter
    from wakfu_server.combat_timeline_snapshot import insert
    from wakfu_server.rift_combat_adapter import acknowledge_wave

    state = getattr(fight, "rift_wave_state", None)
    if (
        not callable(initialize_actor)
        or (initialize_wave is not None and not callable(initialize_wave))
        or fight.phase != "active"
        or not isinstance(state, dict)
        or not state.get("pending_wave")
    ):
        raise ValueError("Native rift admission requires a pending accepted wave")
    monsters = list(monsters)
    from wakfu_server.combat_encounter_roles import assigned_roles

    actors = prepare_wave_npcs(
        monsters, catalog=catalog, team=assigned_roles(fight).npc_team
    )
    from .combat_spawn_facing import toward_nearest

    targets = tuple(
        (member.id, member.position)
        for member in fight.actors.values()
        if member.team != actors[0].team and member.hp > 0 and fight._in_play(member)
    )
    for actor in actors:
        actor.direction = toward_nearest(actor.position, targets)
    from wakfu_server.combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    visible_count = len(fight.actors) - len(hidden_snapshot_actor_ids(fight))
    if visible_count + len(actors) > 127:
        raise ValueError("Native rift visible fighter capacity exhausted")
    occupied = {a.position for a in fight.actors.values() if fight._in_play(a)}
    if any(
        a.id in fight.actors
        or a.position not in fight.walkable
        or a.position in occupied
        for a in actors
    ):
        raise ValueError("Rift NPC placement collides with current fight")
    # big.a(eGH.cle) runs while the constructor PV is detached. Its original
    # effects may query QI (including visibility-property callbacks), so do not
    # publish a slot, fdy entry or timeline row until that constructor returns.
    # Complete each admission before the next constructor, as companion entry
    # does: earlier actors are real registered PVs, later actors are not yet born.
    base = getattr(fight, "native_base_turn_order", None)
    for actor, monster in zip(actors, monsters):
        fight.actors[actor.id] = actor
        try:
            initialize_native_wave_actors(fight, (monster,))
        finally:
            del fight.actors[actor.id]
        registry = current_registry(fight)
        if hasattr(fight, "native_pointer_checkpoint"):
            if actor.native_obstacle_id is None:
                actor.native_obstacle_id = -1
            slot = registry.register_constructor_actor(actor)
        else:
            slot = registry.register(
                dict(
                    identity=["actor", actor.id],
                    position=list(actor.position[:2]),
                    radius=actor.physical_radius,
                    indexed=False,
                    movement_blocking=True,
                )
            )
        if slot < 0:
            raise ValueError("Native rift QI population exhausted")
        actor.native_obstacle_id = slot
        if hasattr(fight, "native_pointer_checkpoint"):
            from wakfu_server.combat_carrying import _publish_registry

            _publish_registry(fight, registry)
        else:
            fight.native_qi_slots = registry.serialized_slots()
            fight.native_qi_touched_cells = registry.serialized_cells()
            fight.native_qi_byte_topology = registry.serialized_byte_topology()
        fight.actors[actor.id] = actor
        register_global_fighter(fight, actor.id)
        # Explicit DEV policy: append wave reinforcements to remaining turns.
        if 114 not in actor.native_fight_properties:
            insert(fight, actor.id, len(fight.order))
            fight.order.append(actor.id)
            if base is not None:
                base.append(actor.id)
    batch_packets = (
        ()
        if initialize_wave is None
        else tuple(initialize_wave(fight, tuple(actors), tuple(monsters)))
    )
    packets, creations = [], {}
    for actor, monster in zip(actors, monsters):
        initialization_packets = initialize_actor(fight, actor, monster)
        actor_packets = creation_packets(
            monster,
            fight.id,
            obstacle_id=actor.native_obstacle_id,
            group_id=state.get("world_group_id", fight.id),
            actor=actor,
            fight=fight,
        )
        creations[actor.id] = actor_packets
        packets.extend(actor_packets)
        packets.extend(initialization_packets)
    packets.extend(batch_packets)
    acknowledge_wave(
        fight,
        [a.id for a in actors],
        creations,
        species_refs=[monster["ref"] for monster in monsters],
    )
    return packets
