"""Own-state fight placement packet construction; no captured fight replay.

World actor appearances must already have been registered for every participant.
Terrain effect template is an explicit current-client reference supplied by caller.
"""
import struct
from .combat_wire import bootstrap, topology, initial_timeline
from .combat_turns import initial_order
from .combat_actor import actor_stats, actor_effects


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
        myK=[],
    )
    return [
        (13652, placement_positions(fight)),
        (12847, bootstrap(value)),
        (13684, struct.pack(">ii", fight.id, duration_ms)),
        (13026, struct.pack(">i", fight.id)),
    ]


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
    placement_cells=None
):
    """Combine authoritative local PC/NPC state into FSM and placement messages.

    No universal racial WP default: caller supplies its verified value. Monster
    reference/level statistics come from monsters.owned_instance, not a capture.
    """
    from .combat_state import Actor, Fight
    from .combat_actor import monster_actor_stats
    from .monsters import owned_instance

    members = list(monster) if isinstance(monster, (list, tuple)) else [monster]
    if not members:
        raise ValueError("Monster group must not be empty")
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
        )
        if member != verified:
            raise ValueError("Monster state differs from its verified own reference")
        if member["map_id"] != arena["map_id"]:
            raise ValueError("Fight actors belong to a different map")
    if character["map_id"] != arena["map_id"]:
        raise ValueError("Fight actors belong to a different map")
    pc = Actor(
        character["id"],
        0,
        (character["x"], character["y"], character["z"]),
        character["hp"],
        player_ap,
        player_mp,
        player_initiative,
        character["level"],
        character["account_id"],
        True,
        max_hp=character["max_hp"],
    )
    npcs = [
        Actor(
            member["id"],
            1,
            (member["x"], member["y"], member["z"]),
            member["hp"],
            member["ap"],
            member["mp"],
            member["initiative"],
            member["level"],
            max_hp=member["max_hp"],
        )
        for member in members
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
    fight = Fight(
        fight_id, [pc, *npcs], cells, placement_cells, arena.get("valid_edges")
    )
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
                monster_actor_stats(member, fight_id, direction=3),
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
