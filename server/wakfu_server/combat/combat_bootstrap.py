"""Own-state fight placement packet construction; no captured fight replay.

World actor appearances must already have been registered for every participant.
Terrain effect template is an explicit current-client reference supplied by caller.
"""
import struct
from .combat_wire import bootstrap, topology, initial_timeline
from .combat_turns import initial_order
from .combat_actor import actor_stats, actor_effects
from .combat_orientation import INITIAL_PLAYER_DIRECTION


def should_rebuild_placement(fight, admitted_actors):
    """Refresh constructor snapshots even when no hero joined the initial fight."""
    return bool(
        admitted_actors
        or getattr(fight, "native_npc_initialization_receipts", {})
        or getattr(fight, "native_npc_ai_actors", frozenset())
        or getattr(fight, "native_dungeon_scaling_receipt", None)
    )


def placement_positions(fight, immediate=True):
    actors = list(fight.actors.values())
    if len(actors) > 32767:
        raise ValueError("Too many placement actors")
    return (
        struct.pack(">ih", fight.id, len(actors))
        + b"".join(struct.pack(">qiih", a.id, *a.position) for a in actors)
        + bytes([bool(immediate)])
    )


def placement_messages(
    fight,
    arena,
    actor_payloads,
    *,
    terrain_effect_id,
    terrain_instance_id,
    leaders,
    kind=2,
    duration_ms=60000
):
    """Validated placement envelopes; actor_payloads ID->(native myE,myF).

    myE/F must come from own actor codecs, including distinct NPC format. This
    explicit mapping prevents treating NPCs as player-character serializers.
    """
    if fight.phase != "placement" or set(actor_payloads) != set(fight.actors):
        raise ValueError("Bootstrap requires exact own placement actors")
    if kind not in (2, 14) or not 0 < duration_ms < 2**31:
        raise ValueError("Unsupported fight mode or placement duration")
    if set(leaders) != {0, 1} or any(
        leaders[t] not in fight.actors or fight.actors[leaders[t]].team != t
        for t in leaders
    ):
        raise ValueError("Invalid own team leaders")
    if (
        type(terrain_effect_id) is not int
        or terrain_effect_id <= 0
        or type(terrain_instance_id) is not int
    ):
        raise ValueError("Invalid terrain effect template or own instance")
    if arena["map_id"] <= 0 or any(
        a.position not in fight.walkable for a in fight.actors.values()
    ):
        raise ValueError("Invalid fight arena placement")
    actors = list(fight.actors.values())
    order = initial_order(
        fight.id,
        [
            dict(
                id=a.id,
                team=a.team,
                initiative=a.initiative,
                effective_level=a.effective_level,
            )
            for a in actors
        ],
    )
    participants = []
    for actor in actors:
        stats, effects = actor_payloads[actor.id]
        if actor.id in getattr(
            fight, "native_npc_initialization_receipts", {}
        ) or actor.id in getattr(fight, "native_dungeon_scaling_receipt", {}).get(
            "actor_ids", ()
        ):
            from .combat_remote_effects import initial_npc_actor_effects

            import time

            effects = initial_npc_actor_effects(
                fight, actor.id, now_milliseconds=time.time_ns() // 1000000
            )
        participants.append(
            dict(
                actor_id=actor.id,
                myB=0 if actor.controlled else 1,
                myn=actor.team,
                myC=1,
                myE=stats,
                myF=effects,
            )
        )
    from .combat_environment_glyphs import environment_sections

    value = dict(
        fight_id=fight.id,
        kind=kind,
        bqh=arena["map_id"],
        myo=terrain_effect_id,
        myp=terrain_instance_id,
        myD=topology(arena),
        myG=initial_timeline([a.id for a in actors], order),
        myI=leaders[0],
        myJ=leaders[1],
        compact=False,
        participants=participants,
        myH=[],
        myM=[],
        myN=[],
        myK=environment_sections(fight),
    )
    messages = [
        (13652, placement_positions(fight)),
        (12847, bootstrap(value)),
        (13684, struct.pack(">ii", fight.id, duration_ms)),
        (13026, struct.pack(">i", fight.id)),
    ]
    # cvb.eHb -> ckP -> buS.a -> fcz.Tv consumes this exact wire byte.
    fight.native_fight_model = kind
    return messages


