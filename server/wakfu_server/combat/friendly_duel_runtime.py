"""Construct owned player companies in a placement runtime for a consented duel."""
import secrets
import time
from .combat_orientation import INITIAL_PLAYER_DIRECTION


def prepare_and_register(
    store,
    adapter,
    db,
    fight_id,
    invitation,
    challenger,
    target,
    *,
    auto_locked,
    terrain_effect_id=46,
    prepared_terrain=None,
):
    """Build, serialize, and reserve a duel before the acceptance TX commits.

    The caller owns the active SQL transaction. All native data is derived
    from its locked character rows and the installed map topology. The return
    callback is safe only while the registry still contains its unpublished
    initial batch; callers use it to compensate a failed SQL commit.
    """
    from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
    from wakfu_server.combat_bootstrap import placement_messages
    from wakfu_server.combat_state import Actor, Fight
    from wakfu_server.combat_shared import Session
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_terrain import local_arena
    from wakfu_server.combat_geometry_snapshot import freeze_terrain
    from wakfu_server.combat_placement_policy import freeze
    from wakfu_server.equipment_stats import combat_resources

    if (
        not isinstance(invitation, dict)
        or not isinstance(challenger, dict)
        or not isinstance(target, dict)
    ):
        raise ValueError("Duel runtime requires owned invitation and characters")
    if type(auto_locked) is not bool:
        raise ValueError("Invalid duel lock policy")
    map_id, instance_id = invitation.get("map_id"), invitation.get("instance_id")
    if (
        type(map_id) is not int
        or map_id <= 0
        or type(instance_id) is not int
        or instance_id < 0
        or (challenger["map_id"], challenger.get("instance_id", 0))
        != (map_id, instance_id)
        or (target["map_id"], target.get("instance_id", 0)) != (map_id, instance_id)
    ):
        raise ValueError("Duel participants left the invitation location")

    duration_row = db.execute(
        "SELECT value FROM settings WHERE name='combat_placement_duration_ms'"
    ).fetchone()
    duration_ms = None if duration_row is None else duration_row["value"]
    if type(duration_ms) is not int or not 1000 <= duration_ms <= 300000:
        raise ValueError("Invalid PostgreSQL placement duration")

    from wakfu_server.combat_arena_policy import cell_budget

    selected = local_arena(
        map_id,
        fight_id,
        (challenger["x"], challenger["y"], challenger["z"]),
        [(target["x"], target["y"], target["z"])],
        relocate_monsters=challenger["account_id"] == target["account_id"],
        compact=True,
        minimum_dimensions=(30, 30),
        prepared_terrain=prepared_terrain,
        automatic_cell_budget=cell_budget(db),
    )
    from wakfu_server.combat_placement_cells import opposing_starts

    combat_positions = opposing_starts(
        selected["validated_cells"],
        selected["valid_edges"],
        selected["placement_cells"],
        avoid_cells=selected.get("native_border_cells", ()),
    )
    selected = dict(selected, participant_positions=[])
    arena = freeze(
        store,
        account_id=challenger["account_id"],
        generation=invitation["challenger_generation"],
        character_id=challenger["id"],
        fight_id=fight_id,
        map_id=map_id,
        instance_id=instance_id,
        selected_arena=selected,
        seeds={
            0: [combat_positions[0]],
            1: [combat_positions[1]],
        },
        db=db,
    )
    terrain_effect_id = arena["terrain_effect_id"]
    # A retry may reuse an already committed placement layout. Always derive
    # starts from that authoritative final layout, not the fresh proposal.
    combat_positions = opposing_starts(
        arena["validated_cells"],
        arena["valid_edges"],
        arena["placement_cells"],
        avoid_cells=arena.get("native_border_cells", ()),
    )

    from wakfu_server import territory_bonuses

    challenger = territory_bonuses.attach_character(db, challenger)
    target = territory_bonuses.attach_character(db, target)
    actors = []
    resources_by_actor = {}
    # Exterior DB rows remain unchanged. Snapshot producers receive owned
    # combat copies matching the actors' initial placement coordinates.
    characters = {}
    for character, team in ((challenger, 0), (target, 1)):
        combat_character = dict(character)
        combat_character.update(zip(("x", "y", "z"), combat_positions[team]))
        characters[character["id"]] = combat_character
        resources = combat_resources(character)
        resources_by_actor[character["id"]] = resources
        from wakfu_server.builds import effective_sheet_level

        actors.append(
            Actor(
                character["id"],
                team,
                combat_positions[team],
                character["hp"],
                resources["ap"],
                resources["mp"],
                resources["initiative"],
                effective_sheet_level(
                    character, character.get("active_build_index", 0)
                ),
                character["account_id"],
                True,
                max_hp=character["max_hp"],
                direction=INITIAL_PLAYER_DIRECTION,
            )
        )
    fight = Fight(
        fight_id,
        actors,
        arena["validated_cells"],
        arena["placement_cells"],
        arena.get("valid_edges"),
    )
    from wakfu_server.combat_qi_snapshot import NativeQISnapshot
    from wakfu_server.combat_global_pv_collections import (
        initialize_global_pv_collections,
    )
    from wakfu_server.combat_cosmetic_conditions import (
        initialize_fresh_player_cosmetics,
    )

    # The duel serializes the same cvb terrain and QK actor bytes as PvE.
    # Install its actual rectangle before the snapshot producer consumes the
    # fresh registration boundary; otherwise it cannot populate native QI.
    qi = NativeQISnapshot(
        {key: arena[key] for key in ("x", "y", "width", "height", "cell_masks")}
    )
    fight.native_qi_snapshot = dict(
        x=qi.x,
        y=qi.y,
        width=qi.width,
        height=qi.height,
        cell_masks=list(qi.masks),
    )
    initialize_global_pv_collections(
        fight, tuple(fight.actors), controller_registration=True
    )
    for actor in fight.actors.values():
        initialize_fresh_player_cosmetics(actor, characters[actor.id])
    provenance = arena.get("native_qi_surface_provenance")
    if provenance is not None:
        from wakfu_server.combat_qi_surface_catalog import native_qi_surface_provenance

        if provenance != native_qi_surface_provenance(map_id):
            raise ValueError("Arena native QI surface provenance mismatch")
        fight.native_qi_surface_provenance = dict(provenance)
    freeze_terrain(fight)
    fight.native_obstacle_cells = (
        frozenset() if arena.get("team_values") == [] else None
    )
    runtime = RuntimeMessages(fight)
    initialize_fight_snapshots(
        fight,
        characters=characters,
        monsters={},
        wp_resources={
            actor_id: (resources["wp"], resources["wp"])
            for actor_id, resources in resources_by_actor.items()
        },
        running_effects={actor_id: () for actor_id in characters},
        initial_effect_uid=1,
    )
    sessions = (
        Session(
            challenger["account_id"],
            challenger["id"],
            invitation["challenger_generation"],
            map_id,
            instance_id,
        ),
        Session(
            target["account_id"],
            target["id"],
            invitation["target_generation"],
            map_id,
            instance_id,
        ),
    )
    # Reuse ordinary atomic hero admission: durable membership is per actor,
    # while transport and input ownership remain the actual selected session.
    from wakfu_server.combat_heroes import admit_owned_heroes

    if challenger["account_id"] == target["account_id"]:
        # One real transport controls the two explicitly nominated opponents.
        # Never duplicate the same company onto both teams.
        sessions = sessions[:1]
    else:
        for session in sessions:
            admitted = admit_owned_heroes(db, store, session, fight)
            fight = admitted["fight"]
            characters.update(admitted["characters"])
    runtime.fight = fight
    payloads = {
        actor.id: adapter.actor_payload(
            fight,
            actor,
            next(
                session for session in sessions if session.account_id == actor.owner_id
            ),
        )
        for actor in fight.actors.values()
    }
    terrain_instance_id = secrets.randbelow(2**60) + 1
    packets = tuple(
        placement_messages(
            fight,
            arena,
            payloads,
            terrain_effect_id=terrain_effect_id,
            terrain_instance_id=terrain_instance_id,
            leaders={0: challenger["id"], 1: target["id"]},
            duration_ms=duration_ms,
        )
    )
    now = time.monotonic()
    context = {
        "arena": arena,
        "terrain_effect_id": terrain_effect_id,
        "terrain_instance_id": terrain_instance_id,
        "leaders": {0: challenger["id"], 1: target["id"]},
        "duration_ms": duration_ms,
        "monsters": {},
        "group_key": None,
        "fight_started_at": now,
        "actor_payload": adapter.actor_payload,
        "duel": True,
    }
    shared = adapter.register_duel(
        fight,
        sessions,
        runtime=runtime,
        auto_locked=auto_locked,
        initial_packets={session.account_id: packets for session in sessions},
        db=db,
        join_context=context,
    )
    shared.is_duel = True
    shared.initiated_at = now
    return {
        "fight": fight,
        "runtime": runtime,
        "shared": shared,
        "sessions": sessions,
        "duration_ms": duration_ms,
        "fight_started_at": now,
        "rollback": lambda: adapter.registry.unregister_unpublished(fight_id),
    }
