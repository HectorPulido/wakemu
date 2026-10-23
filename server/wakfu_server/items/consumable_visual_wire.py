"""Scoped original null-effect HMI lifecycle for owned transformations.

Only nodes qualified by consumable_visual_effects are published. Their native
class400 body has no gameplay operation, children or emitted events. The false
execution flag retains the runner and advances its original HMI phases through
the harmless null body. Other consumable runners keep their existing behavior.
"""
import struct


def _entries(character):
    from wakfu_server.consumable_visual_effects import select

    actor_id = character.get("id")
    if type(actor_id) is not int or not 0 < actor_id < 2**63:
        raise ValueError("Invalid native transformation owner")
    states = character.get("consumable_states", ())
    if not isinstance(states, (list, tuple)):
        raise ValueError("Invalid native transformation collection")
    ordered = sorted(
        states,
        key=lambda state: (
            state.get("metadata", {}).get("native_visual_applied_at_ms", 0),
            state.get("uid", 0),
        ),
    )
    entries = {}
    for state in ordered:
        selected = select(character, state)
        if not selected:
            continue
        uid, identity, level = (state.get(key) for key in ("uid", "state_id", "level"))
        remaining = state.get("remaining_ms")
        metadata = state["metadata"]
        stamp = metadata.get("native_visual_applied_at_ms")
        if (
            type(uid) is not int
            or not 0 < uid < 2**41
            or type(identity) is not int
            or not 0 < identity <= 32767
            or type(level) is not int
            or not 0 < level <= 32767
            or type(remaining) is not int
            or not 0 < remaining < 2**63
            or state.get("clock") not in ("wall", "online")
            or type(stamp) is not int
            or not 0 <= stamp < 2**63
        ):
            raise ValueError("Invalid owned native transformation lifetime")
        for effect in selected:
            effect_id = effect["id"]
            if not 0 < effect_id < 2**20:
                raise ValueError("Native visual definition exceeds owned UID layout")
            # Disjoint from ordinary bit62 display UIDs and inventory UIDs.
            visual_uid = (1 << 61) | (uid << 20) | effect_id
            if visual_uid in entries:
                raise ValueError("Duplicate owned native visual effect")
            entries[visual_uid] = (uid, identity, level, remaining, stamp, effect_id)
    return actor_id, entries


def _payload(actor_id, visual_uid, entry):
    from wakfu_server.combat_running_container import running_container_scope
    from wakfu_server.combat_stat_effects import owned_effect_payload
    from wakfu_server.combat_native_timing_context import native_time_payload

    uid, identity, level, remaining, _stamp, effect_id = entry
    with running_container_scope(
        {"container_present": True, "container_type": 1},
        (identity << 16) | level,
    ):
        return owned_effect_payload(
            uid=visual_uid,
            base_uid=uid,
            generic_effect=effect_id,
            caster_id=actor_id,
            target_id=actor_id,
            value=0,
            timing_payload=native_time_payload(realtime_remaining=remaining),
            executed=False,
        )


def _apply(actor_id, uid, entry, allocate_action):
    from wakfu_server.combat_stat_effects import owned_effect_delivery

    opcode, packet = owned_effect_delivery(
        1,
        allocate_action(),
        native_opcode=12613,
        effect_class=400,
        uid=uid,
        target_id=actor_id,
        running_effect_payload=_payload(actor_id, uid, entry),
    )
    # Original aVo(false) retains an unsubscribed null and completes its HMI
    # notification. True suppresses rze and does not retain this owned runner.
    return opcode, struct.pack(">i", -1) + packet[4:]


def _remove(actor_id, uid, entry, allocate_action):
    from wakfu_server.combat_effect_removal import running_effect_removal

    packet = running_effect_removal(
        1,
        allocate_action(),
        effect_class=400,
        uid=uid,
        target_id=actor_id,
        running_effect_payload=_payload(actor_id, uid, entry),
        notify_unapplication=True,
    )
    return 13560, struct.pack(">i", -1) + packet[4:]


def snapshot(character, *, allocate_action):
    """Return visual applications in durable application and native root order.

    The enclosing consumable publisher supplies the final world queue flush.
    """
    actor, entries = _entries(character)
    return tuple(
        _apply(actor, uid, entry, allocate_action) for uid, entry in entries.items()
    )


def changes(previous, character, *, allocate_action, phase=None):
    """Return removals and additions separately to bracket carrier replacement."""
    if phase not in (None, "remove", "apply"):
        raise ValueError("Unknown native visual publication phase")
    old_actor, before = _entries(previous)
    actor, after = _entries(character)
    if old_actor != actor:
        raise ValueError("Native visual delta belongs to another owner")
    replaced = {
        uid
        for uid in before.keys() & after.keys()
        if before[uid][:3] != after[uid][:3]
        or before[uid][4:] != after[uid][4:]
        or after[uid][3] > before[uid][3]
    }
    removed = (before.keys() - after.keys()) | replaced
    added = (after.keys() - before.keys()) | replaced
    removals = tuple(
        _remove(actor, uid, entry, allocate_action)
        for uid, entry in reversed(tuple(before.items()))
        if phase != "apply" and uid in removed
    )
    applications = tuple(
        _apply(actor, uid, entry, allocate_action)
        for uid, entry in after.items()
        if phase != "remove" and uid in added
    )
    if phase == "remove":
        return removals
    if phase == "apply":
        return applications
    return removals, applications
