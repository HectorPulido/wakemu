"""Daily final-room receipts coexist with weekly journal state and rewards."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import struct
import unittest

from wakfu_server.achievements import rewards, service, storage
from wakfu_server.objectives import environmental_recurring_storage as recurring
from wakfu_server.progression import XP_BY_LEVEL
from wakfu_server.world import World
from wakfu_server.objectives import environmental_daily_selection as selection
from wakfu_server.objectives import environmental_presence as presence


class RecurringDailyHunterBackendTests(unittest.TestCase):
    def test_daily_authenticated_target_period_reset_and_capacity_retry_preserve_weekly_state(
        self,
    ):
        from test_recurring_hunter_backend import RecurringHunterBackendTests

        fixture = RecurringHunterBackendTests(
            methodName="test_source_gated_acceptance_multi_boss_receipt_period_reward_and_rollback"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        daily_id, weekly_id, target_boss, dungeon_id = 4450, 3766, 4731, 141
        store = fixture.store
        with store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(DISTINCT definition_id) AS n FROM recurring_hunter_contracts "
                    "WHERE period_ms=604800000"
                ).fetchone()["n"],
                16,
            )
            daily_ids = [
                r["definition_id"]
                for r in db.execute(
                    "SELECT DISTINCT definition_id FROM "
                    "recurring_hunter_contracts WHERE period_ms=86400000 AND interpretation_policy=%s "
                    "ORDER BY definition_id",
                    (recurring.DAILY_POLICY,),
                )
            ]
            self.assertEqual(len(daily_ids), 50)
            self.assertEqual(
                db.execute(
                    "SELECT count(DISTINCT definition_id) AS n FROM recurring_hunter_contracts "
                    "WHERE period_ms=604800000 OR interpretation_policy=%s",
                    (recurring.DAILY_POLICY,),
                ).fetchone()["n"],
                66,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_hunter_acceptance_sources"
                ).fetchone()["n"],
                0,
            )
            # Load every imported daily through the real global catalog and
            # immutable route/plan attestation, without admitting 50 fights.
            for definition in daily_ids:
                row, contract, original_rewards = recurring._load(db, definition)
                self.assertEqual(
                    (
                        contract.period_ms,
                        contract.required_distinct,
                        len(original_rewards),
                    ),
                    (86400000, 1, 2),
                )
                self.assertEqual(
                    row["daily_target_authority"]["boss_reference"],
                    contract.boss_references[0],
                )
                self.assertEqual(
                    row["daily_target_authority"]["native_reward_order"],
                    [r["reward_id"] for r in original_rewards],
                )
            daily_row, daily, daily_rewards = recurring._load(db, daily_id)
            weekly_row, weekly, _ = recurring._load(db, weekly_id)
            self.assertEqual(
                (daily.period_ms, daily.required_distinct, daily.boss_references),
                (86400000, 1, (target_boss,)),
            )
            self.assertEqual(weekly.period_ms, 604800000)
            self.assertEqual(
                daily_row["interpretation_policy"],
                "wakemu.daily-hunter-public-final-room-v1",
            )
            self.assertEqual(
                sorted(
                    (
                        r["reward_id"],
                        r["native_type"],
                        r["reference"],
                        r["amount"],
                        r["native_flag"],
                    )
                    for r in daily_rewards
                ),
                [(8302, 5, 21001, 20, False), (8303, 6, None, 732590, False)],
            )
            level = max(daily.minimum_level, weekly.minimum_level)
            db.execute(
                "UPDATE characters SET level=%s WHERE id=%s",
                (level, fixture.character["id"]),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[level], fixture.character["id"]),
            )
            fixture.level = level
            fixture.character = store.character(
                fixture.owner["account"], fixture.character["id"], db
            )
            now = recurring._now(db)
            week_start = weekly.anchor_ms + weekly.period(now) * weekly.period_ms
            category = daily_row["daily_target_authority"]["category_id"]
            members = [
                (r["definition_id"], r["version"])
                for r in db.execute(
                    "SELECT definition_id,version FROM recurring_hunter_daily_members WHERE category_id=%s "
                    "AND pool_version=(SELECT pool_version FROM recurring_hunter_daily_active WHERE singleton) "
                    "ORDER BY definition_id,version",
                    (category,),
                )
            ]
            self.assertEqual((category, len(members)), (691, 6))
            target_index = members.index((daily_id, daily_row["version"]))
            self.assertEqual(target_index, 5)
            offset = (target_index - week_start // selection.DAY_MS) % len(members)
            clock = [week_start + offset * selection.DAY_MS + 1000]
            self.assertGreaterEqual(clock[0], daily.anchor_ms)
            daily_period = daily.period(clock[0])
            weekly_period = weekly.period(clock[0])
            next_day = daily.anchor_ms + (daily_period + 1) * daily.period_ms + 1000
            self.assertEqual(weekly.period(next_day), weekly_period)
        # Create a genuine selected lease after the controlled clock changes;
        # no session-expiry SQL or fake live-identity dictionary is used.
        store.clock = lambda: clock[0] / 1000
        old_generation = fixture.owner["generation"]
        generation = store.begin_session(
            fixture.owner["account"], previous_generation=old_generation
        )
        store.select_character(
            fixture.owner["account"], generation, fixture.character["id"]
        )
        fixture.owner["generation"] = generation
        fixture.character = store.character(
            fixture.owner["account"], fixture.character["id"]
        )
        world = World(lambda _: b"", lambda _: b"", lambda *_: True)
        world.join(generation, object(), fixture.character)
        self.enterContext(patch.object(presence, "_world", world))
        self.enterContext(
            patch.object(recurring, "_now", side_effect=lambda _: clock[0])
        )
        with store.connection() as db:
            db.execute("UPDATE recurring_hunter_daily_active SET enabled=true")
            # This binding exercises the backend without claiming that an
            # original NPC acceptance action has been recovered or activated.
            for identity, version in (
                (daily_id, daily_row["version"]),
                (weekly_id, weekly_row["version"]),
            ):
                db.execute(
                    "INSERT INTO recurring_hunter_acceptance_sources VALUES "
                    "(%s,%s,'npc_dialogue',777,888,'isolated test-only acceptance producer')",
                    (identity, version),
                )

            def timestamp():
                return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(
                    milliseconds=clock[0]
                )

            def accept(identity, key):
                storage.record_event(
                    db,
                    fixture.character["id"],
                    key,
                    dict(
                        kind="native_recurring_acceptance",
                        definition_id=identity,
                        real_level=store.character(
                            fixture.owner["account"], fixture.character["id"], db
                        )["level"],
                        source_kind="npc_dialogue",
                        source_reference=777,
                        action_id=888,
                    ),
                )
                db.execute(
                    "UPDATE character_achievement_events SET created_at=%s WHERE character_id=%s AND event_key=%s",
                    (timestamp(), fixture.character["id"], key),
                )
                return recurring.accept_from_receipt(
                    db, store, fixture.character, identity, receipt_key=key
                )

            original_event = service._event

            def fight(references, *, definition=dungeon_id):
                # Reuse the existing real final-room fixture. Provision its
                # durable dungeon identity before the actual event constructor
                # records the receipt; never relabel an existing event payload.
                def event_with_dungeon(connection, character, resolved, originals):
                    connection.execute(
                        "UPDATE dungeon_instances SET definition_id=%s WHERE instance_id="
                        "(SELECT instance_id FROM dungeon_room_encounters WHERE fight_id=%s)",
                        (definition, resolved.id),
                    )
                    return original_event(connection, character, resolved, originals)

                with patch.object(service, "_event", side_effect=event_with_dungeon):
                    resolved, event = fixture.fight(db, references)
                db.execute(
                    "UPDATE character_achievement_events SET created_at=%s WHERE character_id=%s AND event_key=%s",
                    (timestamp(), fixture.character["id"], "fight:" + str(resolved.id)),
                )
                self.assertEqual(event["completed_dungeon_id"], definition)
                return resolved, event

            def balances():
                xp = db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (fixture.character["id"],),
                ).fetchone()["xp"]
                items = db.execute(
                    "SELECT COALESCE(sum(quantity),0)::bigint AS n FROM character_quest_items "
                    "WHERE character_id=%s AND reference=21001",
                    (fixture.character["id"],),
                ).fetchone()["n"]
                return xp, items

            self.assertTrue(accept(weekly_id, "weekly:coexist")["applied"])
            with self.assertRaisesRegex(ValueError, "selection|selected|chosen|pinned"):
                accept(daily_id, "daily:first")
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_hunter_acceptances "
                    "WHERE definition_id=%s",
                    (daily_id,),
                ).fetchone()["n"],
                0,
            )
            self.assertIsNone(
                selection.chosen_for_receipt(
                    db,
                    category_id=category,
                    occurred_at_ms=clock[0],
                    definition_id=daily_id,
                    version=daily_row["version"],
                )
            )
            clock[0] += 1
            choices = selection.select_for_character(db, store, fixture.character)
            chosen = next(row for row in choices if row["category_id"] == category)
            self.assertEqual(
                (chosen["definition_id"], chosen["version"], chosen["eligible"]),
                (daily_id, daily_row["version"], True),
            )
            # Preserve the exact receipt rejected above. Selection may be
            # pinned later in the same day; no fabricated temporal cutoff is
            # added to the original acceptance contract.
            self.assertTrue(
                recurring.accept_from_receipt(
                    db, store, fixture.character, daily_id, receipt_key="daily:first"
                )["applied"]
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_events "
                    "WHERE character_id=%s AND event_key=%s",
                    (fixture.character["id"], "daily:first"),
                ).fetchone()["n"],
                1,
            )
            initial = storage.load_locked(db, fixture.character["id"])
            self.assertIn(weekly_id, initial["running"])
            self.assertIn(daily_id, initial["running"])
            # A valid winning final-room receipt for another boss must not
            # become this daily target merely through its contract/title.
            wrong, wrong_event = fight([1259])
            wrong_result = recurring.settle_combat(
                db, store, fixture.character, wrong, wrong_event
            )
            self.assertEqual(wrong_result["completed"], [])
            self.assertEqual(
                {r["definition_id"] for r in wrong_result["credited"]}, {weekly_id}
            )
            self.assertEqual(
                recurring.settle_combat(
                    db, store, fixture.character, wrong, wrong_event
                )["credited"],
                [],
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_hunter_victories "
                    "WHERE character_id=%s AND definition_id=%s",
                    (fixture.character["id"], daily_id),
                ).fetchone()["n"],
                0,
            )
            wrong_dungeon, wrong_dungeon_event = fight([target_boss], definition=1)
            wrong_dungeon_result = recurring.settle_combat(
                db, store, fixture.character, wrong_dungeon, wrong_dungeon_event
            )
            self.assertEqual(
                (wrong_dungeon_result["credited"], wrong_dungeon_result["completed"]),
                ([], []),
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_hunter_victories "
                    "WHERE character_id=%s AND definition_id=%s",
                    (fixture.character["id"], daily_id),
                ).fetchone()["n"],
                0,
            )
            actual, event = fight([target_boss])
            with self.assertRaises(ValueError):
                recurring.settle_combat(
                    db,
                    store,
                    fixture.character,
                    actual,
                    dict(event, completed_dungeon_id=dungeon_id + 1),
                )
            before = balances()
            real_grant = rewards.grant
            attempts = []

            def grant_then_capacity(connection, backend, character, reward, **kwargs):
                attempts.append(reward["d"])
                real_grant(connection, backend, character, reward, **kwargs)
                raise rewards.RewardCapacity(
                    "injected after actual grant to prove savepoint rollback"
                )

            with patch.object(rewards, "grant", side_effect=grant_then_capacity):
                completed = recurring.settle_combat(
                    db, store, fixture.character, actual, event
                )
            self.assertEqual(completed["completed"], [daily_id])
            self.assertEqual(
                {r["definition_id"] for r in completed["credited"]}, {daily_id}
            )
            self.assertEqual(sorted(attempts), [8302, 8303])
            self.assertEqual(balances(), before)
            journal = storage.load_locked(db, fixture.character["id"])
            self.assertIn(daily_id, journal["completed"])
            self.assertIn(weekly_id, journal["running"])
            pending = storage.pending_rewards(db, fixture.character["id"])
            self.assertEqual(len(pending), 2)
            self.assertEqual({r["achievement_id"] for r in pending}, {daily_id})
            self.assertEqual(
                sorted(
                    (r["payload"]["d"], r["payload"]["aeV"], r["payload"]["ckl"])
                    for r in pending
                ),
                [(8302, 5, [21001, 20]), (8303, 6, [732590])],
            )
            # Pending rewards survive a daily reset while the weekly
            # acceptance and its already-earned boss contribution remain.
            clock[0] = next_day
            reset = recurring.synchronize(db, store, fixture.character)
            self.assertIn(13205, [opcode for opcode, _ in reset])
            journal = storage.load_locked(db, fixture.character["id"])
            self.assertNotIn(daily_id, journal["completed"])
            self.assertIn(weekly_id, journal["running"])
            self.assertEqual(
                storage.pending_rewards(db, fixture.character["id"]), pending
            )
            weekly_acceptance = db.execute(
                "SELECT * FROM recurring_hunter_acceptances WHERE character_id=%s "
                "AND definition_id=%s",
                (fixture.character["id"], weekly_id),
            ).fetchone()
            self.assertEqual(weekly_acceptance["period_index"], weekly_period)
            self.assertIsNone(weekly_acceptance["expired_at_ms"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_hunter_victories WHERE character_id=%s "
                    "AND definition_id=%s",
                    (fixture.character["id"], weekly_id),
                ).fetchone()["n"],
                1,
            )
            delivered_packets = service.drain_rewards(db, store, fixture.character)
            self.assertTrue(delivered_packets)
            quest_packets = [
                body for opcode, body in delivered_packets if opcode == 13879
            ]
            self.assertEqual(len(quest_packets), 1)
            actor, operation, reference, quantity = struct.unpack(
                ">qBih", quest_packets[0]
            )
            self.assertEqual(
                (actor, reference, quantity),
                (fixture.character["id"], 21001, before[1] + 20),
            )
            self.assertEqual(operation, 2 if before[1] else 0)
            self.assertEqual(balances(), (before[0] + 732590, before[1] + 20))
            self.assertEqual(storage.pending_rewards(db, fixture.character["id"]), [])
            self.assertEqual(service.drain_rewards(db, store, fixture.character), [])
            self.assertEqual(balances(), (before[0] + 732590, before[1] + 20))
        # The old reward pair is durably drained before genuine selection
        # bootstrap, so select_character cannot conceal an extra reward grant.
        world.leave(fixture.character["id"], fixture.owner["generation"])
        generation = store.begin_session(
            fixture.owner["account"], previous_generation=fixture.owner["generation"]
        )
        store.select_character(
            fixture.owner["account"], generation, fixture.character["id"]
        )
        fixture.owner["generation"] = generation
        fixture.character = store.character(
            fixture.owner["account"], fixture.character["id"]
        )
        world.join(generation, object(), fixture.character)
        with store.connection() as db:
            with self.assertRaisesRegex(ValueError, "selection|selected|chosen|pinned"):
                accept(daily_id, "daily:unselected-next")
            choices = selection.select_for_character(db, store, fixture.character)
            chosen = next(row for row in choices if row["category_id"] == category)
            next_identity, next_version = chosen["definition_id"], chosen["version"]
            self.assertNotEqual(next_identity, daily_id)
            self.assertIsNone(
                selection.chosen_for_receipt(
                    db,
                    category_id=category,
                    occurred_at_ms=clock[0],
                    definition_id=daily_id,
                    version=daily_row["version"],
                )
            )
            with self.assertRaisesRegex(ValueError, "selection|selected|chosen|pinned"):
                accept(daily_id, "daily:unselected-next")
            db.execute(
                "INSERT INTO recurring_hunter_acceptance_sources VALUES "
                "(%s,%s,'npc_dialogue',777,888,'isolated test-only acceptance producer')",
                (next_identity, next_version),
            )
            self.assertTrue(accept(next_identity, "daily:next")["applied"])
            self.assertFalse(accept(next_identity, "daily:next")["applied"])
            replay = recurring.settle_combat(
                db, store, fixture.character, actual, event
            )
            self.assertEqual((replay["credited"], replay["completed"]), ([], []))
            self.assertEqual(storage.pending_rewards(db, fixture.character["id"]), [])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM recurring_hunter_acceptances a "
                    "JOIN recurring_hunter_contracts c USING(definition_id,version) WHERE a.character_id=%s "
                    "AND c.period_ms=86400000 AND c.interpretation_policy=%s",
                    (fixture.character["id"], recurring.DAILY_POLICY),
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_achievement_reward_outbox WHERE "
                    "character_id=%s AND achievement_id=%s",
                    (fixture.character["id"], daily_id),
                ).fetchone()["n"],
                2,
            )

    def test_published_daily_v2_preserves_today_v1_receipt_and_rotates_tomorrow(self):
        from psycopg import DatabaseError, sql
        from test_recurring_hunter_backend import RecurringHunterBackendTests
        from wakfu_server import native_catalog

        fixture = RecurringHunterBackendTests(
            methodName="test_source_gated_acceptance_multi_boss_receipt_period_reward_and_rollback"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store = fixture.store
        identity, category = 4450, 691
        with store.connection() as db:
            row, contract, _ = recurring._load(db, identity, 1)
            # Warm the actual immutable attestation, then change only the
            # publication query: a cache hit must still reject a foreign release.
            recurring._load(db, identity, 1)
            revision = row["daily_target_authority"]["native_catalog_revision"]
            with patch.object(
                native_catalog,
                "release",
                return_value="0" * 64 if revision != "0" * 64 else "1" * 64,
            ):
                with self.assertRaisesRegex(ValueError, "published catalog"):
                    recurring._load(db, identity, 1)
            recurring._load(db, identity, 1)
            level = contract.minimum_level
            db.execute(
                "UPDATE characters SET level=%s WHERE id=%s",
                (level, fixture.character["id"]),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[level], fixture.character["id"]),
            )
            members = db.execute(
                "SELECT definition_id,version FROM recurring_hunter_daily_members "
                "WHERE category_id=%s AND pool_version=(SELECT pool_version FROM "
                "recurring_hunter_daily_active WHERE singleton) ORDER BY definition_id,version",
                (category,),
            ).fetchall()
            identities = [r["definition_id"] for r in members]
            self.assertEqual(len(identities), 6)
            day = recurring._now(db) // selection.DAY_MS
            day += (identities.index(identity) - day) % len(identities)
            clock = [(day * selection.DAY_MS) + 1000]
        store.clock = lambda: clock[0] / 1000
        generation = store.begin_session(
            fixture.owner["account"], previous_generation=fixture.owner["generation"]
        )
        store.select_character(
            fixture.owner["account"], generation, fixture.character["id"]
        )
        fixture.owner["generation"] = generation
        character = store.character(fixture.owner["account"], fixture.character["id"])
        world = World(lambda _: b"", lambda _: b"", lambda *_: True)
        world.join(generation, object(), character)
        self.enterContext(patch.object(presence, "_world", world))
        self.enterContext(
            patch.object(recurring, "_now", side_effect=lambda _: clock[0])
        )

        def receipt(db, definition, key, *, action=888):
            storage.record_event(
                db,
                character["id"],
                key,
                dict(
                    kind="native_recurring_acceptance",
                    definition_id=definition,
                    real_level=level,
                    source_kind="npc_dialogue",
                    source_reference=777,
                    action_id=action,
                ),
            )
            db.execute(
                "UPDATE character_achievement_events SET created_at=%s "
                "WHERE character_id=%s AND event_key=%s",
                (
                    datetime.fromtimestamp(clock[0] / 1000, timezone.utc),
                    character["id"],
                    key,
                ),
            )

        with store.connection() as db:
            db.execute("UPDATE recurring_hunter_daily_active SET enabled=true")
            choices = selection.select_for_character(db, store, character)
            today = next(r for r in choices if r["category_id"] == category)
            self.assertEqual((today["definition_id"], today["version"]), (identity, 1))
            db.execute(
                "INSERT INTO recurring_hunter_acceptance_sources VALUES "
                "(%s,1,'npc_dialogue',777,888,'isolated test-only v1 acceptance producer')",
                (identity,),
            )
            receipt(db, identity, "daily:immutable:first")
            # Publish complete new immutable versions of this category through
            # ordinary INSERTs. No source row or issued choice is rewritten.
            for table in (
                "recurring_hunter_contracts",
                "recurring_hunter_targets",
                "recurring_hunter_rewards",
                "recurring_hunter_target_authority",
            ):
                columns = [
                    r["column_name"]
                    for r in db.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema=current_schema() AND table_name=%s ORDER BY ordinal_position",
                        (table,),
                    )
                ]
                self.assertIn("version", columns)
                targets = sql.SQL(",").join(sql.Identifier(c) for c in columns)
                values = sql.SQL(",").join(
                    sql.SQL("2") if c == "version" else sql.Identifier(c)
                    for c in columns
                )
                db.execute(
                    sql.SQL(
                        "INSERT INTO {} ({}) SELECT {} FROM {} "
                        "WHERE version=1 AND definition_id=ANY(%s)"
                    ).format(
                        sql.Identifier(table), targets, values, sql.Identifier(table)
                    ),
                    (identities,),
                )
            for definition in identities:
                # A source valid only for v2 must not authorize today's v1.
                action = 999 if definition == identity else 888
                db.execute(
                    "INSERT INTO recurring_hunter_acceptance_sources VALUES "
                    "(%s,2,'npc_dialogue',777,%s,'isolated test-only v2 acceptance producer')",
                    (definition, action),
                )
            self.assertEqual(recurring._load(db, identity)[0]["version"], 2)
            db.execute(
                "INSERT INTO recurring_hunter_daily_pools VALUES "
                "('daily-test-published-v2',%s,%s,false)",
                (selection.POLICY, "b" * 64),
            )
            db.execute(
                "INSERT INTO recurring_hunter_daily_members SELECT "
                "'daily-test-published-v2',category_id,definition_id,"
                "CASE WHEN category_id=%s THEN 2 ELSE version END "
                "FROM recurring_hunter_daily_members WHERE pool_version=%s",
                (category, today["pool_version"]),
            )
            db.execute(
                "UPDATE recurring_hunter_daily_pools SET sealed=true WHERE pool_version='daily-test-published-v2'"
            )
            db.execute(
                "UPDATE recurring_hunter_daily_active SET pool_version='daily-test-published-v2'"
            )
            issued = next(
                r
                for r in selection.select_for_character(db, store, character)
                if r["category_id"] == category
            )
            self.assertEqual(issued, today)
            self.assertIsNone(
                selection.chosen_for_receipt(
                    db,
                    category_id=category,
                    occurred_at_ms=clock[0],
                    definition_id=identity,
                    version=2,
                )
            )
            receipt(db, identity, "daily:immutable:wrong-source", action=999)
            with self.assertRaisesRegex(ValueError, "producer"):
                recurring.accept_from_receipt(
                    db,
                    store,
                    character,
                    identity,
                    receipt_key="daily:immutable:wrong-source",
                )
            other = identities[0]
            receipt(db, other, "daily:immutable:wrong-choice")
            with self.assertRaisesRegex(ValueError, "selected"):
                recurring.accept_from_receipt(
                    db,
                    store,
                    character,
                    other,
                    receipt_key="daily:immutable:wrong-choice",
                )
            self.assertTrue(
                recurring.accept_from_receipt(
                    db, store, character, identity, receipt_key="daily:immutable:first"
                )["applied"]
            )
            self.assertFalse(
                recurring.accept_from_receipt(
                    db, store, character, identity, receipt_key="daily:immutable:first"
                )["applied"]
            )
            accepted = db.execute(
                "SELECT version,acceptance_event_key FROM recurring_hunter_acceptances "
                "WHERE character_id=%s AND definition_id=%s",
                (character["id"], identity),
            ).fetchall()
            self.assertEqual(
                accepted,
                [dict(version=1, acceptance_event_key="daily:immutable:first")],
            )
            for statement in (
                "UPDATE recurring_hunter_contracts SET minimum_level=minimum_level+1 WHERE definition_id=4450 AND version=1",
                "UPDATE recurring_hunter_daily_choices SET version=2 WHERE category_id=691",
            ):
                with self.assertRaises(DatabaseError), db.transaction():
                    db.execute(statement)
            self.assertEqual(storage.pending_rewards(db, character["id"]), [])
        clock[0] += selection.DAY_MS
        world.leave(character["id"], generation)
        generation = store.begin_session(
            fixture.owner["account"], previous_generation=generation
        )
        store.select_character(fixture.owner["account"], generation, character["id"])
        fixture.owner["generation"] = generation
        character = store.character(fixture.owner["account"], character["id"])
        world.join(generation, object(), character)
        with store.connection() as db:
            tomorrow = next(
                r
                for r in selection.select_for_character(db, store, character)
                if r["category_id"] == category
            )
            expected = identities[(day + 1) % len(identities)]
            self.assertEqual(
                (
                    tomorrow["definition_id"],
                    tomorrow["version"],
                    tomorrow["pool_version"],
                ),
                (expected, 2, "daily-test-published-v2"),
            )
            self.assertNotEqual(expected, identity)
            receipt(db, expected, "daily:immutable:tomorrow")
            self.assertTrue(
                recurring.accept_from_receipt(
                    db,
                    store,
                    character,
                    expected,
                    receipt_key="daily:immutable:tomorrow",
                )["applied"]
            )
            self.assertFalse(
                recurring.accept_from_receipt(
                    db,
                    store,
                    character,
                    expected,
                    receipt_key="daily:immutable:tomorrow",
                )["applied"]
            )
            self.assertEqual(
                db.execute(
                    "SELECT version FROM recurring_hunter_acceptances "
                    "WHERE character_id=%s AND definition_id=%s",
                    (character["id"], expected),
                ).fetchone()["version"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT version FROM recurring_hunter_daily_choices "
                    "WHERE category_id=%s AND utc_day=%s",
                    (category, day),
                ).fetchone()["version"],
                1,
            )
            self.assertEqual(storage.pending_rewards(db, character["id"]), [])
