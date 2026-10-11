"""Ecology transport bounds, authentication, and retry-safe planning behavior."""
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from wakfu_server.ecology.client import EcologyClient
from wakfu_server.ecology.protocol import MAX_BODY_BYTES, MAX_PROPOSALS
from wakfu_server.ecology.protocol import (
    MAX_RESPONSE_BYTES,
    bounded_json,
    json_bytes,
    proposal,
    validate_proposals,
    validate_snapshot,
    validate_query,
)

spec = importlib.util.spec_from_file_location(
    "ecology_service",
    Path(__file__).resolve().parents[1] / "ecology-service/service.py",
)
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


def snapshot():
    return {
        "schema_version": 1,
        "world_epoch": "boot-1",
        "epoch": "boot-1",
        "scopes": [],
        "mode": "external",
        "now_ms": 1000,
        "locations": [],
    }


class ProtocolTests(unittest.TestCase):
    def test_identity_is_stable_across_epoch_and_dictionary_order(self):
        first = proposal("plants", {"revision": 1, "uid": 7}, "old")
        second = proposal("plants", {"uid": 7, "revision": 1}, "new")
        self.assertEqual(first["id"], second["id"])
        self.assertNotEqual(first["world_epoch"], second["world_epoch"])
        self.assertNotEqual(
            first["id"], proposal("plants", {"uid": 7, "revision": 2}, "new")["id"]
        )

    def test_rejects_duplicate_unknown_domain_and_over_budget_proposals(self):
        row = proposal("plants", {}, "boot")
        for rows in ([row, row], [dict(row, domain="chat")], [row] * 17):
            with self.subTest(rows=len(rows)), self.assertRaises(ValueError):
                validate_proposals({"schema_version": 1, "proposals": rows})

    def test_json_bounds_and_nonfinite_values(self):
        with self.assertRaises(ValueError):
            json_bytes({"data": "x" * MAX_BODY_BYTES})
        with self.assertRaises(ValueError):
            bounded_json(b"NaN")
        with self.assertRaises(ValueError):
            json_bytes({"bad": float("nan")})
        with self.assertRaises(ValueError):
            validate_snapshot(dict(snapshot(), scopes=[{}] * 65))

    def test_client_caps_reads_and_passes_credentials_and_deadline(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(snapshot()).encode()
        opener = Mock(return_value=response)
        client = EcologyClient(
            "http://world:18081", "private-token", timeout=1, opener=opener
        )
        self.assertEqual(client.snapshot()["world_epoch"], "boot-1")
        request = opener.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer private-token")
        self.assertEqual(opener.call_args.kwargs["timeout"], 1)
        response.read.assert_called_once_with(MAX_RESPONSE_BYTES + 1)

    def test_client_rejects_partial_or_foreign_ack(self):
        client = EcologyClient("http://world", "token")
        row = proposal("mobs", {}, "boot")
        for results in (
            [],
            [{"id": "other", "status": "applied"}],
            [{"id": row["id"], "status": "unknown"}],
        ):
            client.request = Mock(return_value={"results": results})
            with self.subTest(results=results), self.assertRaises(ValueError):
                client.apply([row])

    def test_query_rejects_extra_fields_invalid_scope_and_client_uses_post(self):
        valid = {"kind": "weather", "map_id": 527, "instance_id": 0}
        for value in (
            dict(valid, command="give"),
            dict(valid, map_id=True),
            dict(valid, instance_id=-1),
            dict(valid, region_id=0),
            dict(valid, kind="combat"),
        ):
            with self.assertRaises(ValueError):
                validate_query(value)
        client = EcologyClient("http://ecology:8093", "token")
        client.request = Mock(return_value={"authoritative": True})
        self.assertTrue(client.query("weather", 527, 0)["authoritative"])
        client.request.assert_called_once_with("/query", valid)


class WorkerTests(unittest.TestCase):
    def create(self, domains):
        repository = Mock(spec=service.Repository)
        repository.store = Mock()
        repository.enabled.return_value = True
        repository.pending.return_value = []
        repository.pending_count.return_value = 0
        repository.retry_stats.return_value = {"attempts": 0, "exhausted": 0}
        repository.max_attempts = 5
        repository.dirty.return_value = [{"map_id": 1, "instance_id": 0, "revision": 3}]
        client = Mock()
        client.snapshot.return_value = snapshot()
        return (
            service.Worker(repository, client, domains, wander_interval=lambda: 5),
            repository,
            client,
        )

    def test_durable_delivery_precedes_new_planning(self):
        worker, repository, client = self.create(
            {"plants": lambda *_args, **_kwargs: [{"uid": 1}]}
        )
        pending = proposal("plants", {"uid": 2}, "boot-1")
        repository.pending.side_effect = [[pending], []]
        client.apply.return_value = [{"id": pending["id"], "status": "duplicate"}]
        worker.tick()
        client.apply.assert_called_once_with([pending])
        repository.acknowledge.assert_called_once_with(client.apply.return_value)
        proposals, dirty = repository.save.call_args.args
        self.assertEqual(proposals[0]["payload"], {"uid": 1})
        self.assertEqual(dirty[0]["revision"], 3)
        self.assertEqual(worker.counters["delivered"], 1)

    def test_delivery_splits_combined_body_and_only_acknowledges_sent_prefix(self):
        worker, repository, client = self.create(
            {"plants": lambda *_args, **_kwargs: []}
        )
        rows = [
            proposal(
                "plants", {"uid": uid, "data": "x" * (MAX_BODY_BYTES // 2)}, "boot"
            )
            for uid in (1, 2)
        ]
        for row in rows:
            json_bytes({"schema_version": 1, "proposals": [row]})
        with self.assertRaises(ValueError):
            json_bytes({"schema_version": 1, "proposals": rows})
        client.apply.side_effect = lambda batch: [
            {"id": row["id"], "status": "applied"} for row in batch
        ]
        worker.deliver(rows)
        client.apply.assert_called_once_with(rows[:1])
        repository.acknowledge.assert_called_once_with(
            [{"id": rows[0]["id"], "status": "applied"}]
        )
        worker.deliver(rows[1:])
        self.assertEqual(client.apply.call_args.args[0], rows[1:])
        self.assertEqual(worker.counters["delivered"], 2)

    def test_http_timeout_is_counted_durably_and_proactive_expiry_precedes_capacity_check(
        self,
    ):
        worker, repository, client = self.create({"plants": lambda *_a, **_kw: []})
        row = proposal("plants", {"uid": 991}, "boot")
        client.apply.side_effect = TimeoutError("unknown outcome")
        with self.assertRaises(TimeoutError):
            worker.deliver([row])
        repository.acknowledge.assert_called_once_with(
            [{"id": row["id"], "status": "retry"}]
        )
        self.assertEqual(worker.counters["retries"], 1)
        worker.tick()
        repository.expire_exhausted.assert_called_once()
        client.snapshot.assert_called_once()

    def test_retry_limit_configuration_is_bounded(self):
        for invalid in (0, 101, True, 1.5):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                service.Repository(Mock(), max_attempts=invalid)

    def test_domain_failure_does_not_discard_other_domains_or_ack_dirty(self):
        broken = Mock(side_effect=RuntimeError("private internal context"))
        worker, repository, _ = self.create(
            {"plants": broken, "mobs": lambda *_a, **_kw: [{"id": 5}]}
        )
        worker.tick()
        rows, dirty = repository.save.call_args.args
        self.assertEqual(rows[0]["domain"], "mobs")
        self.assertEqual(dirty, [])
        self.assertEqual(worker.domain_errors, {"plants": "RuntimeError"})
        self.assertNotIn("private", json.dumps(worker.status()))

    def test_offline_apply_preserves_pending_and_does_not_generate_more(self):
        prepare = Mock(return_value=[])
        worker, repository, client = self.create({"plants": prepare})
        repository.pending.return_value = [proposal("plants", {}, "boot")]
        client.apply.side_effect = TimeoutError()
        with self.assertRaises(TimeoutError):
            worker.tick()
        repository.acknowledge.assert_called_once_with(
            [{"id": repository.pending.return_value[0]["id"], "status": "retry"}]
        )
        repository.save.assert_not_called()
        prepare.assert_not_called()

    def test_pending_cap_and_pause_skip_planning(self):
        prepare = Mock(return_value=[])
        worker, repository, client = self.create({"plants": prepare})
        repository.pending_count.return_value = service.MAX_PENDING
        worker.tick()
        prepare.assert_not_called()
        repository.enabled.return_value = False
        client.reset_mock()
        worker.tick()
        client.snapshot.assert_not_called()

    def test_domain_budget_rotation_avoids_starvation(self):
        plants = Mock(side_effect=lambda *_a, limit: [{"n": n} for n in range(limit)])
        mobs = Mock(return_value=[])
        worker, repository, _ = self.create({"plants": plants, "mobs": mobs})
        worker.tick()
        mobs.assert_not_called()
        self.assertEqual(repository.save.call_args.args[1], [])
        worker.counters["ticks"] = 1
        worker.tick()
        mobs.assert_called_once()

    def test_stale_world_mode_and_lost_owner_stop_planning(self):
        prepare = Mock(return_value=[])
        worker, repository, client = self.create({"plants": prepare})
        client.snapshot.return_value = dict(snapshot(), mode="inline")
        with self.assertRaises(RuntimeError):
            worker.tick()
        prepare.assert_not_called()
        repository.assert_owner.side_effect = RuntimeError("lost")
        with self.assertRaises(RuntimeError):
            worker.tick()

    def test_previous_locations_and_wander_cadence_follow_successful_mobs_passes(self):
        captured = []

        def prepare(_store, value, *, limit):
            captured.append(dict(value))
            return []

        worker, _, client = self.create({"mobs": prepare})
        client.snapshot.return_value = dict(
            snapshot(), locations=[[527, 0]], now_ms=1000
        )
        worker.tick()
        self.assertTrue(captured[-1]["allow_wander"])
        client.snapshot.return_value = dict(
            snapshot(), locations=[[528, 0]], now_ms=2000
        )
        worker.tick()
        self.assertEqual(captured[-1]["previous_locations"], [[527, 0]])
        self.assertFalse(captured[-1]["allow_wander"])
        client.snapshot.return_value = dict(snapshot(), now_ms=6000)
        worker.tick()
        self.assertTrue(captured[-1]["allow_wander"])

    def test_failed_durable_save_does_not_advance_mobs_snapshot_clock(self):
        worker, repository, _ = self.create({"mobs": lambda *_a, **_kw: []})
        repository.save.side_effect = RuntimeError("database unavailable")
        with self.assertRaises(RuntimeError):
            worker.tick()
        self.assertIsNone(worker.last_mobs_now_ms)
        self.assertEqual(worker.last_locations, [])

    def test_query_is_single_flight_and_releases_gate_after_completion(self):
        worker, repository, _ = self.create({"plants": lambda *_a, **_kw: []})
        request = {"kind": "population", "map_id": 527, "instance_id": 0}
        repository.query.return_value = {"authoritative": True}
        self.assertTrue(worker.query(request)["authoritative"])
        self.assertTrue(worker.query_gate.acquire(blocking=False))
        try:
            with self.assertRaises(TimeoutError):
                worker.query(request)
        finally:
            worker.query_gate.release()
            worker.query_executor.shutdown(wait=True)

    def test_new_proposals_are_saved_before_same_tick_delivery(self):
        worker, repository, client = self.create(
            {"plants": lambda *_a, **_kw: [{"uid": 1}]}
        )
        prepared = proposal("plants", {"uid": 1}, "boot-1")
        repository.pending.side_effect = [[], [prepared]]
        client.apply.side_effect = lambda rows: (
            repository.save.assert_called_once()
            or [{"id": rows[0]["id"], "status": "applied"}]
        )
        worker.tick()
        client.apply.assert_called_once_with([prepared])
        repository.acknowledge.assert_called_once()


class ControlTests(unittest.TestCase):
    def handler(self, authorization):
        handler = object.__new__(service.Handler)
        handler.token = "secret"
        handler.headers = {"Authorization": authorization}
        handler.reply = Mock()
        handler.worker = Mock()
        return handler

    def test_health_status_and_query_require_dedicated_credential(self):
        for path in ("/health", "/status", "/metrics", "/query"):
            handler = self.handler("Bearer wrong")
            handler.path = path
            handler.do_GET()
            handler.reply.assert_called_once_with(401, {"error": "Unauthorized"})
            handler.worker.status.assert_not_called()

    def test_pause_persists_and_rejects_oversized_requests(self):
        handler = self.handler("Bearer secret")
        handler.path = "/pause"
        handler.headers["Content-Length"] = "2"
        handler.rfile = io.BytesIO(b"{}")
        handler.do_POST()
        handler.worker.repository.set_enabled.assert_called_once_with(False)
        handler.headers["Content-Length"] = str(MAX_BODY_BYTES + 1)
        handler.reply.reset_mock()
        handler.do_POST()
        handler.reply.assert_called_once_with(400, {"error": "Invalid request"})


if __name__ == "__main__":
    unittest.main()
