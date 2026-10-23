"""Native reward17 freezes actual earned level before durable delivery retries."""
import csv
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

from psycopg import DatabaseError
from wakfu_server import builds
from wakfu_server.achievements import rewards, service, storage, scaled_xp
from wakfu_server.progression import XP_BY_LEVEL
from wakfu_server.wakfu_xp import monster_base_xp
from wakfu_server.wire import proto_field


class NativeScaledXpFormulaTests(unittest.TestCase):
    def test_all_980_original_jvm_reward_vectors(self):
        path = Path(__file__).parent / "fixtures/native_reward17_scaled_xp.csv"
        with path.open() as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 980)
        self.assertEqual({int(r["real_level"]) for r in rows}, set(range(1, 246)))
        self.assertEqual(
            {int(r["parameter_percent"]) for r in rows}, {1000, 2000, 3000, 4000}
        )
        for row in rows:
            level, parameter, base, amount = (
                int(row[k])
                for k in (
                    "real_level",
                    "parameter_percent",
                    "native_monster_base_xp",
                    "base_reward_xp",
                )
            )
            with self.subTest(level=level, parameter=parameter):
                self.assertEqual(
                    scaled_xp._rounded(parameter, monster_base_xp(level)), amount
                )
                self.assertEqual(scaled_xp._rounded(parameter, base), amount)


