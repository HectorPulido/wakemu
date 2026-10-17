"""Replay invariant diagnostics stay separate from deterministic outcomes."""
from contextlib import contextmanager, redirect_stdout, redirect_stderr
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from tools import combat_reproduce as cli
from wakfu_server.combat_invariants import Boundary, BoundaryReport, Finding
from wakfu_server.combat_invariant_resources import ResourceAuthority
from wakfu_server.combat_invariant_observation import (
    invariant_observation_scope,
    observe_prepared_boundary,
)


def resource_documents():
    rows = {
        str(stat): dict(hard_minimum=0, hard_maximum=100000, over_max_current=False)
        for stat in (1, 2, 3, 4)
    }
    return {
        "native-actor-characteristics.json": json.dumps(
            {"characteristics": rows}
        ).encode(),
        "native-class-copy-characteristics.json": json.dumps(
            {"fresh_characteristics": rows}
        ).encode(),
    }


def test_authority():
    actor, copied = resource_documents().values()
    return ResourceAuthority.from_documents(
        revision="test-revision",
        actor_bytes=actor,
        copy_bytes=copied,
        actor_sha256=hashlib.sha256(actor).hexdigest(),
        copy_sha256=hashlib.sha256(copied).hexdigest(),
    )


class InvariantReplayCLITests(unittest.TestCase):
    def run_cli(
        self,
        *,
        incident=False,
        enabled=True,
        findings=(),
        emit=True,
        checker_error=None
    ):
        catalog = ModuleType("wakfu_server.combat_reproduction_catalog")

        class ReplayCatalog:
            def __init__(self, root):
                self.root = root

            @contextmanager
            def install(self):
                yield

        catalog.ReplayCatalog = ReplayCatalog
        reproduction = ModuleType("wakfu_server.combat_reproduction")
        incidents = ModuleType("wakfu_server.combat_incident_replay")
        case = dict(boundary="isolated-runtime-action-not-live-session-recovery")
        raw = dict(
            status="accepted",
            sha256="unchanged-operation-hash",
            source_matches=True,
            source_sha256="source-hash",
            catalog_matches=True,
            catalog_revision="revision",
        )
        incident_result = dict(
            status="returned",
            operation_matches=True,
            actual_sha256="unchanged-shared-hash",
            expected_sha256="unchanged-shared-hash",
        )
        unchanged_raw, unchanged_incident = copy.deepcopy(raw), copy.deepcopy(
            incident_result
        )
        required = (
            ("Registry.execute", "commit_spell_transaction")
            if incident
            else ("commit_spell_transaction",)
        )
        executed = []

        def execute(*args, **kwargs):
            executed.append(True)
            if emit:
                for operation in required:
                    observe_prepared_boundary(object(), object(), operation=operation)
            return incident_result if incident else raw

        def inspect(fight, runtime, boundary, *, resource_authority=None, ack=None):
            if checker_error is not None:
                raise checker_error
            identity = (
                tuple(resource_authority.as_dict().values())
                if resource_authority
                else ()
            )
            return BoundaryReport(
                boundary, tuple(findings), ("resource.scalar",), 2, identity
            )

        reproduction.read_case = lambda path: case
        reproduction.verify_catalog_bundle = lambda *args: None
        reproduction.execute_case = execute
        reproduction.compare_expectation = lambda *args: dict(
            has_expectation=True, matches=True
        )
        incidents.read_incident = lambda path: {
            "schema": "wakemu-shared-combat-incident-v1"
        }
        incidents.verify_incident_bundle = lambda *args: None
        incidents.replay_runtime_incident = execute
        modules = {
            module.__name__: module for module in (catalog, reproduction, incidents)
        }
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            "sys.modules", modules
        ), patch.object(
            cli, "_invariant_plan", return_value=("player_spell", required, None)
        ) as plan, patch(
            "tools.combat_reproduce._invariant_resource_authority",
            return_value=(
                test_authority(),
                dict(status="verified", **test_authority().as_dict()),
            ),
        ) as authority_loader, patch(
            "wakfu_server.combat_invariant_observation.check_prepared_boundary",
            side_effect=inspect,
        ) as checker, redirect_stdout(
            output
        ):
            args = ["replay-incident" if incident else "replay", "--bundle", directory]
            if incident:
                args += ["--provider-recipe", "observed-live-server-v1"]
            if enabled:
                args.append("--check-invariants")
            destination = Path(directory) / "diagnostics.json"
            args += ["--output", str(destination)]
            code = cli.main(args)
            result = json.loads(output.getvalue())
            self.assertEqual(json.loads(destination.read_text()), result)
            self.assertEqual(executed, [True])
            self.assertEqual(raw, unchanged_raw)
            self.assertEqual(
                {
                    key: value
                    for key, value in incident_result.items()
                    if key != "invariants"
                },
                unchanged_incident,
            )
            if not enabled:
                checker.assert_not_called()
                plan.assert_not_called()
                authority_loader.assert_not_called()
        return code, result

    def test_replay_reports_unknown_coverage_without_changing_hash_or_normal_exit(self):
        unknown = Finding(
            "qi.coverage", "fight.qi", "unknown", "Dedicated QI adapter pending"
        )
        code, result = self.run_cli(findings=(unknown,))
        self.assertEqual(code, 0)
        self.assertEqual(result["result_sha256"], "unchanged-operation-hash")
        self.assertTrue(result["matches"])
        diagnostics = result["invariants"]
        self.assertEqual(diagnostics["status"], "partial_coverage")
        self.assertEqual(diagnostics["unknown_count"], 1)
        self.assertFalse(diagnostics["qualified"])
        self.assertFalse(diagnostics["full_coverage"])
        self.assertEqual(
            diagnostics["reports"][0]["operation"], "commit_spell_transaction"
        )
        self.assertEqual(diagnostics["reports"][0]["boundary"], "pre_adoption")

    def test_violations_change_only_diagnostic_exit_and_not_recorded_outcome(self):
        violation = Finding(
            "resource.scalar",
            "fight.actors",
            "violation",
            "Scalar disagrees with native projection",
        )
        code, result = self.run_cli(findings=(violation,))
        self.assertEqual(code, 1)
        self.assertEqual(result["result_sha256"], "unchanged-operation-hash")
        self.assertTrue(result["matches"])
        self.assertEqual(result["invariants"]["violation_count"], 1)

    def test_missing_actual_marker_is_unqualified_even_when_replay_matches(self):
        code, result = self.run_cli(emit=False)
        self.assertEqual(code, 2)
        self.assertTrue(result["matches"])
        self.assertEqual(
            result["invariants"]["missing_markers"], ["commit_spell_transaction"]
        )
        self.assertFalse(result["invariants"]["complete"])

    def test_checker_failure_remains_observational_and_returns_unqualified_code(self):
        code, result = self.run_cli(
            checker_error=RuntimeError("diagnostic-only failure")
        )
        self.assertEqual(code, 2)
        self.assertTrue(result["matches"])
        self.assertEqual(result["result_sha256"], "unchanged-operation-hash")
        self.assertTrue(result["invariants"]["checker_failed"])

    def test_incident_scope_covers_registry_and_spell_boundaries_separately(self):
        code, result = self.run_cli(incident=True)
        self.assertEqual(code, 0)
        self.assertEqual(result["actual_sha256"], "unchanged-shared-hash")
        self.assertEqual(result["expected_sha256"], "unchanged-shared-hash")
        self.assertEqual(
            result["invariants"]["expected_markers"],
            ["Registry.execute", "commit_spell_transaction"],
        )
        self.assertEqual(len(result["invariants"]["reports"]), 2)

    def test_default_replay_does_not_enable_checker_or_add_diagnostics(self):
        code, result = self.run_cli(enabled=False)
        self.assertEqual(code, 0)
        self.assertNotIn("invariants", result)

    def test_truncated_observations_and_finding_limits_return_unqualified_code(self):
        report = BoundaryReport(
            Boundary("commit_spell_transaction", "pre_adoption"), (), (), 2
        )
        with invariant_observation_scope(limit=1) as observed, patch(
            "wakfu_server.combat_invariant_observation.check_prepared_boundary",
            return_value=report,
        ):
            observe_prepared_boundary(
                object(), object(), operation="commit_spell_transaction"
            )
            observe_prepared_boundary(
                object(), object(), operation="commit_spell_transaction"
            )
        diagnostics = cli._invariant_summary(
            observed, ("player_spell", ("commit_spell_transaction",), None)
        )
        self.assertTrue(diagnostics["truncated"])
        self.assertEqual(diagnostics["dropped_reports"], 1)
        self.assertEqual(cli._invariant_exit_code(0, diagnostics), 2)
        limit = Finding(
            "coverage.limit", "fight", "unknown", "Additional findings omitted"
        )
        limited = SimpleNamespace(
            reports=(BoundaryReport(report.boundary, (limit,), (), 2),),
            _dropped=0,
            complete=False,
        )
        self.assertTrue(
            cli._invariant_summary(
                limited, ("player_spell", ("commit_spell_transaction",), None)
            )["truncated"]
        )

    def test_report_dicts_are_detached_and_operation_failure_is_preserved(self):
        finding = Finding("qi.coverage", "fight.qi", "unknown", "Missing adapter")
        report = BoundaryReport(
            Boundary("commit_spell_transaction", "pre_adoption"), (finding,), (), 2
        )
        observed = SimpleNamespace(reports=(report,), _dropped=0, complete=True)
        diagnostics = cli._invariant_summary(
            observed, ("player_spell", ("commit_spell_transaction",), None)
        )
        diagnostics["reports"][0]["findings"][0]["reason"] = "changed copy"
        self.assertEqual(report.findings[0].reason, "Missing adapter")
        self.assertEqual(cli._invariant_exit_code(1, diagnostics), 1)

    def test_unmodeled_native_and_ack_boundaries_are_explicitly_unsupported(self):
        with patch(
            "wakfu_server.combat_reproduction_state.decode_state",
            return_value={"type": "shared_ack"},
        ):
            ack = cli._invariant_plan(
                {"schema": "wakemu-shared-combat-incident-v1", "request": {}},
                incident=True,
            )
        chosen = cli._invariant_plan(
            {"schema": "wakemu-combat-npc-incident-v1"}, incident=True
        )
        publication = cli._invariant_plan(
            {"schema": "wakemu-combat-npc-publication-v1"}, incident=True
        )
        self.assertEqual(ack[1], ())
        self.assertIsNotNone(ack[2])
        self.assertEqual(chosen[1], ())
        self.assertIsNotNone(chosen[2])
        self.assertEqual(publication[1], ("Registry.execute_server",))
        observed = SimpleNamespace(reports=(), _dropped=0, complete=True)
        summary = cli._invariant_summary(observed, chosen)
        self.assertEqual(summary["reports"], [])
        self.assertFalse(summary["complete"])
        self.assertEqual(cli._invariant_exit_code(0, summary), 2)

    def test_flag_is_not_available_for_live_capture_recording(self):
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            cli.main(
                [
                    "record",
                    "--request",
                    "missing.json",
                    "--output",
                    "unused-output",
                    "--check-invariants",
                ]
            )
        self.assertEqual(caught.exception.code, 2)


