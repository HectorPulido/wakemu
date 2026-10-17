"""Run the complete server unittest suite and emit timing/source evidence.

The runner is deliberately read-only with respect to services and gameplay data.
Its JSON output contains hashes and test diagnostics, never environment values.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import inspect
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import unittest
import uuid
from functools import wraps


ROOT = Path(__file__).resolve().parents[2]
ENVIRONMENT_MARKERS = (
    "connection refused",
    "could not connect",
    "connection timed out",
    "name or service not known",
    "temporary failure in name resolution",
    "no such file or directory",
    "permission denied",
    "module not found",
    "no module named",
    "database is unavailable",
    "service unavailable",
)


def _manifest(root: Path) -> dict:
    """Hash executable source and versioned protocol/catalog inputs only."""
    roots = (root / "server",)
    allowed_data = {".json", ".jsonl", ".csv", ".tsv", ".txt", ".gz", ".bin"}
    entries = {}
    excluded_parts = {".runtime", ".git", "__pycache__", "node_modules", ".venv"}
    for base in roots:
        for path in base.rglob("*"):
            if (
                not path.is_file()
                or path.is_symlink()
                or excluded_parts.intersection(path.parts)
            ):
                continue
            rel = path.relative_to(root).as_posix()
            suffix = path.suffix.lower()
            if suffix != ".py" and not (
                suffix in allowed_data
                and (
                    "protocol" in path.parts
                    or "catalog" in path.name.lower()
                    or "fixture" in path.parts
                )
            ):
                continue
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            entries[rel] = hashlib.sha256(raw).hexdigest()
    return {
        "algorithm": "sha256",
        "scope": "server Python source and protocol/catalog/fixture data; credentials, runtime files, service state and client files excluded",
        "files": entries,
    }


def _provenance(root: Path) -> dict:
    """Prefer the shared inventory API for code identity and published catalogs."""
    sys.path.insert(0, str(root / "server"))
    try:
        from tools.combat_baseline_inventory import (
            catalog_manifest,
            environment_manifest,
            source_manifest,
        )
    except ImportError:
        return {
            "source": _manifest(root),
            "catalog": {
                "status": "unavailable",
                "error_type": "InventoryToolUnavailable",
            },
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
            },
        }
    try:
        catalog = catalog_manifest()
    except Exception as error:
        catalog = {"status": "unavailable", "error_type": type(error).__name__}
    return {
        "source": source_manifest(root),
        "catalog": catalog,
        "environment": environment_manifest(),
    }


def _classify(kind: str, details: str) -> dict:
    lowered = details.lower()
    matches = [marker for marker in ENVIRONMENT_MARKERS if marker in lowered]
    if kind == "failure":
        return {
            "classification": "baseline_test_failure",
            "evidence": "assertion failure in test result",
        }
    if matches:
        return {
            "classification": "environment_error_candidate",
            "evidence": "traceback contains: " + ", ".join(matches),
        }
    return {
        "classification": "baseline_test_error_unclassified",
        "evidence": "test raised an error; no recognized environment marker",
    }


def _remember_cli_asset_owners(factories):
    """Retain only already-loaded native resource factories; never import assets."""
    for name in ("wakfu_server.native_catalog", "wakfu_server.storage.native_catalog"):
        module = sys.modules.get(name)
        if module is None:
            continue
        for kind, attribute in (("database", "_database"), ("redis", "_redis")):
            factory = getattr(module, attribute, None)
            if callable(getattr(factory, "cache_info", None)):
                factories.setdefault(id(factory), (kind, factory))


def _finish_cli_asset_owners(factories):
    """Close observed cached owners after worker reporting, then exit normally."""
    _remember_cli_asset_owners(factories)
    errors, seen = [], set()
    for kind, factory in factories.values():
        try:
            info = factory.cache_info()
            if (
                info.maxsize != 1
                or type(info.currsize) is not int
                or info.currsize not in (0, 1)
            ):
                raise ValueError("Unexpected native CLI resource cache population")
            if info.currsize == 0:
                continue
            owner = factory()  # An existing no-argument cache hit, never a new owner.
            if id(owner) in seen:
                continue
            seen.add(id(owner))
        except Exception as error:
            errors.append(error)
            continue
        closed = False
        try:
            owner.close()
            closed = True
        except Exception as error:
            errors.append(error)
        try:
            if kind == "database" and closed:
                if owner.pool.closed is not True:
                    raise RuntimeError("Native CLI database pool remained open")
            elif kind == "redis":
                owner.connection_pool.disconnect()
        except Exception as error:
            errors.append(error)
    if errors:
        raise ExceptionGroup("Native CLI worker resource cleanup failed", errors)
    import gc

    # Only the short-lived CLI worker calls this after completed assertions and
    # report serialization. Imported APIs and the long-lived server never do.
    gc.freeze()


class ProfileResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_records = []
        self.test_outcomes = []
        self.started = {}
        self.current_test = None
        self.phases = {}
        self.progress_stream = None
        self.next_invocation_index = 0
        self.invocations = {}
        self.progress_sequence = 0
        self.cli_asset_owners = None

    def _progress(self, event):
        if self.progress_stream is not None:
            event = {
                "event_sequence": self.progress_sequence,
                "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                **event,
            }
            self.progress_stream.write(json.dumps(event, sort_keys=True) + "\n")
            self.progress_stream.flush()
            try:
                descriptor = self.progress_stream.fileno()
            except (AttributeError, io.UnsupportedOperation):
                # In-memory callers have no durable file descriptor. Real
                # journal write/fsync errors must remain visible.
                descriptor = None
            if descriptor is not None:
                os.fsync(descriptor)
            self.progress_sequence += 1

    def _outcome(self, test, status, **diagnostics):
        # Keep the existing exact report shape used by offline receipt readers.
        self.test_outcomes.append({"test_id": test.id(), "status": status})
        invocation = self.invocations.get(id(test))
        self._progress(
            {
                "event": "outcome",
                "id": test.id(),
                "status": status,
                "invocation_index": invocation,
                "synthetic_holder": not isinstance(test, unittest.TestCase),
                **diagnostics,
            }
        )

    def startTest(self, test):
        if self.cli_asset_owners is not None:
            _remember_cli_asset_owners(self.cli_asset_owners)
        self.started[test] = time.perf_counter()
        invocation = self.next_invocation_index
        self.next_invocation_index += 1
        self.invocations[id(test)] = invocation
        self.current_test = test
        super().startTest(test)
        self._progress(
            {"event": "start", "id": test.id(), "invocation_index": invocation}
        )

    def stopTest(self, test):
        if self.cli_asset_owners is not None:
            _remember_cli_asset_owners(self.cli_asset_owners)
        elapsed = time.perf_counter() - self.started.pop(test, time.perf_counter())
        self.current_test = None
        invocation = self.invocations.pop(id(test), None)
        super().stopTest(test)
        self.test_records.append({"id": test.id(), "elapsed_seconds": elapsed})
        self._progress(
            {
                "event": "stop",
                "id": test.id(),
                "invocation_index": invocation,
                "elapsed_seconds": elapsed,
            }
        )

    def addFailure(self, test, err):
        super().addFailure(test, err)
        details = self._exc_info_to_string(err, test)
        self._outcome(test, "failure", details=details)
        self.test_records.append(
            {"id": test.id(), **_classify("failure", details), "details": details}
        )

    def addError(self, test, err):
        super().addError(test, err)
        details = self._exc_info_to_string(err, test)
        self._outcome(test, "error", details=details)
        self.test_records.append(
            {"id": test.id(), **_classify("error", details), "details": details}
        )

    def addSuccess(self, test):
        super().addSuccess(test)
        self._outcome(test, "passed")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._outcome(test, "skipped", reason=reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._outcome(
            test, "expected_failure", details=self._exc_info_to_string(err, test)
        )

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._outcome(test, "unexpected_success")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self._outcome(
                test,
                "subtest_failure",
                subtest_id=subtest.id(),
                error_kind="failure"
                if issubclass(err[0], test.failureException)
                else "error",
                details=self._exc_info_to_string(err, subtest),
            )


class ProfileRunner(unittest.TextTestRunner):
    resultclass = ProfileResult

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.result_holder = {}
        self.progress_path = None
        self.cli_asset_owners = None

    def _makeResult(self):
        result = super()._makeResult()
        result.cli_asset_owners = self.cli_asset_owners
        if self.progress_path:
            result.progress_stream = self.progress_path.open("w", encoding="utf-8")
            os.chmod(self.progress_path, 0o600)
        self.result_holder["result"] = result
        return result

    def run(self, test):
        original_methods = {}
        fixture_restores = []

        def instrument(method_name, phase):
            original = getattr(unittest.TestCase, method_name)
            original_methods[method_name] = original

            @wraps(original)
            def wrapped(case, *args, **kwargs):
                started = time.perf_counter()
                try:
                    return original(case, *args, **kwargs)
                finally:
                    result = self.result_holder.get("result")
                    if result is not None:
                        key = case.id()
                        entry = result.phases.setdefault(
                            key,
                            {
                                "setUp_seconds": 0.0,
                                "test_method_seconds": 0.0,
                                "tearDown_seconds": 0.0,
                            },
                        )
                        entry[phase] += time.perf_counter() - started

            setattr(unittest.TestCase, method_name, wrapped)

        instrument("_callSetUp", "setUp_seconds")
        instrument("_callTestMethod", "test_method_seconds")
        instrument("_callTearDown", "tearDown_seconds")
        fixture_timing = {}

        def wrap_fixture(owner, name, label):
            descriptor = inspect.getattr_static(owner, name, None)
            if descriptor is None:
                return
            is_classmethod = isinstance(descriptor, classmethod)
            original = descriptor.__func__ if is_classmethod else descriptor

            @wraps(original)
            def timed(*args, **kwargs):
                started = time.perf_counter()
                try:
                    return original(*args, **kwargs)
                finally:
                    fixture_timing[label] = (
                        fixture_timing.get(label, 0.0) + time.perf_counter() - started
                    )

            setattr(owner, name, classmethod(timed) if is_classmethod else timed)
            fixture_restores.append((owner, name, descriptor))

        seen_modules = set()

        def visit(suite):
            if isinstance(suite, unittest.TestSuite):
                for child in suite:
                    visit(child)
            else:
                module = sys.modules.get(suite.__class__.__module__)
                if module is not None and module not in seen_modules:
                    seen_modules.add(module)
                    wrap_fixture(
                        module, "setUpModule", f"{module.__name__}.setUpModule_seconds"
                    )
                    wrap_fixture(
                        module,
                        "tearDownModule",
                        f"{module.__name__}.tearDownModule_seconds",
                    )
                cls = suite.__class__
                if cls not in seen_classes:
                    seen_classes.add(cls)
                    wrap_fixture(
                        cls,
                        "setUpClass",
                        f"{cls.__module__}.{cls.__qualname__}.setUpClass_seconds",
                    )
                    wrap_fixture(
                        cls,
                        "tearDownClass",
                        f"{cls.__module__}.{cls.__qualname__}.tearDownClass_seconds",
                    )

        seen_classes = set()
        visit(test)
        try:
            result = super().run(test)
            result.fixture_timing = fixture_timing
            return result
        finally:
            result = self.result_holder.get("result")
            if result is not None and result.progress_stream is not None:
                result.progress_stream.close()
            for method_name, original in original_methods.items():
                setattr(unittest.TestCase, method_name, original)
            for owner, name, original in reversed(fixture_restores):
                setattr(owner, name, original)


def _test_modules(test_dir: Path) -> list[str]:
    return sorted(path.stem for path in test_dir.glob("test*.py") if path.is_file())


def _run_single_module(
    root: Path,
    module: str,
    output: Path | None,
    verbosity: int,
    progress: Path | None,
    *,
    cli_asset_owners=None,
) -> dict:
    root = root.resolve()
    test_dir = root / "server/tests"
    sys.path.insert(0, str(root))
    sys.path.insert(0, str(root / "server"))
    # Match `python -m unittest discover -s server/tests`, where individual
    # test modules and helper modules such as postgres_case are top-level.
    sys.path.insert(0, str(test_dir))
    if cli_asset_owners is not None:
        _remember_cli_asset_owners(cli_asset_owners)
    loader = unittest.TestLoader()
    modules = [module]
    discovery_start = time.perf_counter()
    suite = loader.discover(
        str(test_dir), pattern=f"{module}.py", top_level_dir=str(test_dir)
    )
    discovery_seconds = time.perf_counter() - discovery_start

    # Preserve actual discovery order without running or consuming the suite.
    def discovered_ids(selected):
        if isinstance(selected, unittest.TestSuite):
            for child in selected:
                yield from discovered_ids(child)
        else:
            yield selected.id()

    expected_ids = list(discovered_ids(suite))
    expected_count = len(expected_ids)
    run_start = time.perf_counter()
    runner = ProfileRunner(verbosity=verbosity)
    runner.cli_asset_owners = cli_asset_owners
    runner.progress_path = progress.resolve() if progress else None
    result = runner.run(suite)
    run_seconds = time.perf_counter() - run_start
    import_origins = {}
    for name, imported in tuple(sys.modules.items()):
        filename = getattr(imported, "__file__", None)
        if isinstance(filename, str):
            candidate = Path(filename).resolve()
            if candidate.is_relative_to(root):
                import_origins[name] = candidate.relative_to(root).as_posix()
    failures = []
    for test, tb in result.failures:
        failures.append({"id": test.id(), **_classify("failure", tb), "details": tb})
    errors = []
    for test, tb in result.errors:
        errors.append({"id": test.id(), **_classify("error", tb), "details": tb})
    durations = [
        record for record in result.test_records if "elapsed_seconds" in record
    ]
    by_module = {}
    for record in durations:
        module = record["id"].rsplit(".", 1)[0]
        aggregate = by_module.setdefault(module, {"tests": 0, "elapsed_seconds": 0.0})
        aggregate["tests"] += 1
        aggregate["elapsed_seconds"] += record["elapsed_seconds"]
    report = {
        "schema_version": 1,
        "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "suite": "server/tests isolated module unittest discovery",
        "root": str(root),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "cwd": os.getcwd(),
        },
        "provenance": None,
        "timing": {
            "discovery_seconds": discovery_seconds,
            "execution_seconds": run_seconds,
            "total_seconds": discovery_seconds + run_seconds,
        },
        "discovery": {
            "modules": len(modules),
            "module_names": modules,
            "tests": expected_count,
            "test_ids": expected_ids,
            "loader_errors": loader.errors,
        },
        "test_outcomes": result.test_outcomes,
        "progress_journal_schema": "wakemu-profile-outcome-events-v2",
        "import_origins": dict(sorted(import_origins.items())),
        "python_startup": _python_startup(),
        "result": {
            "tests_run": result.testsRun,
            "failures": len(failures),
            "errors": len(errors),
            "expected_failures": len(result.expectedFailures),
            "unexpected_successes": len(result.unexpectedSuccesses),
            "skipped": len(result.skipped),
            "successful": result.wasSuccessful(),
        },
        "module_timing": dict(
            sorted(
                by_module.items(),
                key=lambda item: item[1]["elapsed_seconds"],
                reverse=True,
            )
        ),
        "test_timing": sorted(
            durations, key=lambda item: item["elapsed_seconds"], reverse=True
        ),
        "test_phase_timing": result.phases,
        "module_class_fixture_timing": getattr(result, "fixture_timing", {}),
        "failures": failures,
        "errors": errors,
        "skipped": [
            {"id": test.id(), "reason": reason} for test, reason in result.skipped
        ],
        "timing_note": "per-test phase timing separates setUp, test method and tearDown; total test timing also includes unittest cleanup and framework overhead. Module/class setup is included in execution_seconds but not yet separately attributed.",
    }
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n")
    return report


def _impact_observation(root, run_dir, provenance, before_graph, runner_policy):
    """Prepare an explanatory plan without changing the execution scope."""
    from tools.combat_test_impact import (
        build_graph,
        impact_inputs,
        runtime_policy_inputs,
        select_changes,
    )

    inputs = impact_inputs(root)
    graph = build_graph(
        root, catalog_inventory=provenance.get("catalog"), runner_policy=runner_policy
    )
    inputs.update(
        runtime_policy_inputs(
            graph.get("provenance", {}).get("runtime_policy_names", [])
        )
    )
    plan = select_changes(before_graph, graph)
    if plan.get("mode") != "observation":
        raise ValueError("Only observation impact plans are supported")
    artifacts = {}
    for name, value in (("after-graph", graph), ("selection-plan", plan)):
        path = run_dir / (name + ".json")
        raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
        with path.open("xb") as stream:
            os.chmod(path, 0o600)
            stream.write(raw)
        artifacts[name] = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
    if before_graph is not None:
        path = run_dir / "before-graph.json"
        raw = (json.dumps(before_graph, indent=2, sort_keys=True) + "\n").encode()
        with path.open("xb") as stream:
            os.chmod(path, 0o600)
            stream.write(raw)
        artifacts["before-graph"] = {
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    return plan, artifacts, inputs


def _python_startup():
    return {
        "isolated": bool(sys.flags.isolated),
        "no_site": bool(sys.flags.no_site),
        "ignore_environment": bool(sys.flags.ignore_environment),
    }


def _reuse_inputs(root, module, runner, policies):
    from tools.combat_baseline_inventory import environment_manifest
    from tools.combat_validation_offline import Eligibility, eligibility

    if not all(_python_startup().values()):
        return Eligibility(None, "Reuse requires parent Python -I -S")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != runner:
        return Eligibility(None, "Runner changed during supervision")
    return eligibility(
        root,
        module,
        runner_sha256=runner,
        environment_sha256=environment_manifest()["sha256"],
        policies=policies,
    )


def _private_artifact(path, raw):
    with path.open("xb") as stream:
        os.chmod(path, 0o600)
        stream.write(raw)


def run_profile(
    root: Path = ROOT,
    output: Path | None = None,
    verbosity: int = 1,
    progress: Path | None = None,
    *,
    module_timeout: float = 240.0,
    observe_impact: bool = False,
    impact_before_graph: dict | None = None,
    module_names: list[str] | None = None,
    result_store: Path | None = None,
    force_fresh: bool = False,
    full_refresh: bool = False,
) -> dict:
    """Run each test module in a fresh bounded child process.

    A module that exceeds its timeout is recorded and the remaining modules
    continue, so one blocked integration test cannot hang the complete baseline.
    """
    root = root.resolve()
    available_modules = _test_modules(root / "server/tests")
    if full_refresh and module_names is not None:
        raise ValueError("Full refresh cannot be limited to explicit modules")
    if module_names is not None and (observe_impact or impact_before_graph is not None):
        raise ValueError("Impact observation requires every discovered module")
    if module_names is not None and (
        not module_names
        or len(set(module_names)) != len(module_names)
        or any(name not in available_modules for name in module_names)
    ):
        raise ValueError("Explicit modules must be unique discovered test modules")
    modules = available_modules if module_names is None else list(module_names)
    force_fresh = (
        force_fresh or full_refresh or observe_impact or impact_before_graph is not None
    )
    if not output:
        raise ValueError("An output report path is required")
    output = output.resolve()
    progress = progress.resolve() if progress else None
    output.parent.mkdir(parents=True, exist_ok=True)
    run_dir = output.parent / (output.stem + "-modules")
    run_dir.mkdir(parents=True, exist_ok=False)
    if progress and progress.exists():
        raise FileExistsError(
            f"Refusing to reuse existing progress journal: {progress}"
        )
    started_all = time.perf_counter()
    provenance_before = _provenance(root)
    runner = {
        "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "policy": {
            "execution_model": "one module per subprocess",
            "module_timeout_seconds": module_timeout,
        },
    }
    if result_store is not None and all(_python_startup().values()):
        runner["policy"].update(
            python_import_mode="isolated-no-site-v1", python_startup=_python_startup()
        )
    cache = None
    cache_error = None
    if result_store is not None:
        try:
            from tools.combat_validation_reuse import LocalResultStore

            cache = LocalResultStore(result_store)
        except Exception as error:
            cache_error = type(error).__name__
    impact_plan = None
    impact = None
    impact_inputs_before = None
    if observe_impact or impact_before_graph is not None:
        try:
            impact_plan, artifacts, impact_inputs_before = _impact_observation(
                root, run_dir, provenance_before, impact_before_graph, runner["policy"]
            )
            impact = {
                "mode": "observation",
                "execution_scope": "all-discovered-modules",
                "artifacts": artifacts,
            }
        except Exception as error:
            # A diagnostic selector failure never suppresses normal validation.
            impact = {
                "mode": "observation",
                "execution_scope": "all-discovered-modules",
                "status": "unavailable",
                "error_type": type(error).__name__,
            }
    module_reports = {}
    completed_tests = []
    failures, errors, skipped, timings, phases, fixtures = [], [], [], [], {}, {}
    for index, name in enumerate(modules, 1):
        child_output = run_dir / f"{name}.json"
        child_progress = run_dir / f"{name}.jsonl"
        child_log = run_dir / f"{name}.log"
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--root",
            str(root),
            "--output",
            str(child_output),
            "--module",
            name,
            "--verbosity",
            "0",
            "--progress",
            str(child_progress),
        ]
        if runner["policy"].get("python_import_mode") == "isolated-no-site-v1":
            command[1:1] = ["-I", "-S"]
        child_started = time.perf_counter()
        outcome = {"status": "completed", "return_code": None, "origin": "executed"}
        reuse = {"enabled": result_store is not None, "forced_fresh": force_fresh}
        manifest_before = None
        hit = None
        if cache is not None:
            try:
                eligible = _reuse_inputs(root, name, runner["sha256"], runner["policy"])
                manifest_before = eligible.manifest
                reuse.update(
                    eligible=manifest_before is not None, reason=eligible.reason
                )
                if manifest_before is not None:
                    reuse["key"] = manifest_before.key
                    if not force_fresh:
                        hit = cache.lookup(manifest_before)
                        if hit is not None:
                            current = _reuse_inputs(
                                root, name, runner["sha256"], runner["policy"]
                            ).manifest
                            if current != manifest_before:
                                hit = None
                                manifest_before = current
                                reuse["reason"] = "inputs-changed-during-lookup"
                                reuse["key"] = None if current is None else current.key
            except Exception as error:
                reuse.update(
                    reason="cache-evidence-unavailable", error_type=type(error).__name__
                )
                hit = None
                manifest_before = None
        elif cache_error is not None:
            reuse.update(reason="store-unavailable", error_type=cache_error)
        if progress:
            progress.parent.mkdir(parents=True, exist_ok=True)
            with progress.open("a", encoding="utf-8") as journal:
                journal.write(
                    json.dumps(
                        {
                            "event": "module_start",
                            "index": index,
                            "modules": len(modules),
                            "module": name,
                            "utc": datetime.datetime.now(
                                datetime.timezone.utc
                            ).isoformat(),
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        if hit is not None:
            _private_artifact(child_output, hit.report_bytes)
            outcome.update(status="reused", origin="reused")
            reuse.update(
                receipt_sha256=hashlib.sha256(hit.receipt.encoded).hexdigest(),
                original_invocation_id=hit.receipt.as_dict()["parent"]["invocation_id"],
                original_receipt=str(cache.root / manifest_before.key / "receipt.json"),
            )
        else:
            with child_log.open("w", encoding="utf-8") as log:
                try:
                    process = subprocess.run(
                        command,
                        cwd=root,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        timeout=module_timeout,
                        check=False,
                    )
                    outcome["return_code"] = process.returncode
                    if process.returncode not in (0, 1) or not child_output.is_file():
                        outcome["status"] = "runner_error"
                except subprocess.TimeoutExpired:
                    outcome["status"] = "timeout"
        elapsed = time.perf_counter() - child_started
        if child_output.is_file():
            try:
                report = json.loads(child_output.read_text())
            except (OSError, json.JSONDecodeError) as error:
                report = None
                outcome.update(
                    status="runner_error",
                    evidence=f"invalid child report: {type(error).__name__}",
                )
            if report:
                if hit is None and outcome["status"] == "completed":
                    expected_exit = (
                        0 if report["result"].get("successful") is True else 1
                    )
                    if outcome["return_code"] != expected_exit:
                        outcome.update(
                            status="runner_error",
                            evidence="Child exit contradicts reported test outcome",
                        )
                current_result = dict(report["result"])
                current_timing = report["timing"]
                if hit is not None:
                    current_result.update(
                        tests_run=0,
                        tests_verified=report["result"]["tests_run"],
                        reused_tests=report["result"]["tests_run"],
                    )
                    current_timing = {
                        "discovery_seconds": 0.0,
                        "execution_seconds": 0.0,
                    }
                    reuse["original_child_timing"] = report["timing"]
                elif cache is not None and manifest_before is not None:
                    try:
                        from tools.combat_validation_reuse import (
                            ParentObservation,
                            terminal_receipt,
                        )

                        manifest_after = _reuse_inputs(
                            root, name, runner["sha256"], runner["policy"]
                        ).manifest
                        receipt = terminal_receipt(
                            manifest_before,
                            manifest_after,
                            ParentObservation(
                                outcome["status"],
                                outcome["return_code"],
                                outcome["status"] == "completed"
                                and outcome["return_code"] is not None
                                and outcome["return_code"] >= 0,
                                uuid.uuid4().hex,
                                name,
                                manifest_before.as_dict()["scope"],
                                runner["sha256"],
                            ),
                            child_output.read_bytes(),
                        )
                        receipt_path = run_dir / (name + ".receipt.json")
                        _private_artifact(receipt_path, receipt.encoded)
                        cache.publish(receipt, child_output.read_bytes())
                        reuse.update(
                            published=True,
                            receipt=str(receipt_path),
                            receipt_sha256=hashlib.sha256(receipt.encoded).hexdigest(),
                        )
                    except Exception as error:
                        reuse.update(
                            published=False, rejection_type=type(error).__name__
                        )
                module_reports[name] = {
                    "timing": current_timing,
                    "discovery": report["discovery"],
                    "result": current_result,
                    "wall_seconds": elapsed,
                    "status": outcome["status"],
                    "origin": outcome["origin"],
                    "return_code": outcome["return_code"],
                    "report": str(child_output),
                    "progress": None if hit is not None else str(child_progress),
                    "log": None if hit is not None else str(child_log),
                    "reuse": reuse,
                }
                if hit is None:
                    completed_tests.extend(report.get("test_timing", []))
                failures.extend(report.get("failures", []))
                errors.extend(report.get("errors", []))
                skipped.extend(report.get("skipped", []))
                if hit is None:
                    timings.extend(report.get("test_timing", []))
                    phases.update(report.get("test_phase_timing", {}))
                    fixtures.update(report.get("module_class_fixture_timing", {}))
            else:
                module_reports[name] = {
                    "status": outcome["status"],
                    "wall_seconds": elapsed,
                    "report": str(child_output),
                    "progress": str(child_progress),
                    "log": str(child_log),
                    **{key: value for key, value in outcome.items() if key != "status"},
                }
        else:
            module_reports[name] = {
                "status": outcome["status"],
                "wall_seconds": elapsed,
                "progress": str(child_progress),
                "log": str(child_log),
                **{key: value for key, value in outcome.items() if key != "status"},
            }
        module_reports[name].setdefault("reuse", reuse)
        if progress:
            progress.parent.mkdir(parents=True, exist_ok=True)
            with progress.open("a", encoding="utf-8") as journal:
                journal.write(
                    json.dumps(
                        {
                            "event": "module_complete",
                            "index": index,
                            "modules": len(modules),
                            "module": name,
                            **module_reports[name],
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
    total_run = time.perf_counter() - started_all
    discovery_seconds = sum(
        item.get("timing", {}).get("discovery_seconds", 0.0)
        for item in module_reports.values()
    )
    execution_seconds = sum(
        item.get("timing", {}).get("execution_seconds", 0.0)
        for item in module_reports.values()
    )
    test_count = sum(
        item.get("discovery", {}).get("tests", 0) for item in module_reports.values()
    )
    test_run = sum(
        item.get("result", {}).get("tests_run", 0) for item in module_reports.values()
    )
    failure_count = sum(
        item.get("result", {}).get("failures", 0) for item in module_reports.values()
    )
    error_count = sum(
        item.get("result", {}).get("errors", 0) for item in module_reports.values()
    )
    skip_count = sum(
        item.get("result", {}).get("skipped", 0) for item in module_reports.values()
    )
    timed_out = [
        name for name, item in module_reports.items() if item["status"] == "timeout"
    ]
    runner_errors = [
        name
        for name, item in module_reports.items()
        if item["status"] == "runner_error"
    ]
    provenance_after = _provenance(root)
    source_before = provenance_before.get("source", {}).get("sha256")
    source_after = provenance_after.get("source", {}).get("sha256")
    catalog_before = provenance_before.get("catalog", {})
    catalog_after = provenance_after.get("catalog", {})
    catalog_identity_verified = all(
        item.get("status") == "published"
        and item.get("publication_verified") is True
        and bool(item.get("sha256"))
        and bool(item.get("revision"))
        for item in (catalog_before, catalog_after)
    )
    provenance_stable = (
        bool(source_before)
        and source_before == source_after
        and catalog_identity_verified
        and catalog_before.get("sha256") == catalog_after.get("sha256")
        and catalog_before.get("revision") == catalog_after.get("revision")
    )
    report = {
        "schema_version": 1,
        "created_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "suite": "server/tests all test*.py modules"
        if module_names is None
        else "server/tests explicitly requested modules",
        "execution_scope": "all-discovered-modules"
        if module_names is None
        else "explicit-modules",
        "root": str(root),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "cwd": os.getcwd(),
        },
        "provenance_before": provenance_before,
        "provenance_after": provenance_after,
        "runner": runner,
        "catalog_identity_verified": catalog_identity_verified,
        "provenance_stable": provenance_stable,
        "timing": {
            "discovery_seconds": discovery_seconds,
            "execution_seconds": execution_seconds,
            "orchestration_and_profiling_seconds": max(
                0.0, total_run - discovery_seconds - execution_seconds
            ),
            "wall_seconds": total_run,
            "total_seconds": total_run,
            "execution_model": "one module per subprocess",
            "module_timeout_seconds": module_timeout,
        },
        "discovery": {
            "modules": len(modules),
            "module_names": modules,
            "available_module_names": available_modules,
            "tests": test_count,
            "loader_errors": [],
        },
        "result": {
            "tests_run": test_run,
            "tests_verified": sum(
                item.get("result", {}).get(
                    "tests_verified", item.get("result", {}).get("tests_run", 0)
                )
                for item in module_reports.values()
            ),
            "reused_tests": sum(
                item.get("result", {}).get("reused_tests", 0)
                for item in module_reports.values()
            ),
            "failures": failure_count,
            "errors": error_count,
            "expected_failures": sum(
                item.get("result", {}).get("expected_failures", 0)
                for item in module_reports.values()
            ),
            "unexpected_successes": sum(
                item.get("result", {}).get("unexpected_successes", 0)
                for item in module_reports.values()
            ),
            "skipped": skip_count,
            "timed_out_modules": timed_out,
            "runner_error_modules": runner_errors,
            "successful": not (
                failure_count
                or error_count
                or timed_out
                or runner_errors
                or any(
                    item.get("result", {}).get("unexpected_successes", 0)
                    for item in module_reports.values()
                )
            ),
        },
        "module_timing": module_reports,
        "test_timing": sorted(
            timings, key=lambda item: item["elapsed_seconds"], reverse=True
        ),
        "test_phase_timing": phases,
        "module_class_fixture_timing": fixtures,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "reuse": {
            "enabled": result_store is not None,
            "forced_fresh": force_fresh,
            "executed_modules": sum(
                item.get("origin", "executed") == "executed"
                for item in module_reports.values()
            ),
            "reused_modules": sum(
                item.get("origin") == "reused" for item in module_reports.values()
            ),
            "current_timing_excludes_original_reused_durations": True,
        },
        "timing_note": "each file is discovered and run in an isolated subprocess; per-test phase timing separates setUp, test method and tearDown, and module/class fixture setup is recorded separately. Per-module reports, logs and flushed progress journals are linked above.",
    }
    if impact is not None:
        if impact_plan is not None:
            from tools.combat_test_impact import (
                compare_shadow,
                impact_inputs,
                runtime_policy_inputs,
            )

            try:
                report["impact_inputs_before"] = impact_inputs_before
                report["impact_inputs_after"] = impact_inputs(root)
                report["impact_inputs_after"].update(
                    runtime_policy_inputs(
                        impact_inputs_before.get("runtime_policy_names", [])
                    )
                )
                impact["comparison"] = compare_shadow(impact_plan, report)
            except Exception as error:
                impact["comparison"] = {
                    "status": "unavailable",
                    "error_type": type(error).__name__,
                }
        report["impact_observation"] = impact
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main(argv=None, *, finish_worker=False) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Private JSON report path, preferably under .runtime",
    )
    parser.add_argument("--verbosity", type=int, choices=(0, 1, 2), default=1)
    parser.add_argument(
        "--progress", type=Path, help="Optional flushed JSONL test-start/stop journal"
    )
    parser.add_argument("--module", help=argparse.SUPPRESS)
    parser.add_argument(
        "--module-timeout",
        type=float,
        default=240.0,
        help="Timeout for each isolated test module (seconds)",
    )
    parser.add_argument(
        "--observe-impact",
        action="store_true",
        help="Explain proposed impact selection while executing every discovered module",
    )
    parser.add_argument(
        "--impact-before-graph",
        type=Path,
        help="Previously captured impact graph; enables observation mode",
    )
    parser.add_argument(
        "--modules",
        nargs="+",
        help="Explicit parent-supervised module scope; distinct from impact selection",
    )
    parser.add_argument(
        "--result-store",
        type=Path,
        help="Private store for complete qualified offline passes",
    )
    parser.add_argument(
        "--force-fresh",
        action="store_true",
        help="Bypass reuse for the requested scope",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Execute every discovered module without reuse",
    )
    args = parser.parse_args(argv)
    if args.module and (
        args.observe_impact
        or args.impact_before_graph
        or args.modules
        or args.result_store
        or args.force_fresh
        or args.full_refresh
    ):
        parser.error("Selection, reuse and observation belong to the parent supervisor")
    if args.modules and (
        args.full_refresh or args.observe_impact or args.impact_before_graph
    ):
        parser.error(
            "Full refresh and impact observation require every discovered module"
        )
    before_graph = None
    if args.impact_before_graph:
        try:
            before_graph = json.loads(args.impact_before_graph.read_text())
        except (OSError, ValueError):
            parser.error("Cannot read the previous impact graph")
    cli_asset_owners = {} if finish_worker and args.module else None
    report = (
        _run_single_module(
            args.root,
            args.module,
            args.output,
            args.verbosity,
            args.progress,
            cli_asset_owners=cli_asset_owners,
        )
        if args.module
        else run_profile(
            args.root,
            args.output,
            args.verbosity,
            args.progress,
            module_timeout=args.module_timeout,
            observe_impact=args.observe_impact,
            impact_before_graph=before_graph,
            module_names=args.modules,
            result_store=args.result_store,
            force_fresh=args.force_fresh,
            full_refresh=args.full_refresh,
        )
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "timing": report["timing"],
                "discovery": {
                    "modules": report["discovery"]["modules"],
                    "tests": report["discovery"]["tests"],
                },
                "result": report["result"],
            },
            indent=2,
        )
    )
    if cli_asset_owners is not None:
        sys.stdout.flush()
        _finish_cli_asset_owners(cli_asset_owners)
    return 0 if report["result"]["successful"] else 1


if __name__ == "__main__":
    raise SystemExit(main(finish_worker=True))
