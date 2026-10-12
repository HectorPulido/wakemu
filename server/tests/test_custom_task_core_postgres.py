"""Isolated PostgreSQL qualification; Luna owns execution after source promotion."""
from custom_task_fixtures import task_definitions
import copy
from postgres_case import PostgresCase
from wakfu_server.custom_tasks import catalog, service


class CustomTaskCorePostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("custom-owner", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Custom Owner")["id"]
        self.event = {
            "kind": "original_monster_killed",
            "fight_id": 1,
            "actors": [{"actor_id": -index - 1, "reference": 1} for index in range(20)],
        }

    def settle(self, db, key="fight:1", event=None, definitions=None):
        facts = copy.deepcopy(self.event) if event is None else event
        if event is None and key.startswith("fight:"):
            facts["fight_id"] = int(key.split(":")[1])
        return service.settle(db, self.account, self.character, key, facts, definitions)

    def test_completion_replay_conflict_and_reward_reservation(self):
        definitions = copy.deepcopy(task_definitions())
        definitions[0]["rewards"] = [{"aeV": 5, "ckl": [12686, 20]}]
        with self.store.connection() as db:
            result = self.settle(db, definitions=definitions)
            self.assertEqual(result["completed"], ["gobball-kills-20"])
            self.assertTrue(self.settle(db, definitions=definitions)["replayed"])
            self.assertEqual(
                self.settle(db, key="fight:2", definitions=definitions)["completed"], []
            )
        with self.store.connection() as db:
            row = service.snapshot(db, self.account, self.character, definitions)[0]
            self.assertEqual((row["count"], row["completed"]), (20, True))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_reward_outbox"
                ).fetchone()["n"],
                1,
            )
        changed = copy.deepcopy(self.event)
        changed["actors"][0]["reference"] = 2
        with self.assertRaises(ValueError), self.store.connection() as db:
            self.settle(db, event=changed, definitions=definitions)

    def test_disabled_filter_retains_history_and_never_retrocounts(self):
        disabled = copy.deepcopy(task_definitions())
        disabled[0]["enabled"] = False
        with self.store.connection() as db:
            self.assertEqual(self.settle(db, definitions=disabled)["completed"], [])
            self.assertNotIn(
                "gobball-kills-20",
                [
                    row["key"]
                    for row in service.snapshot(
                        db, self.account, self.character, disabled
                    )
                ],
            )
        with self.store.connection() as db:
            self.assertTrue(self.settle(db)["replayed"])
            self.assertEqual(
                service.snapshot(db, self.account, self.character)[0]["count"], 0
            )
            self.assertEqual(
                self.settle(db, key="fight:2")["completed"], ["gobball-kills-20"]
            )
        with self.store.connection() as db:
            service.snapshot(db, self.account, self.character, disabled)
            self.assertEqual(
                db.execute(
                    "SELECT count FROM character_custom_task_progress WHERE task_key=%s",
                    ("gobball-kills-20",),
                ).fetchone()["count"],
                20,
            )
            self.assertEqual(self.settle(db, key="fight:3")["completed"], [])

    def test_rollback_foreign_owner_and_semantic_rekey(self):
        with self.assertRaises(RuntimeError), self.store.connection() as db:
            self.settle(db)
            raise RuntimeError("Simulated enclosing gameplay rollback")
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_events"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                service.snapshot(db, self.account, self.character)[0]["count"], 0
            )
        with self.assertRaises(ValueError), self.store.connection() as db:
            service.settle(
                db, self.account + 999, self.character, "fight:1", self.event
            )
        with self.store.connection() as db:
            self.settle(db)
        changed = copy.deepcopy(task_definitions())
        changed[0]["target"] = 30
        with self.assertRaises(ValueError), self.store.connection() as db:
            self.settle(db, key="fight:2", definitions=changed)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_events"
                ).fetchone()["n"],
                1,
            )

    def test_successful_plant_operations_exactly_once_in_enclosing_transaction(self):
        event = {
            "kind": "monster_seed_planted",
            "family_ids": [68],
            "seed_reference": 7361,
            "resource_reference": 192,
            "operation_id": "12345678123456789234123456789abc",
        }
        with self.store.connection() as db:
            self.settle(
                db, key="planting:12345678123456789234123456789abc", event=event
            )
            self.assertTrue(
                self.settle(
                    db, key="planting:12345678123456789234123456789abc", event=event
                )["replayed"]
            )
        with self.store.connection() as db:
            self.assertEqual(
                service.snapshot(db, self.account, self.character)[1]["count"], 1
            )
        with self.assertRaises(RuntimeError), self.store.connection() as db:
            self.settle(
                db,
                key="planting:12345678123456789234123456789abd",
                event=dict(event, operation_id="12345678123456789234123456789abd"),
            )
            raise RuntimeError("Seed placement transaction failed")
        with self.store.connection() as db:
            self.assertEqual(
                service.snapshot(db, self.account, self.character)[1]["count"], 1
            )

    def test_source_identity_cannot_be_recredited_under_arbitrary_keys(self):
        seed = {
            "kind": "monster_seed_planted",
            "family_ids": [68],
            "seed_reference": 7361,
            "resource_reference": 192,
            "operation_id": "12345678123456789234123456789abc",
        }
        canonical = "planting:" + seed["operation_id"]
        with self.store.connection() as db:
            self.settle(db)
            self.settle(db, key=canonical, event=seed)
        attempts = [
            ("arbitrary-fight", self.event),
            ("fight:2", self.event),
            ("planting:12345678123456789234123456789abd", seed),
            ("arbitrary-planting", seed),
        ]
        for key, facts in attempts:
            with self.subTest(key=key), self.assertRaises(
                ValueError
            ), self.store.connection() as db:
                self.settle(db, key=key, event=facts)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_events"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                service.snapshot(db, self.account, self.character)[1]["count"], 1
            )

    def _plant_event(self, number, families=None):
        import uuid

        return {
            "kind": "monster_seed_planted",
            "family_ids": [68] if families is None else families,
            "seed_reference": 7361,
            "resource_reference": 192,
            "operation_id": uuid.UUID(int=number).hex,
        }

    def _plant(self, db, number, families=None, definitions=None):
        event = self._plant_event(number, families)
        return self.settle(
            db,
            key="planting:" + event["operation_id"],
            event=event,
            definitions=definitions,
        )

    def test_twenty_distinct_successful_placements_complete_once(self):
        definitions = copy.deepcopy(task_definitions())
        definitions[1]["rewards"] = [{"aeV": 6, "ckl": [100]}]
        with self.store.connection() as db:
            for operation in range(1, 20):
                self.assertEqual(
                    self._plant(db, operation, [69, 68], definitions)["completed"], []
                )
            view = service.snapshot(db, self.account, self.character, definitions)[1]
            self.assertEqual((view["count"], view["completed"]), (19, False))
        with self.store.connection() as db:
            result = self._plant(db, 20, [68, 69], definitions)
            self.assertEqual(result["completed"], ["gobball-seeds-20"])
            self.assertTrue(self._plant(db, 20, [69, 68], definitions)["replayed"])
            self.assertEqual(self._plant(db, 21, [68], definitions)["completed"], [])
        with self.store.connection() as db:
            view = service.snapshot(db, self.account, self.character, definitions)[1]
            self.assertEqual((view["count"], view["completed"]), (20, True))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_reward_outbox"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_events"
                ).fetchone()["n"],
                21,
            )
        # Same operation with an altered native family binding must conflict.
        with self.assertRaises(ValueError), self.store.connection() as db:
            self._plant(db, 20, [68], definitions)

    def test_two_concurrent_twentieth_placement_retries_complete_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        definitions = copy.deepcopy(task_definitions())
        definitions[1]["rewards"] = [{"aeV": 6, "ckl": [100]}]
        with self.store.connection() as db:
            for operation in range(1, 20):
                self._plant(db, operation, definitions=definitions)
        barrier = Barrier(2)

        def commit_twentieth():
            with self.store.connection() as db:
                db.execute("SET LOCAL lock_timeout='10s'")
                barrier.wait(timeout=10)
                return self._plant(db, 20, definitions=definitions)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(commit_twentieth) for _ in range(2)]
            results = [future.result(timeout=20) for future in futures]
        self.assertEqual(sum(result["replayed"] for result in results), 1)
        self.assertEqual(sum(len(result["completed"]) for result in results), 1)
        with self.store.connection() as db:
            view = service.snapshot(db, self.account, self.character, definitions)[1]
            self.assertEqual((view["count"], view["completed"]), (20, True))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_reward_outbox"
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_events"
                ).fetchone()["n"],
                20,
            )

    def test_soft_deleted_owned_character_cannot_settle_or_read_tasks(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET deleted_at=CURRENT_TIMESTAMP WHERE id=%s",
                (self.character,),
            )
        with self.assertRaises(ValueError), self.store.connection() as db:
            self.settle(db)
        with self.assertRaises(ValueError), self.store.connection() as db:
            service.snapshot(db, self.account, self.character)
        with self.store.connection() as db:
            for table in (
                "character_custom_task_events",
                "character_custom_task_progress",
                "character_custom_task_reward_outbox",
            ):
                self.assertEqual(
                    db.execute("SELECT count(*) AS n FROM " + table).fetchone()["n"], 0
                )

    def test_database_policy_is_authoritative_and_missing_policy_fails_closed(self):
        from psycopg.types.json import Jsonb

        with self.store.connection() as db:
            original = catalog.load(db)
            self.assertEqual(original, catalog.validate(task_definitions()))
            disabled = task_definitions()
            disabled[0]["enabled"] = False
            db.execute(
                "UPDATE settings SET value=%s WHERE name=%s",
                (Jsonb(disabled), catalog.SETTING),
            )
            self.assertEqual(self.settle(db)["updated"], [])
            self.assertNotIn(
                "gobball-kills-20",
                [
                    row["key"]
                    for row in service.snapshot(db, self.account, self.character)
                ],
            )
        with self.store.connection() as db:
            db.execute("DELETE FROM settings WHERE name=%s", (catalog.SETTING,))
        with self.assertRaises(ValueError), self.store.connection() as db:
            self.settle(db, key="fight:2")
        with self.assertRaises(ValueError), self.store.connection() as db:
            service.snapshot(db, self.account, self.character)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM character_custom_task_events"
                ).fetchone()["n"],
                1,
            )