class OfflineInvariantAuthorityTests(unittest.TestCase):
    @contextmanager
    def offline_bundle(self, *, missing=False):
        from wakfu_server import native_catalog
        from wakfu_server.combat_reproduction_catalog import ReplayCatalog

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "catalog").mkdir()
            documents = resource_documents()

            def blob(raw):
                digest = hashlib.sha256(raw).hexdigest()
                (root / "catalog" / digest).write_bytes(raw)
                return dict(sha256=digest, size=len(raw))

            descriptors = {name: blob(raw) for name, raw in documents.items()}
            manifest = dict(
                version=1,
                authority="postgresql-published-release",
                revision="offline-revision",
                published_hashes={
                    name: row["sha256"] for name, row in descriptors.items()
                },
                documents={} if missing else descriptors,
                records=blob(b"[]"),
                exists={},
            )
            (root / "catalog.json").write_text(json.dumps(manifest))
            with patch.object(
                native_catalog,
                "_database",
                side_effect=AssertionError("Offline replay contacted SQL"),
            ) as database:
                with ReplayCatalog(root).install():
                    yield root, descriptors
                database.assert_not_called()

    def collect(self):
        def inspect(fight, runtime, boundary, *, resource_authority=None, ack=None):
            identity = (
                tuple(resource_authority.as_dict().values())
                if resource_authority
                else ()
            )
            return BoundaryReport(boundary, (), (), 2, identity)

        with cli._invariant_scope(True) as observation, patch(
            "wakfu_server.combat_invariant_observation.check_prepared_boundary",
            side_effect=inspect,
        ):
            observe_prepared_boundary(
                object(), object(), operation="commit_spell_transaction"
            )
        return cli._invariant_summary(
            observation, ("player_spell", ("commit_spell_transaction",), None)
        )

    def test_offline_documents_provide_verified_identity_to_actual_scope(self):
        with self.offline_bundle():
            diagnostics = self.collect()
        self.assertEqual(diagnostics["resource_authority_input"]["status"], "verified")
        self.assertEqual(
            diagnostics["reports"][0]["resource_authority"]["revision"],
            "offline-revision",
        )
        self.assertEqual(cli._invariant_exit_code(0, diagnostics), 0)

    def test_missing_documents_are_explicit_partial_coverage_without_sql_fallback(self):
        with self.offline_bundle(missing=True):
            diagnostics = self.collect()
        self.assertEqual(diagnostics["resource_authority_input"]["status"], "missing")
        self.assertEqual(diagnostics["status"], "partial_coverage")
        self.assertFalse(diagnostics["qualified"])
        self.assertIsNone(diagnostics["reports"][0]["resource_authority"])
        self.assertEqual(cli._invariant_exit_code(0, diagnostics), 0)

    def test_tampered_document_is_diagnostic_error_without_sql_fallback(self):
        with self.offline_bundle() as (root, descriptors):
            digest = descriptors["native-actor-characteristics.json"]["sha256"]
            (root / "catalog" / digest).write_bytes(b"tampered")
            diagnostics = self.collect()
        self.assertEqual(diagnostics["resource_authority_input"]["status"], "error")
        self.assertFalse(diagnostics["complete"])
        self.assertEqual(cli._invariant_exit_code(0, diagnostics), 2)

    def test_published_hash_mismatch_is_not_silently_missing(self):
        from wakfu_server import native_catalog

        with self.offline_bundle(), patch.object(
            native_catalog, "document_hashes", return_value={}
        ):
            diagnostics = self.collect()
        self.assertEqual(diagnostics["resource_authority_input"]["status"], "error")
        self.assertEqual(cli._invariant_exit_code(0, diagnostics), 2)
