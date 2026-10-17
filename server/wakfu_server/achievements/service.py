"""Achievement adapters consume authenticated settlement facts, never client kills."""
from psycopg.pq import TransactionStatus
from . import catalog, engine, rewards, storage, wire


def _owner(db, character):
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Achievement settlement requires an active transaction")
    # Match existing account-cosmetic lock order, including disconnected heroes.
    row = db.execute(
        "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (character["account_id"],)
    ).fetchone()
    own = db.execute(
        "SELECT id FROM characters WHERE id=%s AND account_id=%s AND deleted_at IS NULL FOR UPDATE",
        (character["id"], character["account_id"]),
    ).fetchone()
    if row is None or own is None:
        raise ValueError("Missing owned achievement character")


def _event(db, character, fight, original_monsters):
    participant = db.execute(
        "SELECT p.team,f.status,f.fight_kind FROM combat_fight_participants p "
        "JOIN combat_fights f ON f.id=p.fight_id WHERE p.fight_id=%s "
        "AND p.character_id=%s AND p.account_id=%s",
        (fight.id, character["id"], character["account_id"]),
    ).fetchone()
    actor = fight.actors.get(character["id"])
    if (
        fight.phase != "finished"
        or fight.winner not in (0, 1)
        or participant is None
        or participant["status"] != "finished"
        or participant["fight_kind"] != "pve"
        or participant["team"] != fight.winner
        or actor is None
        or not actor.controlled
        or actor.owner_id != character["account_id"]
        or actor.team != fight.winner
        or getattr(actor, "pve_withdrawn", False)
    ):
        raise ValueError("Achievement requires a durable winning participant")
    registrations = getattr(fight, "native_summon_registrations", {})
    if not isinstance(registrations, dict):
        raise ValueError("Invalid authoritative summon registry")
    identities, breeds = set(), []
    for monster in original_monsters:
        identity, breed = monster["id"], monster["ref"]
        target = fight.actors.get(identity)
        if (
            type(identity) is not int
            or identity in identities
            or target is None
            or type(breed) is not int
            or breed <= 0
            or identity in registrations
            or target.controlled
            or target.team == fight.winner
            or target.hp > 0
        ):
            raise ValueError(
                "Achievement kill roster must contain distinct defeated original monsters"
            )
        identities.add(identity)
        breeds.append((identity, breed))
    encounter = db.execute(
        "SELECT i.definition_id FROM dungeon_room_encounters e JOIN dungeon_instances i "
        "ON i.instance_id=e.instance_id JOIN dungeon_instance_members m ON m.instance_id=i.instance_id "
        "WHERE e.fight_id=%s AND e.status='victory' AND e.result->>'completed'='true' "
        "AND m.character_id=%s AND m.party_id=i.party_id",
        (fight.id, character["id"]),
    ).fetchone()
    return {
        "fight_id": fight.id,
        "original_breeds": [breed for _, breed in sorted(breeds)],
        "original_monsters": [[identity, breed] for identity, breed in sorted(breeds)],
        "completed_dungeon_id": None
        if encounter is None
        else encounter["definition_id"],
    }


def drain_rewards(db, store, character):
    """Retry durable entitlements; capacity never discards a reward or fight."""
    _owner(db, character)
    packets = []
    for pending in storage.pending_rewards(db, character["id"]):
        try:
            with db.transaction():
                current = store.character(character["account_id"], character["id"], db)
                granted = rewards.grant(db, store, current, pending["payload"])
                storage.mark_reward_delivered(
                    db,
                    character["id"],
                    pending["achievement_id"],
                    pending["cycle_key"],
                    pending["reward_key"],
                )
        except rewards.RewardCapacity:
            continue
        packets.extend(granted)
    return packets


def settle(db, store, character, fight, original_monsters):
    """Called after final room settlement, inside the existing reward transaction.

    The original roster is supplied by the authoritative fight constructor, not
    rebuilt from dynamic actors, client packets, names or summoned copies.
    """
    _owner(db, character)
    event = _event(db, character, fight, original_monsters)
    key = f"fight:{fight.id}"
    before = storage.load_locked(db, character["id"])
    fresh = storage.record_event(db, character["id"], key, event)
    packets = []
    notification_key = None
    if fresh:
        now_ms = int(store.now().timestamp() * 1000)
        after, intents, objectives, completed = engine.advance(
            before, event, catalog.load(db), now_ms=now_ms
        )
        for identity, reward in intents:
            rewards.validate(reward)
            storage.claim_reward(
                db, character["id"], identity, "once", reward["d"], reward
            )
        storage.store(db, character["id"], after)
        from wakfu_server.custom_tasks.external import enqueue_fact

        enqueue_fact(
            db,
            character["account_id"],
            character["id"],
            f"combat-completed:{fight.id}",
            {
                "kind": "combat_completed",
                "fight_id": fight.id,
                "fight_kind": "pve",
                "won": True,
                "map_id": character["map_id"],
                "dungeon_id": event["completed_dungeon_id"],
            },
        )
        if event["completed_dungeon_id"] is not None:
            enqueue_fact(
                db,
                character["account_id"],
                character["id"],
                f"dungeon-completed:{fight.id}",
                {
                    "kind": "dungeon_completed",
                    "fight_id": fight.id,
                    "dungeon_id": event["completed_dungeon_id"],
                },
            )
        for achievement_id in completed:
            enqueue_fact(
                db,
                character["account_id"],
                character["id"],
                f"achievement-completed:{achievement_id}",
                {"kind": "achievement_completed", "achievement_id": achievement_id},
            )
        packets.extend(
            wire.changes(character["id"], before, after, objectives, completed, now_ms)
        )
    packets.extend(drain_rewards(db, store, character))
    if packets:
        # Each actual batch has its own durable identity, including reward retries.
        import hashlib

        envelopes = [
            {"opcode": opcode, "payload_hex": body.hex()} for opcode, body in packets
        ]
        digest = hashlib.sha256(str(envelopes).encode()).hexdigest()
        notification_key = key + ":" + digest
        storage.enqueue_notifications(db, character["id"], notification_key, envelopes)
    return {
        "packets": packets,
        "replay": not fresh,
        "notification_key": notification_key,
    }


