"""Offline contract and startup-mode coverage for the ecology bridge."""

import ast
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server.ecology.protocol import proposal
from wakfu_server.ecology.client import EcologyClient
from wakfu_server.ecology.world_bridge import EcologyBusy, EcologyWorldBridge


SERVER = Path(__file__).resolve().parents[1] / "local_game_server.py"


class EcologyWorldBridgeTests(unittest.TestCase):
    def setUp(self):
        self.players = [
            {
                "id": 17,
                "account_id": 9,
                "map_id": 100,
                "instance_id": 4,
                "x": 11,
                "y": 12,
                "z": 0,
                "inventory": ["must not cross the boundary"],
                "session_token": "private",
            }
        ]
        self.harvest_lock = threading.RLock()
        self.plantings = SimpleNamespace(
            growth_seconds=30,
            open_test_policy=True,
            ecology_world_epoch=None,
        )
        self.records = []
        self.bridge = EcologyWorldBridge(
            store=object(),
            world=SimpleNamespace(ecology_snapshot=lambda: self.players),
            groups=SimpleNamespace(),
            harvests=SimpleNamespace(lock=self.harvest_lock, targets={-40: 17}),
            plantings=self.plantings,
            token="secret-token",
            mode="external",
            record=lambda **fields: self.records.append(fields)
            if fields["event"] not in ("ecology_handler_started", "ecology_apply_batch")
            else None,
            clock=lambda: 123.456,
            background_limit=16,
        )

    def test_snapshot_is_scalar_only_detached_epoch_scoped_and_does_no_http(self):
        before = dict(self.players[0])
        with patch(
            "urllib.request.urlopen",
            side_effect=AssertionError("unexpected HTTP request"),
        ) as urlopen:
            snapshot = self.bridge.snapshot()

        self.assertEqual(
            set(snapshot["players"][0]),
            {"id", "account_id", "map_id", "instance_id", "x", "y", "z"},
        )
        self.assertEqual(snapshot["players"][0]["map_id"], 100)
        self.assertEqual(snapshot["scopes"], [[100, 4]])
        self.assertEqual(snapshot["locations"], [[100, 4]])
        self.assertEqual(snapshot["excluded_ids"], [-40])
        self.assertEqual(snapshot["now_ms"], 123456)
        self.assertEqual(snapshot["epoch"], self.bridge.epoch)
        self.assertEqual(snapshot["world_epoch"], self.bridge.epoch)
        self.assertEqual(self.plantings.ecology_world_epoch, self.bridge.epoch)
        self.assertEqual(self.players[0], before)
        snapshot["players"][0]["x"] = -100
        snapshot["scopes"][0][0] = -100
        self.assertEqual(self.players[0]["x"], 11)
        self.assertEqual(self.players[0]["map_id"], 100)
        urlopen.assert_not_called()

    def test_external_token_is_exact_bearer_and_compared_in_constant_time(self):
        self.assertTrue(self.bridge.authorized("Bearer secret-token"))
        for header in (
            "secret-token",
            "bearer secret-token",
            "Bearer secret-token ",
            "Bearer wrong-token",
            "Bearer secret-token extra",
            None,
        ):
            with self.subTest(header=header):
                self.assertFalse(self.bridge.authorized(header))

    def test_external_apply_dispatches_each_domain_and_isolates_handler_errors(self):
        calls = []

        def broken(payload):
            calls.append(("plants", payload["value"]))
            raise RuntimeError("private exception detail")

        def accepted(payload):
            calls.append(("mobs", payload["value"]))
            return {"status": "applied", "private": "not returned"}

        self.bridge.handlers.update(plants=broken, mobs=accepted)
        envelope = {
            "schema_version": 1,
            "proposals": [
                proposal(
                    "plants",
                    {"world_epoch": self.bridge.epoch, "value": 1},
                    self.bridge.epoch,
                ),
                proposal(
                    "mobs",
                    {"world_epoch": self.bridge.epoch, "value": 2},
                    self.bridge.epoch,
                ),
            ],
        }

        result = self.bridge.apply(envelope)

        self.assertEqual(calls, [("plants", 1), ("mobs", 2)])
        self.assertEqual(
            result["results"],
            [
                {"id": envelope["proposals"][0]["id"], "status": "retry"},
                {"id": envelope["proposals"][1]["id"], "status": "applied"},
            ],
        )
        self.assertEqual(
            self.records,
            [
                {
                    "event": "ecology_apply_failed",
                    "domain": "plants",
                    "error_type": "RuntimeError",
                }
            ],
        )

    def test_lost_live_fences_are_terminal_stale_instead_of_retry(self):
        statuses = (
            "absent",
            "harvesting",
            "occupied",
            "stale_epoch",
            "stale_policy",
            "stale_group",
        )
        self.bridge.handlers["mobs"] = lambda payload: {"status": payload["reason"]}
        rows = [
            proposal(
                "mobs",
                {"world_epoch": self.bridge.epoch, "reason": status},
                self.bridge.epoch,
            )
            for status in statuses
        ]
        result = self.bridge.apply({"schema_version": 1, "proposals": rows})
        self.assertEqual(
            [row["status"] for row in result["results"]], ["stale"] * len(rows)
        )
        self.assertEqual(
            [row["rejected_status"] for row in self.records], list(statuses)
        )
        self.assertTrue(
            all(row["event"] == "ecology_proposal_stale" for row in self.records)
        )

    def test_unknown_status_remains_retry_and_records_bounded_status(self):
        self.bridge.handlers["mobs"] = lambda payload: {"status": "unexpected" * 100}
        row = proposal("mobs", {"world_epoch": self.bridge.epoch}, self.bridge.epoch)
        result = self.bridge.apply({"schema_version": 1, "proposals": [row]})
        self.assertEqual(result["results"], [{"id": row["id"], "status": "retry"}])
        self.assertEqual(len(self.records[0]["rejected_status"]), 64)
        self.assertEqual(self.records[-1]["error_type"], "ValueError")

    def test_apply_rejects_busy_gate_and_stale_proposal_epochs_without_dispatch(self):
        calls = []
        self.bridge.handlers["plants"] = lambda payload: calls.append(payload) or {
            "status": "applied"
        }
        envelope = {
            "schema_version": 1,
            "proposals": [
                proposal(
                    "plants", {"world_epoch": self.bridge.epoch}, "old-world-epoch"
                ),
                proposal(
                    "plants", {"world_epoch": "old-payload-epoch"}, self.bridge.epoch
                ),
            ],
        }

        self.assertTrue(self.bridge.gate.acquire(blocking=False))
        try:
            with self.assertRaises(EcologyBusy):
                self.bridge.apply(envelope)
        finally:
            self.bridge.gate.release()
        result = self.bridge.apply(envelope)
        self.assertEqual(
            [row["status"] for row in result["results"]], ["stale", "stale"]
        )
        self.assertEqual(calls, [])

    def test_external_mode_requires_nonblank_credential(self):
        for token in (None, "", "  "):
            with self.subTest(token=token), self.assertRaises(ValueError):
                EcologyWorldBridge(
                    store=object(),
                    world=object(),
                    groups=object(),
                    harvests=object(),
                    plantings=SimpleNamespace(),
                    token=token,
                    mode="external",
                )

    def query_result(self):
        return {
            "authoritative": True,
            "kind": "weather",
            "map_id": 100,
            "instance_id": 4,
            "revision": 3,
            "data": {"regions": []},
            "observed_at": datetime.fromtimestamp(123.456, timezone.utc).isoformat(),
        }

    def test_on_demand_query_returns_fresh_authority_without_caching_errors(self):
        client = Mock()
        result = self.query_result()
        client.query.side_effect = [result, TimeoutError("service unavailable")]
        self.bridge.ecology_client = client
        self.assertEqual(self.bridge.query("weather", 100, 4, 99), result)
        client.query.assert_called_with("weather", 100, 4, region_id=99)
        with self.assertRaises(TimeoutError):
            self.bridge.query("weather", 100, 4, 99)
        self.assertEqual(client.query.call_count, 2)

    def test_query_refuses_current_thread_world_group_and_harvest_locks(self):
        client = Mock()
        self.bridge.ecology_client = client
        self.bridge.world.lock = threading.RLock()
        self.bridge.groups.lock = threading.RLock()
        for lock in (
            self.bridge.world.lock,
            self.bridge.groups.lock,
            self.harvest_lock,
        ):
            with self.subTest(lock=lock), lock:
                with self.assertRaisesRegex(RuntimeError, "gameplay locks"):
                    self.bridge.query("weather", 100, 4)
        client.query.assert_not_called()

    def test_another_threads_world_lock_does_not_reject_lock_free_caller(self):
        self.bridge.world.lock = threading.RLock()
        self.bridge.ecology_client = Mock()
        self.bridge.ecology_client.query.return_value = self.query_result()
        held, release = threading.Event(), threading.Event()

        def hold():
            with self.bridge.world.lock:
                held.set()
                release.wait(2)

        thread = threading.Thread(target=hold)
        thread.start()
        self.assertTrue(held.wait(1))
        try:
            self.assertTrue(self.bridge.query("weather", 100, 4)["authoritative"])
        finally:
            release.set()
            thread.join(2)

    def test_query_rejects_stale_or_invalid_authority_and_scope(self):
        self.bridge.ecology_client = Mock()
        valid = self.query_result()
        invalid = [
            dict(valid, authoritative=False),
            dict(valid, map_id=101),
            dict(valid, kind="population"),
            dict(valid, revision=True),
            dict(valid, observed_at="1970-01-01T00:01:00+00:00"),
            dict(valid, observed_at="1970-01-01T00:02:10+00:00"),
            dict(valid, observed_at="1970-01-01T00:02:03"),
            dict(valid, observed_at="invalid"),
        ]
        for result in invalid:
            self.bridge.ecology_client.query.return_value = result
            with self.subTest(result=result), self.assertRaises(ValueError):
                self.bridge.query("weather", 100, 4)

    def test_query_client_uses_finite_deadline_and_propagates_failure(self):
        def unavailable(_request, *, timeout):
            self.assertEqual(timeout, 2.0)
            raise TimeoutError("read deadline")

        self.bridge.ecology_client = EcologyClient(
            "http://ecology:8093", "secret-token", timeout=2.0, opener=unavailable
        )
        with self.assertRaises(TimeoutError):
            self.bridge.query("weather", 100, 4)

    def test_query_requires_external_mode_and_explicit_client(self):
        with self.assertRaises(RuntimeError):
            self.bridge.query("weather", 100, 4)
        self.bridge.ecology_client = Mock()
        self.bridge.mode = "disabled"
        with self.assertRaises(RuntimeError):
            self.bridge.query("weather", 100, 4)
        self.bridge.ecology_client.query.assert_not_called()


