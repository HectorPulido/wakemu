"""Durable native consumable states with explicit wall and connected-time clocks.

Descriptors must prove duration, clock and replacement behavior. No item, state,
stat or profession mapping is inferred here. Inventory callers own consumption,
lease/hero authorization, character locks and the encompassing transaction.
"""
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb


def _context(store, db, character_id, now_ms):
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Consumable states require an active transaction")
    if type(character_id) is not int or character_id <= 0:
        raise ValueError("Invalid consumable state owner")
    now_ms = int(store.clock() * 1000) if now_ms is None else now_ms
    if type(now_ms) is not int or not 0 <= now_ms < 2**63:
        raise ValueError("Invalid consumable state clock")
    return now_ms


def _generation(value):
    if value is not None and (
        not isinstance(value, str) or not value or len(value) > 128
    ):
        raise ValueError("Invalid consumable state session generation")
    return value


def _rows(db, character_id):
    return tuple(
        dict(row)
        for row in db.execute(
            "SELECT * FROM character_consumable_buffs WHERE character_id=%s ORDER BY state_id FOR UPDATE",
            (character_id,),
        ).fetchall()
    )


def _public(row):
    value = dict(row["metadata"])
    value.update(
        {
            key: row[key]
            for key in (
                "uid",
                "state_id",
                "level",
                "source_item_ref",
                "source_item_uid",
                "clock",
                "duration_ms",
                "remaining_ms",
                "combat_id",
            )
        }
    )
    value["metadata"] = dict(row["metadata"].get("metadata", {}))
    if row.get("native_origin") is not None:
        value["native_origin"] = dict(row["native_origin"])
    return value


def hydrated_states(store, db, character_id, *, now_ms=None):
    """Read the visible persisted states without advancing or writing clocks.

    Character hydration also runs inside the AI's read-only snapshot. Wall
    expiry can be projected from its deadline; connected-time advancement
    remains owned by the session lifecycle with its matching generation.
    """
    now_ms = _context(store, db, character_id, now_ms)
    active = []
    rows = db.execute(
        "SELECT * FROM character_consumable_buffs WHERE character_id=%s ORDER BY state_id",
        (character_id,),
    ).fetchall()
    for stored in rows:
        row = dict(stored)
        if row["clock"] == "event":
            active.append(_public(row))
            continue
        remaining = (
            max(0, row["expires_ms"] - now_ms)
            if row["clock"] == "wall"
            else row["remaining_ms"]
        )
        if remaining == 0 and row["combat_id"] is None:
            continue
        row["remaining_ms"] = (
            max(1, remaining) if row["combat_id"] is not None else remaining
        )
        active.append(_public(row))
    return tuple(active)


def evaluated_states(store, db, character_id, *, generation=None, now_ms=None):
    """Evaluate action bonuses without retiring unpublished world states.

    Profession actions borrow the owner's guarded transaction. Retirement,
    health reconciliation and wire deltas remain one lifecycle operation.
    """
    now_ms = _context(store, db, character_id, now_ms)
    generation = _generation(generation)
    states = []
    for stored in db.execute(
        "SELECT * FROM character_consumable_buffs WHERE character_id=%s ORDER BY state_id",
        (character_id,),
    ).fetchall():
        row = dict(stored)
        if row["clock"] == "event":
            states.append(_public(row))
            continue
        if row["clock"] == "wall":
            remaining = max(0, row["expires_ms"] - now_ms)
        elif generation is not None and row["online_generation"] == generation:
            if now_ms < row["online_anchor_ms"]:
                raise ValueError("Consumable online clock moved backwards")
            remaining = max(0, row["remaining_ms"] - (now_ms - row["online_anchor_ms"]))
        else:
            remaining = row["remaining_ms"]
        if remaining == 0 and row["combat_id"] is None:
            continue
        row["remaining_ms"] = (
            max(1, remaining) if row["combat_id"] is not None else remaining
        )
        states.append(_public(row))
    return tuple(states)


