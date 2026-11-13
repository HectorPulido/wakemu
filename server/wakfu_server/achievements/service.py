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
                granted = rewards.grant(
                    db, store, current, pending["payload"], entitlement=pending
                )
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
        from wakfu_server.guild_daily_quests import settle_combat

        packets.extend(settle_combat(db, store, character, fight, event))
        # Persist the eligibility snapshot with the fight, before processing it
        # in a separate savepoint. A replay can retry this receipt only.
        from .combat_missions import stage as stage_combat_missions

        try:
            with db.transaction():
                stage_combat_missions(db, store, character, event)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Combat mission receipt failed for character %s fight %s",
                character["id"],
                fight.id,
            )
    if fresh:
        from .rii_combat_counters import settle as settle_rii_combat

        try:
            with db.transaction():
                packets.extend(settle_rii_combat(db, store, character, event))
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Rii combat counter failed for character %s fight %s",
                character["id"],
                fight.id,
            )
    if fresh:
        from .ruel_story import settle_trace_fight

        try:
            with db.transaction():
                packets.extend(settle_trace_fight(db, store, character, event))
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Ruel trace settlement failed for character %s fight %s",
                character["id"],
                fight.id,
            )
    if fresh:
        # Only an already assigned Ruel hunt may consume this authenticated
        # fresh victory. A later assignment cannot backfill an older fight.
        from .ruel_hunts import settle as settle_ruel_hunt

        try:
            with db.transaction():
                ruel_packets = settle_ruel_hunt(db, store, character, event)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Ruel hunt settlement failed for character %s fight %s",
                character["id"],
                fight.id,
            )
        else:
            packets.extend(ruel_packets)
    # A replay may process an existing pending receipt, but never creates one.
    # Isolate failures so the fight and all other rewards remain durable.
    from .combat_missions import settle as settle_combat_missions

    try:
        with db.transaction():
            mission_packets = settle_combat_missions(db, store, character, event)
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "Combat mission settlement failed for character %s fight %s",
            character["id"],
            fight.id,
        )
    else:
        packets.extend(mission_packets)
    if event["completed_dungeon_id"] is not None:
        # The native fight receipt above is the sole source for recurring
        # victories. Keep this independent of combat settlement: a missing or
        # stale recurring contract must not roll back a legitimate fight.
        # Replays may retry this step; its own receipt and rewards are durable
        # and idempotent.
        from wakfu_server.objectives.environmental_recurring_storage import (
            settle_combat as settle_recurring,
        )

        try:
            with db.transaction():
                from wakfu_server.objectives.recurring_combat_auto import (
                    accept_matching,
                )

                try:
                    # A malformed optional auto-accept policy must not prevent
                    # already accepted recurring missions from settling.
                    with db.transaction():
                        accepted_packets = accept_matching(
                            db, store, character, fight, event
                        )
                except Exception:
                    import logging

                    logging.getLogger(__name__).exception(
                        "Automatic recurring acceptance failed for character %s fight %s",
                        character["id"],
                        fight.id,
                    )
                    accepted_packets = []
                recurring = settle_recurring(db, store, character, fight, event)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Recurring hunter settlement failed for character %s fight %s",
                character["id"],
                fight.id,
            )
        else:
            packets.extend(accepted_packets)
            packets.extend(recurring["packets"])
    packets.extend(drain_rewards(db, store, character))
    if 5144 in before["running"]:
        # The fight reward or an achievement reward may have raised the real
        # level. Resolve the reminder only after both have been settled.
        current = store.character(character["account_id"], character["id"], db)
        if current["level"] >= 30:
            from .rii_class_mission import reached_level

            packets.extend(reached_level(db, store, current, current["level"]))
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
    from wakfu_server.guild_daily_quests import synchronize

    synchronize(db, character_id)
    from wakfu_server.objectives import environmental_recurring_storage as recurring

    active_recurring = db.execute(
        "SELECT 1 FROM recurring_hunter_acceptances WHERE character_id=%s AND expired_at_ms IS NULL LIMIT 1",
        (character_id,),
    ).fetchone()
    if active_recurring:
        owner = db.execute(
            "SELECT account_id FROM characters WHERE id=%s", (character_id,)
        ).fetchone()
        if owner is None:
            raise ValueError("Missing recurring hunter owner")
        recurring.synchronize(
            db, None, {"id": character_id, "account_id": owner["account_id"]}
        )
    state = storage.load_locked(db, character_id)
    running = sorted(
        (set(state["running"]) | set(catalog.load(db)["definitions"]))
        - set(state["completed"])
    )
    if state["running"] != running:
        state["running"] = running
        storage.store(db, character_id, state)
    from wakfu_server.guild_daily_quests import activation_dates

    dates = activation_dates(db, character_id)
    if active_recurring:
        dates.update(recurring.activation_dates(db, character_id))
    return _journal_section(db, state, dates, character_id)


