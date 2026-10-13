"""Native cvK12727 death animation from authoritative own fight state."""
import struct


def newly_registered_death_messages(runtime, *, after_sequence):
    """Deliver settled deaths from one private action, once per actor identity."""
    if type(after_sequence) is not int or after_sequence < 0:
        raise ValueError("Actual pre-action death sequence required")
    identities = []
    reported = getattr(runtime, "_reported_deaths", set())
    for event in runtime.fight.events:
        if event["sequence"] <= after_sequence or event.get("kind") != "death":
            continue
        identity = event["actor_id"]
        actor = runtime.fight.actors.get(identity)
        # A reaction may legitimately resurrect the defeated actor before the
        # outer action settles. Do not replay its stale death over the revival.
        if actor is None:
            raise ValueError("Registered death recipient is missing")
        if actor.hp == 0 and identity not in reported and identity not in identities:
            identities.append(identity)
    packets = []
    for identity in identities:
        packets.extend(runtime.prepare_delivery(death_messages(runtime, identity)))
    return packets


def death_messages(runtime, actor_id, *, fighter_state=None):
    """NPC state0 removes the timeline member before state2/AnimMort.

    Official dungeon captures send state0 then state2 for each dead NPC.
    aTS.cbj immediately calls D for state0; state2 defers that call until its
    animation callback. Sending only state2 lets the next-turn action overtake
    timeline removal. Controlled player death defaults to reversible state0, matching OFF_PLAY and
    the retained resurrection QI slot. Explicit state2 finalizes any ordinary
    registered fighter, including players; HP0 alone does not request finality.
    State0 is KO, state1 resurrection, state3 another removal mode. Only
    actual HP-zero actors belonging to this fight can receive a death event.
    Send after the lethal damage action and before normal fight results.
    """
    actor = runtime.fight.actors.get(actor_id)
    if actor is None or actor.hp != 0:
        raise ValueError("Death requires an owned zero-HP fight actor")
    pending_restoration = False
    if fighter_state is None and not actor.controlled:
        from .combat_pending_restoration import pending_restoration_uids

        pending_restoration = bool(pending_restoration_uids(runtime.fight, actor_id))
    if pending_restoration:
        fighter_state = 0
    if fighter_state is None:
        fighter_state = (
            0
            if actor.controlled and getattr(actor, "native_summon_source", None) is None
            else 2
        )
    if type(fighter_state) is not int or fighter_state not in (0, 2):
        raise ValueError("Death delivery requires native KO0 or final state2")
    sent = getattr(runtime, "_reported_deaths", set())
    status = getattr(actor, "native_death_status", {})
    writer = status.get("last_writer") if isinstance(status, dict) else None
    previous_state = (
        0
        if writer == "owned.aTS.F.type0"
        else 2
        if writer == "owned.aTS.F.type2"
        else None
    )
    if (actor_id in sent or previous_state is not None) and not (
        fighter_state == 2 and previous_state == 0
    ):
        raise ValueError("Death was already reported")
    # Explicit withdrawal is a different native source: QI.g/fdt.bx already
    # retired the fighter before HP changes, so it is not a damage corpse.
    departed = False
    if getattr(actor, "pve_withdrawn", False):
        from .combat_pve_departure import retired_pve_actor_ids

        departed = actor_id in retired_pve_actor_ids(runtime.fight)
        if departed and fighter_state != 2:
            raise ValueError("Retired PvE departure requires final fighter state2")
    if hasattr(runtime.fight, "native_global_pv_collections") and not departed:
        from .combat_ordinary_death import registered_ordinary_death

        if not registered_ordinary_death(runtime.fight, actor):
            raise ValueError("Death delivery requires a registered corpse")
    queued = getattr(runtime.fight, "native_finisher_after_death_packets", {})
    if not isinstance(queued, dict):
        raise ValueError("Malformed owned finisher post-death deliveries")
    cleanup = queued.get(str(actor_id), ())
    decoded = []
    for row in cleanup:
        if not isinstance(row, (tuple, list)) or len(row) != 2:
            raise ValueError("Malformed owned finisher cleanup delivery")
        opcode, payload_hex = row
        if opcode not in (12613, 13497, 13560) or not isinstance(payload_hex, str):
            raise ValueError("Unknown owned finisher cleanup delivery")
        payload = bytes.fromhex(payload_hex)
        if (
            len(payload) < 18
            or struct.unpack_from(">i", payload)[0] != runtime.fight.id
        ):
            raise ValueError("Finisher cleanup belongs to another fight")
        decoded.append((opcode, payload))
    # Preflight status writes before committing QI/global collection mutations.
    from copy import deepcopy
    from .combat_native_death_status import apply_native_fighter_state_transition

    status_preview = deepcopy(actor)
    apply_native_fighter_state_transition(status_preview, fighter_state)
    if fighter_state == 2:
        status_preview.native_death_status.pop("pending_restoration", None)
    if pending_restoration:
        from .combat_pending_restoration import SOURCE

        status_preview.native_death_status["pending_restoration"] = SOURCE
    from .combat_ordinary_qi_retirement import complete_ordinary_qi_death

    # Serialize every packet on a shallow runtime preview before committing.
    # _prefix only advances the preview's logical counter; QI remains private.
    from copy import copy

    wire_preview = copy(runtime)
    prefix = wire_preview._prefix()
    body = prefix + struct.pack(">qB", actor_id, fighter_state)
    flush = wire_preview._flush()
    packets = []
    if not actor.controlled and fighter_state == 2 and previous_state != 0:
        packets.append((12727, prefix + struct.pack(">qB", actor_id, 0)))
    packets.extend(((12727, body), flush))
    if decoded:
        packets.extend(decoded)
        packets.append(flush)
    if fighter_state == 2 and not departed:
        complete_ordinary_qi_death(runtime.fight, actor, fighter_state=2)
    actor.native_death_status = status_preview.native_death_status
    if hasattr(wire_preview, "action_id"):
        runtime.action_id = wire_preview.action_id
    runtime._reported_deaths = sent | {actor_id}
    if decoded:
        queued.pop(str(actor_id))
    return packets


def despawn_monster(fight, actor_id):
    """ctA12304: remove one owned dead NPC from exploration after12925.

    13082/cwH removes interactive objects; it cannot remove a world NPC.
    """
    actor = fight.actors.get(actor_id)
    if fight.phase != "finished" or actor is None or actor.controlled or actor.hp != 0:
        raise ValueError("Despawn requires a finished own fight and dead NPC")
    return (12304, b"\x00\x00\x01" + struct.pack(">Bq", 1, actor_id))


def dead_world_removals(fight, member_ids):
    """Remove this group's dead exploration actors after native12925 cleanup.

    Validation covers the entire roster before emitting anything. This does
    not finish a registry lease or schedule respawn: those are independent
    authoritative operations, and may already have occurred at victory.
    """
    from .combat_monster_world import remove_message

    identities = tuple(member_ids)
    if not identities or len(set(identities)) != len(identities):
        raise ValueError("Expected a unique owned group roster")
    if fight.phase != "finished":
        raise ValueError("World removal requires a resolved fight")
    dead = []
    for identity in identities:
        actor = fight.actors.get(identity)
        if actor is None or actor.controlled or identity >= 0:
            raise ValueError("Group roster contains a foreign or player actor")
        if actor.hp == 0:
            dead.append(identity)
    return [
        remove_message(dead[offset : offset + 255])
        for offset in range(0, len(dead), 255)
    ]
