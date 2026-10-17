"""Differential gates reject stale, missing-selection and changed outcomes."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import combat_migration_replay as replay


class CombatMigrationReplayTests(unittest.TestCase):
    def workers(self):
        legacy = dict(
            schema=replay.SCHEMA,
            backend="legacy",
            families=["vitality"],
            capsule_sha256="capsule",
            catalog_manifest_sha256="manifest",
            runner_sha256="runner",
            source_sha256="source",
            catalog={"revision": "catalog"},
            outcome_sha256="exact-typed-state-and-packet-digest",
            status="accepted",
            baseline_matches=True,
            observations=[dict(family="vitality", backend="legacy", count=2)],
            isolation="fresh-interpreter-read-only-offline-catalog",
        )
        shared = copy.deepcopy(legacy)
        shared.update(
            backend="shared",
            observations=[dict(family="vitality", backend="shared", count=2)],
        )
        return legacy, shared

    def test_matching_typed_outcome_qualifies_exact_backend_comparison_only(self):
        legacy, shared = self.workers()
        result = replay.compare_workers(legacy, shared, ["vitality"])
        self.assertTrue(result["qualified"])
        self.assertFalse(result["selection_counts_prove_effect_execution"])
        self.assertFalse(result["live_commit"])
        self.assertFalse(result["live_delivery"])

    def test_equal_hash_without_requested_backend_resolution_does_not_qualify(self):
        legacy, shared = self.workers()
        shared["observations"] = []
        result = replay.compare_workers(legacy, shared, ["vitality"])
        self.assertTrue(result["matches"])
        self.assertFalse(result["qualified"])
        self.assertEqual(
            result["missing_family_selection"],
            [dict(family="vitality", backend="shared")],
        )

    def test_changed_input_source_catalog_or_policy_rejects_equal_outcome(self):
        for field in (
            "capsule_sha256",
            "source_sha256",
            "catalog_manifest_sha256",
            "catalog",
            "families",
            "isolation",
            "backend",
            "runner_sha256",
        ):
            with self.subTest(field=field):
                legacy, shared = self.workers()
                shared[field] = "changed"
                result = replay.compare_workers(legacy, shared, ["vitality"])
                self.assertFalse(result["qualified"])
                self.assertIn(field, result["identity_mismatches"])

    def test_packet_state_rng_or_error_change_is_not_normalized(self):
        legacy, shared = self.workers()
        shared["outcome_sha256"] = "different-typed-packet-state-or-rng"
        self.assertFalse(
            replay.compare_workers(legacy, shared, ["vitality"])["matches"]
        )
        shared["outcome_sha256"] = legacy["outcome_sha256"]
        shared["status"] = "execution_error"
        self.assertFalse(
            replay.compare_workers(legacy, shared, ["vitality"])["matches"]
        )

    def test_inherited_expectation_failure_is_reported_separately(self):
        legacy, shared = self.workers()
        legacy["baseline_matches"] = shared["baseline_matches"] = False
        result = replay.compare_workers(legacy, shared, ["vitality"])
        self.assertTrue(result["qualified"])
        self.assertFalse(result["shared"]["baseline_matches"])

    def test_external_historical_engine_is_required_without_current_fallback(self):
        with self.assertRaisesRegex(ValueError, "unavailable"):
            replay.validate_historical_root(replay.SERVER, "a" * 64)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "unavailable"):
                replay.validate_historical_root(root, "a" * 64)
            policy = root / "wakfu_server" / "combat" / "combat_core_migration.py"
            policy.parent.mkdir(parents=True)
            policy.write_text("# Explicit test archive sentinel\n")
            with self.assertRaisesRegex(ValueError, "SHA256"):
                replay.validate_historical_root(root, "unpinned")
            with self.assertRaisesRegex(ValueError, "explicitly pinned"):
                replay.validate_historical_root(root, "a" * 64)
            expected = replay.historical_source_sha256(root)
            self.assertEqual(
                replay.validate_historical_root(root, expected), root.resolve()
            )
            policy.write_text("# Archive changed after pinning\n")
            with self.assertRaisesRegex(ValueError, "explicitly pinned"):
                replay.validate_historical_root(root, expected)

    def test_worker_audit_rejects_mutation_process_and_network(self):
        events = [
            ("open", ("file", "w", os.O_WRONLY)),
            ("open", ("file", None, os.O_CREAT)),
            ("socket.connect", (None, ("localhost", 1))),
            ("os.rename", ("a", "b", -1, -1)),
            ("subprocess.Popen", ("python", [], None, {})),
        ]
        for event, arguments in events:
            with self.subTest(event=event), self.assertRaises(PermissionError):
                replay._read_only(event, arguments)
        replay._read_only("open", ("file", "r", os.O_RDONLY))

    def test_subprocess_uses_fresh_isolated_interpreter_with_timeout(self):
        args = SimpleNamespace(
            bundle=Path("/private/bundle"),
            capsule="case.json",
            kind="case",
            families=["vitality"],
            provider_recipe=None,
            historical_server_root=Path("/private/archive/server"),
            expected_source_sha256="a" * 64,
            timeout=42,
        )
        with patch.object(
            replay.subprocess,
            "run",
            return_value=SimpleNamespace(
                returncode=0, stdout=json.dumps({"receipt": True})
            ),
        ) as run:
            self.assertEqual(replay._run_worker(args, "legacy"), {"receipt": True})
        command = run.call_args.args[0]
        self.assertEqual(command[1:5], ["-I", "-S", "-B", "-c"])
        self.assertEqual(run.call_args.kwargs["timeout"], 42)
        self.assertIn("sys.path.append(", command[-1])
        self.assertNotIn("sys.path.insert(0,", command[-1])
        self.assertIn("'legacy'", command[-1])
        self.assertNotIn("--allow-source-drift", command[-1])
        self.assertIn("'--historical-server-root'", command[-1])
        self.assertIn("'/private/archive/server'", command[-1])
        self.assertIn("'--expected-source-sha256'", command[-1])
        # Exercise the real generated bootstrap path setup against a dependency
        # directory containing a poison legacy typing module. Importing stdlib
        # typing must still work under the same -I -S interpreter flags.
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "typing.py").write_text(
                "raise RuntimeError('third-party typing shadowed stdlib')\n"
            )
            with patch.object(
                replay.sysconfig, "get_path", return_value=directory
            ), patch.object(
                replay.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0, stdout="{}"),
            ) as generated:
                replay._run_worker(args, "legacy")
            path_setup = generated.call_args.args[0][-1].split(";sys.argv=", 1)[0]
            probe = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-S",
                    "-B",
                    "-c",
                    path_setup + ";import typing;print(typing.__file__)",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            expected_typing = Path(replay.sysconfig.get_path("stdlib")) / "typing.py"
            self.assertEqual(
                Path(probe.stdout.strip()).resolve(), expected_typing.resolve()
            )

    def test_real_worker_audit_blocks_writes_and_connections_even_if_caught(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "must-not-be-created"
            code = "\n".join(
                [
                    "import sys,os,json,socket,subprocess",
                    "sys.path.insert(0," + repr(str(replay.SERVER)) + ")",
                    "from tools import combat_migration_replay as replay",
                    "sys.addaudithook(replay._read_only)",
                    "attempts = [lambda: open(" + repr(str(target)) + ", 'w'),",
                    "            lambda: socket.socket(),",
                    "            lambda: subprocess.run([sys.executable, '-c', 'pass'])]",
                    "blocked = 0",
                    "for attempt in attempts:",
                    "    try: attempt()",
                    "    except PermissionError: blocked += 1",
                    "print(json.dumps({'blocked': blocked, 'recorded': len(replay._ISOLATION_VIOLATIONS)}))",
                ]
            )
            result = subprocess.run(
                [sys.executable, "-I", "-S", "-B", "-c", code],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            self.assertEqual(json.loads(result.stdout), dict(blocked=3, recorded=3))
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
