"""Attested native4872 START304 lineage, with a fresh6874 online clock.

This is not a generic permission to introduce timed states. Only the original
316701 applicator beneath an owned4872 carrier can use this migration.
"""
import time


def source_binding(fight, invocation, reference, level):
    if (reference, level, invocation.reference) != (6874, 100, 316701):
        return None
    if (
        invocation.target_id != invocation.caster_id
        or invocation.target_id not in fight.actors
    ):
        return None
    actor = fight.actors[invocation.target_id]
    roots = getattr(fight, "native_consumable_initializations", {}).get(actor.id, ())
    matches = [
        row
        for row in roots
        if row["state_id"] == 4872
        and row["combat_uid"] == invocation.state_uid
        and row.get("handoff_target", {}).get("state_id") == 6874
    ]
    if len(matches) != 1:
        return None
    actual = [
        entry
        for entry in actor.state_ledger.entries
        if entry.uid == invocation.state_uid
        and entry.reference == 4872
        and entry.caster_id == actor.id
        and entry.target_id == actor.id
    ]
    if len(actual) != 1 or tuple(actual[0].effect_ids) != (203485, 203486):
        return None
    return matches[0]


def install(fight, invocation, entry):
    binding = source_binding(fight, invocation, entry.reference, entry.level)
    if binding is None:
        return entry
    if entry.uid == binding["combat_uid"] or entry.realtime_duration != 7200000:
        raise ValueError("Native consumable handoff requires a fresh two-hour carrier")
    now_ms = int(time.time() * 1000)
    actor = fight.actors[entry.target_id]
    result = actor.state_ledger.install_realtime_clock(
        entry.uid,
        deadline_ms=now_ms + 7200000,
        in_combat=True,
    )
    replacement = dict(
        binding,
        combat_uid=entry.uid,
        state_id=6874,
        handoff=dict(
            source_state_id=4872,
            source_combat_uid=binding["combat_uid"],
            effect_id=316701,
            applied_at_ms=now_ms,
        ),
    )
    fight.native_consumable_initializations[actor.id] = tuple(
        replacement if row is binding else row
        for row in fight.native_consumable_initializations[actor.id]
    )
    return result


def persist(store, db, fight):
    """Commit world-reference/clock handoff with its authoritative checkpoint.

    The checkpoint owner has already validated the durable participant roster.
    Repeated checkpointing never resets an already migrated clock. A failed
    checkpoint CAS rolls this update back in the same database transaction.
    """
    from psycopg.types.json import Jsonb
    from wakfu_server.consumable_catalog import load_plan

    bindings = getattr(fight, "native_consumable_initializations", {})
    committed = getattr(fight, "native_consumable_handoff_committed", frozenset())
    pending = [
        (actor_id, binding)
        for actor_id, rows in bindings.items()
        for binding in rows
        if binding.get("handoff") and binding["world_uid"] not in committed
    ]
    if not pending:
        return ()
    source = load_plan(db, 22146)
    target = source["states"][0]["metadata"]["native_handoff_target"]
    if (
        target["state_id"],
        target["level"],
        target["duration_ms"],
        target["clock"],
    ) != (6874, 100, 7200000, "online"):
        raise ValueError("Unqualified native consumable handoff target")
    now_ms = int(store.clock() * 1000)
    for actor_id, binding in pending:
        evidence = binding["handoff"]
        if binding.get("handoff_target") != target:
            raise ValueError("Native consumable handoff descriptor changed")
        if (
            binding["state_id"] != 6874
            or evidence["source_state_id"] != 4872
            or evidence["effect_id"] != 316701
            or binding["combat_uid"] == evidence["source_combat_uid"]
        ):
            raise ValueError("Invalid native consumable handoff lineage")
        row = db.execute(
            "SELECT * FROM character_consumable_buffs WHERE uid=%s AND character_id=%s FOR UPDATE",
            (binding["world_uid"], actor_id),
        ).fetchone()
        if (
            row is None
            or row["combat_id"] != fight.id
            or row["source_item_ref"] != 22146
        ):
            raise ValueError("Native consumable handoff lacks its durable source")
        if row["state_id"] == 6874:
            continue
        if row["state_id"] != 4872:
            raise ValueError("Native consumable handoff source changed")
        remaining = max(1, 7200000 - max(0, now_ms - evidence["applied_at_ms"]))
        metadata = dict(target)
        db.execute(
            "UPDATE character_consumable_buffs SET state_id=6874,level=100,duration_ms=7200000,"
            "remaining_ms=%s,online_anchor_ms=%s,metadata=%s WHERE uid=%s",
            (
                remaining,
                now_ms if row["online_generation"] is not None else None,
                Jsonb(metadata),
                row["uid"],
            ),
        )
    return tuple(binding["world_uid"] for _actor_id, binding in pending)


def mark_committed(fight, world_uids):
    """Cache a successful DB fence only after commit, never during a failed CAS."""
    if not world_uids:
        return
    fight.native_consumable_handoff_committed = getattr(
        fight, "native_consumable_handoff_committed", frozenset()
    ) | frozenset(world_uids)