def active_states(store, db, character_id, *, generation=None, now_ms=None):
    """Expire wall states and checkpoint online states for the matching session.

    With generation=None, online time stays at its last lifecycle checkpoint.
    Providers must not fabricate a generation to resume disconnected clocks.
    """
    now_ms = _context(store, db, character_id, now_ms)
    generation = _generation(generation)
    active = []
    for row in _rows(db, character_id):
        if row["clock"] == "event":
            active.append(_public(row))
            continue
        if row["clock"] == "wall":
            remaining = max(0, row["expires_ms"] - now_ms)
        elif generation is not None and row["online_generation"] == generation:
            if now_ms < row["online_anchor_ms"]:
                raise ValueError("Consumable online clock moved backwards")
            remaining = max(0, row["remaining_ms"] - (now_ms - row["online_anchor_ms"]))
            row["online_anchor_ms"] = now_ms
        else:
            remaining = row["remaining_ms"]
        if remaining == 0 and row["combat_id"] is None:
            db.execute(
                "DELETE FROM character_consumable_buffs WHERE uid=%s", (row["uid"],)
            )
            continue
        if remaining != row["remaining_ms"] or (
            row["clock"] == "online"
            and generation is not None
            and row["online_generation"] == generation
        ):
            db.execute(
                "UPDATE character_consumable_buffs SET remaining_ms=%s,online_anchor_ms=%s WHERE uid=%s",
                (remaining, row["online_anchor_ms"], row["uid"]),
            )
        row["remaining_ms"] = (
            max(1, remaining) if row["combat_id"] is not None else remaining
        )
        active.append(_public(row))
    return tuple(active)


def snapshot(store, character_id, *, generation=None, now_ms=None):
    """Convenience provider when the caller has no surrounding transaction."""
    with store.connection() as db:
        return active_states(
            store, db, character_id, generation=generation, now_ms=now_ms
        )


