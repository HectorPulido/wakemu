"""Opt-in, serializable rift wave boundaries inside one ordinary fight.

This module stages gameplay facts only. The accepted command transaction must
install native NPC authority, publish creation packets and persist the receipt
before admitting another command. No database or network work runs in previews.
"""

from wakfu_server.combat_encounter_roles import assigned_roles


def _state(fight):
    state = getattr(fight, "rift_wave_state", None)
    if state is None:
        return None
    if (
        not isinstance(state, dict)
        or type(state.get("instance_id")) is not int
        or state["instance_id"] <= 0
        or type(state.get("wave")) is not int
        or state["wave"] < 1
        or type(state.get("turn_budget")) is not int
        or state["turn_budget"] < 1
    ):
        raise ValueError("Missing frozen rift combat policy")
    return state


def defer_wave_victory(fight, alive):
    """Stage a cleared wave instead of settling the fight or paying loot."""
    state = _state(fight)
    if state is None or alive != {assigned_roles(fight).player_team}:
        return False
    pending = state.get("pending_wave")
    if pending is not None:
        if pending.get("completed_wave") != state["wave"]:
            raise ValueError("Stale pending rift wave")
        return True
    enemies = [
        actor.id
        for actor in fight.actors.values()
        if actor.team == assigned_roles(fight).npc_team
    ]
    if not enemies or any(fight._in_play(fight.actors[uid]) for uid in enemies):
        raise ValueError("Rift wave is not cleared")
    # Initial identities and later wave identities remain registered for native
    # corpse/effect references. Only this wave belongs in its durable receipt.
    identities = state.get("wave_actor_ids", state.get("current_actor_ids", enemies))
    if (
        not isinstance(identities, (list, tuple))
        or not identities
        or len(set(identities)) != len(identities)
        or any(uid not in enemies for uid in identities)
    ):
        raise ValueError("Missing exact rift wave roster")
    state["pending_wave"] = dict(
        completed_wave=state["wave"],
        actor_ids=list(identities),
        turn=fight.native_timeline_round,
    )
    fight._event("rift_wave_cleared", wave=state["wave"], actor_ids=list(identities))
    return True


def acknowledge_wave(fight, actor_ids, creation_packets, *, species_refs):
    """Commit a native-provider-installed wave; never construct fake NPCs.

    Caller installs complete ordinary NPC snapshots, QI/global registration,
    authority sources and timeline before calling. Exact creation deliveries
    are retained for observers and reconnect instead of inferring summon data.
    """
    state = _state(fight)
    if state is None or fight.phase != "active" or not state.get("pending_wave"):
        raise ValueError("No pending rift wave admission")
    identities = list(actor_ids)
    packets = dict(creation_packets)
    references = list(species_refs)
    if (
        not identities
        or len(set(identities)) != len(identities)
        or set(packets) != set(identities)
        or len(references) != len(identities)
        or any(type(reference) is not int or reference <= 0 for reference in references)
        or set(identities) & set(state["pending_wave"]["actor_ids"])
    ):
        raise ValueError("Invalid next rift roster")
    deliveries = {}
    for identity in identities:
        actor = fight.actors.get(identity)
        actor_packets = packets[identity]
        if (
            actor is None
            or actor.team != assigned_roles(fight).npc_team
            or actor.controlled
            or not fight._in_play(actor)
            or identity not in fight.order
            or actor.effect_stats is None
            or actor.physical_radius is None
            or not isinstance(actor_packets, (tuple, list))
            or not actor_packets
            or any(
                not isinstance(packet, (tuple, list))
                or len(packet) != 2
                or type(packet[0]) is not int
                or not isinstance(packet[1], bytes)
                or not packet[1]
                for packet in actor_packets
            )
        ):
            raise ValueError("Missing native rift NPC creation authority")
        deliveries[identity] = [
            dict(opcode=packet[0], payload_hex=packet[1].hex())
            for packet in actor_packets
        ]
    receipts = state.setdefault("staged_receipts", [])
    if not isinstance(receipts, list):
        raise ValueError("Invalid staged rift receipts")
    existing = getattr(fight, "native_rift_creation_deliveries", {})
    if set(existing) & set(deliveries):
        raise ValueError("Rift actor identity was reused")
    receipts.append(
        dict(
            state["pending_wave"],
            next_actor_ids=identities,
            next_species_refs=references,
        )
    )
    state["wave"] += 1
    state["current_actor_ids"] = identities
    state["wave_actor_ids"] = identities
    state["wave_species_refs"] = references
    state["pending_wave"] = None
    fight.native_rift_creation_deliveries = {**existing, **deliveries}
    fight._event("rift_wave_started", wave=state["wave"], actor_ids=identities)


