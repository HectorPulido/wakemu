"""Each maturation/publication refreshes authority after releasing the previous fence."""
from contextlib import contextmanager
import threading
import unittest
from unittest.mock import patch

from wakfu_server import monster_maturation as maturation


class MaturationCoordinationTests(unittest.TestCase):
    def test_departure_before_attempt_pauses_growth(self):
        @contextmanager
        def coordinator(stage, *_):
            yield (
                [{"map_id": 1, "instance_id": 0}] if stage == "observe" else []
            ), set()

        with patch.object(maturation, "observe") as observe, patch.object(
            maturation, "pending", return_value=[{"monster_id": -10}]
        ), patch.object(maturation, "attempt") as attempt, patch.object(
            maturation, "unpublished", return_value=[]
        ):
            self.run_tick(coordinator)
        self.assertTrue(observe.call_args.kwargs["present"])
        self.assertFalse(attempt.call_args.kwargs["present"])

    def run_tick(self, coordinator, **overrides):
        arguments = dict(
            generation="worker",
            now_ms=1000,
            excluded_ids=set(),
            emit=lambda *_: None,
            coordination=coordinator,
        )
        arguments.update(overrides)
        with patch.object(maturation, "policy", return_value={"interval_ms": 60000}):
            return maturation.tick(object(), {(1, 0)}, set(), **arguments)

    def test_harvest_and_player_changes_between_operations_refresh_attempt(self):
        lock = threading.RLock()
        observed, changed = threading.Event(), threading.Event()
        authority = {"players": [{"map_id": 1, "instance_id": 0}], "excluded": set()}
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
            self.assertEqual(facts["excluded_ids"], {-10})

        try:
            with patch.object(maturation, "observe"), patch.object(
                maturation, "pending", return_value=[{"monster_id": -10}]
            ), patch.object(maturation, "attempt", side_effect=attempt), patch.object(
                maturation, "unpublished", return_value=[]
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
                yield [{"map_id": 1, "instance_id": 0}], set()

        emitted = []
        try:
            with patch.object(maturation, "observe"), patch.object(
                maturation, "pending", return_value=[]
            ), patch.object(
                maturation, "unpublished", side_effect=lambda *_, **__: [dict(row)]
            ) as query, patch.object(
                maturation, "acknowledge"
            ) as acknowledge:
                self.run_tick(coordinator, emit=lambda *args: emitted.append(args))
                self.assertEqual(query.call_count, 2)
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
                yield [{"map_id": 1, "instance_id": 0}], set()
            finally:
                held[0] = False

        def emit(*args):
            self.assertTrue(held[0])
            order.append(args[2])

        def acknowledge(*_):
            self.assertTrue(held[0])
            order.append("ack")

        with patch.object(maturation, "observe"), patch.object(
            maturation, "pending", return_value=[]
        ), patch.object(maturation, "unpublished", return_value=[row]), patch.object(
            maturation, "acknowledge", side_effect=acknowledge
        ), patch(
            "wakfu_server.combat_monster_world.remove_message",
            return_value=(12002, b"remove"),
        ), patch(
            "wakfu_server.combat_monster_world.spawn_group", return_value=b"spawn"
        ):
            self.run_tick(coordinator, emit=emit)
        self.assertEqual(order, [12002, 12608, "ack"])
