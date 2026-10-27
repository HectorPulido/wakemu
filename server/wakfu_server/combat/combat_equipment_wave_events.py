"""Consumer-backed1048 reconstruction for an actual ordinary next-wave admission.

Installed Frenzy/Fury branches rebuild damage listeners over current fighters;
other installed rift consumers pair1048 with opening/new-fighter subscriptions.
The original server publisher is unavailable. This policy supplies1048 only to
qualified existing equipment owners and actual retained NPC-source managers
after an accepted native wave birth. It is
not a general summon/revival event and does not initialize Rift gameplay states.
"""

POLICY = "wakemu.equipment.registered-ordinary-wave-v1"


def deliver_registered_wave(dispatcher, *, actors, monsters, player_ids):
    fight = dispatcher.native_retention.fight
    state = getattr(fight, "rift_wave_state", None)
    pending = None if state is None else state.get("pending_wave")
    if not isinstance(pending, dict) or fight.phase != "active":
        raise ValueError(
            "Equipment wave boundary requires its actual pending ordinary wave"
        )
    wave = state["wave"] + 1
    old_ids = tuple(pending["actor_ids"])
    new_ids = tuple(actor.id for actor in actors)
    players = tuple(player_ids)
    from wakfu_server.rift_policy import select_wave
    from .combat_global_pv_collections import global_fighter_guards

    expected_refs = select_wave(state["catalog"], state["policy"], state["seed"], wave)
    from wakfu_server.combat_encounter_roles import assigned_roles

    roles = assigned_roles(fight)
    if (
        pending["completed_wave"] != state["wave"]
        or set(old_ids) != set(state["wave_actor_ids"])
        or any(
            uid not in fight.actors or fight._in_play(fight.actors[uid])
            for uid in old_ids
        )
        or not new_ids
        or len(set(new_ids)) != len(new_ids)
        or len(actors) != len(monsters)
        or tuple(source["ref"] for source in monsters) != expected_refs
        or not players
        or len(set(players)) != len(players)
        or any(
            uid not in fight.actors
            or not fight.actors[uid].controlled
            or fight.actors[uid].team != roles.player_team
            for uid in players
        )
    ):
        raise ValueError("Equipment wave facts differ from frozen ordinary roster")
    sources = getattr(fight, "rift_monsters", {})
    for actor, source in zip(actors, monsters):
        if (
            fight.actors.get(actor.id) is not actor
            or actor.controlled
            or actor.team != roles.npc_team
            or actor.id >= 0
            or actor.id in old_ids
            or source.get("id") != actor.id
            or sources.get(actor.id) != source
            or source.get("level") != actor.effective_level
            or source.get("instance_id") != state["instance_id"]
            or actor.native_obstacle_id is None
            or not global_fighter_guards(fight, actor.id)["baF"]
            or not fight._in_play(actor)
        ):
            raise ValueError(
                "Equipment wave lacks the actual registered fresh native NPC"
            )
    receipt = dict(
        policy=POLICY,
        wave=wave,
        completed_ids=list(old_ids),
        new_ids=list(new_ids),
        species_refs=list(expected_refs),
        players=list(players),
    )
    receipts = state.setdefault("equipment_wave_boundaries", {})
    previous = receipts.get(str(wave))
    if previous is not None:
        if previous != receipt:
            raise ValueError("Equipment wave replay changed its native identities")
        return ()
    receipts[str(wave)] = receipt
    from .combat_equipment_external_events import deliver_scoped_pairs
    from .combat_npc_external_event_scope import qualified_npc_uids
    from .combat_global_pv_collections import global_pv_iterator

    eligible = qualified_npc_uids(dispatcher)
    managers = {
        entry.manager_id
        for entry in dispatcher.native_retention.view().entries
        if entry.uid in eligible
    }
    # Preserve the original equipment recipients and order. Additional NPC-
    # origin managers may be fighters or Qq; they receive NPC scope only.
    recipients = list(players)
    for identity in global_pv_iterator(fight, caster_id=new_ids[0]):
        if identity in managers and identity not in recipients:
            recipients.append(identity)
    # fcd.v owns OUT_OF_PLAY/retired-manager exclusion. A retained program on
    # such a manager is not authority to manufacture an extra global recipient.

    return deliver_scoped_pairs(
        dispatcher,
        event_id=1048,
        recipients=tuple(
            (uid, channel) for uid in recipients for channel in (6, 60, 61)
        ),
        npc_sources=True,
        equipment_actor_ids=frozenset(players),
    )