class EcologyModeStartupTests(unittest.TestCase):
    CALLBACKS = {
        "grow_planted_resources",
        "reproduce_monsters",
        "mature_monsters",
        "wander_monsters",
        "expire_monster_corpses",
    }

    @staticmethod
    def condition(node, *, mode, combat_test=True):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name) and node.id == "ECOLOGY_MODE":
            return mode
        if isinstance(node, ast.Name) and node.id == "COMBAT_TEST":
            return combat_test
        if isinstance(node, ast.BoolOp):
            if isinstance(node.op, ast.And):
                for value in node.values:
                    if not EcologyModeStartupTests.condition(
                        value, mode=mode, combat_test=combat_test
                    ):
                        return False
                return True
            if isinstance(node.op, ast.Or):
                for value in node.values:
                    if EcologyModeStartupTests.condition(
                        value, mode=mode, combat_test=combat_test
                    ):
                        return True
                return False
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not EcologyModeStartupTests.condition(
                node.operand, mode=mode, combat_test=combat_test
            )
        if (
            isinstance(node, ast.Compare)
            and len(node.ops) == len(node.comparators) == 1
        ):
            left = EcologyModeStartupTests.condition(
                node.left, mode=mode, combat_test=combat_test
            )
            right = EcologyModeStartupTests.condition(
                node.comparators[0], mode=mode, combat_test=combat_test
            )
            if isinstance(node.ops[0], ast.Eq):
                return left == right
            if isinstance(node.ops[0], ast.NotEq):
                return left != right
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "hasattr"
        ):
            return True
        raise AssertionError(f"Unsupported startup condition: {ast.dump(node)}")

    def test_external_and_disabled_modes_never_start_legacy_ecology_workers_or_weather_tick(
        self,
    ):
        tree = ast.parse(SERVER.read_text())
        main = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        for mode in ("external", "disabled"):
            reachable = []

            def visit_many(nodes, guards):
                for child in nodes:
                    visit(child, guards)

            def visit(node, guards=()):
                if isinstance(node, ast.If):
                    if any(
                        isinstance(child, ast.Name) and child.id == "ECOLOGY_MODE"
                        for child in ast.walk(node.test)
                    ):
                        selected = self.condition(node.test, mode=mode)
                        visit_many(
                            node.body if selected else node.orelse,
                            guards + (node.test,),
                        )
                    else:
                        visit_many(node.body, guards)
                        visit_many(node.orelse, guards)
                    return
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr == "Thread":
                        target = next(
                            (kw.value for kw in node.keywords if kw.arg == "target"),
                            None,
                        )
                        if isinstance(target, ast.Name) and target.id in self.CALLBACKS:
                            reachable.append(target.id)
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if (
                            isinstance(target, ast.Subscript)
                            and isinstance(target.value, ast.Name)
                            and target.value.id == "callbacks"
                            and isinstance(target.slice, ast.Constant)
                            and target.slice.value == "territory_weather_tick"
                        ):
                            reachable.append("territory_weather_tick")
                visit_many(ast.iter_child_nodes(node), guards)

            visit(main)
            with self.subTest(mode=mode):
                self.assertEqual(reachable, [])

    def test_external_and_disabled_modes_do_not_seed_inline_population(self):
        tree = ast.parse(SERVER.read_text())
        main = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        for mode in ("external", "disabled"):
            calls = []

            def visit(node):
                if isinstance(node, ast.If):
                    if any(
                        isinstance(child, ast.Name) and child.id == "ECOLOGY_MODE"
                        for child in ast.walk(node.test)
                    ):
                        selected = self.condition(node.test, mode=mode)
                        selected_body = node.body if selected else node.orelse
                    else:
                        selected_body = node.body + node.orelse
                    for child in selected_body:
                        visit(child)
                    return
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "seed_configured"
                ):
                    calls.append(node.func.id)
                for child in ast.iter_child_nodes(node):
                    visit(child)

            visit(main)
            with self.subTest(mode=mode):
                self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
