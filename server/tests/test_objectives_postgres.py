"""Durable objective ingress, revisions, retries and one-time period rewards."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import copy
import hashlib
import json
import os
from pathlib import Path
import psycopg
import select
import subprocess
import sys
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server.objectives import repository


def definition(
    *, target=2, schedule=None, rewards=None, event="original_monster_killed"
):
    return {
        "key": "fixture-objective",
        "title": "Fixture objective",
        "description": "Isolated persistence check",
        # These fixtures exercise evaluator and recurrence mechanics rather
        # than assignment eligibility; use an always-visible account objective.
        "kind": "achievement",
        "enabled": True,
        "objectives": [
            {
                "key": "count",
                "event": event,
                "filters": (
                    {"references": [1]}
                    if event == "original_monster_killed"
                    else {"subject": 1}
                ),
                "target": target,
            }
        ],
        "schedule": schedule or {"type": "daily", "timezone": "UTC"},
        "rewards": rewards
        if rewards is not None
        else [{"kind": "kamas", "amount": 100}],
    }


def kill(fight_id, reference=1):
    return {
        "kind": "original_monster_killed",
        "fight_id": fight_id,
        "actors": [{"actor_id": -fight_id, "reference": reference}],
    }


class ObjectivesPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("objectives-test-owner", "local-password")[
            "id"
        ]
        self.character = self.store.create_character(self.account, "Objective Test")[
            "id"
        ]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character)

    def add_definition(self, value=None, **options):
        value = value or definition(**options)
        with self.store.connection() as db:
            return repository.put_definition(db, value, 0)

    def ingest(self, fight_id, *, at=None, reference=1):
        with self.store.connection() as db:
            return repository.enqueue(
                db,
                self.account,
                self.character,
                f"fight:{fight_id}",
                kill(fight_id, reference),
                at,
            )

    def run_worker(self, limit=100):
        with self.store.connection() as db:
            return repository.process_batch(db, limit)

    def test_replay_is_idempotent_and_conflicting_identity_is_rejected(self):
        self.add_definition()
        at = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
        self.assertFalse(self.ingest(101, at=at)["replayed"])
        self.assertTrue(self.ingest(101, at=at)["replayed"])
        with self.assertRaises(repository.ConflictError):
            self.ingest(101, at=at, reference=999)
        with self.store.connection() as db:
            event_before = db.execute(
                "SELECT definitions,payload FROM objectives_events WHERE event_key='fight:101'"
            ).fetchone()
        self.assertIn(
            {"key": "fixture-objective", "revision": 1}, event_before["definitions"]
        )
        result = self.run_worker()
        self.assertEqual((result["processed"], result["failed"]), (1, 0), event_before)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) n FROM objectives_events").fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT counters->>'count' AS n FROM objectives_account_progress WHERE account_id=%s AND definition_key='fixture-objective'",
                    (self.account,),
                ).fetchone()["n"],
                "1",
            )

    def test_multiple_facts_complete_each_period_and_reserve_reward_once(self):
        self.add_definition(target=2)
        self.ingest(201, at=datetime(2026, 10, 15, 10, tzinfo=timezone.utc))
        self.ingest(202, at=datetime(2026, 10, 15, 11, tzinfo=timezone.utc))
        first = self.run_worker()
        self.assertEqual(first["processed"], 2)
        self.assertEqual(self.run_worker()["processed"], 0)
        with self.store.connection() as db:
            progress = db.execute(
                "SELECT period_key,counters,completed_at FROM objectives_account_progress WHERE account_id=%s AND definition_key='fixture-objective'",
                (self.account,),
            ).fetchall()
            rewards = db.execute(
                "SELECT count(*) n FROM objectives_rewards WHERE character_id=%s AND definition_key='fixture-objective'",
                (self.character,),
            ).fetchone()["n"]
        self.assertEqual(len(progress), 1)
        self.assertEqual(progress[0]["counters"]["count"], 2)
        self.assertIsNotNone(progress[0]["completed_at"])
        self.assertEqual(rewards, 1)

        # The next UTC calendar day gets a separate entitlement; same-period replays do not.
        self.ingest(203, at=datetime(2026, 10, 16, 0, 1, tzinfo=timezone.utc))
        self.ingest(204, at=datetime(2026, 10, 16, 0, 2, tzinfo=timezone.utc))
        self.assertEqual(self.run_worker()["processed"], 2)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM objectives_account_progress WHERE account_id=%s AND definition_key='fixture-objective'",
                    (self.account,),
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM objectives_rewards WHERE character_id=%s AND definition_key='fixture-objective'",
                    (self.character,),
                ).fetchone()["n"],
                2,
            )

    def test_independent_objective_counters_complete_only_after_all_requirements(self):
        value = definition(target=1)
        value["objectives"] = [
            {
                "key": "kills",
                "event": "original_monster_killed",
                "filters": {"references": [1]},
                "target": 1,
            },
            {
                "key": "plant",
                "event": "monster_seed_planted",
                "filters": {
                    "family_id": 68,
                    "seed_reference": 7361,
                    "resource_reference": 192,
                },
                "target": 1,
            },
        ]
        self.add_definition(value)
        operation = "12345678123456789234123456789abc"
        with self.store.connection() as db:
            repository.enqueue(db, self.account, self.character, "fight:601", kill(601))
        self.assertEqual(self.run_worker()["processed"], 1)
        with self.store.connection() as db:
            state = db.execute(
                "SELECT counters,completed_at FROM objectives_account_progress WHERE account_id=%s AND definition_key='fixture-objective'",
                (self.account,),
            ).fetchone()
        self.assertEqual(state["counters"], {"kills": 1, "plant": 0})
        self.assertIsNone(state["completed_at"])
        with self.store.connection() as db:
            repository.enqueue(
                db,
                self.account,
                self.character,
                "planting:" + operation,
                {
                    "kind": "monster_seed_planted",
                    "family_ids": [68],
                    "seed_reference": 7361,
                    "resource_reference": 192,
                    "operation_id": operation,
                },
            )
        self.assertEqual(self.run_worker()["processed"], 1)
        with self.store.connection() as db:
            state = db.execute(
                "SELECT counters,completed_at FROM objectives_account_progress WHERE account_id=%s AND definition_key='fixture-objective'",
                (self.account,),
            ).fetchone()
            rewards = db.execute(
                "SELECT count(*) n FROM objectives_rewards WHERE character_id=%s AND definition_key='fixture-objective'",
                (self.character,),
            ).fetchone()["n"]
        self.assertEqual(state["counters"], {"kills": 1, "plant": 1})
        self.assertIsNotNone(state["completed_at"])
        self.assertEqual(rewards, 1)

    def test_definition_revision_optimistic_lock_and_earned_semantics_are_immutable(
        self,
    ):
        row = self.add_definition(target=1)
        self.assertEqual(row["revision"], 1)
        renamed = copy.deepcopy(row["definition"])
        renamed["title"] = "Updated presentation"
        with self.store.connection() as db:
            revised = repository.put_definition(db, renamed, 1)
        self.assertEqual(revised["revision"], 2)
        with self.assertRaises(repository.ConflictError):
            with self.store.connection() as db:
                repository.put_definition(db, renamed, 1)
        self.ingest(301, at=datetime(2026, 10, 15, 12, tzinfo=timezone.utc))
        self.assertEqual(self.run_worker()["processed"], 1)
        changed = copy.deepcopy(renamed)
        changed["objectives"][0]["target"] = 7
        with self.assertRaisesRegex(repository.ConflictError, "immutable"):
            with self.store.connection() as db:
                repository.put_definition(db, changed, 2)

    def test_source_level_and_reward_policy_revision_are_frozen_before_worker_runs(
        self,
    ):
        from wakfu_server.objectives import reward_policies

        revision = "c" * 64
        documents = {
            "item-stack-rules.json": json.dumps({"items": {"2021": {}}}).encode(),
            "item-equipment-rules.json": json.dumps(
                {"items": [{"reference": 2021, "minimum_level": 1}]}
            ).encode(),
        }
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_catalog_releases(revision,document_count,source_bytes,complete) VALUES(%s,2,%s,true)",
                (revision, sum(map(len, documents.values()))),
            )
            for path, raw in documents.items():
                db.execute(
                    "INSERT INTO native_catalog_documents(revision,path,raw,sha256,source_bytes,record_count) VALUES(%s,%s,%s,%s,%s,1)",
                    (revision, path, raw, hashlib.sha256(raw).hexdigest(), len(raw)),
                )
            db.execute(
                "INSERT INTO native_catalog_active(id,revision) VALUES(1,%s)",
                (revision,),
            )
            db.execute("UPDATE characters SET level=20 WHERE id=%s", (self.character,))
            reward_policies.put_policy(
                db,
                "test-level-rewards",
                {
                    "bands": [
                        {
                            "minimum": 1,
                            "maximum": 99,
                            "rewards": [{"kind": "kamas", "amount": 100}],
                        },
                        {
                            "minimum": 100,
                            "maximum": 200,
                            "rewards": [{"kind": "kamas", "amount": 200}],
                        },
                    ]
                },
                0,
                operator="test",
            )
            value = definition(target=1)
            value["rewards"] = [{"kind": "scaled", "policy_key": "test-level-rewards"}]
            repository.put_definition(db, value, 0)

        # The event source snapshot must freeze both level and policy revision,
        # even if the player levels up and an administrator revises the policy
        # before the asynchronous evaluator claims the event.
        self.ingest(321, at=datetime(2026, 10, 15, 12, tzinfo=timezone.utc))
        with self.store.connection() as db:
            event = db.execute(
                "SELECT character_level,reward_policies->'test-level-rewards'->>'revision' AS revision FROM objectives_events WHERE event_key='fight:321'"
            ).fetchone()
            self.assertEqual((event["character_level"], event["revision"]), (20, "1"))
            db.execute("UPDATE characters SET level=120 WHERE id=%s", (self.character,))
            reward_policies.put_policy(
                db,
                "test-level-rewards",
                {
                    "bands": [
                        {
                            "minimum": 1,
                            "maximum": 99,
                            "rewards": [{"kind": "kamas", "amount": 999}],
                        },
                        {
                            "minimum": 100,
                            "maximum": 200,
                            "rewards": [{"kind": "kamas", "amount": 1999}],
                        },
                    ]
                },
                1,
                operator="test-revision",
            )

        self.assertEqual(self.run_worker()["processed"], 1)
        with self.store.connection() as db:
            entitlement = db.execute(
                "SELECT payload,policy_snapshot FROM objectives_rewards WHERE character_id=%s AND definition_key='fixture-objective'",
                (self.character,),
            ).fetchone()
        self.assertEqual(entitlement["payload"], {"kind": "kamas", "amount": 100})
        self.assertEqual(
            entitlement["policy_snapshot"],
            [{"key": "test-level-rewards", "revision": 1, "level": 20}],
        )
        self.assertTrue(
            self.ingest(321, at=datetime(2026, 10, 15, 12, tzinfo=timezone.utc))[
                "replayed"
            ]
        )
        self.assertEqual(self.run_worker()["processed"], 0)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM objectives_rewards WHERE character_id=%s",
                    (self.character,),
                ).fetchone()["n"],
                1,
            )

    def test_queued_event_freezes_eligible_definitions_and_fences_semantic_edits(self):
        initial = definition(target=1)
        self.add_definition(initial)
        self.ingest(350, at=datetime(2026, 10, 15, 12, tzinfo=timezone.utc))
        changed = copy.deepcopy(initial)
        changed["objectives"][0]["target"] = 2
        with self.assertRaises(repository.ConflictError):
            with self.store.connection() as db:
                repository.put_definition(db, changed, 1)

        later = copy.deepcopy(initial)
        later["key"] = "added-after-event"
        with self.store.connection() as db:
            repository.put_definition(db, later, 0)
        self.assertEqual(self.run_worker()["processed"], 1)
        with self.store.connection() as db:
            keys = db.execute(
                "SELECT definition_key FROM objectives_account_progress WHERE account_id=%s",
                (self.account,),
            ).fetchall()
        names = {row["definition_key"] for row in keys}
        self.assertIn("fixture-objective", names)
        self.assertIn("gobball-kills-20", names)
        self.assertNotIn("added-after-event", names)

    def test_prerequisite_completion_does_not_unlock_child_on_same_event_in_either_key_order(
        self,
    ):
        for label, parent_key, child_key in (
            ("forward", "a-parent", "z-child"),
            ("reverse", "z-parent", "a-child"),
        ):
            parent = definition(target=1, event="synthetic")
            parent.update(key=parent_key, title=parent_key)
            parent["objectives"][0]["filters"] = {"segment": label}
            child = definition(target=1, event="synthetic")
            child.update(key=child_key, title=child_key, prerequisite_keys=[parent_key])
            child["objectives"][0]["filters"] = {"segment": label}
            self.add_definition(parent)
            with self.store.connection() as db:
                repository.put_definition(db, child, 0)

            first_time = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)
            with self.store.connection() as db:
                repository.enqueue(
                    db,
                    self.account,
                    self.character,
                    f"synthetic:{label}:first",
                    {"kind": "synthetic", "segment": label},
                    first_time,
                )
            self.assertEqual(self.run_worker()["processed"], 1)
            with self.store.connection() as db:
                parent_state = db.execute(
                    "SELECT completed_at FROM objectives_account_progress WHERE account_id=%s AND definition_key=%s",
                    (self.account, parent_key),
                ).fetchone()
                child_state = db.execute(
                    "SELECT 1 FROM objectives_account_progress WHERE account_id=%s AND definition_key=%s",
                    (self.account, child_key),
                ).fetchone()
            self.assertIsNotNone(parent_state["completed_at"])
            self.assertIsNone(
                child_state,
                f"{child_key} counted the event that completed {parent_key}",
            )

            second_time = datetime(2026, 10, 15, 13, tzinfo=timezone.utc)
            with self.store.connection() as db:
                repository.enqueue(
                    db,
                    self.account,
                    self.character,
                    f"synthetic:{label}:second",
                    {"kind": "synthetic", "segment": label},
                    second_time,
                )
            self.assertEqual(self.run_worker()["processed"], 1)
            with self.store.connection() as db:
                child_state = db.execute(
                    "SELECT counters,completed_at FROM objectives_account_progress WHERE account_id=%s AND definition_key=%s",
                    (self.account, child_key),
                ).fetchone()
            self.assertEqual(child_state["counters"], {"count": 1})
            self.assertIsNotNone(child_state["completed_at"])

    def test_worker_failure_is_retried_after_definition_repair(self):
        self.add_definition(target=1, event="synthetic")
        with self.store.connection() as db:
            repository.enqueue(
                db,
                self.account,
                self.character,
                "synthetic:retry",
                {"kind": "synthetic", "subject": 1},
            )
            db.execute(
                "UPDATE objectives_events SET definitions=jsonb_set(definitions,'{0,revision}','999'::jsonb) WHERE event_key='synthetic:retry'"
            )
        failed = self.run_worker()
        self.assertEqual((failed["processed"], failed["failed"]), (0, 1))
        with self.store.connection() as db:
            event = db.execute(
                "SELECT attempts,processed_at FROM objectives_events"
            ).fetchone()
            self.assertEqual(event["attempts"], 1)
            self.assertIsNone(event["processed_at"])
            db.execute(
                "UPDATE objectives_events SET definitions=%s WHERE event_key='synthetic:retry'",
                (
                    Jsonb(
                        [
                            {
                                "key": "fixture-objective",
                                "revision": 1,
                                "definition": definition(target=1, event="synthetic"),
                            }
                        ]
                    ),
                ),
            )
        retried = self.run_worker()
        self.assertEqual((retried["processed"], retried["failed"]), (1, 0))
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM objectives_account_progress WHERE account_id=%s AND definition_key='fixture-objective'",
                    (self.account,),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute("SELECT attempts FROM objectives_events").fetchone()[
                    "attempts"
                ],
                1,
            )

    def test_concurrent_workers_process_durable_events_once(self):
        self.add_definition(target=3)
        self.ingest(401, at=datetime(2026, 10, 15, 10, tzinfo=timezone.utc))
        self.ingest(402, at=datetime(2026, 10, 15, 11, tzinfo=timezone.utc))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _n: self.run_worker(), range(2)))
        self.assertEqual(sum(row["processed"] for row in results), 2)
        self.assertEqual(sum(row["failed"] for row in results), 0)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM objectives_events WHERE processed_at IS NOT NULL"
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT counters->>'count' AS n FROM objectives_account_progress WHERE account_id=%s AND definition_key='fixture-objective'",
                    (self.account,),
                ).fetchone()["n"],
                "2",
            )
            self.assertEqual(
                db.execute("SELECT count(*) n FROM objectives_rewards").fetchone()["n"],
                0,
            )

    def test_external_reward_delivery_is_once_per_completed_period(self):
        from wakfu_server.custom_tasks import reward_delivery

        self.add_definition(target=1, rewards=[{"kind": "kamas", "amount": 100}])
        with self.store.connection() as db:
            before = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (self.account,)
            ).fetchone()["kamas"]
        for index, (period, first_fight) in enumerate(
            (("2026-10-15", 801), ("2026-10-16", 802))
        ):
            self.ingest(
                first_fight, at=datetime.fromisoformat(period + "T12:00:00+00:00")
            )
            self.assertEqual(self.run_worker()["processed"], 1)
            with patch.dict(
                os.environ, {"WAKFU_OBJECTIVES_MODE": "external"}, clear=False
            ):
                delivered = reward_delivery.deliver(
                    self.store, self.account, self.generation, self.character
                )
                replay = reward_delivery.deliver(
                    self.store, self.account, self.generation, self.character
                )
            self.assertEqual(len(delivered["delivered"]), 1)
            self.assertEqual(
                delivered["delivered"][0][:2], ("fixture-objective", period)
            )
            self.assertEqual(replay["delivered"], [])
        with self.store.connection() as db:
            after = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (self.account,)
            ).fetchone()["kamas"]
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM objectives_rewards WHERE delivered_at IS NOT NULL"
                ).fetchone()["n"],
                2,
            )
        self.assertEqual(after, before + 200)

    def test_external_item_reward_survives_capacity_and_reconnect(self):
        from wakfu_server.custom_tasks import reward_delivery
        from wakfu_server.inventory_elements import create
        from wakfu_server.inventory_move import ACQUISITION_STACKS
        from wakfu_server.combat_drop_delivery import _template_bound

        self.add_definition(target=1, rewards=[{"aeV": 5, "ckl": [2021, 1]}])
        self.ingest(850, at=datetime(2026, 10, 15, 12, tzinfo=timezone.utc))
        self.assertEqual(self.run_worker()["processed"], 1)
        filler = next(
            reference
            for reference, rule in ACQUISITION_STACKS.items()
            if not rule["minimal_mergeable"]
            and create(reference) is None
            and not _template_bound(reference)
        )
        with self.store.connection() as db:
            containers = db.execute(
                "SELECT uid,capacity FROM inventory_containers WHERE character_id=%s ORDER BY kind,uid",
                (self.character,),
            ).fetchall()
            filler_count = sum(container["capacity"] for container in containers)
            for container in containers:
                db.execute(
                    "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                    "SELECT %s,%s,1,%s,slot FROM generate_series(0,%s) AS slot",
                    (
                        self.character,
                        filler,
                        container["uid"],
                        container["capacity"] - 1,
                    ),
                )
        with patch.dict(os.environ, {"WAKFU_OBJECTIVES_MODE": "external"}, clear=False):
            blocked = reward_delivery.deliver(
                self.store, self.account, self.generation, self.character
            )
            self.assertEqual(blocked["delivered"], [])
            self.assertEqual(
                blocked["capacity_pending"], [("fixture-objective", "2026-10-15", 0)]
            )
            with self.store.connection() as db:
                self.assertIsNone(
                    db.execute(
                        "SELECT delivered_at FROM objectives_rewards WHERE character_id=%s AND definition_key='fixture-objective'",
                        (self.character,),
                    ).fetchone()["delivered_at"]
                )
                db.execute(
                    "DELETE FROM inventory_items WHERE container=%s AND slot=%s",
                    (containers[0]["uid"], containers[0]["capacity"] - 1),
                )
            reopened = self.reopen()
            delivered = reward_delivery.deliver(
                reopened, self.account, self.generation, self.character
            )
            replay = reward_delivery.deliver(
                reopened, self.account, self.generation, self.character
            )
        self.assertEqual(
            delivered["delivered"], [("fixture-objective", "2026-10-15", 0)]
        )
        self.assertEqual(replay["packets"], [])
        self.assertEqual(len(delivered["character"]["inventory_items"]), filler_count)

    def test_committed_ingress_and_progress_notify_but_rolled_back_ingress_is_silent(
        self,
    ):
        self.add_definition(target=1)
        password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
        password = Path(password_file).read_text().strip() if password_file else None
        with psycopg.connect(
            self.database_url, password=password, autocommit=True
        ) as listener:
            listener.execute("LISTEN wakemu_objectives_events")
            listener.execute("LISTEN wakemu_objectives_updates")
            with self.assertRaises(RuntimeError):
                with self.store.connection() as db:
                    repository.enqueue(
                        db,
                        self.account,
                        self.character,
                        "fight:501",
                        kill(501),
                        datetime(2026, 10, 15, 12, tzinfo=timezone.utc),
                    )
                    raise RuntimeError("force rollback")
            self.assertEqual(list(listener.notifies(timeout=0.1, stop_after=1)), [])

            self.ingest(502, at=datetime(2026, 10, 15, 12, tzinfo=timezone.utc))
            event_notifications = list(listener.notifies(timeout=1, stop_after=1))
            self.assertEqual(len(event_notifications), 1)
            self.assertEqual(event_notifications[0].channel, "wakemu_objectives_events")
            self.assertEqual(event_notifications[0].payload, str(self.character))

            self.assertEqual(self.run_worker()["processed"], 1)
            progress_notifications = list(listener.notifies(timeout=1, stop_after=1))
            self.assertEqual(len(progress_notifications), 1)
            self.assertEqual(
                progress_notifications[0].channel, "wakemu_objectives_updates"
            )
            self.assertEqual(progress_notifications[0].payload, str(self.character))

    def test_service_worker_commit_wakes_world_socket_subscription_within_two_seconds(
        self,
    ):
        from wakfu_server.custom_tasks.external_updates import Listener

        self.add_definition(target=1)
        stopping = threading.Event()
        listener = Listener(self.store, stopping)
        subscription = listener.subscribe()
        subscription.character_id = self.character
        password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
        password = Path(password_file).read_text().strip() if password_file else ""
        environment = dict(os.environ)
        environment["WAKFU_DATABASE_URL"] = self.database_url
        environment["PGPASSWORD"] = password
        environment["PYTHONPATH"] = os.pathsep.join(
            (
                str(Path(__file__).resolve().parents[1]),
                environment.get("PYTHONPATH", ""),
            )
        )
        worker = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import importlib.util; from pathlib import Path; p=Path('server/objectives-service/service.py'); s=importlib.util.spec_from_file_location('objectives_worker_process',p); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); m.worker()",
            ],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.addCleanup(worker.terminate)
        self.addCleanup(worker.wait)
        try:
            # Ensure both LISTEN sessions are ready before enqueueing. Their query
            # text remains visible in pg_stat_activity while the sessions idle.
            deadline = time.monotonic() + 5
            ready = False
            while time.monotonic() < deadline:
                with self.store.connection() as db:
                    count = db.execute(
                        "SELECT count(*) n FROM pg_stat_activity WHERE datname=current_database() AND query IN ('LISTEN wakemu_objectives_events','LISTEN wakemu_objectives_updates')"
                    ).fetchone()["n"]
                if count >= 2:
                    ready = True
                    break
                if worker.poll() is not None:
                    self.fail("Objectives service worker exited before LISTEN")
                time.sleep(0.02)
            self.assertTrue(
                ready, "Objectives worker and World listener did not finish LISTEN"
            )
            started = time.monotonic()
            self.ingest(901, at=datetime.now(timezone.utc))
            readable, _, _ = select.select([subscription.reader], [], [], 2.0)
            self.assertTrue(
                readable, "Committed objective progress did not wake the World socket"
            )
            self.assertLess(time.monotonic() - started, 2.0)
            self.assertTrue(subscription.dirty.is_set())
            with self.store.connection() as db:
                self.assertIsNotNone(
                    db.execute(
                        "SELECT completed_at FROM objectives_account_progress WHERE account_id=%s AND definition_key='fixture-objective'",
                        (self.account,),
                    ).fetchone()["completed_at"]
                )
        finally:
            subscription.close()
            stopping.set()
            listener.thread.join(timeout=2)
            worker.terminate()
            worker.wait(timeout=5)

    def test_settled_duel_publishes_one_pvp_fact_per_participant_and_replay_is_quiet(
        self,
    ):
        from test_friendly_duels import FriendlyDuelStoreTests
        from wakfu_server.friendly_duels import settle

        context = FriendlyDuelStoreTests(
            methodName="test_duel_settlement_accepts_valid_registered_controlled_summon"
        )
        context.setUp()
        self.addCleanup(context.doCleanups)
        accepted = context._create_accepted_fight()
        fight = context._finished_duel_with_registered_summon(accepted["fight_id"])
        with patch.dict(os.environ, {"WAKFU_OBJECTIVES_MODE": "external"}, clear=False):
            first = settle(
                context.store,
                context.account_a,
                context.generation_a,
                context.char_a["id"],
                fight,
            )
            replay = settle(
                context.store,
                context.account_a,
                context.generation_a,
                context.char_a["id"],
                fight,
            )
        self.assertFalse(first["replayed"])
        self.assertTrue(replay["replayed"])
        with context.store.connection() as db:
            facts = db.execute(
                "SELECT character_id,event_key,payload FROM objectives_events WHERE event_key=%s ORDER BY character_id",
                (f"pvp-completed:{fight.id}",),
            ).fetchall()
        self.assertEqual(
            {row["character_id"] for row in facts},
            {context.char_a["id"], context.char_b["id"]},
        )
        self.assertEqual(len(facts), 2)
        self.assertTrue(all(row["payload"]["kind"] == "pvp_completed" for row in facts))

    def test_ready_scene_map_and_region_visits_are_exact_and_reconnect_idempotent(self):
        from wakfu_server.custom_tasks import exploration

        def discovery(key, event, field, value):
            return {
                "key": key,
                "title": key,
                "description": "Explore a specific source-backed location",
                "kind": "achievement",
                "enabled": True,
                "objectives": [
                    {
                        "key": "visit",
                        "event": event,
                        "filters": {field: value},
                        "target": 1,
                    }
                ],
                "schedule": {"type": "once", "timezone": "UTC"},
                "rewards": [],
            }

        with self.store.connection() as db:
            repository.put_definition(
                db, discovery("map-100", "map_entered", "map_id", 100), 0
            )
            repository.put_definition(
                db, discovery("map-200", "map_entered", "map_id", 200), 0
            )
            repository.put_definition(
                db, discovery("region-77", "region_entered", "region_id", 77), 0
            )
        from wakfu_server import territory_cells

        def region(map_id, x, y):
            return {(100, 0): 77, (100, 1): 78, (200, 0): 90}.get((map_id, x), None)

        with patch.dict(
            os.environ, {"WAKFU_OBJECTIVES_MODE": "external"}, clear=False
        ), patch.object(territory_cells, "region_at", side_effect=region):
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=100,instance_id=0,x=0,y=0 WHERE id=%s",
                    (self.character,),
                )
            self.assertTrue(
                exploration.observe(
                    self.store, self.account, self.generation, self.character
                )
            )
            self.assertFalse(
                exploration.observe(
                    self.store, self.account, self.generation, self.character
                )
            )
            with self.store.connection() as db:
                staged = db.execute(
                    "SELECT payload->>'kind' AS kind FROM objectives_events ORDER BY id"
                ).fetchall()
            self.assertEqual(
                {row["kind"] for row in staged},
                {"map_entered", "region_entered"},
                staged,
            )
            first_batch = self.run_worker()
            self.assertEqual(first_batch["processed"], 2, first_batch)
            with self.store.connection() as db:
                keys = {
                    row["definition_key"]
                    for row in db.execute(
                        "SELECT definition_key FROM objectives_account_progress WHERE account_id=%s",
                        (self.account,),
                    ).fetchall()
                }
            self.assertEqual(keys, {"map-100", "region-77"})

            # A region boundary inside the same map is a true region visit but
            # must not synthesize another map visit or advance another map's task.
            with self.store.connection() as db:
                db.execute("UPDATE characters SET x=1 WHERE id=%s", (self.character,))
            self.assertTrue(
                exploration.observe(
                    self.store, self.account, self.generation, self.character
                )
            )
            self.assertEqual(self.run_worker()["processed"], 1)
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) n FROM objectives_events WHERE character_id=%s AND payload->>'kind'='map_entered'",
                        (self.character,),
                    ).fetchone()["n"],
                    1,
                )
                self.assertIsNone(
                    db.execute(
                        "SELECT 1 FROM objectives_account_progress WHERE account_id=%s AND definition_key='map-200'",
                        (self.account,),
                    ).fetchone()
                )

            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=200,x=0 WHERE id=%s",
                    (self.character,),
                )
            self.assertTrue(
                exploration.observe(
                    self.store, self.account, self.generation, self.character
                )
            )
            self.assertEqual(self.run_worker()["processed"], 2)
            with self.store.connection() as db:
                self.assertIsNotNone(
                    db.execute(
                        "SELECT completed_at FROM objectives_account_progress WHERE account_id=%s AND definition_key='map-200'",
                        (self.account,),
                    ).fetchone()["completed_at"]
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) n FROM objectives_events WHERE character_id=%s AND payload->>'kind'='map_entered'",
                        (self.character,),
                    ).fetchone()["n"],
                    2,
                )

    def _enter_finite_challenge(self, groups, challenges, now):
        from unittest.mock import patch

        from wakfu_server import dungeon_encounters
        from wakfu_server import monsters
        from wakfu_server.objectives import challenges_profiles

        positions = [(-10 + index, -17, 0) for index in range(12)]

        def actor(reference, level, actor_id, *, map_id, x, y, z, instance_id, team=1):
            return {
                "id": actor_id,
                "ref": reference,
                "breed": reference,
                "level": level,
                "effective_level": level,
                "map_id": map_id,
                "instance_id": instance_id,
                "x": x,
                "y": y,
                "z": z,
                "team": team,
                "hp": 10,
                "max_hp": 10,
                "ap": 6,
                "mp": 3,
                "wp": 0,
                "initiative": 1,
                "sprite_id": reference,
            }

        with (
            patch.object(
                challenges_profiles, "validate_profile", side_effect=lambda value: value
            ),
            patch.object(dungeon_encounters, "enemy_formation", return_value=positions),
            patch.object(monsters, "owned_instance", side_effect=actor),
            patch(
                "wakfu_server.combat_monster_world.spawn_group", return_value=b"fixture"
            ),
        ):
            with self.store.connection() as db:
                return challenges.enter_weekly(
                    db,
                    groups,
                    self.account,
                    self.character,
                    geometry_loader=lambda _map_id: {"cells": [], "edges": []},
                    now=now,
                )

    def _settle_finite_challenge(
        self, challenges, groups, run, now, turns, *, winner=0, test_mode=False
    ):
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (fight_id, self.character, self.account),
            )
            challenges.bind_fight(
                db, run["map_id"], run["instance_id"], run["group_id"], fight_id
            )
            if test_mode:
                challenges.mark_test_fight(db, fight_id)
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,)
            )
            settled = challenges.settle_fight(
                db,
                SimpleNamespace(
                    id=fight_id,
                    phase="finished",
                    winner=winner,
                    native_timeline_round=turns,
                ),
                now=now,
            )
            return settled

    def test_finite_challenge_instance_ownership_reconnect_return_and_no_ecology_respawn(
        self,
    ):
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server.objectives import challenges

        now = datetime(2026, 10, 12, 6, tzinfo=timezone.utc)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=10,map_id=1134,instance_id=0,x=-12,y=-8,z=-1 WHERE id=%s",
                (self.character,),
            )
        groups = PersistentGroups(self.store)
        run = self._enter_finite_challenge(groups, challenges, now)
        self.assertFalse(run["replay"])
        self.assertNotEqual(run["instance_id"], 0)
        self.assertTrue(
            all(
                member["instance_id"] == run["instance_id"] for member in run["members"]
            )
        )
        with self.store.connection() as db:
            current = db.execute(
                "SELECT map_id,instance_id FROM characters WHERE id=%s",
                (self.character,),
            ).fetchone()
        self.assertEqual(
            (current["map_id"], current["instance_id"]),
            (run["map_id"], run["instance_id"]),
        )

        replay = self._enter_finite_challenge(groups, challenges, now)
        self.assertTrue(replay["replay"])
        self.assertEqual(
            (replay["attempt_id"], replay["instance_id"]),
            (run["attempt_id"], run["instance_id"]),
        )
        with self.store.connection() as db:
            with self.assertRaisesRegex(ValueError, "use !challenge abandon"):
                challenges.return_from_challenge(db, self.account, self.character)

        outsider = self.store.register(
            "objectives-challenge-outsider", "local-password"
        )["id"]
        foreign_character = self.store.create_character(outsider, "Challenge Outsider")[
            "id"
        ]
        with self.store.connection() as db:
            with self.assertRaisesRegex(ValueError, "foreign"):
                challenges.return_from_challenge(db, outsider, self.character)
            foreign_fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) VALUES(%s,%s,%s,0)",
                (foreign_fight, foreign_character, outsider),
            )
            with self.assertRaisesRegex(ValueError, "unauthorized participant"):
                challenges.bind_fight(
                    db,
                    run["map_id"],
                    run["instance_id"],
                    run["group_id"],
                    foreign_fight,
                )
        self.assertGreater(foreign_character, 0)

        with self.store.connection() as db:
            returned = challenges.return_from_challenge(
                db, self.account, self.character, abandon=True
            )
            run_row = db.execute(
                "SELECT status,returned_at FROM objectives_challenge_runs WHERE attempt_id=%s",
                (run["attempt_id"],),
            ).fetchone()
        self.assertEqual(
            tuple(
                returned[field] for field in ("map_id", "instance_id", "x", "y", "z")
            ),
            (1134, 0, -12, -8, -1),
        )
        self.assertEqual(run_row["status"], "abandoned")
        self.assertIsNotNone(run_row["returned_at"])
        with self.assertRaisesRegex(ValueError, "Finite challenge groups"):
            groups.respawn((run["map_id"], run["instance_id"], run["group_id"]))

    def test_escaped_challenge_recovers_only_members_still_inside_and_allows_fresh_attempt(
        self,
    ):
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server.objectives import challenges

        now = datetime(2026, 10, 12, 6, tzinfo=timezone.utc)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=10,map_id=1134,instance_id=0,x=9,y=8,z=1 WHERE id=%s",
                (self.character,),
            )
        groups = PersistentGroups(self.store)
        run = self._enter_finite_challenge(groups, challenges, now)
        # Simulate an authorized server-side escape of the selected character;
        # recovery must preserve that new location rather than overwrite it.
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=2000,instance_id=0,x=41,y=42,z=0 WHERE id=%s",
                (self.character,),
            )
            escaped = challenges.current_run(db, self.account, self.character)
            challenges.recover_escaped_run(db, escaped)
            recovered_position = db.execute(
                "SELECT map_id,instance_id,x,y,z FROM characters WHERE id=%s",
                (self.character,),
            ).fetchone()
        retry = self._enter_finite_challenge(groups, challenges, now)
        with self.store.connection() as db:
            old = db.execute(
                "SELECT status,returned_at FROM objectives_challenge_runs WHERE attempt_id=%s",
                (run["attempt_id"],),
            ).fetchone()
        self.assertNotEqual(retry["attempt_id"], run["attempt_id"])
        self.assertEqual(old["status"], "abandoned")
        self.assertIsNotNone(old["returned_at"])
        self.assertEqual(tuple(recovered_position.values()), (2000, 0, 41, 42, 0))

    def test_challenge_level_bracket_uses_active_hero_level(self):
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server.objectives import challenges
        from wakfu_server import dungeon_encounters, monsters
        from wakfu_server.objectives import challenges_profiles

        now = datetime(2026, 10, 12, 6, tzinfo=timezone.utc)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=10,map_id=1134,instance_id=0 WHERE id=%s",
                (self.character,),
            )
            hero = self.store.create_character(self.account, "High Level Hero")["id"]
            db.execute(
                "UPDATE characters SET level=30,map_id=1134,instance_id=0 WHERE id=%s",
                (hero,),
            )
            db.execute(
                "INSERT INTO account_hero_rosters(account_id,leader_id) VALUES(%s,%s)",
                (self.account, self.character),
            )
            db.execute(
                "INSERT INTO account_hero_slots(account_id,slot,character_id) VALUES(%s,0,%s)",
                (self.account, hero),
            )
        groups = PersistentGroups(self.store)
        positions = [(-10 + index, -17, 0) for index in range(12)]

        def actor(reference, level, actor_id, *, map_id, x, y, z, instance_id, team=1):
            return {
                "id": actor_id,
                "ref": reference,
                "breed": reference,
                "level": level,
                "effective_level": level,
                "map_id": map_id,
                "instance_id": instance_id,
                "x": x,
                "y": y,
                "z": z,
                "team": team,
                "hp": 10,
                "max_hp": 10,
                "ap": 6,
                "mp": 3,
                "wp": 0,
                "initiative": 1,
                "sprite_id": reference,
            }

        with (
            patch.object(
                challenges_profiles, "validate_profile", side_effect=lambda value: value
            ),
            patch.object(dungeon_encounters, "enemy_formation", return_value=positions),
            patch.object(monsters, "owned_instance", side_effect=actor),
            patch(
                "wakfu_server.combat_monster_world.spawn_group", return_value=b"fixture"
            ),
        ):
            with self.store.connection() as db:
                run = challenges.enter_weekly(
                    db,
                    groups,
                    self.account,
                    self.character,
                    geometry_loader=lambda _map_id: {"cells": [], "edges": []},
                    now=now,
                )
        self.assertEqual(
            (run["bracket"], run["group_level"], run["level"]), ("021-040", 30, 10)
        )

    def test_normal_shared_fight_settlement_publishes_challenge_receipt_once(self):
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server.fight_store import settle_shared
        from wakfu_server.objectives import challenges

        now = datetime(2026, 10, 12, 6, tzinfo=timezone.utc)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=10,map_id=1134,instance_id=0 WHERE id=%s",
                (self.character,),
            )
        groups = PersistentGroups(self.store)
        run = self._enter_finite_challenge(groups, challenges, now)
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                (fight_id, self.character, self.account, self.generation),
            )
            challenges.bind_fight(
                db, run["map_id"], run["instance_id"], run["group_id"], fight_id
            )
        actor = SimpleNamespace(
            id=self.character, owner_id=self.account, controlled=True, team=0
        )
        fight = SimpleNamespace(
            id=fight_id,
            phase="finished",
            winner=0,
            native_timeline_round=4,
            actors={self.character: actor},
            native_summon_registrations={},
        )
        packet = (19531, b"normal-fight-result")
        with patch.dict(
            os.environ, {"WAKFU_OBJECTIVES_MODE": "external"}, clear=False
        ), patch(
            "wakfu_server.combat.combat_terminal_metadata.registered_summon_actor_ids",
            return_value=frozenset(),
        ), patch(
            "wakfu_server.combat.fight_store._write_terminal_checkpoint"
        ):
            first = settle_shared(
                self.store,
                self.account,
                self.generation,
                self.character,
                fight,
                lambda _db, _members, _fight: [packet],
            )
            replay = settle_shared(
                self.store,
                self.account,
                self.generation,
                self.character,
                fight,
                lambda _db, _members, _fight: [packet],
            )
        self.assertEqual(first, [packet])
        self.assertEqual(replay, [packet])
        with self.store.connection() as db:
            event = db.execute(
                "SELECT count(*) n FROM objectives_events WHERE event_key=%s",
                ("challenge:" + run["attempt_id"],),
            ).fetchone()["n"]
            receipt = db.execute(
                "SELECT status,turns FROM objectives_challenge_runs WHERE attempt_id=%s",
                (run["attempt_id"],),
            ).fetchone()
        self.assertEqual(event, 1)
        self.assertEqual((receipt["status"], receipt["turns"]), ("won", 4))

    def test_real_hero_add_remove_fences_preserve_frozen_challenge_roster_and_allow_member_switch(
        self,
    ):
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server.characters import heroes
        from wakfu_server.objectives import challenges

        now = datetime(2026, 10, 12, 6, tzinfo=timezone.utc)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=10,map_id=1134,instance_id=0 WHERE id=%s",
                (self.character,),
            )
        admitted_hero = self.store.create_character(self.account, "Admitted Hero")["id"]
        later_hero = self.store.create_character(self.account, "Later Hero")["id"]
        with self.store.connection() as db:
            for hero_id in (admitted_hero, later_hero):
                db.execute(
                    "UPDATE characters SET level=10,map_id=1134,instance_id=0 WHERE id=%s",
                    (hero_id,),
                )
            db.execute(
                "INSERT INTO account_hero_rosters(account_id,leader_id) VALUES(%s,%s)",
                (self.account, self.character),
            )
            db.execute(
                "INSERT INTO account_hero_slots(account_id,slot,character_id) VALUES(%s,0,%s)",
                (self.account, admitted_hero),
            )
        groups = PersistentGroups(self.store)
        run = self._enter_finite_challenge(groups, challenges, now)

        with self.assertRaisesRegex(ValueError, "Leave the weekly challenge"):
            heroes.add(
                self.store, self.account, self.generation, self.character, later_hero
            )
        with self.assertRaisesRegex(ValueError, "Leave the weekly challenge"):
            heroes.remove(
                self.store, self.account, self.generation, self.character, admitted_hero
            )

        # The selected main may switch to an already admitted hero; this does
        # not mutate the frozen participant set or its original score owner.
        switched = heroes.switch_main(
            self.store, self.account, self.generation, self.character, admitted_hero
        )
        self.assertTrue(switched["applied"])
        with self.store.connection() as db:
            members = db.execute(
                "SELECT character_id FROM objectives_challenge_members WHERE attempt_id=%s ORDER BY character_id",
                (run["attempt_id"],),
            ).fetchall()
            run_row = db.execute(
                "SELECT character_id,owner_account_id FROM objectives_challenge_runs WHERE attempt_id=%s",
                (run["attempt_id"],),
            ).fetchone()
            active_slots = db.execute(
                "SELECT character_id FROM account_hero_slots WHERE account_id=%s ORDER BY slot",
                (self.account,),
            ).fetchall()
        self.assertEqual(
            {row["character_id"] for row in members}, {self.character, admitted_hero}
        )
        self.assertEqual(
            (run_row["character_id"], run_row["owner_account_id"]),
            (self.character, self.account),
        )
        self.assertEqual(
            [row["character_id"] for row in active_slots], [self.character]
        )

    def test_only_finished_normal_week_wins_score_best_attempt_and_finalize_once(self):
        from wakfu_server.combat_group_store import PersistentGroups
        from wakfu_server.objectives import (
            challenges,
            points as account_points,
            rankings,
            reward_policies,
        )

        revision = "d" * 64
        documents = {
            "item-stack-rules.json": json.dumps({"items": {}}).encode(),
            "item-equipment-rules.json": json.dumps({"items": []}).encode(),
        }
        now = datetime(2026, 10, 12, 6, tzinfo=timezone.utc)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=10,map_id=1134,instance_id=0 WHERE id=%s",
                (self.character,),
            )
            # This test isolates ranking receipts from unrelated content reward
            # expansions; catalog-level native reward references are asserted
            # separately against the shipped content artifact.
            db.execute(
                "DELETE FROM objectives_definitions WHERE key LIKE 'content-v1.%'"
            )
            db.execute(
                "INSERT INTO native_catalog_releases(revision,document_count,source_bytes,complete) VALUES(%s,2,%s,true)",
                (revision, sum(map(len, documents.values()))),
            )
            for path, raw in documents.items():
                db.execute(
                    "INSERT INTO native_catalog_documents(revision,path,raw,sha256,source_bytes,record_count) VALUES(%s,%s,%s,%s,%s,0)",
                    (revision, path, raw, hashlib.sha256(raw).hexdigest(), len(raw)),
                )
            db.execute(
                "INSERT INTO native_catalog_active(id,revision) VALUES(1,%s)",
                (revision,),
            )
            reward_policies.put_policy(
                db,
                "weekly-ranking-v1",
                {
                    "bands": [
                        {
                            "minimum": 1,
                            "maximum": 200,
                            "rewards": [{"kind": "kamas", "amount": 500}],
                        }
                    ]
                },
                1,
                operator="test",
            )

        groups = PersistentGroups(self.store)

        # A client-shaped, otherwise plausible payload is not a result receipt:
        # only a durable challenge run joined to a finished won fight may rank.
        forged_attempt = "f" * 32
        with self.store.connection() as db:
            repository.enqueue(
                db,
                self.account,
                self.character,
                "challenge:" + forged_attempt,
                {
                    "kind": "challenge_completed",
                    "attempt_id": forged_attempt,
                    "profile_key": "weekly-native-001-020",
                    "week_key": "2026-10-12",
                    "bracket": "001-020",
                    "level": 10,
                    "turns": 1,
                    "won": True,
                    "ranked": True,
                },
                now,
            )
            forged_result = repository.process_batch(db)
            self.assertEqual(
                (forged_result["processed"], forged_result["failed"]), (0, 1)
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM objectives_weekly_scores"
                ).fetchone()["n"],
                0,
            )
            db.execute(
                "UPDATE objectives_events SET attempts=5 WHERE event_key=%s",
                ("challenge:" + forged_attempt,),
            )

        # A test-marked win and a normal loss both settle but neither may create
        # an objective event or a ranking score.
        test_run = self._enter_finite_challenge(groups, challenges, now)
        self._settle_finite_challenge(
            challenges, groups, test_run, now, 3, test_mode=True
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) n FROM objectives_events").fetchone()["n"],
                1,
            )
            challenges.return_from_challenge(db, self.account, self.character)
        loss_run = self._enter_finite_challenge(groups, challenges, now)
        self._settle_finite_challenge(challenges, groups, loss_run, now, 5, winner=1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) n FROM objectives_events").fetchone()["n"],
                1,
            )
            challenges.return_from_challenge(db, self.account, self.character)

        challenge_scores = []
        for attempt_number, turns in enumerate((8, 4, 10), start=1):
            run = self._enter_finite_challenge(groups, challenges, now)
            won = self._settle_finite_challenge(challenges, groups, run, now, turns)
            self.assertEqual(won["status"], "won")
            with self.store.connection() as db:
                batch = repository.process_batch(db)
                event_state = db.execute(
                    "SELECT error,attempts,payload FROM objectives_events WHERE event_key=%s",
                    ("challenge:" + run["attempt_id"],),
                ).fetchone()
                self.assertEqual(batch["processed"], 1, (batch, event_state))
                score = db.execute(
                    "SELECT points,turns FROM objectives_weekly_scores WHERE week_key=%s AND account_id=%s",
                    ("2026-10-12", self.account),
                ).fetchone()
                challenge_scores.append(score["points"])
                # The idempotent challenge settlement never queues a second fact.
                again = challenges.settle_fight(
                    db,
                    SimpleNamespace(
                        id=won["fight_id"],
                        phase="finished",
                        winner=0,
                        native_timeline_round=turns,
                    ),
                    now=now,
                )
                self.assertEqual(again["status"], "won")
                challenges.return_from_challenge(db, self.account, self.character)
        self.assertEqual(challenge_scores, [1250, 2500, 2500])

        # Private challenge attempt records retain their best-time history;
        # the public ranking/finalizer now uses the shared account points
        # ledger, so give this fixture one durable weekly completion receipt.
        with self.store.connection() as db:
            self.assertTrue(
                account_points.award_points(
                    db,
                    self.account,
                    "test:weekly-objective-completion",
                    2500,
                    character_id=self.character,
                    level=10,
                    occurred_at=now,
                    category="weekly",
                )
            )

        with self.store.connection() as db:
            before_kamas = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (self.account,)
            ).fetchone()["kamas"]
        with self.store.connection() as db:
            ranking = rankings.list_rankings(db, "2026-10-12", bracket="all")
            self.assertEqual(len(ranking), 1)
            self.assertEqual((ranking[0]["rank"], ranking[0]["points"]), (1, 2500))
            self.assertEqual(
                rankings.finalize_weeks(
                    db, datetime(2026, 10, 19, 6, tzinfo=timezone.utc)
                ),
                1,
            )
            self.assertEqual(
                rankings.finalize_weeks(
                    db, datetime(2026, 10, 19, 6, tzinfo=timezone.utc)
                ),
                0,
            )
            award = db.execute(
                "SELECT payload,policy_snapshot,delivered_at FROM objectives_rewards WHERE definition_key='weekly-ranking-awards'"
            ).fetchone()
        self.assertEqual(award["payload"], {"kind": "kamas", "amount": 500})
        self.assertEqual(
            award["policy_snapshot"],
            [{"key": "weekly-ranking-v1", "revision": 2, "level": 10}],
        )
        self.assertIsNone(award["delivered_at"])

        from wakfu_server.custom_tasks import reward_delivery

        with patch.dict(os.environ, {"WAKFU_OBJECTIVES_MODE": "external"}, clear=False):
            delivered = reward_delivery.deliver(
                self.store, self.account, self.generation, self.character
            )
            replay = reward_delivery.deliver(
                self.store, self.account, self.generation, self.character
            )
        self.assertEqual(
            delivered["delivered"], [("weekly-ranking-awards", "2026-10-12:all", 0)]
        )
        self.assertEqual(replay["delivered"], [])
        self.assertEqual(delivered["character"]["kamas"], before_kamas + 500)
        self.assertEqual(replay["character"]["kamas"], before_kamas + 500)

        # An attempt left active through its weekly close may be won later, but
        # it cannot mint a score in the new week or reopen the finalized week.
        rollover_start = datetime(2026, 10, 19, 6, tzinfo=timezone.utc)
        rollover_finish = datetime(2026, 10, 26, 6, tzinfo=timezone.utc)
        rollover = self._enter_finite_challenge(groups, challenges, rollover_start)
        self._settle_finite_challenge(challenges, groups, rollover, rollover_finish, 2)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM objectives_events WHERE event_key=%s",
                    ("challenge:" + rollover["attempt_id"],),
                ).fetchone()
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) n FROM objectives_weekly_scores WHERE account_id=%s",
                    (self.account,),
                ).fetchone()["n"],
                1,
            )


if __name__ == "__main__":
    unittest.main()