def apply_states(
    store,
    db,
    character_id,
    states,
    *,
    source_item_ref,
    source_item_uid,
    generation=None,
    now_ms=None
):
    """Apply a descriptor-proven replacement plan atomically with consumption.

    Event states require explicit native removal/counter metadata. Additive
    counters use their native maximum; unproven clocks remain unsupported.
    """
    now_ms = _context(store, db, character_id, now_ms)
    generation = _generation(generation)
    if any(
        type(value) is not int or value <= 0
        for value in (source_item_ref, source_item_uid)
    ):
        raise ValueError("Invalid consumable state source")
    if not isinstance(states, (list, tuple)) or not states:
        raise ValueError("Missing native consumable state plan")
    validated = []
    identities = set()
    for state in states:
        if not isinstance(state, dict):
            raise ValueError("Invalid native consumable state descriptor")
        identity, level = state.get("state_id"), state.get("level")
        clock, duration = state.get("clock"), state.get("duration_ms")
        if (
            type(identity) is not int
            or identity <= 0
            or identity in identities
            or type(level) is not int
            or not 0 < level <= 32767
            or clock not in ("wall", "online", "event")
            or type(duration) is not int
            or not 0 <= duration < 2**63
            or (clock == "event" and duration != 0)
            or (clock != "event" and duration == 0)
            or now_ms + duration >= 2**63
            or not (
                state.get("stacking")
                in (
                    "replace",
                    "additive",
                    "reject_duplicate",
                    "native_reject_duplicate",
                )
                or state.get("replace") is True
                or state.get("additive") is True
            )
        ):
            raise ValueError("Unproven consumable state timing or stacking")
        metadata = state.get("metadata", {})
        counter = metadata.get("counter", {}) if isinstance(metadata, dict) else {}
        additive = state.get("additive") is True or state.get("stacking") == "additive"
        maximum = state.get("maximum_level", counter.get("maximum_level"))
        if (
            not isinstance(metadata, dict)
            or (
                clock == "event"
                and not (
                    metadata.get("removal_event_ids")
                    or counter.get("decrement_event_ids")
                )
            )
            or (
                additive
                and (
                    clock != "event"
                    or type(maximum) is not int
                    or not 0 < maximum <= 32767
                )
            )
        ):
            raise ValueError("Unproven consumable state timing or stacking")
        if clock == "online" and generation is None:
            raise ValueError("Online consumable requires its active session generation")
        effects, removes = state.get("effect_ids", []), state.get("removes", [])
        if any(
            not isinstance(values, (list, tuple))
            or any(type(value) is not int or value <= 0 for value in values)
            for values in (effects, removes)
        ):
            raise ValueError("Invalid native consumable effect or removal identities")
        identities.add(identity)
        validated.append(dict(state))
    existing_states = active_states(
        store, db, character_id, generation=generation, now_ms=now_ms
    )
    active_levels = {state["state_id"]: state["level"] for state in existing_states}
    if any(
        state.get("stacking") in ("reject_duplicate", "native_reject_duplicate")
        and state["state_id"] in active_levels
        for state in validated
    ):
        raise ValueError("Este efecto ya está activo")
    for state in validated:
        additive = state.get("additive") is True or state.get("stacking") == "additive"
        replacement = state.get("replace") is True or state.get("stacking") == "replace"
        maximum = state.get(
            "maximum_level",
            state.get("metadata", {}).get("counter", {}).get("maximum_level"),
        )
        if (
            additive
            and state.get("refresh") is False
            and active_levels.get(state["state_id"], 0) >= maximum
        ):
            raise ValueError("Este efecto ya alcanzó su nivel máximo")
        if (
            replacement
            and not additive
            and state["state_id"] in active_levels
            and state["level"] < active_levels[state["state_id"]]
        ):
            raise ValueError(
                "No puedes reemplazar este efecto por uno de nivel inferior"
            )
    for state in validated:
        if state.get("additive") is True or state.get("stacking") == "additive":
            existing = db.execute(
                "SELECT level FROM character_consumable_buffs WHERE character_id=%s AND state_id=%s FOR UPDATE",
                (character_id, state["state_id"]),
            ).fetchone()
            maximum = state.get(
                "maximum_level",
                state.get("metadata", {}).get("counter", {}).get("maximum_level"),
            )
            state["level"] = min(
                maximum, state["level"] + (0 if existing is None else existing["level"])
            )
        removes = state.get("removes", [])
        if removes:
            db.execute(
                "DELETE FROM character_consumable_buffs WHERE character_id=%s AND state_id=ANY(%s)",
                (character_id, list(removes)),
            )
        clock, duration = state["clock"], state["duration_ms"]
        db.execute(
            "INSERT INTO character_consumable_buffs "
            "(character_id,state_id,level,source_item_ref,source_item_uid,clock,duration_ms,remaining_ms,expires_ms,online_generation,online_anchor_ms,metadata) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
            "ON CONFLICT(character_id,state_id) DO UPDATE SET "
            "level=excluded.level,source_item_ref=excluded.source_item_ref,source_item_uid=excluded.source_item_uid,native_origin=NULL,"
            "clock=excluded.clock,duration_ms=excluded.duration_ms,remaining_ms=excluded.remaining_ms,"
            "expires_ms=excluded.expires_ms,online_generation=excluded.online_generation,online_anchor_ms=excluded.online_anchor_ms,metadata=excluded.metadata",
            (
                character_id,
                state["state_id"],
                state["level"],
                source_item_ref,
                source_item_uid,
                clock,
                duration,
                duration,
                now_ms + duration if clock == "wall" else None,
                generation if clock == "online" else None,
                now_ms if clock == "online" else None,
                Jsonb(state),
            ),
        )
    return active_states(store, db, character_id, generation=generation, now_ms=now_ms)


def resume(store, db, character_id, generation, *, now_ms=None):
    """Resume at login; a new generation never charges an unobserved offline gap."""
    now_ms = _context(store, db, character_id, now_ms)
    generation = _generation(generation)
    if generation is None:
        raise ValueError("Consumable resume requires a session generation")
    active_states(store, db, character_id, generation=generation, now_ms=now_ms)
    db.execute(
        "UPDATE character_consumable_buffs SET online_generation=%s,online_anchor_ms=%s "
        "WHERE character_id=%s AND clock='online'",
        (generation, now_ms, character_id),
    )
    return active_states(store, db, character_id, generation=generation, now_ms=now_ms)


