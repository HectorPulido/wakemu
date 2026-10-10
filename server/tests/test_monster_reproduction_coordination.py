"""Each birth/publication refreshes authority after releasing the previous fence."""
from contextlib import contextmanager
import threading
import unittest
from unittest.mock import patch

from wakfu_server import monster_reproduction as reproduction


class ReproductionCoordinationTests(unittest.TestCase):
    def setUp(self):
        configuration = {
            "interval_ms": 60000,
            "birth_probability": 0.05,
            "birth_stage_decay": 0.5,
            "new_group_probability": 0.5,
            "max_members": 8,
            "max_zone_members": 128,
            "max_zone_groups": 32,
        }
        patcher = patch.object(reproduction, "policy", return_value=configuration)
        self.policy = patcher.start()
        self.addCleanup(patcher.stop)

    def run_tick(self, coordinator, **overrides):
        arguments = dict(
            generation="worker",
            now_ms=1000,
            indexed_by_map={1: (None, {})},
            players=[],
            excluded_ids=set(),
            emit=lambda *_: None,
            coordination=coordinator,
        )
        arguments.update(overrides)
        return reproduction.tick(object(), {(1, 0)}, set(), **arguments)

    def test_policy_is_read_outside_fences_once_per_tick_and_refreshes_next_tick(self):
        held = [False]
        observed, attempted = [], []
        original = self.policy.return_value

        def policy(_store):
            self.assertFalse(held[0])
            return dict(original, interval_ms=60000 + self.policy.call_count)

        self.policy.side_effect = policy

        @contextmanager
        def coordinator(*_):
            held[0] = True
            try:
                yield [{"map_id": 1, "instance_id": 0}], set()
            finally:
                held[0] = False

        with patch.object(
            reproduction,
            "observe",
            side_effect=lambda *_, **facts: observed.append(facts),
        ), patch.object(reproduction, "pending", return_value=[{}, {}]), patch.object(
            reproduction,
            "attempt",
            side_effect=lambda *_, **facts: attempted.append(facts),
        ), patch.object(
            reproduction, "unpublished", return_value=[]
        ):
            self.run_tick(coordinator)
            self.run_tick(coordinator)
        self.assertEqual(self.policy.call_count, 2)
        self.assertEqual(
            [row["configuration"]["interval_ms"] for row in observed], [60001, 60002]
        )
        self.assertEqual(
            [row["configuration"]["interval_ms"] for row in attempted],
            [60001, 60001, 60002, 60002],
        )

    def test_departed_players_pause_observation_and_prevent_offline_attempt(self):
        @contextmanager
        def coordinator(*_):
            yield [], set()

        with patch.object(reproduction, "observe") as observe, patch.object(
            reproduction, "pending", return_value=[{}]
        ), patch.object(reproduction, "attempt") as attempt, patch.object(
            reproduction, "unpublished", return_value=[]
        ):
            self.run_tick(coordinator)
        self.assertFalse(observe.call_args.kwargs["present"])
        self.assertFalse(attempt.call_args.kwargs["present"])

    def test_harvest_and_player_changes_between_operations_refresh_attempt(self):
        lock = threading.RLock()
        observed, changed = threading.Event(), threading.Event()
        authority = {"players": [], "excluded": set()}
        stages = []

        def occupy():
            if not observed.wait(2):
                return
            with lock:
                authority["players"].append({"id": 7, "map_id": 1, "instance_id": 0})
                authority["excluded"].add(-10)
            changed.set()

        worker = threading.Thread(target=occupy)
        worker.start()

        @contextmanager
        def coordinator(stage, *_):
            stages.append(stage)
            with lock:
                yield list(authority["players"]), set(authority["excluded"])
            if stage == "observe":
                observed.set()
                self.assertTrue(changed.wait(2))

        def attempt(_store, _ticket, **facts):
            self.assertEqual(
                facts["players"], [{"id": 7, "map_id": 1, "instance_id": 0}]
            )
            self.assertEqual(facts["excluded_ids"], {-10})

        try:
            with patch.object(reproduction, "observe"), patch.object(
                reproduction, "pending", return_value=[{"monster_id": -10}]
            ), patch.object(reproduction, "attempt", side_effect=attempt), patch.object(
                reproduction, "unpublished", return_value=[]
            ):
                self.run_tick(coordinator)
        finally:
            observed.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(stages, ["observe", "attempt"])

    def test_claim_after_outbox_enumeration_cannot_publish_stale_available_group(self):
        row = {"group_id": 3, "status": "available", "members": [{"id": -10}]}
        enumerated, claimed = threading.Event(), threading.Event()
        lock = threading.RLock()

        def claim():
            if not enumerated.wait(2):
                return
            with lock:
                row["status"] = "fighting"
            claimed.set()

        worker = threading.Thread(target=claim)
        worker.start()

        @contextmanager
        def coordinator(stage, *_):
            if stage == "publish":
                enumerated.set()
                self.assertTrue(claimed.wait(2))
            with lock:
                yield [], set()

        emitted = []
        try:
            with patch.object(reproduction, "observe"), patch.object(
                reproduction, "pending", return_value=[]
            ), patch.object(
                reproduction, "unpublished", side_effect=lambda *_, **__: [dict(row)]
            ) as query, patch.object(
                reproduction, "acknowledge"
            ) as acknowledge:
                self.run_tick(coordinator, emit=lambda *args: emitted.append(args))
                self.assertEqual(query.call_count, 2)
                self.assertEqual(query.call_args.kwargs, {"group_id": 3})
                acknowledge.assert_not_called()
        finally:
            enumerated.set()
            worker.join(2)
        self.assertEqual(emitted, [])
        self.assertFalse(worker.is_alive())

    def test_removal_spawn_and_acknowledgment_share_publication_fence(self):
        held = [False]
        order = []
        row = {"group_id": 3, "status": "available", "members": [{"id": -10}]}

        @contextmanager
        def coordinator(stage, *_):
            held[0] = True
            try:
                yield [], set()
            finally:
                held[0] = False

        def emit(*args):
            self.assertTrue(held[0])
            order.append(args[2])

        def acknowledge(*_):
            self.assertTrue(held[0])
            order.append("ack")

        with patch.object(reproduction, "observe"), patch.object(
            reproduction, "pending", return_value=[]
        ), patch.object(reproduction, "unpublished", return_value=[row]), patch.object(
            reproduction, "acknowledge", side_effect=acknowledge
        ), patch(
            "wakfu_server.combat_monster_world.remove_message",
            return_value=(12002, b"remove"),
        ), patch(
            "wakfu_server.combat_monster_world.spawn_group", return_value=b"spawn"
        ):
            self.run_tick(coordinator, emit=emit)
        self.assertEqual(order, [12002, 12608, "ack"])
