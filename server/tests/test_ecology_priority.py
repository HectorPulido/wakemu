"""Player requests take admission precedence over bounded durable background work."""
import threading
from types import SimpleNamespace
import unittest

from wakfu_server.ecology.protocol import proposal
from wakfu_server.ecology.world_bridge import EcologyBusy, EcologyWorldBridge
from wakfu_server.request_diagnostics import RequestTrace


class EcologyPriorityTests(unittest.TestCase):
    def bridge(self, **options):
        options.setdefault("background_limit", 1)
        return EcologyWorldBridge(
            store=object(),
            world=SimpleNamespace(),
            groups=SimpleNamespace(),
            harvests=SimpleNamespace(),
            plantings=SimpleNamespace(),
            token="test",
            **options
        )

    def row(self, bridge, identity, *, interactive=False):
        return proposal(
            "plants" if interactive else "mobs",
            {
                "world_epoch": bridge.epoch,
                "kind": "planting_begin" if interactive else "wander",
                "identity": identity,
            },
            bridge.epoch,
        )

    def apply(self, bridge, rows):
        return bridge.apply(dict(schema_version=1, proposals=rows))["results"]

    def test_full_background_batch_drains_and_player_request_still_runs_first(self):
        bridge = self.bridge(background_limit=16, monotonic=lambda: 0)
        calls = []
        for domain in ("plants", "mobs"):
            bridge.handlers[domain] = lambda payload: calls.append(
                payload["identity"]
            ) or {"status": "applied"}
        rows = [self.row(bridge, identity) for identity in range(15)]
        rows.append(self.row(bridge, "player", interactive=True))
        results = self.apply(bridge, rows)
        self.assertEqual(calls[0], "player")
        self.assertEqual(len(calls), 16)
        self.assertTrue(all(result["status"] == "applied" for result in results))
        with bridge.interactive():
            blocked = self.apply(bridge, [self.row(bridge, "ambient")])[0]
            self.assertEqual(blocked["status"], "deferred")
        self.assertEqual(len(calls), 16)

    def test_interactive_work_runs_first_but_results_preserve_delivery_order(self):
        bridge = self.bridge()
        calls = []
        for domain in ("plants", "mobs"):
            bridge.handlers[domain] = lambda payload: calls.append(
                payload["identity"]
            ) or {"status": "applied"}
        rows = [
            self.row(bridge, "background1"),
            self.row(bridge, "player", interactive=True),
            self.row(bridge, "background2"),
        ]
        results = self.apply(bridge, rows)
        self.assertEqual(calls, ["player", "background1"])
        self.assertEqual(
            [result["id"] for result in results], [row["id"] for row in rows]
        )
        self.assertEqual(
            [result["status"] for result in results], ["applied", "applied", "deferred"]
        )

    def test_default_background_budget_does_not_drop_deferred_work(self):
        bridge = self.bridge()
        calls = []
        bridge.handlers["mobs"] = lambda payload: calls.append(payload["identity"]) or {
            "status": "applied"
        }
        rows = [self.row(bridge, value) for value in range(3)]
        self.assertEqual(
            [r["status"] for r in self.apply(bridge, rows)],
            ["applied", "deferred", "deferred"],
        )
        self.assertEqual(
            [r["status"] for r in self.apply(bridge, rows[1:])], ["applied", "deferred"]
        )
        self.assertEqual(self.apply(bridge, rows[2:])[0]["status"], "applied")
        self.assertEqual(calls, [0, 1, 2])

    def test_batch_diagnostics_include_kind_status_admission_reason_and_timing(self):
        records = []
        bridge = self.bridge(record=lambda **fields: records.append(fields))
        bridge.handlers["mobs"] = lambda payload: {"status": "applied"}
        rows = [self.row(bridge, 1), self.row(bridge, 2)]
        self.apply(bridge, rows)
        started = next(
            row for row in records if row["event"] == "ecology_handler_started"
        )
        self.assertEqual(started["proposal_id"], rows[0]["id"])
        batch = next(row for row in records if row["event"] == "ecology_apply_batch")
        self.assertEqual(
            [row["status"] for row in batch["results"]], ["applied", "deferred"]
        )
        self.assertEqual(
            [row["kind"] for row in batch["results"]], ["wander", "wander"]
        )
        self.assertEqual([row["domain"] for row in batch["results"]], ["mobs", "mobs"])
        self.assertIsNotNone(batch["results"][1]["admission_reason"])
        self.assertTrue(all(row["elapsed_ms"] >= 0 for row in batch["results"]))

    def test_time_budget_defers_after_slow_background_unit(self):
        now = [0.0]
        bridge = self.bridge(background_limit=16, monotonic=lambda: now[0])

        def work(payload):
            now[0] += 0.030
            return {"status": "applied"}

        bridge.handlers["mobs"] = work
        self.assertEqual(
            [
                r["status"]
                for r in self.apply(bridge, [self.row(bridge, 1), self.row(bridge, 2)])
            ],
            ["applied", "deferred"],
        )

    def test_interactive_scope_defers_background_without_holding_commit_gate(self):
        bridge = self.bridge()
        bridge.handlers["plants"] = lambda payload: {"status": "applied"}
        with bridge.interactive():
            self.assertTrue(bridge.gate.acquire(blocking=False))
            bridge.gate.release()
            results = self.apply(
                bridge, [self.row(bridge, 1), self.row(bridge, 2, interactive=True)]
            )
            self.assertEqual([r["status"] for r in results], ["deferred", "applied"])
        self.assertFalse(bridge.priority.interactive_active)

    def test_busy_commit_gate_never_blocks_another_caller(self):
        bridge = self.bridge()
        bridge.gate.acquire()
        result = []

        def caller():
            try:
                self.apply(bridge, [self.row(bridge, 1)])
            except EcologyBusy:
                result.append("busy")

        thread = threading.Thread(target=caller)
        thread.start()
        thread.join(1)
        bridge.gate.release()
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, ["busy"])

    def trace(self, bridge, **overrides):
        options = dict(
            sink=lambda **fields: None,
            opcode=1,
            service="test",
            connection_id="c",
            snapshot=lambda: {},
            activity_scope=bridge.interactive(),
        )
        options.update(overrides)
        return RequestTrace(**options)

    def test_request_flush_threshold_keeps_priority_active_until_finish(self):
        bridge = self.bridge()
        flushed = []

        def flush(rows):
            self.assertTrue(bridge.priority.interactive_active)
            flushed.append(rows)

        trace = self.trace(bridge, flush=flush)
        for index in range(1024):
            trace.append({"index": index})
        self.assertEqual(len(flushed), 1)
        self.assertTrue(bridge.priority.interactive_active)
        trace.finish()
        self.assertFalse(bridge.priority.interactive_active)
        trace.finish()

    def test_request_constructor_failure_releases_interactive_priority(self):
        bridge = self.bridge()

        def sink(**fields):
            raise RuntimeError("start failed")

        with self.assertRaisesRegex(RuntimeError, "start failed"):
            self.trace(bridge, sink=sink)
        self.assertFalse(bridge.priority.interactive_active)

    def test_request_finish_failure_releases_interactive_priority(self):
        bridge = self.bridge()

        def sink(**fields):
            if fields["event"] == "request_finished":
                raise RuntimeError("finish failed")

        trace = self.trace(bridge, sink=sink)
        with self.assertRaisesRegex(RuntimeError, "finish failed"):
            trace.finish()
        self.assertFalse(bridge.priority.interactive_active)