def pause(store, db, character_id, generation, *, now_ms=None):
    """Checkpoint and pause the departing session without pausing its replacement."""
    now_ms = _context(store, db, character_id, now_ms)
    generation = _generation(generation)
    if generation is None:
        raise ValueError("Consumable pause requires a session generation")
    active_states(store, db, character_id, generation=generation, now_ms=now_ms)
    db.execute(
        "UPDATE character_consumable_buffs SET online_generation=NULL,online_anchor_ms=NULL "
        "WHERE character_id=%s AND clock='online' AND online_generation=%s",
        (character_id, generation),
    )
    return active_states(store, db, character_id, now_ms=now_ms)


def retire_states(store, db, character_id, *, uids=(), state_ids=(), now_ms=None):
    """Retire durable states explicitly removed by native combat/world events."""
    _context(store, db, character_id, now_ms)
    if any(
        not isinstance(values, (tuple, list))
        or any(type(value) is not int or value <= 0 for value in values)
        for values in (uids, state_ids)
    ):
        raise ValueError("Invalid consumable state retirement")
    if uids or state_ids:
        db.execute(
            "DELETE FROM character_consumable_buffs WHERE character_id=%s AND (uid=ANY(%s) OR state_id=ANY(%s))",
            (character_id, list(uids), list(state_ids)),
        )


def enter_combat(store, db, character_id, fight_id, *, generation=None, now_ms=None):
    """Keep native deadlines running while suppressing combat-time retirement."""
    now_ms = _context(store, db, character_id, now_ms)
    if type(fight_id) is not int or fight_id <= 0:
        raise ValueError("Invalid consumable combat identity")
    states = active_states(
        store, db, character_id, generation=generation, now_ms=now_ms
    )
    if any(row["combat_id"] not in (None, fight_id) for row in states):
        raise ValueError("Consumable state belongs to another combat")
    db.execute(
        "UPDATE character_consumable_buffs SET combat_id=%s WHERE character_id=%s",
        (fight_id, character_id),
    )
    return active_states(store, db, character_id, generation=generation, now_ms=now_ms)


def return_from_combat(
    store, db, character_id, fight_id, state_updates, *, generation=None, now_ms=None
):
    """Reconcile native removal/level and max(1, remaining) on world return.

    Updates come from the actual native combat state registry, never a client
    packet. All protected durable states must be represented exactly once.
    """
    now_ms = _context(store, db, character_id, now_ms)
    generation = _generation(generation)
    if (
        type(fight_id) is not int
        or fight_id <= 0
        or not isinstance(state_updates, (list, tuple))
    ):
        raise ValueError("Invalid consumable combat return")
    # Connected-time accounting is durable across disconnect/reconnect while a
    # native combat carrier may retain an absolute deadline. Advance only the
    # current session here; never charge its offline gap using that deadline.
    active_states(store, db, character_id, generation=generation, now_ms=now_ms)
    rows = {
        row["uid"]: row
        for row in _rows(db, character_id)
        if row["combat_id"] == fight_id
    }
    updates = {}
    for update in state_updates:
        if not isinstance(update, dict) or type(update.get("uid")) is not int:
            raise ValueError("Invalid consumable combat state update")
        uid = update["uid"]
        if (
            uid in updates
            or uid not in rows
            or update.get("state_id") != rows[uid]["state_id"]
            or type(update.get("removed")) is not bool
        ):
            raise ValueError("Foreign or duplicate consumable combat state update")
        if not update["removed"]:
            remaining, level = update.get("remaining_ms"), update.get("level")
            if (
                type(remaining) is not int
                or not 0 <= remaining < 2**63
                or (rows[uid]["clock"] != "event" and remaining == 0)
                or (rows[uid]["clock"] == "event" and remaining != 0)
                or now_ms + remaining >= 2**63
                or type(level) is not int
                or not 0 < level <= 32767
                or update.get("clock") != rows[uid]["clock"]
                or (rows[uid]["clock"] == "online" and generation is None)
            ):
                raise ValueError("Invalid retained consumable combat state")
        updates[uid] = update
    if set(updates) != set(rows):
        raise ValueError("Incomplete consumable combat return")
    for uid, update in updates.items():
        if update["removed"]:
            db.execute("DELETE FROM character_consumable_buffs WHERE uid=%s", (uid,))
            continue
        row = rows[uid]
        online = row["clock"] == "online"
        remaining = max(1, row["remaining_ms"]) if online else update["remaining_ms"]
        metadata = dict(row["metadata"], level=update["level"])
        db.execute(
            "UPDATE character_consumable_buffs SET level=%s,remaining_ms=%s,expires_ms=%s,"
            "online_generation=%s,online_anchor_ms=%s,metadata=%s,combat_id=NULL WHERE uid=%s",
            (
                update["level"],
                remaining,
                now_ms + remaining if row["clock"] == "wall" else None,
                generation if online else None,
                now_ms if online else None,
                Jsonb(metadata),
                uid,
            ),
        )
    return active_states(store, db, character_id, generation=generation, now_ms=now_ms)