def player_payload(character, actor, fight_id, *, wp):
    if not actor.controlled or actor.id != character["id"]:
        raise ValueError("Own player actor identity mismatch")
    snapshot = dict(
        character,
        x=actor.position[0],
        y=actor.position[1],
        z=actor.position[2],
        hp=actor.hp,
        max_hp=actor.max_hp,
    )
    return (
        actor_stats(
            snapshot,
            fight_id,
            actor.team,
            direction=actor.direction,
            obstacle_id=actor.native_obstacle_id,
            wp=wp,
            ap=actor.max_ap,
            mp=actor.max_mp,
            initiative=actor.initiative,
        ),
        actor_effects(),
    )


def create_placement(
    character,
    monster,
    arena,
    *,
    fight_id,
    player_ap,
    player_mp,
    player_wp,
    player_initiative,
    terrain_effect_id,
    terrain_instance_id,
    placement_cells=None,
    duration_ms=60000
):
    """Combine authoritative local PC/NPC state into FSM and placement messages.

    No universal racial WP default: caller supplies its verified value. Monster
    reference/level statistics come from monsters.owned_instance, not a capture.
    """
    from .combat_state import Actor, Fight
    from .combat_actor import monster_actor_stats
    from wakfu_server.monsters import owned_instance

    members = list(monster) if isinstance(monster, (list, tuple)) else [monster]
    if not members:
        raise ValueError("Monster group must not be empty")
    owned_instance_id = character.get("instance_id", 0)
    if type(owned_instance_id) is not int or not 0 <= owned_instance_id < 2**63:
        raise ValueError("Invalid authoritative character instance")
    for member in members:
        verified = owned_instance(
            member["ref"],
            member["level"],
            member["id"],
            map_id=member["map_id"],
            x=member["x"],
            y=member["y"],
            z=member["z"],
            team=1,
            instance_id=member["instance_id"],
        )
        if member != verified:
            raise ValueError("Monster state differs from its verified own reference")
        if member["instance_id"] != owned_instance_id:
            raise ValueError("Fight actors belong to a different owned instance")
        if member["map_id"] != arena["map_id"]:
            raise ValueError("Fight actors belong to a different map")
    if character["map_id"] != arena["map_id"]:
        raise ValueError("Fight actors belong to a different map")
    from wakfu_server.builds import effective_sheet_level

    effective_level = effective_sheet_level(
        character, character.get("active_build_index", 0)
    )
    pc = Actor(
        character["id"],
        0,
        (character["x"], character["y"], character["z"]),
        character["hp"],
        player_ap,
        player_mp,
        player_initiative,
        effective_level,
        character["account_id"],
        True,
        max_hp=character["max_hp"],
        direction=INITIAL_PLAYER_DIRECTION,
    )
    relocations = arena.get("participant_positions", [])
    if relocations and (
        len(relocations) != len(members)
        or [tuple(pair[0]) for pair in relocations]
        != [(m["x"], m["y"], m["z"]) for m in members]
    ):
        raise ValueError("Encounter relocation does not match verified monster roster")
    npc_positions = (
        [tuple(pair[1]) for pair in relocations]
        if relocations
        else [(m["x"], m["y"], m["z"]) for m in members]
    )
    npcs = [
        Actor(
            member["id"],
            1,
            position,
            member["hp"],
            member["ap"],
            member["mp"],
            member["initiative"],
            member["level"],
            max_hp=member["max_hp"],
            direction=3,
        )
        for member, position in zip(members, npc_positions)
    ]
    # Read selected terrain cells from the serialized mask rectangle. Actual
    # altitudes must be supplied by caller; one position per selected XY.
    cells = arena.get("validated_cells")
    if cells is None:
        raise ValueError("Arena needs prevalidated client topology cells")
    if placement_cells is None:
        placement_cells = arena.get("placement_cells")
    if placement_cells is None:
        placement_cells = {0: {pc.position}, 1: {npc.position for npc in npcs}}
    from .combat_geometry_snapshot import freeze_terrain

    fight = Fight(
        fight_id, [pc, *npcs], cells, placement_cells, arena.get("valid_edges")
    )
    from .combat_cosmetic_conditions import initialize_fresh_player_cosmetics

    initialize_fresh_player_cosmetics(pc, character)
    from .combat_global_pv_collections import initialize_global_pv_collections

    # This is the participant order serialized by placement_messages, hence
    # the actual fresh client fdt registration order rather than initiative.
    initialize_global_pv_collections(
        fight, tuple(fight.actors), controller_registration=True
    )
    # QI.P reads the serialized terrain mask, so retain only a plain copy of
    # the actual mask rectangle. Missing arena fields stay unknown; partial
    # serialized QI authority is rejected instead of padded or reconstructed.
    qi_names = ("x", "y", "width", "height", "cell_masks")
    present_qi_names = set(qi_names) & set(arena)
    if not present_qi_names:
        fight.native_qi_snapshot = None
    elif present_qi_names != set(qi_names):
        raise ValueError("Incomplete serialized native QI arena snapshot")
    else:
        from .combat_qi_snapshot import NativeQISnapshot

        qi_source = {name: arena[name] for name in qi_names}
        qi_validated = NativeQISnapshot(qi_source)
        fight.native_qi_snapshot = {
            "x": qi_validated.x,
            "y": qi_validated.y,
            "width": qi_validated.width,
            "height": qi_validated.height,
            "cell_masks": list(qi_validated.masks),
        }
    freeze_terrain(fight)
    if arena.get("native_border_policy") is not None:
        # The QI actor registration boundary must remain empty until ordinary
        # actor snapshots have installed. The first runtime then registers
        # the same faP clone as the placement cvb consumer.
        fight.native_border_constructor = dict(
            reference=terrain_effect_id,
            identity=terrain_instance_id,
            arena={
                key: arena[key]
                for key in ("native_border_policy", "native_border_cells", "min_z")
            },
        )
    from .combat_environment_glyphs import prepare_environment_glyphs

    prepare_environment_glyphs(fight, arena, terrain_instance_id)
    provenance = arena.get("native_qi_surface_provenance")
    if provenance is not None:
        from .combat_qi_surface_catalog import native_qi_surface_provenance

        expected_provenance = native_qi_surface_provenance(arena["map_id"])
        if provenance != expected_provenance:
            raise ValueError("Arena native QI surface provenance mismatch")
        fight.native_qi_surface_provenance = dict(provenance)
    # QL obstacle occupancy is serialized separately from terrain masks and
    # placement teams. Only the explicitly empty owned table proves no QI.V
    # obstacles; absence or populated unknown entries remain unavailable.
    fight.native_obstacle_cells = (
        frozenset() if arena.get("team_values") == [] else None
    )
    payloads = {pc.id: player_payload(character, pc, fight_id, wp=player_wp)}
    payloads.update(
        {
            member["id"]: (
                monster_actor_stats(
                    {
                        **member,
                        **dict(
                            zip(("x", "y", "z"), fight.actors[member["id"]].position)
                        ),
                    },
                    fight_id,
                    direction=3,
                    obstacle_id=fight.actors[member["id"]].native_obstacle_id,
                ),
                actor_effects(),
            )
            for member in members
        }
    )
    messages = placement_messages(
        fight,
        arena,
        payloads,
        terrain_effect_id=terrain_effect_id,
        terrain_instance_id=terrain_instance_id,
        leaders={0: pc.id, 1: npcs[0].id},
        duration_ms=duration_ms,
    )
    return fight, messages


def target_position(monster, position=None):
    """ctH13249 clears the target renderer path and sets its world cell.

    This has no accept/reject status field. Send before fight creation when an
    attack freezes/repositions an owned NPC, matching observed13130 sequence.
    """
    position = (
        tuple(position)
        if position is not None
        else (monster["x"], monster["y"], monster["z"])
    )
    return (13249, struct.pack(">qiih", monster["id"], *position))