def _journal_section(db, state, dates, character_id):
    # Native completion marks the completed bit without clearing the active
    # bit. Apply this reconstruction only to reviewed, nonperiodic missions;
    # other completions may have an independent deactivation/reset policy.
    active_after_completion = {5146}
    completed_with_dates = sorted(
        identity
        for identity in state["completed"]
        if identity in active_after_completion
        and str(identity) in state["completion_dates"]
    )
    retained_active = set()
    if character_id is not None and completed_with_dates:
        definitions = db.execute(
            "SELECT definition_id,data FROM native_quest_metadata_definitions "
            "WHERE revision=(SELECT revision FROM native_quest_metadata_releases "
            "ORDER BY imported_at DESC LIMIT 1) AND definition_id=ANY(%s)",
            (completed_with_dates,),
        ).fetchall()
        for row in definitions:
            native = row["data"].get("native", {})
            if (
                native.get("d") == row["definition_id"]
                and native.get("native_class") == "aJM"
                and native.get("aqb") is False
                and native.get("getDuration") == 0
                and native.get("cjU") == 0
            ):
                retained_active.add(row["definition_id"])
    # Include actual acceptance timestamps for periodic dialogue turn-ins so
    # the native client can evaluate their running period after reconnect.
    if character_id is not None and state["running"]:
        rows = db.execute(
            "SELECT DISTINCT ON (definition_id) definition_id,accepted_at_ms "
            "FROM character_recurring_mission_cycles WHERE character_id=%s "
            "AND definition_id=ANY(%s) ORDER BY definition_id,cycle_index DESC",
            (character_id, state["running"]),
        ).fetchall()
        dates = dict(dates)
        dates.update({row["definition_id"]: row["accepted_at_ms"] for row in rows})
    # Reuse durable Rii acceptance times after reconnect.
    for identity, event_key in (
        (5135, "incarnam-start:5135"),
        (5136, "incarnam-start:5136"),
        (5137, "incarnam-start:5137"),
        (5138, "incarnam-start:5138"),
        (5139, "incarnam-start:5139"),
        (5160, "zone-entry-mission:5160"),
        (5146, "zone-entry-mission:5146"),
        (5144, "rii-class-reminder:start"),
        (5161, "rii-departure-activation:5161"),
        (5163, "rii-fresco-activation:5163"),
    ):
        if (
            character_id is None
            or identity not in state["running"] + state["completed"]
        ):
            continue
        receipt = db.execute(
            "SELECT payload FROM character_achievement_events "
            "WHERE character_id=%s AND event_key=%s",
            (character_id, event_key),
        ).fetchone()
        if receipt is not None:
            accepted_at = receipt["payload"].get("accepted_at_ms")
            if type(accepted_at) is int and 0 <= accepted_at < 2**63:
                dates = dict(dates)
                dates.setdefault(identity, accepted_at)
    # The optional preview changes only bytes sent to this specific character.
    preview = db.execute(
        "SELECT value FROM settings WHERE name=%s", ("mission_journal_preview",)
    ).fetchone()
    active, completed = (), ()
    if preview is not None:
        value = preview["value"]
        if (
            isinstance(value, dict)
            and value.get("character_id") == character_id
            and value.get("schema") == "mission_journal_preview_v1"
        ):
            active = set(value.get("active", ())) & set(state["completed"])
            completed = value.get("completed", ())
    return wire.section(
        state,
        activation_dates=dates,
        retained_active=retained_active,
        preview_active=active,
        preview_completed=completed,
    )


def track(db, character, achievement_id, enabled):
    _owner(db, character)
    if (
        type(enabled) is not bool
        or type(achievement_id) is not int
        or achievement_id <= 0
    ):
        raise ValueError("Unknown or unqualified tracked achievement")
    state = storage.load_locked(db, character["id"])
    if (
        achievement_id not in state["running"]
        and achievement_id not in catalog.load(db)["definitions"]
        and not _guild_daily_trackable(db, character["id"], achievement_id)
    ):
        raise ValueError("Unknown or unqualified tracked achievement")
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


def project_section(progress, authority, *, db, character_id=None):
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
    dates = {}
    if character_id is not None and set(state["running"] + state["completed"]) & {
        1389,
        1390,
        1391,
    }:
        from wakfu_server.guild_daily_quests import activation_dates

        dates = activation_dates(db, character_id)
    if character_id is not None and state["running"]:
        # Recurring missions need their activation timestamp in every owned
        # character projection, not only the explicit journal snapshot. The
        # native client uses it to decide whether a mission is still running.
        from wakfu_server.objectives.environmental_recurring_storage import (
            activation_dates as recurring_activation_dates,
        )

        dates.update(recurring_activation_dates(db, character_id))
    return _journal_section(db, state, dates, character_id)


def _guild_daily_trackable(db, character_id, identity):
    from wakfu_server.guild_daily_quests import trackable

    return trackable(db, character_id, identity)
