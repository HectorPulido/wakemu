import tempfile
import unittest
import io
import json
import sys
import hashlib
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.combat_validation_profile import (
    ProfileRunner,
    ProfileResult,
    _classify,
    _manifest,
    _impact_observation,
    run_profile,
)


class _InstrumentedSample(unittest.TestCase):
    def setUp(self):
        self.value = 1

    def test_value(self):
        self.assertEqual(self.value, 1)

    def tearDown(self):
        self.value = None


class CombatValidationProfileTests(unittest.TestCase):
    def _journal_run(self, suite):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        journal = Path(temporary.name) / "events.jsonl"
        runner = ProfileRunner(stream=io.StringIO(), verbosity=0)
        runner.progress_path = journal
        result = runner.run(suite)
        events = [json.loads(line) for line in journal.read_text().splitlines()]
        self.assertEqual(
            [event["event_sequence"] for event in events], list(range(len(events)))
        )
        self.assertEqual(journal.stat().st_mode & 0o077, 0)
        return result, events

    def test_durable_outcomes_distinguish_repeated_identical_case_ids(self):
        class Repeated(unittest.TestCase):
            def test_value(self):
                self.assertEqual(2 + 2, 4)

        first, second = Repeated("test_value"), Repeated("test_value")
        self.assertEqual(first.id(), second.id())
        result, events = self._journal_run(unittest.TestSuite((first, second)))
        self.assertEqual(result.testsRun, 2)
        self.assertEqual(
            [event["event"] for event in events],
            ["start", "outcome", "stop", "start", "outcome", "stop"],
        )
        self.assertEqual(
            [event["invocation_index"] for event in events], [0, 0, 0, 1, 1, 1]
        )
        self.assertEqual(
            result.test_outcomes, [{"test_id": first.id(), "status": "passed"}] * 2
        )
        self.assertTrue(
            all(
                not event["synthetic_holder"]
                for event in events
                if event["event"] == "outcome"
            )
        )

    def test_fixture_error_is_durable_without_inventing_a_test_invocation(self):
        class BrokenSetup(unittest.TestCase):
            @classmethod
            def setUpClass(cls):
                raise RuntimeError("durable fixture diagnosis")

            def test_never_started(self):
                raise AssertionError("Fixture failure must prevent this case")

        class Continued(unittest.TestCase):
            def test_runs_after_fixture_failure(self):
                self.assertTrue(True)

        suite = unittest.TestSuite(
            (
                BrokenSetup("test_never_started"),
                Continued("test_runs_after_fixture_failure"),
            )
        )
        result, events = self._journal_run(suite)
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.errors), 1)
        holder = events[0]
        self.assertEqual(holder["event"], "outcome")
        self.assertEqual(holder["status"], "error")
        self.assertTrue(holder["synthetic_holder"])
        self.assertIsNone(holder["invocation_index"])
        self.assertIn("durable fixture diagnosis", holder["details"])
        self.assertEqual([event["invocation_index"] for event in events[1:]], [0, 0, 0])
        self.assertEqual(events[2]["status"], "passed")

    def test_subtest_journal_keeps_parent_occurrence_and_actual_failure_kind(self):
        class Subtests(unittest.TestCase):
            def test_variants(self):
                with self.subTest(branch="assertion"):
                    self.fail("durable subtest assertion")
                with self.subTest(branch="exception"):
                    raise ValueError("durable subtest exception")
                with self.subTest(branch="success"):
                    self.assertTrue(True)

        result, events = self._journal_run(
            unittest.TestSuite((Subtests("test_variants"),))
        )
        outcomes = [event for event in events if event["event"] == "outcome"]
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual([event["invocation_index"] for event in outcomes], [0, 0])
        self.assertEqual(
            [event["error_kind"] for event in outcomes if "error_kind" in event],
            ["failure", "error"],
        )
        self.assertEqual(
            [event["status"] for event in outcomes],
            ["subtest_failure", "subtest_failure"],
        )
        self.assertEqual(
            [event["status"] for event in result.test_outcomes],
            ["subtest_failure", "subtest_failure"],
        )
        self.assertIn("branch='assertion'", outcomes[0]["subtest_id"])
        self.assertIn("durable subtest assertion", outcomes[0]["details"])
        self.assertIn("durable subtest exception", outcomes[1]["details"])
        self.assertFalse(any(event["status"] == "passed" for event in outcomes))

    def test_cli_cleanup_never_constructs_empty_cached_owners(self):
        from functools import lru_cache
        from tools.combat_validation_profile import (
            _remember_cli_asset_owners,
            _finish_cli_asset_owners,
        )

        @lru_cache(maxsize=1)
        def empty():
            self.fail("Cleanup constructed a new owner")

        owners = {}
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.native_catalog": SimpleNamespace(_database=empty),
                "wakfu_server.storage.native_catalog": None,
            },
        ), patch("gc.freeze") as freeze:
            _remember_cli_asset_owners(owners)
            _finish_cli_asset_owners(owners)
        self.assertEqual(empty.cache_info().misses, 0)
        freeze.assert_called_once_with()

    def test_cli_cleanup_retains_overlay_replaced_owners_and_closes_pools(self):
        from functools import lru_cache
        from tools.combat_validation_profile import (
            _remember_cli_asset_owners,
            _finish_cli_asset_owners,
        )

        events = []
        pool = SimpleNamespace(closed=False)

        def close_database():
            events.append("database.close")
            pool.closed = True

        database_owner = SimpleNamespace(close=close_database, pool=pool)
        redis_owner = SimpleNamespace(
            close=lambda: events.append("redis.close"),
            connection_pool=SimpleNamespace(
                disconnect=lambda: events.append("redis.disconnect")
            ),
        )
        database = lru_cache(maxsize=1)(lambda: database_owner)
        redis = lru_cache(maxsize=1)(lambda: redis_owner)
        database()
        redis()
        module = SimpleNamespace(_database=database, _redis=redis)
        owners = {}
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.native_catalog": module,
                "wakfu_server.storage.native_catalog": module,
            },
        ), patch("gc.freeze", side_effect=lambda: events.append("freeze")):
            _remember_cli_asset_owners(owners)
            module._redis = lambda: self.fail("Overlay resource factory was called")
            _finish_cli_asset_owners(owners)
        self.assertEqual(
            events, ["database.close", "redis.close", "redis.disconnect", "freeze"]
        )
        self.assertEqual(
            (database.cache_info().misses, redis.cache_info().misses), (1, 1)
        )
        self.assertTrue(pool.closed)

    def test_cli_cleanup_errors_remain_visible_and_prevent_freeze(self):
        from functools import lru_cache
        from tools.combat_validation_profile import _finish_cli_asset_owners

        def broken_close():
            raise RuntimeError("visible resource close failure")

        owner = SimpleNamespace(close=broken_close)
        factory = lru_cache(maxsize=1)(lambda: owner)
        factory()
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.native_catalog": None,
                "wakfu_server.storage.native_catalog": None,
            },
        ), patch("gc.freeze") as freeze:
            with self.assertRaises(ExceptionGroup) as caught:
                _finish_cli_asset_owners({id(factory): ("database", factory)})
        self.assertIn(
            "visible resource close failure", str(caught.exception.exceptions[0])
        )
        freeze.assert_not_called()

    def test_cli_worker_serializes_before_cleanup_and_exits_normally(self):
        project = Path(__file__).resolve().parents[2]
        for passing in (True, False):
            with self.subTest(
                passing=passing
            ), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                tests = root / "server/tests"
                tests.mkdir(parents=True)
                (tests / "test_fixture.py").write_text(
                    "import unittest\nclass Actual(unittest.TestCase):\n"
                    + " def test_value(self): self.assertTrue("
                    + repr(passing)
                    + ")\n"
                )
                output, closed = root / "report.json", root / "closed.json"
                worker = root / "worker.py"
                worker.write_text(
                    "import json, sys\nfrom pathlib import Path\nfrom types import SimpleNamespace\n"
                    "from functools import lru_cache\n"
                    + "sys.path.insert(0, "
                    + repr(str(project / "server"))
                    + ")\n"
                    "from tools.combat_validation_profile import main\n"
                    + "output=Path("
                    + repr(str(output))
                    + ")\n"
                    "pool=SimpleNamespace(closed=False)\n"
                    "def close():\n"
                    " report=json.loads(output.read_text())\n"
                    " assert report['result']['tests_run']==1\n"
                    " pool.closed=True\n"
                    "owner=SimpleNamespace(close=close,pool=pool)\n"
                    "database=lru_cache(maxsize=1)(lambda: owner)\n"
                    "database()\n"
                    "sys.modules['wakfu_server.native_catalog']=SimpleNamespace(_database=database)\n"
                    + "code=main(['--root',"
                    + repr(str(root))
                    + ",'--module','test_fixture','--output',"
                    + repr(str(output))
                    + ",'--verbosity','0'],finish_worker=True)\n"
                    + "Path("
                    + repr(str(closed))
                    + ").write_text(json.dumps({'closed':pool.closed,'misses':database.cache_info().misses}))\n"
                    "raise SystemExit(code)\n"
                )
                result = subprocess.run(
                    [sys.executable, "-I", "-S", "-B", str(worker)],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                self.assertEqual(result.returncode, 0 if passing else 1, result.stderr)
                self.assertEqual(
                    json.loads(closed.read_text()), {"closed": True, "misses": 1}
                )
                self.assertEqual(
                    json.loads(output.read_text())["result"]["successful"], passing
                )

    def test_large_successful_subtest_loops_keep_bounded_durable_events(self):
        iterations = 2000

        class LargeLoop(unittest.TestCase):
            def test_all_pass(self):
                for value in range(iterations):
                    with self.subTest(value=value):
                        self.assertGreaterEqual(value, 0)

            def test_one_failure(self):
                for value in range(iterations):
                    with self.subTest(value=value):
                        if value == iterations // 2:
                            self.fail("retained large-loop subtest failure")

        result, events = self._journal_run(
            unittest.defaultTestLoader.loadTestsFromTestCase(LargeLoop)
        )
        self.assertEqual(result.testsRun, 2)
        self.assertEqual(len(result.failures), 1)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(
            [event["event"] for event in events],
            ["start", "outcome", "stop", "start", "outcome", "stop"],
        )
        self.assertEqual(
            [event["invocation_index"] for event in events], [0, 0, 0, 1, 1, 1]
        )
        outcomes = [event for event in events if event["event"] == "outcome"]
        self.assertEqual(
            [event["status"] for event in outcomes], ["passed", "subtest_failure"]
        )
        self.assertIn("value=1000", outcomes[1]["subtest_id"])
        self.assertIn("retained large-loop subtest failure", outcomes[1]["details"])
        self.assertEqual(result.test_outcomes[1]["status"], "subtest_failure")

    def test_all_unittest_terminal_callback_kinds_are_streamed(self):
        class Outcomes(unittest.TestCase):
            def test_error(self):
                raise ValueError("ordinary streamed error")

            @unittest.expectedFailure
            def test_expected(self):
                self.fail("expected streamed assertion")

            def test_failure(self):
                self.fail("ordinary streamed assertion")

            def test_pass(self):
                self.assertTrue(True)

            @unittest.skip("streamed skip reason")
            def test_skip(self):
                pass

            @unittest.expectedFailure
            def test_unexpected(self):
                pass

        result, events = self._journal_run(
            unittest.defaultTestLoader.loadTestsFromTestCase(Outcomes)
        )
        outcomes = [event for event in events if event["event"] == "outcome"]
        self.assertEqual(
            [event["status"] for event in outcomes],
            [
                "error",
                "expected_failure",
                "failure",
                "passed",
                "skipped",
                "unexpected_success",
            ],
        )
        self.assertEqual(
            [event["invocation_index"] for event in outcomes], list(range(6))
        )
        self.assertEqual(outcomes[4]["reason"], "streamed skip reason")
        self.assertEqual(result.testsRun, 6)
        self.assertEqual(
            (
                len(result.errors),
                len(result.failures),
                len(result.skipped),
                len(result.expectedFailures),
                len(result.unexpectedSuccesses),
            ),
            (1, 1, 1, 1, 1),
        )

    def test_hard_interruption_retains_durable_outcome_prefix_without_final_report(
        self,
    ):
        project = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temporary:
            journal = Path(temporary) / "interrupted.jsonl"
            worker = Path(temporary) / "worker.py"
            worker.write_text(
                "import io, os, sys, unittest\nfrom pathlib import Path\n"
                + "sys.path.insert(0, "
                + repr(str(project / "server"))
                + ")\n"
                + "from tools.combat_validation_profile import ProfileRunner\n"
                + "class Interrupted(unittest.TestCase):\n"
                + " def test_a_pass(self): self.assertTrue(True)\n"
                + " def test_b_failure(self): self.fail('persisted before hard interruption')\n"
                + " def test_c_interrupt(self): os._exit(23)\n"
                + "runner = ProfileRunner(stream=io.StringIO(), verbosity=0)\n"
                + "runner.progress_path = Path("
                + repr(str(journal))
                + ")\n"
                + "runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(Interrupted))\n"
            )
            completed = subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(worker)],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(completed.returncode, 23, completed.stderr)
            events = [json.loads(line) for line in journal.read_text().splitlines()]
            self.assertEqual(
                [event["event_sequence"] for event in events], list(range(7))
            )
            self.assertEqual(
                [event["status"] for event in events if event["event"] == "outcome"],
                ["passed", "failure"],
            )
            failure = next(
                event for event in events if event.get("status") == "failure"
            )
            self.assertEqual(failure["invocation_index"], 1)
            self.assertIn("persisted before hard interruption", failure["details"])
            self.assertEqual(events[-1]["event"], "start")
            self.assertEqual(events[-1]["invocation_index"], 2)
            self.assertFalse(
                any(
                    event["event"] == "outcome" and event["invocation_index"] == 2
                    for event in events
                )
            )

    def test_real_offline_pass_reuses_and_invalidates_through_parent_supervision(self):
        from tools.combat_validation_offline import IMPLEMENTATIONS, REGISTRY

        project = Path(__file__).resolve().parents[2]
        declaration = json.loads((project / REGISTRY).read_bytes())
        entry = declaration["modules"]["test_combat_transaction_rng"]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "repo"
            for name in (
                set(entry["source"])
                | set(IMPLEMENTATIONS)
                | {
                    REGISTRY,
                    "server/tools/combat_validation_profile.py",
                    "server/tools/combat_baseline_inventory.py",
                }
            ):
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((project / name).read_bytes())
            store = Path(temporary) / "store"
            counter = 0

            external = Path(temporary) / "external"
            external.mkdir()
            sentinel = Path(temporary) / "startup-hook-ran"
            (external / "random.py").write_text(
                "raise RuntimeError('External random imported')\n"
            )
            (external / "sitecustomize.py").write_text(
                f"from pathlib import Path; Path({str(sentinel)!r}).touch()\n"
            )

            def invoke(*, fresh=False, timeout=240.0, isolated=True):
                nonlocal counter
                counter += 1
                output = Path(temporary) / f"run-{counter}.json"
                command = [sys.executable]
                if isolated:
                    command += ["-I", "-S"]
                command += [
                    str(root / "server/tools/combat_validation_profile.py"),
                    "--root",
                    str(root),
                    "--output",
                    str(output),
                    "--modules",
                    "test_combat_transaction_rng",
                    "--result-store",
                    str(store),
                    "--module-timeout",
                    str(timeout),
                ]
                if fresh:
                    command.append("--force-fresh")
                environment = dict(os.environ)
                if isolated:
                    environment["PYTHONPATH"] = str(external)
                else:
                    environment.pop("PYTHONPATH", None)
                completed = subprocess.run(
                    command,
                    cwd=root,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                report = json.loads(output.read_bytes())
                row = report["module_timing"]["test_combat_transaction_rng"]
                workers = int(row["origin"] == "executed")
                if not workers:
                    self.assertIsNone(row["log"])
                    self.assertIsNone(row["progress"])
                self.assertFalse(sentinel.exists())
                return report, workers

            first, workers = invoke()
            first_module = first["module_timing"]["test_combat_transaction_rng"]
            self.assertEqual(workers, 1)
            self.assertEqual(first["result"]["tests_run"], 3)
            self.assertTrue(first_module["reuse"].get("published"), first_module)
            original = json.loads(Path(first_module["reuse"]["receipt"]).read_bytes())

            cached, workers = invoke()
            row = cached["module_timing"]["test_combat_transaction_rng"]
            self.assertEqual(workers, 0)
            self.assertEqual(row["origin"], "reused")
            self.assertIsNone(row["return_code"])
            self.assertEqual(cached["result"]["tests_run"], 0)
            self.assertEqual(cached["result"]["tests_verified"], 3)
            self.assertEqual(cached["result"]["reused_tests"], 3)
            self.assertEqual(cached["timing"]["execution_seconds"], 0)
            self.assertEqual(
                row["reuse"]["original_invocation_id"],
                original["parent"]["invocation_id"],
            )

            (root / "server/unrelated.py").write_text("UNRELATED = True\n")
            unrelated, workers = invoke()
            self.assertEqual(workers, 0)
            self.assertEqual(unrelated["reuse"]["reused_modules"], 1)

            forced, workers = invoke(fresh=True)
            self.assertEqual(workers, 1)
            forced_row = forced["module_timing"]["test_combat_transaction_rng"]
            self.assertEqual(forced_row["origin"], "executed")
            forced_receipt = json.loads(
                Path(forced_row["reuse"]["receipt"]).read_bytes()
            )
            self.assertNotEqual(
                forced_receipt["parent"]["invocation_id"],
                original["parent"]["invocation_id"],
            )

            policy_changed, workers = invoke(timeout=239.0)
            self.assertEqual(workers, 1)
            self.assertTrue(
                policy_changed["module_timing"]["test_combat_transaction_rng"][
                    "reuse"
                ].get("published")
            )
            self.assertNotEqual(
                policy_changed["module_timing"]["test_combat_transaction_rng"]["reuse"][
                    "key"
                ],
                first_module["reuse"]["key"],
            )

            ordinary, workers = invoke(isolated=False)
            self.assertEqual(workers, 1)
            ordinary_row = ordinary["module_timing"]["test_combat_transaction_rng"]
            self.assertFalse(ordinary_row["reuse"]["eligible"])
            self.assertIn("-I -S", ordinary_row["reuse"]["reason"])
            self.assertNotIn("published", ordinary_row["reuse"])

            implementation = (
                root / "server/wakfu_server/combat/combat_transaction_rng.py"
            )
            implementation.write_bytes(
                implementation.read_bytes()
                + b"\n# Private qualification invalidation fixture.\n"
            )
            changed, workers = invoke()
            self.assertEqual(workers, 1)
            changed_row = changed["module_timing"]["test_combat_transaction_rng"]
            self.assertEqual(changed_row["origin"], "executed")
            self.assertFalse(changed_row["reuse"]["eligible"])
            self.assertNotIn("published", changed_row["reuse"])

    def test_namespaced_server_tools_imports_match_standard_unittest_discovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tests = root / "server/tests"
            tests.mkdir(parents=True)
            helper = root / "server/tools/namespaced_fixture.py"
            helper.parent.mkdir(parents=True)
            helper.write_text("VALUE = 47\n")
            (tests / "test_namespaced.py").write_text(
                "import unittest\nfrom server.tools.namespaced_fixture import VALUE\n"
                "class Contract(unittest.TestCase):\n"
                " def test_value(self): self.assertEqual(VALUE, 47)\n"
            )
            environment = dict(os.environ, PYTHONPATH=str(root / "server"))
            control = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "unittest",
                    "discover",
                    "-s",
                    "server/tests",
                    "-p",
                    "test_namespaced.py",
                ],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=15,
            )
            self.assertEqual(control.returncode, 0, control.stderr)
            provenance = {
                "source": {"sha256": "isolated-fixture"},
                "catalog": {"status": "not-consumed"},
            }
            with patch(
                "tools.combat_validation_profile._provenance", return_value=provenance
            ):
                report = run_profile(
                    root, root / "profile.json", module_names=["test_namespaced"]
                )
            self.assertTrue(report["result"]["successful"], report["module_timing"])
            self.assertEqual(report["result"]["tests_run"], 1)
            self.assertEqual(
                report["module_timing"]["test_namespaced"]["return_code"], 0
            )

    def test_relative_artifacts_resolve_from_caller_when_root_differs(self):
        script = (
            Path(__file__).resolve().parents[1] / "tools/combat_validation_profile.py"
        )
        with tempfile.TemporaryDirectory() as temporary:
            caller = Path(temporary) / "caller"
            caller.mkdir()
            root = Path(temporary) / "target"
            tests = root / "server/tests"
            tests.mkdir(parents=True)
            (tests / "test_sample.py").write_text(
                "import unittest\nclass Contract(unittest.TestCase):\n"
                " def test_value(self): self.assertEqual(1, 1)\n"
            )
            process = subprocess.run(
                [
                    sys.executable,
                    str(script),
                    "--root",
                    str(root),
                    "--modules",
                    "test_sample",
                    "--output",
                    "artifacts/profile.json",
                    "--progress",
                    "artifacts/profile.jsonl",
                ],
                cwd=caller,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            report = json.loads((caller / "artifacts/profile.json").read_bytes())
            row = report["module_timing"]["test_sample"]
            self.assertEqual(report["result"]["tests_run"], 1)
            self.assertTrue(report["result"]["successful"])
            self.assertEqual(row["return_code"], 0)
            self.assertTrue(Path(row["report"]).is_relative_to(caller.resolve()))
            self.assertTrue(Path(row["progress"]).is_file())
            self.assertFalse((root / "artifacts").exists())
            self.assertEqual(
                json.loads(
                    (caller / "artifacts/profile.jsonl").read_text().splitlines()[-1]
                )["event"],
                "module_complete",
            )

    def test_outcomes_distinguish_pass_from_stop_and_subtest_failure(self):
        class Cases(unittest.TestCase):
            def test_broken(self):
                with self.subTest(case="broken"):
                    self.assertEqual(1, 2)

            def test_passed(self):
                self.assertEqual(1, 1)

            @unittest.skip("fixture")
            def test_skipped(self):
                pass

        result = ProfileRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(Cases)
        )
        self.assertEqual(result.testsRun, 3)
        self.assertEqual(
            [row["status"] for row in result.test_outcomes],
            ["subtest_failure", "passed", "skipped"],
        )
        self.assertEqual(
            len([row for row in result.test_records if "elapsed_seconds" in row]), 3
        )

    def test_real_child_processes_and_graph_report_an_introduced_contract_failure(self):
        from tools.combat_baseline_inventory import (
            environment_manifest,
            source_manifest,
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            tests = root / "server/tests"
            tests.mkdir(parents=True)
            runner_path = root / "server/tools/combat_validation_profile.py"
            runner_path.parent.mkdir(parents=True)
            runner_path.write_bytes(
                (
                    Path(__file__).resolve().parents[1]
                    / "tools/combat_validation_profile.py"
                ).read_bytes()
            )
            contract = root / "server/impact_fixture_contract.py"
            contract.write_text("VALUE = 2\n")
            (tests / "test_contract.py").write_text(
                "import unittest\nimport os\nos.getenv('WAKFU_VALIDATION_TEST_POLICY')\nfrom impact_fixture_contract import VALUE\n"
                "class Contract(unittest.TestCase):\n"
                " def test_value(self): self.assertEqual(VALUE, 2)\n"
            )
            (tests / "test_other.py").write_text(
                "import unittest\nclass Other(unittest.TestCase):\n"
                " def test_value(self): self.assertEqual(1, 1)\n"
            )

            def provenance(_root):
                # Declared isolated catalog authority for a graph/runner fixture;
                # these two tests consume no catalog or gameplay data.
                return {
                    "source": source_manifest(_root),
                    "environment": environment_manifest(),
                    "catalog": {
                        "status": "published",
                        "publication_verified": True,
                        "revision": "isolated-runner-fixture",
                        "sha256": "a" * 64,
                        "documents": {},
                    },
                }

            with patch(
                "tools.combat_validation_profile._provenance", side_effect=provenance
            ):
                before = run_profile(root, root / "before.json", observe_impact=True)
                self.assertTrue(before["result"]["successful"])
                graph_path = before["impact_observation"]["artifacts"]["after-graph"][
                    "path"
                ]
                graph = json.loads(Path(graph_path).read_bytes())
                # Different byte length prevents same-timestamp bytecode reuse
                # from hiding the actual introduced failure in fresh children.
                contract.write_text("VALUE = 300\n")
                after = run_profile(
                    root, root / "after.json", impact_before_graph=graph
                )

            # A policy changing during supervision must invalidate shadow
            # compatibility even when the actual tests themselves pass.
            contract.write_text("VALUE = 2\n")
            calls = 0

            def drifting_provenance(_root):
                nonlocal calls
                calls += 1
                value = provenance(_root)
                if calls == 2:
                    os.environ["WAKFU_VALIDATION_TEST_POLICY"] = "changed-during-run"
                return value

            with patch.dict(
                os.environ, {"WAKFU_VALIDATION_TEST_POLICY": "initial"}
            ), patch(
                "tools.combat_validation_profile._provenance",
                side_effect=drifting_provenance,
            ):
                drifted = run_profile(
                    root, root / "drifted.json", impact_before_graph=graph
                )
            self.assertTrue(drifted["result"]["successful"])
            self.assertEqual(
                drifted["impact_observation"]["comparison"]["status"], "incompatible"
            )
            self.assertIn(
                "impact_inputs_after:runtime_policy_sha256",
                drifted["impact_observation"]["comparison"]["mismatches"],
            )

            observation = after["impact_observation"]
            self.assertEqual(
                observation["comparison"]["status"], "matched", observation
            )
            plan = json.loads(
                Path(observation["artifacts"]["selection-plan"]["path"]).read_bytes()
            )
            self.assertEqual(plan["selected_module_names"], ["test_contract"])
            self.assertEqual(after["module_timing"]["test_contract"]["return_code"], 1)
            self.assertEqual(
                after["module_timing"]["test_contract"]["result"]["failures"], 1
            )
            self.assertEqual(after["module_timing"]["test_other"]["return_code"], 0)
            self.assertFalse(after["result"]["successful"])

    def test_observation_artifacts_bind_both_graphs_and_execution_policy(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            before = {"digest": "old"}
            after = {"digest": "new"}
            plan = {"mode": "observation", "selected_module_names": []}
            policy = {
                "execution_model": "one module per subprocess",
                "module_timeout_seconds": 73.0,
            }
            calls = []

            def build(root, **kwargs):
                calls.append((root, kwargs))
                return after

            fake = SimpleNamespace(
                build_graph=build,
                impact_inputs=lambda root: {"fixture": "stable"},
                runtime_policy_inputs=lambda names: {},
                select_changes=lambda old, new: plan
                if (old, new) == (before, after)
                else None,
            )
            with patch.dict(sys.modules, {"tools.combat_test_impact": fake}):
                actual, artifacts, inputs = _impact_observation(
                    run_dir,
                    run_dir,
                    {"catalog": {"revision": "pinned"}},
                    before,
                    policy,
                )
            self.assertEqual(actual, plan)
            self.assertEqual(inputs, {"fixture": "stable"})
            self.assertEqual(
                calls,
                [
                    (
                        run_dir,
                        {
                            "catalog_inventory": {"revision": "pinned"},
                            "runner_policy": policy,
                        },
                    )
                ],
            )
            for name, value in (
                ("before-graph", before),
                ("after-graph", after),
                ("selection-plan", plan),
            ):
                path = Path(artifacts[name]["path"])
                self.assertEqual(json.loads(path.read_bytes()), value)
                self.assertEqual(
                    hashlib.sha256(path.read_bytes()).hexdigest(),
                    artifacts[name]["sha256"],
                )
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with patch.dict(
                sys.modules, {"tools.combat_test_impact": fake}
            ), self.assertRaises(FileExistsError):
                _impact_observation(run_dir, run_dir, {}, before, policy)

    def test_impact_observation_keeps_every_module_and_records_outside_outcomes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "server/tests").mkdir(parents=True)
            executed = []
            plan = {"mode": "observation", "selected_module_names": ["test_first"]}

            def execute(command, **_kwargs):
                name = command[command.index("--module") + 1]
                executed.append(name)
                failures = int(name == "test_outside")
                Path(command[command.index("--output") + 1]).write_text(
                    json.dumps(
                        {
                            "timing": {},
                            "discovery": {"tests": 1},
                            "result": {
                                "tests_run": 1,
                                "failures": failures,
                                "errors": 0,
                                "skipped": 0,
                                "successful": not failures,
                            },
                        }
                    )
                )
                return SimpleNamespace(returncode=failures)

            comparisons = []

            def compare(selection, report):
                comparisons.append(
                    (
                        selection,
                        report["module_timing"]["test_outside"]["result"]["failures"],
                    )
                )
                return {"status": "matched", "outside_failures": ["test_outside"]}

            with patch(
                "tools.combat_validation_profile._test_modules",
                return_value=["test_first", "test_outside"],
            ), patch(
                "tools.combat_validation_profile._provenance", return_value={}
            ), patch(
                "tools.combat_validation_profile._impact_observation",
                return_value=(plan, {}, {"fixture": "stable"}),
            ), patch(
                "tools.combat_validation_profile.platform.platform",
                return_value="test-platform",
            ), patch(
                "tools.combat_validation_profile.subprocess.run", side_effect=execute
            ), patch.dict(
                sys.modules,
                {
                    "tools.combat_test_impact": SimpleNamespace(
                        compare_shadow=compare,
                        impact_inputs=lambda root: {"fixture": "stable"},
                        runtime_policy_inputs=lambda names: {},
                    )
                },
            ):
                report = run_profile(root, root / "profile.json", observe_impact=True)

            self.assertEqual(executed, ["test_first", "test_outside"])
            self.assertEqual(comparisons, [(plan, 1)])
            self.assertEqual(
                report["impact_inputs_before"], report["impact_inputs_after"]
            )
            self.assertFalse(report["result"]["successful"])
            self.assertEqual(
                report["impact_observation"]["comparison"]["outside_failures"],
                ["test_outside"],
            )
            self.assertEqual(
                report["impact_observation"]["execution_scope"],
                "all-discovered-modules",
            )

    def test_unavailable_selector_preserves_full_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "server/tests").mkdir(parents=True)
            with patch(
                "tools.combat_validation_profile._test_modules", return_value=[]
            ), patch(
                "tools.combat_validation_profile._provenance", return_value={}
            ), patch(
                "tools.combat_validation_profile._impact_observation",
                side_effect=ValueError("invalid graph"),
            ):
                report = run_profile(root, root / "profile.json", observe_impact=True)
            self.assertEqual(report["impact_observation"]["status"], "unavailable")
            self.assertEqual(
                report["impact_observation"]["execution_scope"],
                "all-discovered-modules",
            )
            self.assertEqual(report["impact_observation"]["error_type"], "ValueError")

    def test_phase_timing_covers_setup_method_and_teardown(self):
        result = ProfileRunner(stream=io.StringIO(), verbosity=0).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(_InstrumentedSample)
        )
        self.assertIsInstance(result, ProfileResult)
        key = next(
            key
            for key in result.phases
            if key.endswith("_InstrumentedSample.test_value")
        )
        phases = result.phases[key]
        self.assertEqual(
            set(phases), {"setUp_seconds", "test_method_seconds", "tearDown_seconds"}
        )
        self.assertTrue(all(value >= 0 for value in phases.values()))

    def test_failure_and_environment_classification_include_evidence(self):
        self.assertEqual(
            _classify("failure", "AssertionError: wrong value")["classification"],
            "baseline_test_failure",
        )
        classified = _classify(
            "error", "Connection refused while connecting to database"
        )
        self.assertEqual(classified["classification"], "environment_error_candidate")
        self.assertIn("connection refused", classified["evidence"])
        unclassified = _classify("error", "ValueError: bad state")
        self.assertEqual(
            unclassified["classification"], "baseline_test_error_unclassified"
        )

    def test_manifest_hashes_python_and_catalog_inputs_without_reading_runtime_files(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "server/tools").mkdir(parents=True)
            (root / "server/protocol").mkdir(parents=True)
            (root / "server/.runtime").mkdir(parents=True)
            (root / "server/tools/a.py").write_text("pass\n")
            (root / "server/protocol/spell_catalog.json").write_text("{}\n")
            (root / "server/.runtime/secret.json").write_text("private\n")
            manifest = _manifest(root)
            self.assertIn("server/tools/a.py", manifest["files"])
            self.assertIn("server/protocol/spell_catalog.json", manifest["files"])
            self.assertNotIn("server/.runtime/secret.json", manifest["files"])

    def test_profile_records_child_return_codes_for_pass_and_failure(self):
        provenance = {
            "source": {"sha256": "source-digest"},
            "catalog": {
                "status": "published",
                "publication_verified": True,
                "sha256": "catalog-digest",
                "revision": "release-1",
            },
        }
        for return_code, failures in ((0, 0), (1, 1), (1, 0), (0, 1)):
            with self.subTest(
                return_code=return_code
            ), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                (root / "server/tests").mkdir(parents=True)
                output = root / "profile.json"
                progress = root / "profile.jsonl"

                def fake_run(command, **_kwargs):
                    child_output = Path(command[command.index("--output") + 1])
                    child_output.write_text(
                        json.dumps(
                            {
                                "timing": {
                                    "discovery_seconds": 0.1,
                                    "execution_seconds": 0.2,
                                },
                                "discovery": {
                                    "modules": 1,
                                    "module_names": ["test_sample"],
                                    "tests": 1,
                                },
                                "result": {
                                    "tests_run": 1,
                                    "failures": failures,
                                    "errors": 0,
                                    "expected_failures": 0,
                                    "unexpected_successes": 0,
                                    "skipped": 0,
                                    "successful": failures == 0,
                                },
                                "test_timing": [],
                                "test_phase_timing": {},
                                "module_class_fixture_timing": {},
                                "failures": [],
                                "errors": [],
                                "skipped": [],
                            }
                        )
                    )
                    return SimpleNamespace(returncode=return_code)

                with patch(
                    "tools.combat_validation_profile._test_modules",
                    return_value=["test_sample"],
                ), patch(
                    "tools.combat_validation_profile._provenance",
                    return_value=provenance,
                ), patch(
                    "tools.combat_validation_profile.platform.platform",
                    return_value="test-platform",
                ), patch(
                    "tools.combat_validation_profile.subprocess.run",
                    side_effect=fake_run,
                ):
                    report = run_profile(root, output, progress=progress)

                module = report["module_timing"]["test_sample"]
                self.assertEqual(module["return_code"], return_code)
                contradictory = return_code != int(bool(failures))
                self.assertEqual(
                    module["status"], "runner_error" if contradictory else "completed"
                )
                self.assertEqual(
                    report["result"]["successful"], not (contradictory or failures)
                )
                events = [
                    json.loads(line) for line in progress.read_text().splitlines()
                ]
                completed = next(
                    event for event in events if event["event"] == "module_complete"
                )
                self.assertEqual(completed["return_code"], return_code)


if __name__ == "__main__":
    unittest.main()
