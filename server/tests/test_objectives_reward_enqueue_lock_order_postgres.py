"""Account-first locking prevents enqueue/reward-delivery FK deadlocks."""
from concurrent.futures import ThreadPoolExecutor
import copy
import threading
import time
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.custom_tasks import reward_delivery, service
from wakfu_server.objectives import player_actions, player_auth, player_views


TEST_TRAVEL_ACTIONS = [
    {
        "action_key": "travel.map.527",
        "label": "Travel to Astrub",
        "target": {"map_id": 527, "instance_id": 0, "x": 1, "y": 2, "z": 0},
        "objective_key": "content-v1.map.527",
        "cost_kamas": 0,
    }
]


class ObjectivesRewardEnqueueLockOrderPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "objective-lock-order-owner", "local-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Lock Order Owner")[
            "id"
        ]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character)
        self.identity = {
            "account_id": self.account,
            "character_id": self.character,
            "generation": self.generation,
        }
        definition = {
            "key": "lock-order-reward",
            "title": "Lock order reward",
            "description": "One completed task",
            "target": 1,
            "enabled": True,
            "predicate": {"kind": "original_monster_killed", "references": [1]},
            "rewards": [{"aeV": 5, "ckl": [2021, 1]}],
        }
        event = {
            "kind": "original_monster_killed",
            "fight_id": 81001,
            "actors": [{"actor_id": -1, "reference": 1}],
        }
        with self.store.connection() as db:
            result = service.settle(
                db,
                self.account,
                self.character,
                "fight:81001",
                event,
                [copy.deepcopy(definition)],
            )
        self.assertEqual(result["completed"], ["lock-order-reward"])

    def test_launch_lock_reference_rejects_invalid_owner_without_inserting_tokens(self):
        foreign_account = self.store.register(
            "objective-lock-order-foreign", "local-password"
        )["id"]
        foreign_character = self.store.create_character(
            foreign_account, "Foreign Lock Owner"
        )["id"]
        invalid_requests = [
            (True, self.character, self.generation),
            (self.account, foreign_character, self.generation),
            (self.account, self.character, "stale-generation"),
        ]
        with self.store.connection() as db:
            before = db.execute(
                "SELECT count(*) AS n FROM objectives_player_tokens"
            ).fetchone()["n"]
            for account_id, character_id, generation in invalid_requests:
                with self.subTest(account_id=account_id, character_id=character_id):
                    with self.assertRaises(player_auth.Unauthorized):
                        player_auth.issue_launch(
                            db, account_id, character_id, generation
                        )
            after = db.execute(
                "SELECT count(*) AS n FROM objectives_player_tokens"
            ).fetchone()["n"]
        self.assertEqual(after, before)

    def test_enqueue_waits_on_account_before_session_while_reward_delivery_owns_account(
        self,
    ):
        reward_at_session_lock = threading.Event()
        allow_reward_session_lock = threading.Event()
        reward_pid = []
        enqueue_pid = []
        original_lock_character = self.store.lock_character

        def paused_lock_character(
            db, account_id, generation, character_id, *, selected=True
        ):
            reward_pid.append(
                db.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
            )
            reward_at_session_lock.set()
            if not allow_reward_session_lock.wait(5):
                raise TimeoutError("test did not release reward delivery")
            return original_lock_character(
                db, account_id, generation, character_id, selected=selected
            )

        def deliver_reward():
            with patch.object(
                self.store, "lock_character", side_effect=paused_lock_character
            ):
                return reward_delivery.deliver(
                    self.store, self.account, self.generation, self.character
                )

        def enqueue_action():
            with self.store.connection() as db:
                enqueue_pid.append(
                    db.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
                )
                with patch(
                    "wakfu_server.objectives.player_travel.actions",
                    return_value=TEST_TRAVEL_ACTIONS,
                ):
                    return player_actions.enqueue(
                        db, self.identity, "travel.map.527", "deadlock-proof-request"
                    )

        with ThreadPoolExecutor(max_workers=2) as pool:
            reward_future = pool.submit(deliver_reward)
            self.assertTrue(reward_at_session_lock.wait(5))
            enqueue_future = pool.submit(enqueue_action)
            deadline = time.monotonic() + 5
            activity = None
            while time.monotonic() < deadline:
                if enqueue_pid:
                    with self.store.connection() as db:
                        activity = db.execute(
                            "SELECT wait_event_type,query,pg_blocking_pids(pid) AS blockers "
                            "FROM pg_stat_activity WHERE pid=%s",
                            (enqueue_pid[0],),
                        ).fetchone()
                    if activity and activity["wait_event_type"] == "Lock":
                        break
                time.sleep(0.02)

            self.assertIsNotNone(activity, "enqueue backend did not enter a lock wait")
            self.assertEqual(activity["wait_event_type"], "Lock", activity)
            self.assertIn("FOR KEY SHARE", activity["query"].upper(), activity)
            self.assertIn(reward_pid[0], activity["blockers"], activity)
            self.assertFalse(
                enqueue_future.done(), "enqueue passed the reward account lock"
            )

            allow_reward_session_lock.set()
            delivered = reward_future.result(timeout=8)
            queued = enqueue_future.result(timeout=8)

        self.assertEqual(delivered["delivered"], [("lock-order-reward", 0)])
        self.assertEqual(queued["action_key"], "travel.map.527")
        self.assertEqual(queued["status"], "pending")
        with self.store.connection() as db:
            reward = db.execute(
                "SELECT delivered_at FROM character_custom_task_reward_outbox "
                "WHERE character_id=%s AND task_key='lock-order-reward' AND reward_index=0",
                (self.character,),
            ).fetchone()
            action_count = db.execute(
                "SELECT count(*) AS n FROM objectives_player_actions "
                "WHERE account_id=%s AND request_id='deadlock-proof-request'",
                (self.account,),
            ).fetchone()["n"]
            inventory_count = db.execute(
                "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s",
                (self.character,),
            ).fetchone()["n"]
        self.assertIsNotNone(reward["delivered_at"])
        self.assertEqual(action_count, 1)
        self.assertEqual(inventory_count, 1)

    def test_snapshot_waits_on_account_before_session_while_reward_delivery_owns_account(
        self,
    ):
        reward_at_session_lock = threading.Event()
        allow_reward_session_lock = threading.Event()
        reward_pid = []
        snapshot_pid = []
        original_lock_character = self.store.lock_character

        def paused_lock_character(
            db, account_id, generation, character_id, *, selected=True
        ):
            reward_pid.append(
                db.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
            )
            reward_at_session_lock.set()
            if not allow_reward_session_lock.wait(5):
                raise TimeoutError("test did not release reward delivery")
            return original_lock_character(
                db, account_id, generation, character_id, selected=selected
            )

        def deliver_reward():
            with patch.object(
                self.store, "lock_character", side_effect=paused_lock_character
            ):
                return reward_delivery.deliver(
                    self.store, self.account, self.generation, self.character
                )

        def read_snapshot():
            with self.store.connection() as db:
                snapshot_pid.append(
                    db.execute("SELECT pg_backend_pid() AS pid").fetchone()["pid"]
                )
                with patch(
                    "wakfu_server.objectives.player_travel.actions", return_value=[]
                ), patch(
                    "wakfu_server.objectives.seasonal_entry.actions", return_value=[]
                ), patch(
                    "wakfu_server.objectives.pvp.actions", return_value=[]
                ):
                    return player_views.snapshot(db, self.identity)

        with ThreadPoolExecutor(max_workers=2) as pool:
            reward_future = pool.submit(deliver_reward)
            self.assertTrue(reward_at_session_lock.wait(5))
            snapshot_future = pool.submit(read_snapshot)
            deadline = time.monotonic() + 5
            activity = None
            while time.monotonic() < deadline:
                if snapshot_pid:
                    with self.store.connection() as db:
                        activity = db.execute(
                            "SELECT wait_event_type,query,pg_blocking_pids(pid) AS blockers "
                            "FROM pg_stat_activity WHERE pid=%s",
                            (snapshot_pid[0],),
                        ).fetchone()
                    if activity and activity["wait_event_type"] == "Lock":
                        break
                time.sleep(0.02)

            self.assertIsNotNone(activity, "snapshot backend did not enter a lock wait")
            self.assertEqual(activity["wait_event_type"], "Lock", activity)
            self.assertIn("FOR KEY SHARE", activity["query"].upper(), activity)
            self.assertIn(reward_pid[0], activity["blockers"], activity)
            self.assertFalse(
                snapshot_future.done(), "snapshot passed the reward account lock"
            )

            allow_reward_session_lock.set()
            delivered = reward_future.result(timeout=8)
            snapshot = snapshot_future.result(timeout=8)

        self.assertEqual(delivered["delivered"], [("lock-order-reward", 0)])
        self.assertEqual(snapshot["actor"]["id"], self.character)