def emit_events(
    store, db, character_id, events, *, generation=None, now_ms=None, fight_model=None
):
    """Execute descriptor-proven removal/counter events on durable world states.

    Marker exclusions use the original emitting effect identity; a bare event
    carries no such exclusion. Call before applying the source's new states so
    existing food groups react while the incoming marker can preserve itself.
    """
    now_ms = _context(store, db, character_id, now_ms)
    if not isinstance(events, (tuple, list)):
        raise ValueError("Invalid consumable native events")
    normalized = []
    for event in events:
        if type(event) is int:
            event = {"event_id": event, "effect_id": None}
        if (
            not isinstance(event, dict)
            or type(event.get("event_id")) is not int
            or event["event_id"] <= 0
            or (
                event.get("effect_id") is not None
                and (type(event["effect_id"]) is not int or event["effect_id"] <= 0)
            )
        ):
            raise ValueError("Invalid consumable native event identity")
        normalized.append(event)
    states = active_states(
        store, db, character_id, generation=generation, now_ms=now_ms
    )
    for state in states:
        metadata = state["metadata"]
        removal_ids = metadata.get("removal_event_ids", [])
        rules = metadata.get("removal_event_rules", [])
        counter = metadata.get("counter", {})
        remove = False
        decrement = 0
        for event in normalized:
            matching_rules = [
                rule for rule in rules if rule["event_id"] == event["event_id"]
            ]
            if matching_rules:
                if any(
                    event.get("effect_id") not in rule.get("excluded_effect_ids", [])
                    for rule in matching_rules
                ):
                    remove = True
            elif event["event_id"] in removal_ids:
                remove = True
            if event["event_id"] in counter.get("decrement_event_ids", []):
                amount = counter.get("decrement")
                if type(amount) is not int or amount <= 0:
                    raise ValueError("Unproven consumable counter event")
                if counter.get("criteria"):
                    models = counter.get("fight_models")
                    if models != [2, 24, 73, 76] or type(fight_model) is not int:
                        raise ValueError("Unproven consumable counter context")
                    if fight_model not in models:
                        continue
                decrement += amount
        if remove or state["level"] - decrement <= 0:
            db.execute(
                "DELETE FROM character_consumable_buffs WHERE uid=%s", (state["uid"],)
            )
        elif decrement:
            row = db.execute(
                "SELECT metadata FROM character_consumable_buffs WHERE uid=%s FOR UPDATE",
                (state["uid"],),
            ).fetchone()
            payload = dict(row["metadata"], level=state["level"] - decrement)
            db.execute(
                "UPDATE character_consumable_buffs SET level=%s,metadata=%s WHERE uid=%s",
                (state["level"] - decrement, Jsonb(payload), state["uid"]),
            )
    return active_states(store, db, character_id, generation=generation, now_ms=now_ms)