def snapshot(db, character_id):
    state = storage.load_locked(db, character_id)
    running = sorted(
        (set(state["running"]) | set(catalog.load(db)["definitions"]))
        - set(state["completed"])
    )
    if state["running"] != running:
        state["running"] = running
        storage.store(db, character_id, state)
    return wire.section(state)


def track(db, character, achievement_id, enabled):
    _owner(db, character)
    if (
        type(enabled) is not bool
        or type(achievement_id) is not int
        or achievement_id not in catalog.load(db)["definitions"]
    ):
        raise ValueError("Unknown or unqualified tracked achievement")
    state = storage.load_locked(db, character["id"])
    if enabled and achievement_id in state["completed"]:
        raise ValueError("Completed achievement cannot be tracked")
    tracked = set(state["tracking"])
    if enabled:
        tracked.add(achievement_id)
    else:
        tracked.discard(achievement_id)
    if len(tracked) > 255:
        raise ValueError("Native tracking limit reached")
    state["tracking"] = sorted(tracked)
    storage.store(db, character["id"], state)
    import struct

    return [(13371, struct.pack(">qiB", character["id"], achievement_id, enabled))]


def decode_tracking(body):
    """Native cnI13175: signed32 definition and one canonical boolean byte."""
    import struct

    if not isinstance(body, bytes) or len(body) != 5:
        raise ValueError("Tracking request requires exactly five bytes")
    identity, enabled = struct.unpack(">iB", body)
    if identity <= 0 or enabled not in (0, 1):
        raise ValueError("Invalid native tracking request")
    return identity, bool(enabled)


def notification_batches(db, character):
    _owner(db, character)
    return [
        {
            "key": row["event_key"],
            "packets": [
                (packet["opcode"], bytes.fromhex(packet["payload_hex"]))
                for packet in row["packets"]
            ],
        }
        for row in storage.pending_notifications(db, character["id"])
    ]


def acknowledge_notifications(db, character, keys):
    """Server-only acknowledgement AFTER successful socket publication."""
    _owner(db, character)
    if not isinstance(keys, (list, tuple)) or any(
        not isinstance(key, str) for key in keys
    ):
        raise ValueError("Invalid notification acknowledgements")
    for key in keys:
        storage.mark_notifications_delivered(db, character["id"], key)


def bootstrap(db, character):
    """Capture section and covered outbox keys under the same owner lock.

    Caller sends the complete native character bootstrap, including inventory,
    then acknowledges ONLY these captured keys. Snapshot creation never acks.
    An event arriving later retains its own pending notification batch.
    """
    _owner(db, character)
    section = snapshot(db, character["id"])
    keys = [
        row["event_key"] for row in storage.pending_notifications(db, character["id"])
    ]
    return {"section": section, "covered_notifications": keys}


def tracking_request(store, account_id, generation, character_id, body):
    """Apply native tracking only to the currently leased owned character."""
    identity, enabled = decode_tracking(body)
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        character = store.character(account_id, character_id, db)
        return track(db, character, identity, enabled)


def project_section(progress, authority, *, db):
    """Serialize an owned read snapshot without locks, grants or state writes.

    Every owned entity refresh needs the current journal, not just map entry.
    The containing character SELECT supplies progress and fallback authority
    from the same database statement snapshot.
    """
    if progress is None:
        from wakfu_server.maps.dungeon_achievement_authority import (
            queries_from_snapshot,
        )

        queries_from_snapshot(authority)
        state = {
            "variables": {},
            "tracking": [],
            "recent": [],
            "completion_dates": {},
            **authority,
        }
    else:
        state = dict(progress)
    storage._state(state)
    state["running"] = sorted(
        (set(state["running"]) | set(catalog.load(db)["definitions"]))
        - set(state["completed"])
    )
    return wire.section(state)
