"""Attest the original987→45980→981 lineage without producing a death penalty."""
import time


def source_binding(fight, invocation, reference, level):
    if (reference, invocation.reference) != (981, 45980) or not 1 <= level <= 100:
        return None
    if (
        invocation.caster_id != invocation.target_id
        or type(invocation.state_uid) is not int
        or invocation.state_uid <= 0
        or type(invocation.native_running_uid) is not int
        or invocation.native_running_uid <= 0
    ):
        return None
    from .combat_native_container import resolve_state_container

    parent = resolve_state_container(fight, invocation.state_uid)
    if (
        parent is None
        or parent.reference != 987
        or parent.uid != invocation.state_uid
        or tuple(parent.effect_ids) != (45980,)
        or parent.target_id != invocation.target_id
        or parent.caster_id != invocation.caster_id
    ):
        return None
    return parent


def install(fight, invocation, entry):
    parent = source_binding(fight, invocation, entry.reference, entry.level)
    if parent is None:
        return entry
    if (
        not entry.retained
        or entry.realtime_duration != 240000
        or entry.timer is not None
    ):
        raise ValueError("Invalid native retained981 clock")
    now_ms = int(time.time() * 1000)
    actor = fight.actors[entry.target_id]
    result = actor.state_ledger.install_realtime_clock(
        entry.uid, deadline_ms=now_ms + 240000, in_combat=True
    )
    origins = dict(getattr(fight, "native_external_state_origins", {}))
    origins[entry.uid] = dict(
        kind="native-state",
        effect_id=45980,
        parent_state_id=987,
        parent_uid=parent.uid,
        source_uid=invocation.native_running_uid,
        combat_uid=entry.uid,
        character_id=entry.target_id,
        fight_id=fight.id,
        applied_at_ms=now_ms,
    )
    fight.native_external_state_origins = origins
    return result


def descriptor(db, level):
    """The same original state graph is shared by combat and world reduction."""
    from wakfu_server.consumable_catalog import load_plan

    model = load_plan(db, 10657)["reduce_states"][0]["native_state"]
    if type(level) is not int or not 1 <= level <= model["maximum_level"]:
        raise ValueError("Invalid retained981 level")
    return dict(
        state_id=981,
        level=level,
        maximum_level=100,
        clock="online",
        duration_ms=240000,
        replace=False,
        additive=True,
        refresh=True,
        stacking="additive",
        removes=[],
        effect_ids=model["effect_ids_by_level"][str(level)],
        metadata=dict(
            native_effects=model["native_effects"],
            combat_only_effect_ids=[254574],
            native_state_flags=model["native_state_flags"],
            removal_event_ids=[],
            native_duration_base=-1,
            native_realtime_duration_base=240000,
            native_realtime_duration_per_level=0,
            skip_turn_timer=True,
            clock_contract="eZU.remaining/eZV.restore_remaining;fyW.cxn=false",
        ),
    )


def capture(store, db, account_id, generation, character_id, fight, combat_uid):
    """Capture a real surviving external carrier at an owned terminal return.

    This never applies987 or981. The caller supplies its terminal native fight
    under the normal participant/health-return transaction and its owner locks.
    """
    from psycopg.types.json import Jsonb
    from wakfu_server.consumable_buffs import active_states

    actor = fight.actors.get(character_id)
    origin = getattr(fight, "native_external_state_origins", {}).get(combat_uid)
    entries = (
        ()
        if actor is None
        else [entry for entry in actor.state_ledger.entries if entry.uid == combat_uid]
    )
    if (
        fight.phase != "finished"
        or not isinstance(origin, dict)
        or len(entries) != 1
        or origin.get("character_id") != character_id
        or origin.get("fight_id") != fight.id
        or origin.get("effect_id") != 45980
        or origin.get("parent_state_id") != 987
        or origin.get("combat_uid") != combat_uid
        or combat_uid not in fight.state_wire_payloads
    ):
        raise ValueError("Missing actual terminal retained981 provenance")
    entry = entries[0]
    if (
        entry.reference != 981
        or entry.caster_id != character_id
        or entry.target_id != character_id
        or entry.realtime_duration != 240000
        or entry.realtime_deadline_ms is None
        or entry.timer is not None
    ):
        raise ValueError("Native external981 carrier changed")
    participant = db.execute(
        "SELECT 1 FROM combat_fight_participants WHERE fight_id=%s AND character_id=%s "
        "AND account_id=%s AND session_generation=%s",
        (fight.id, character_id, account_id, generation),
    ).fetchone()
    if participant is None:
        raise ValueError("External981 capture has no owned fight participant")
    now_ms = int(store.clock() * 1000)
    remaining = max(0, entry.realtime_deadline_ms - now_ms)
    active_states(store, db, character_id, generation=generation, now_ms=now_ms)
    existing = db.execute(
        "SELECT * FROM character_consumable_buffs WHERE character_id=%s AND state_id=981 FOR UPDATE",
        (character_id,),
    ).fetchone()
    bindings = dict(getattr(fight, "native_consumable_initializations", {}))
    owned = list(bindings.get(character_id, ()))
    matching = (
        []
        if existing is None
        else [
            row
            for row in owned
            if row["world_uid"] == existing["uid"]
            and row["state_id"] == 981
            and row["clock"] == "online"
        ]
    )
    if existing is not None and existing.get("native_origin") == origin:
        stored = dict(existing)  # A retried return never renews the deadline.
    else:
        if existing is not None and (
            existing.get("native_origin") is None
            or existing["combat_id"] != fight.id
            or len(matching) != 1
        ):
            raise ValueError(
                "External981 capture would replace an unattested world source"
            )
        if remaining == 0:
            return None
        state = descriptor(db, entry.level)
        if existing is None:
            stored = dict(
                db.execute(
                    "INSERT INTO character_consumable_buffs(character_id,state_id,level,source_item_ref,"
                    "source_item_uid,clock,duration_ms,remaining_ms,expires_ms,online_generation,online_anchor_ms,"
                    "metadata,native_origin,combat_id) VALUES(%s,981,%s,NULL,NULL,'online',240000,%s,NULL,%s,%s,%s,%s,%s) RETURNING *",
                    (
                        character_id,
                        entry.level,
                        remaining,
                        generation,
                        now_ms,
                        Jsonb(state),
                        Jsonb(origin),
                        fight.id,
                    ),
                ).fetchone()
            )
        else:
            stored = dict(
                db.execute(
                    "UPDATE character_consumable_buffs SET level=%s,remaining_ms=%s,online_generation=%s,"
                    "online_anchor_ms=%s,metadata=%s,native_origin=%s WHERE uid=%s RETURNING *",
                    (
                        entry.level,
                        remaining,
                        generation,
                        now_ms,
                        Jsonb(state),
                        Jsonb(origin),
                        existing["uid"],
                    ),
                ).fetchone()
            )
    owned = [row for row in owned if row["world_uid"] != stored["uid"]]
    owned.append(
        dict(
            world_uid=stored["uid"], combat_uid=entry.uid, state_id=981, clock="online"
        )
    )
    bindings[character_id] = tuple(owned)
    fight.native_consumable_initializations = bindings
    return stored


def capture_all(store, db, account_id, generation, character_id, fight):
    """Caller owns a private return preview; adopt it only with the DB commit."""
    actor = fight.actors.get(character_id)
    origins = getattr(fight, "native_external_state_origins", {})
    if actor is None:
        return ()
    actual = {
        entry.uid for entry in actor.state_ledger.entries if entry.reference == 981
    }
    return tuple(
        capture(store, db, account_id, generation, character_id, fight, uid)
        for uid in sorted(actual & set(origins))
    )