def finish_survival(fight):
    """Finish after the complete configured number of timeline rounds."""
    state = _state(fight)
    if state is None or fight.native_timeline_round <= state["turn_budget"]:
        return False
    alive = {a.team for a in fight.actors.values() if fight._in_play(a)}
    fight.phase = "finished"
    roles = assigned_roles(fight)
    fight.winner = (
        roles.player_team
        if roles.player_team in alive
        else (roles.npc_team if roles.npc_team in alive else None)
    )
    state["outcome"] = "survived" if fight.winner == roles.player_team else "defeated"
    fight._event("finished", winner=fight.winner, reason="rift_turn_budget")
    return True


def finish_defeat(fight, alive):
    """Wakemu survival policy: no surviving player side is a Rift loss.

    Actual outer death reconciliation supplies native IN_PLAY teams. A
    mutually lethal chain must settle as loss, rather than leaving an
    unpayable winner-less terminal fight. Ordinary/duel draws stay unchanged.
    """
    state = _state(fight)
    if state is None or assigned_roles(fight).player_team in alive:
        return False
    roles = assigned_roles(fight)
    fight.phase = "finished"
    fight.winner = roles.npc_team
    state["outcome"] = "defeated"
    if "pending_wave" in state:
        state["pending_wave"] = None
    fight._event("finished", winner=fight.winner, reason="rift_no_surviving_players")
    return True


def creation_replay(fight, *, world_only=False):
    """Replay stored births before a snapshot, without changing server state.

    A complete fight bootstrap already admits its participants. For that path
    use world_only=True BEFORE bootstrap: ordinary NPC avatars must exist, but
    replaying 13091 afterward would admit them twice. Incremental peers missing
    the roster consume the complete ordered pair followed by current stats.
    """
    import struct

    records = getattr(fight, "native_rift_creation_deliveries", {})
    if not isinstance(records, dict):
        raise ValueError("Invalid rift creation replay ledger")
    from wakfu_server.combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    hidden = hidden_snapshot_actor_ids(fight)
    packets = []
    for identity, deliveries in records.items():
        if type(identity) is not int or identity not in fight.actors:
            raise ValueError("Rift creation replay actor is missing")
        if not isinstance(deliveries, list) or len(deliveries) != 2:
            raise ValueError("Missing exact rift world and admission deliveries")
        restored = []
        for row, opcode in zip(deliveries, (12608, 13091)):
            if not isinstance(row, dict) or row.get("opcode") != opcode:
                raise ValueError("Invalid rift creation replay opcode")
            try:
                payload = bytes.fromhex(row["payload_hex"])
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("Invalid rift creation replay payload") from error
            restored.append((opcode, payload))
        world = restored[0][1]
        admission = restored[1][1]
        if (
            len(world) < 11
            or world[:3] != b"\x00\x01\x01"
            or struct.unpack_from(">q", world, 3)[0] != identity
            or len(admission) < 12
            or struct.unpack_from(">iq", admission)[0:2] != (fight.id, identity)
        ):
            raise ValueError("Rift replay delivery belongs to another actor or fight")
        if identity not in hidden:
            packets.extend(restored[:1] if world_only else restored)
    return tuple(packets)


def world_snapshot(fight):
    """Create current ordinary rift avatars before a complete fight bootstrap."""
    import struct
    from wakfu_server.monsters import owned_instance
    from wakfu_server.combat_monster_world import world_actor

    state = _state(fight)
    if state is None:
        return ()
    sources = getattr(fight, "rift_monsters", None)
    if not isinstance(sources, dict):
        raise ValueError("Rift world snapshot lacks native monster sources")
    from wakfu_server.combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    hidden = hidden_snapshot_actor_ids(fight)
    packets = []
    for identity, source in sources.items():
        actor = fight.actors.get(identity)
        if (
            actor is None
            or actor.controlled
            or actor.team != assigned_roles(fight).npc_team
        ):
            raise ValueError("Rift world snapshot roster changed")
        if identity in hidden:
            continue
        monster = owned_instance(
            source["ref"],
            source["level"],
            identity,
            map_id=source["map_id"],
            instance_id=source["instance_id"],
            x=actor.position[0],
            y=actor.position[1],
            z=actor.position[2],
        )
        blob = world_actor(
            monster,
            group_id=state.get("world_group_id", fight.id),
            direction=actor.direction,
            dead=actor.hp <= 0,
        )
        packets.append(
            (12608, b"\x00\x01" + struct.pack(">BqH", 1, identity, len(blob)) + blob)
        )
    return tuple(packets)