class NativeScaledXpPostgresTests(unittest.TestCase):
    def test_disabled_policy_atomic_reservation_frozen_real_level_and_once_delivery(
        self,
    ):
        from test_recurring_hunter_backend import RecurringHunterBackendTests

        fixture = RecurringHunterBackendTests(
            methodName="test_source_gated_acceptance_multi_boss_receipt_period_reward_and_rollback"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        store, owner = fixture.store, fixture.owner
        identity = fixture.character["id"]
        achievement, cycle, reward_id = 3766, "native17:component", 17001
        payload = dict(d=reward_id, aeV=17, ckk=False, ckl=[1000])
        sheet = b"".join(
            proto_field(k, v)
            for k, v in (
                (8, 0),
                (18, b"Scaled XP effective ten"),
                (24, 10),
                (56, 0),
                (64, 1),
            )
        )
        with store.connection() as db:
            self.assertFalse(
                db.execute(
                    "SELECT enabled FROM achievement_scaled_xp_active WHERE singleton"
                ).fetchone()["enabled"]
            )
            db.execute("UPDATE characters SET level=50 WHERE id=%s", (identity,))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[50], identity),
            )
            db.execute(
                "INSERT INTO character_builds VALUES(%s,0,%s,%s,%s,%s) "
                "ON CONFLICT(character_id,build_index) DO UPDATE SET sheet=EXCLUDED.sheet",
                (identity, sheet, builds.EMPTY_EQUIPMENT, b"", builds.EMPTY_APTITUDES),
            )
            db.execute(
                "UPDATE character_build_selection SET active_index=0,revision=revision+1 WHERE character_id=%s",
                (identity,),
            )
            character = store.character(owner["account"], identity, db)
            self.assertEqual(
                (character["level"], character["effective_level"]), (50, 10)
            )
            self.assertEqual(character["xp"], XP_BY_LEVEL[50])
            with self.assertRaisesRegex(ValueError, "policy"):
                storage.enqueue_reward(
                    db, identity, achievement, cycle, str(reward_id), payload
                )
            self.assertEqual(storage.pending_rewards(db, identity), [])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM achievement_scaled_xp_receipts"
                ).fetchone()["n"],
                0,
            )
            db.execute(
                "UPDATE achievement_scaled_xp_active SET enabled=true WHERE singleton"
            )
            with self.assertRaises(ValueError):
                rewards.grant(db, store, character, payload)
            with self.assertRaises(ValueError):
                scaled_xp.reserve(
                    db, identity, achievement, cycle, str(reward_id), payload
                )
            for invalid in (
                dict(payload, ckl=[]),
                dict(payload, ckl=[True]),
                dict(payload, ckl=[0]),
                dict(payload, ckl=[-1]),
                dict(payload, ckl=[1.5]),
                dict(payload, ckl=[2**31]),
                dict(payload, ckk=0),
                dict(payload, d=True),
            ):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    storage.enqueue_reward(
                        db, identity, achievement, cycle, str(reward_id), invalid
                    )
            with self.assertRaises(ValueError):
                storage.enqueue_reward(
                    db, identity, achievement, cycle, "wrong-native-reference", payload
                )
            self.assertEqual(storage.pending_rewards(db, identity), [])
            self.assertTrue(
                storage.enqueue_reward(
                    db, identity, achievement, cycle, str(reward_id), payload
                )
            )
            earned = dict(
                db.execute(
                    "SELECT * FROM achievement_scaled_xp_receipts WHERE character_id=%s",
                    (identity,),
                ).fetchone()
            )
            self.assertEqual(
                (
                    earned["real_level"],
                    earned["native_base_xp"],
                    earned["native_parameter"],
                    earned["final_amount"],
                ),
                (50, 37810, 1000, 378100),
            )
            self.assertEqual(earned["payload"], payload)
            self.assertEqual(
                store.character(owner["account"], identity, db)["xp"], XP_BY_LEVEL[50]
            )
            pending = storage.pending_rewards(db, identity)[0]
            foreign = store.character(
                fixture.foreign["account"], fixture.foreign["character"], db
            )
            for character_arg, reward_arg, entitlement in (
                (foreign, payload, pending),
                (dict(character, account_id=foreign["account_id"]), payload, pending),
                (character, dict(payload, d=reward_id + 1), pending),
                (
                    character,
                    payload,
                    dict(pending, reward_key="wrong-native-reference"),
                ),
            ):
                with self.assertRaises(ValueError):
                    rewards.grant(
                        db, store, character_arg, reward_arg, entitlement=entitlement
                    )
            with self.assertRaises(DatabaseError), db.transaction():
                db.execute(
                    "UPDATE achievement_scaled_xp_receipts SET final_amount=final_amount+1 WHERE character_id=%s",
                    (identity,),
                )
            # A later actual progression change and policy disable cannot
            # reprice an entitlement already earned at real level fifty.
            db.execute("UPDATE characters SET level=96 WHERE id=%s", (identity,))
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[96], identity),
            )
            db.execute(
                "UPDATE achievement_scaled_xp_active SET enabled=false WHERE singleton"
            )
            self.assertFalse(
                storage.enqueue_reward(
                    db, identity, achievement, cycle, str(reward_id), payload
                )
            )
            fixed = dict(d=6001, aeV=6, ckk=False, ckl=[37])
            item = dict(d=5001, aeV=5, ckk=False, ckl=[20752, 2])
            self.assertTrue(
                storage.enqueue_reward(db, identity, achievement, cycle, "6001", fixed)
            )
            self.assertTrue(
                storage.enqueue_reward(db, identity, achievement, cycle, "5001", item)
            )
            before = store.character(owner["account"], identity, db)
            tokens_before = db.execute(
                "SELECT COALESCE(sum(quantity),0)::bigint AS n FROM character_quest_items "
                "WHERE character_id=%s AND reference=20752",
                (identity,),
            ).fetchone()["n"]
            real_grant = rewards.grant
            attempted = []

            def fail_after_real_grant(connection, backend, actor, reward, **kwargs):
                result = real_grant(connection, backend, actor, reward, **kwargs)
                if reward["aeV"] == 17:
                    attempted.append(reward["d"])
                    raise rewards.RewardCapacity(
                        "injected after actual scaled XP grant"
                    )
                return result

            # Outer rollback also removes the ordinary item/fixed rewards that
            # can be delivered while the scaled reward's savepoint is retried.
            with self.assertRaisesRegex(
                RuntimeError, "rollback delivery"
            ), db.transaction():
                with patch.object(rewards, "grant", side_effect=fail_after_real_grant):
                    service.drain_rewards(db, store, before)
                self.assertEqual(
                    [
                        r["payload"]["aeV"]
                        for r in storage.pending_rewards(db, identity)
                    ],
                    [17],
                )
                raise RuntimeError("rollback delivery")
            self.assertEqual(attempted, [reward_id])
            self.assertEqual(
                store.character(owner["account"], identity, db)["xp"], before["xp"]
            )
            self.assertEqual(len(storage.pending_rewards(db, identity)), 3)
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM achievement_scaled_xp_receipts WHERE character_id=%s",
                        (identity,),
                    ).fetchone()
                ),
                earned,
            )
        # Real reconnect selection retries the durable outbox. Capture only
        # the actual native XP publisher; its arithmetic and grants stay real.
        original_notice = rewards._xp
        notices = []

        def capture_grant(*args, **kwargs):
            packets = original_notice(*args, **kwargs)
            notices.extend(body for opcode, body in packets if opcode == 13613)
            return packets

        generation = store.begin_session(
            owner["account"], previous_generation=owner["generation"]
        )
        with patch.object(rewards, "_xp", side_effect=capture_grant):
            store.select_character(owner["account"], generation, identity)
        owner["generation"] = generation
        decoded = [struct.unpack(">BBqqhB", body) for body in notices]
        self.assertEqual(sorted(row[3] for row in decoded), [37, 378100])
        self.assertTrue(
            all(row[0:3] == (1, 1, identity) and row[-1] == 0 for row in decoded)
        )
        with store.connection() as db:
            current = store.character(owner["account"], identity, db)
            self.assertEqual(current["xp"], before["xp"] + 378100 + 37)
            self.assertEqual(current["effective_level"], 10)
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM character_quest_items WHERE character_id=%s "
                    "AND reference=20752",
                    (identity,),
                ).fetchone()["quantity"],
                tokens_before + 2,
            )
            self.assertEqual(storage.pending_rewards(db, identity), [])
            self.assertEqual(service.drain_rewards(db, store, current), [])
            self.assertEqual(
                rewards.grant(db, store, current, payload, entitlement=pending), []
            )
            self.assertFalse(
                storage.enqueue_reward(
                    db, identity, achievement, cycle, str(reward_id), payload
                )
            )
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM achievement_scaled_xp_receipts WHERE character_id=%s",
                        (identity,),
                    ).fetchone()
                ),
                earned,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM achievement_scaled_xp_receipts"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                store.character(owner["account"], identity, db)["xp"], current["xp"]
            )
        generation = store.begin_session(
            owner["account"], previous_generation=generation
        )
        with patch.object(
            rewards,
            "_xp",
            side_effect=AssertionError("reconnect attempted a second XP grant"),
        ):
            store.select_character(owner["account"], generation, identity)
