"""Account-scoped first steps are deduplicated and paid through existing receipts."""
from datetime import datetime, timezone
import hashlib
import json
import unittest

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server.objectives import catalog, onboarding, repository


class ObjectivesOnboardingPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("onboarding-test-owner", "local-password")[
            "id"
        ]
        self.main = self.store.create_character(self.account, "Onboarding Main")["id"]
        self.hero = self.store.create_character(self.account, "Onboarding Hero")["id"]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.main)
        self._seed_daily_reward_catalog()

    def _seed_daily_reward_catalog(self):
        revision = "e" * 64
        docs = {
            "item-stack-rules.json": json.dumps(
                {"items": {"27083": {"max_stack": 9999}, "27093": {"max_stack": 9999}}}
            ).encode(),
            "item-equipment-rules.json": json.dumps({"items": []}).encode(),
        }
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_catalog_releases(revision,document_count,source_bytes,complete) VALUES(%s,2,%s,true)",
                (revision, sum(len(raw) for raw in docs.values())),
            )
            for path, raw in docs.items():
                db.execute(
                    "INSERT INTO native_catalog_documents(revision,path,raw,sha256,source_bytes,record_count) VALUES(%s,%s,%s,%s,%s,0)",
                    (revision, path, raw, hashlib.sha256(raw).hexdigest(), len(raw)),
                )
            db.execute(
                "INSERT INTO native_catalog_active(id,revision) VALUES(1,%s)",
                (revision,),
            )

    def enqueue(self, character, key, payload, at):
        with self.store.connection() as db:
            return repository.enqueue(db, self.account, character, key, payload, at)

    def test_seeded_first_steps_are_account_once_ordered_and_valid(self):
        with self.store.connection() as db:
            rows = {
                row["key"]: row["definition"]
                for row in repository.list_definitions(db)
                if row["key"].startswith("onboarding-v1.")
            }
        self.assertEqual(len(rows), 7)
        for index in range(1, 8):
            key = f"onboarding-v1.{index:02d}"
            rule = catalog.validate_definition(rows[key])
            self.assertEqual(
                (rule["scope"], rule["kind"], rule["schedule"]["type"]),
                ("account", "onboarding", "once"),
            )
            self.assertEqual(
                rule["prerequisite_keys"],
                [] if index == 1 else [f"onboarding-v1.{index-1:02d}"],
            )
            self.assertEqual(
                rule["rewards"], [{"kind": "scaled", "policy_key": "content-v1.daily"}]
            )
        self.assertEqual([row["key"] for row in onboarding.definitions()], list(rows))

    def test_scope_kind_and_prerequisite_graph_validation_is_bidirectional(self):
        def rule(key, *, scope="account", kind="task", prerequisites=()):
            return {
                "key": key,
                "title": key,
                "description": key,
                "kind": kind,
                "enabled": True,
                "scope": scope,
                "prerequisite_keys": list(prerequisites),
                "objectives": [
                    {"key": "x", "event": "synthetic", "filters": {}, "target": 1}
                ],
                "schedule": {"type": "once", "timezone": "UTC"},
                "rewards": [],
            }

        account_once = rule("scope-account-parent", scope="account", kind="onboarding")
        character_rule = rule("scope-character-rejected", scope="character")
        with self.store.connection() as db:
            repository.put_definition(db, account_once, 0)
            with self.assertRaisesRegex(ValueError, "account scope"):
                repository.put_definition(db, character_rule, 0)

        # Account progress supports every schedule and recurrence. Legacy
        # character definitions remain readable, but new definitions cannot
        # be created with character-only ownership.
        for index, schedule in enumerate(
            (
                {"type": "daily", "timezone": "UTC"},
                {"type": "weekly", "timezone": "UTC"},
                {"type": "calendar", "timezone": "UTC", "dates": ["2026-10-15"]},
                {
                    "type": "interval",
                    "timezone": "UTC",
                    "anchor": "2026-10-15T00:00:00+00:00",
                    "seconds": 3600,
                },
            )
        ):
            account_recurring = rule(f"account-recurrence-{index}", kind="daily")
            account_recurring["schedule"] = schedule
            self.assertEqual(
                catalog.validate_definition(account_recurring)["scope"], "account"
            )
        unsupported_scope = rule("invalid-scope", scope="global")
        with self.assertRaisesRegex(ValueError, "scope"):
            catalog.validate_definition(unsupported_scope)

    def test_first_steps_dedup_same_fight_across_heroes_and_pay_only_completing_character(
        self,
    ):
        before = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
        later = datetime(2026, 10, 15, 12, 0, 1, tzinfo=timezone.utc)
        # A future step source before its prerequisite is permanently ignored.
        early_kill = {
            "kind": "original_monster_killed",
            "fight_id": 699,
            "actors": [{"actor_id": -6990 - i, "reference": 1} for i in range(3)],
        }
        self.enqueue(self.hero, "fight:699", early_kill, before)
        with self.store.connection() as db:
            result = repository.process_batch(db)
            self.assertEqual((result["processed"], result["failed"]), (1, 0))
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM objectives_account_progress WHERE account_id=%s AND definition_key='onboarding-v1.02'",
                    (self.account,),
                ).fetchone()
            )

        self.enqueue(
            self.main,
            "transition:astrub:first",
            {"kind": "map_entered", "map_id": 527},
            later,
        )
        with self.store.connection() as db:
            result = repository.process_batch(db)
            self.assertEqual((result["processed"], result["failed"]), (1, 0), result)
            first = db.execute(
                "SELECT counters,completed_at,reward_character_id FROM objectives_account_progress WHERE account_id=%s AND definition_key='onboarding-v1.01'",
                (self.account,),
            ).fetchone()
            self.assertEqual(first["counters"], {"arrive": 1})
            self.assertIsNotNone(first["completed_at"])
            self.assertEqual(first["reward_character_id"], self.main)

        fight = {
            "kind": "original_monster_killed",
            "fight_id": 700,
            "actors": [{"actor_id": -7000 - i, "reference": 1} for i in range(3)],
        }
        first_enqueue = self.enqueue(self.main, "fight:700", fight, later)
        hero_enqueue = self.enqueue(
            self.hero,
            "fight:700",
            fight,
            datetime(2026, 10, 15, 12, 0, 2, tzinfo=timezone.utc),
        )
        self.assertFalse(first_enqueue["replayed"])
        self.assertFalse(hero_enqueue["replayed"])
        self.assertTrue(
            self.enqueue(
                self.hero,
                "fight:700",
                fight,
                datetime(2026, 10, 15, 12, 0, 2, tzinfo=timezone.utc),
            )["replayed"]
        )
        with self.store.connection() as db:
            result = repository.process_batch(db)
            self.assertEqual((result["processed"], result["failed"]), (2, 0), result)
            progress = db.execute(
                "SELECT counters,completed_at,reward_character_id FROM objectives_account_progress WHERE account_id=%s AND definition_key='onboarding-v1.02'",
                (self.account,),
            ).fetchone()
            self.assertEqual(progress["counters"], {"gobballs": 3})
            self.assertIsNotNone(progress["completed_at"])
            self.assertEqual(progress["reward_character_id"], self.main)
            source = db.execute(
                "SELECT count(*) n FROM objectives_account_sources WHERE account_id=%s AND source_key='original_monster_killed:fight:700'",
                (self.account,),
            ).fetchone()["n"]
            rewards = db.execute(
                "SELECT count(*) n FROM objectives_rewards WHERE character_id=%s AND definition_key='onboarding-v1.02' AND period_key='once'",
                (self.main,),
            ).fetchone()["n"]
            other_rewards = db.execute(
                "SELECT count(*) n FROM objectives_rewards WHERE character_id=%s AND definition_key='onboarding-v1.02'",
                (self.hero,),
            ).fetchone()["n"]
            main_projection = repository.list_progress(db, self.main)
            hero_projection = repository.list_progress(db, self.hero)
        self.assertEqual(source, 1)
        self.assertEqual(rewards, 3)
        self.assertEqual(other_rewards, 0)
        for character_progress in (main_projection, hero_projection):
            by_key = {
                row["definition_key"]: row
                for row in character_progress
                if row["definition_key"].startswith("onboarding-v1.")
            }
            self.assertEqual(set(by_key), {"onboarding-v1.01", "onboarding-v1.02"})
            self.assertIsNotNone(by_key["onboarding-v1.02"]["completed_at"])


if __name__ == "__main__":
    unittest.main()
