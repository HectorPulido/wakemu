"""Restore ordinary PvE NPC objects before an owned combat bootstrap.

Exploration snapshots exclude claimed monster groups. A fresh client therefore
needs their native appearances before cvb can resolve combat participants.
This projection does not release the group or modify the shared fight.
"""


def ordinary_npc_appearances(fight, shared):
    if getattr(fight, "rift_wave_state", None) is not None:
        return ()  # Rift snapshots own their current wave appearances.
    context = shared.join_context
    if not isinstance(context, dict) or "monsters" not in context:
        return ()  # Friendly duels have no monster-group authority.
    monsters = context["monsters"]
    if not isinstance(monsters, dict):
        raise ValueError("Reconnect monster metadata must be an owned mapping")
    from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    hidden = hidden_snapshot_actor_ids(fight)
    registrations = getattr(fight, "native_summon_registrations", {})
    actors = [
        actor
        for actor in fight.actors.values()
        if not actor.controlled
        and actor.id not in registrations
        and actor.id not in hidden
    ]
    if {actor.id for actor in actors} - monsters.keys():
        raise ValueError("Reconnect is missing original NPC appearance authority")
    if not actors:
        return ()
    group_key = context.get("group_key")
    if (
        not isinstance(group_key, (tuple, list))
        or len(group_key) != 3
        or tuple(group_key[:2]) != (shared.map_id, shared.instance_id)
        or type(group_key[2]) is not int
        or not 0 < group_key[2] < 2**63
    ):
        raise ValueError("Reconnect lacks the claimed NPC group identity")
    from wakfu_server.monsters import owned_instance
    from .combat_monster_world import spawn_group

    members = []
    for actor in actors:
        original = monsters[actor.id]
        if (
            original.get("id") != actor.id
            or original.get("map_id") != shared.map_id
            or original.get("instance_id") != shared.instance_id
            or original.get("team") != actor.team
        ):
            raise ValueError("Reconnect NPC identity differs from its owned group")
        members.append(
            owned_instance(
                original["ref"],
                original["level"],
                actor.id,
                map_id=shared.map_id,
                instance_id=shared.instance_id,
                x=actor.position[0],
                y=actor.position[1],
                z=actor.position[2],
                team=actor.team,
            )
        )
    return ((12608, spawn_group(members, group_id=group_key[2])),)
