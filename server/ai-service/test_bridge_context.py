"""HTTP sender/exporter acceptance for complete native context transport."""
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import server as ai_server
from server import BoundedHTTPServer, Handler
from context_store import ContextStore
from native_context import NativeGraph
from world_bridge import CompleteContextExporter, ContextTransport, _json_bytes
from native_deadline import bounded
from native_deadline import check as native_deadline_check


class ContextBridgeHTTPTests(unittest.TestCase):
    def test_parts_transport_provisions_all_blobs_before_manifest_and_verifies_cached_content(
        self,
    ):
        from native_graph_parts import encode_parts, load_graph
        from native_context import encode
        from wakfu_server.combat_geometry_snapshot import ImmutableTerrainSet

        coordinate = tuple([61, 62, 63])
        value = {
            "outside": coordinate,
            "terrain": ImmutableTerrainSet([coordinate, (64, 65, 66)]),
        }
        value["cycle"] = value
        parts = encode_parts(value)
        digest = self.transport.instance_parts(parts)
        store = self.store()
        self.addCleanup(store.close)
        graph = load_graph(store, digest)
        self.assertEqual(list(graph.nodes), encode(value)["nodes"])
        self.assertEqual(self.transport.instance_parts(parts), digest)
        blob_digest = next(iter(parts[1]))
        store._path(blob_digest).write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            load_graph(store, digest)
        self.assertEqual(self.transport.instance_parts(parts), digest)
        self.assertEqual(list(load_graph(store, digest).nodes), encode(value)["nodes"])

    def test_concurrent_inventory_callers_share_scan_but_receive_independent_results(
        self,
    ):
        root = Path(self.temporary.name) / "coalesced-native"
        root.mkdir()
        (root / "opaque.future").write_bytes(b"complete bytes")
        exporter = CompleteContextExporter({"all": root})
        self.addCleanup(exporter.close)
        exporter._inventory_admission_seconds = 0.05
        original = exporter._inventory_scan
        calls = []
        calls_lock = threading.Lock()

        def counted_scan():
            with calls_lock:
                calls.append(1)
            return original()

        exporter._inventory_scan = counted_scan
        barrier = threading.Barrier(6)
        results = [None] * 6
        errors = []

        def invoke(index):
            try:
                barrier.wait(timeout=2)
                results[index] = exporter.inventory()
            except BaseException as error:
                errors.append(error)

        workers = [threading.Thread(target=invoke, args=(index,)) for index in range(6)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(3)
        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertEqual(errors, [])
        self.assertEqual(len(calls), 1)
        first_manifest, first_sources = results[0]
        second_manifest, second_sources = results[1]
        self.assertIsNot(first_manifest, second_manifest)
        self.assertIsNot(first_manifest["entries"], second_manifest["entries"])
        self.assertIsNot(first_sources, second_sources)
        first_manifest["entries"][0]["path"] = "corrupted-by-caller"
        first_sources.clear()
        self.assertEqual(second_manifest["entries"][0]["path"], "all/opaque.future")
        digest = second_manifest["entries"][0]["sha256"]
        self.assertEqual(second_sources[digest].read_bytes(), b"complete bytes")

    def test_inventory_late_caller_gets_next_scan_and_sees_new_future_file(self):
        root = Path(self.temporary.name) / "late-native"
        root.mkdir()
        (root / "initial.bin").write_bytes(b"initial")
        exporter = CompleteContextExporter({"all": root})
        self.addCleanup(exporter.close)
        exporter._inventory_admission_seconds = 0.005
        original = exporter._inventory_scan
        first_scan_finished = threading.Event()
        release_first = threading.Event()
        calls = []
        calls_lock = threading.Lock()
        results = {}
        errors = []

        def gated_scan():
            with calls_lock:
                index = len(calls)
                calls.append(index)
            value = original()
            if index == 0:
                first_scan_finished.set()
                if not release_first.wait(3):
                    raise TimeoutError("test failed to release first inventory scan")
            return value

        exporter._inventory_scan = gated_scan

        def invoke(name):
            try:
                results[name] = exporter.inventory()
            except BaseException as error:
                errors.append(error)

        first = threading.Thread(target=invoke, args=("first",))
        first.start()
        self.assertTrue(first_scan_finished.wait(2))
        (root / "created-during-first-scan.future").write_bytes(b"new source")
        late = threading.Thread(target=invoke, args=("late",))
        late.start()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            with exporter._inventory_condition:
                if len(exporter._inventory_batches) >= 2:
                    break
            time.sleep(0.001)
        else:
            self.fail("late caller did not form a next inventory batch")
        release_first.set()
        first.join(3)
        late.join(3)
        self.assertFalse(first.is_alive() or late.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(calls), 2)
        first_paths = {row["path"] for row in results["first"][0]["entries"]}
        late_paths = {row["path"] for row in results["late"][0]["entries"]}
        self.assertNotIn("all/created-during-first-scan.future", first_paths)
        self.assertIn("all/created-during-first-scan.future", late_paths)
        late_digest = next(
            row["sha256"]
            for row in results["late"][0]["entries"]
            if row["path"].endswith("created-during-first-scan.future")
        )
        self.assertEqual(results["late"][1][late_digest].read_bytes(), b"new source")

    def test_inventory_batch_failure_is_shared_and_later_call_retries(self):
        root = Path(self.temporary.name) / "retry-native"
        root.mkdir()
        (root / "asset").write_bytes(b"source")
        exporter = CompleteContextExporter({"all": root})
        self.addCleanup(exporter.close)
        exporter._inventory_admission_seconds = 0.05
        original = exporter._inventory_scan
        calls = []
        calls_lock = threading.Lock()
        barrier = threading.Barrier(2)
        failures = []

        def flaky_scan():
            with calls_lock:
                calls.append(1)
                number = len(calls)
            if number == 1:
                raise ValueError("shared inventory failure")
            return original()

        exporter._inventory_scan = flaky_scan

        def invoke():
            try:
                barrier.wait(timeout=2)
                exporter.inventory()
            except ValueError as error:
                failures.append(str(error))

        workers = [threading.Thread(target=invoke) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(3)
        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertEqual(failures, ["shared inventory failure"] * 2)
        self.assertEqual(len(calls), 1)
        manifest, sources = exporter.inventory()
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(manifest["entries"]), 1)
        digest = manifest["entries"][0]["sha256"]
        self.assertEqual(sources[digest].read_bytes(), b"source")

    def test_inventory_waiter_deadline_does_not_cancel_other_waiter_or_leader(self):
        root = Path(self.temporary.name) / "deadline-native"
        root.mkdir()
        (root / "asset").write_bytes(b"source")
        exporter = CompleteContextExporter({"all": root})
        self.addCleanup(exporter.close)
        exporter._inventory_admission_seconds = 0.02
        original = exporter._inventory_scan
        first_scan_finished = threading.Event()
        release_first = threading.Event()
        calls = []
        calls_lock = threading.Lock()
        errors = []
        results = []

        def gated_scan():
            with calls_lock:
                index = len(calls)
                calls.append(index)
            value = original()
            if index == 0:
                first_scan_finished.set()
                if not release_first.wait(3):
                    raise TimeoutError("test failed to release inventory leader")
            return value

        exporter._inventory_scan = gated_scan
        leader = threading.Thread(target=lambda: results.append(exporter.inventory()))
        leader.start()
        self.assertTrue(first_scan_finished.wait(2))

        def short_waiter():
            try:
                with bounded(time.monotonic() + 0.06):
                    exporter.inventory()
            except TimeoutError:
                errors.append("waiter deadline")

        def long_waiter():
            try:
                results.append(exporter.inventory())
            except BaseException as error:
                errors.append(str(error))

        short = threading.Thread(target=short_waiter)
        long = threading.Thread(target=long_waiter)
        short.start()
        long.start()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            with exporter._inventory_condition:
                if len(exporter._inventory_batches) >= 2:
                    break
            time.sleep(0.001)
        else:
            self.fail("waiters did not queue a second batch")
        short.join(1)
        self.assertFalse(short.is_alive())
        self.assertEqual(errors, ["waiter deadline"])
        release_first.set()
        for worker in (leader, long):
            worker.join(3)
        self.assertFalse(leader.is_alive() or long.is_alive())
        self.assertEqual(errors, ["waiter deadline"])
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][0], results[1][0])

    def test_inventory_expired_waiter_does_not_accept_completed_batch_result(self):
        root = Path(self.temporary.name) / "expired-result-native"
        root.mkdir()
        (root / "asset").write_bytes(b"source")
        exporter = CompleteContextExporter({"all": root})
        self.addCleanup(exporter.close)
        exporter._inventory_admission_seconds = 0
        original = exporter._inventory_scan
        scan_ready = threading.Event()
        release_scan = threading.Event()
        waiter_at_return_check = threading.Event()
        release_waiter = threading.Event()
        waiter_clock = [0.0]
        waiter_checks = threading.local()
        errors = []

        def gated_scan():
            result = original()
            scan_ready.set()
            if not release_scan.wait(3):
                raise TimeoutError("test failed to release completed inventory scan")
            return result

        exporter._inventory_scan = gated_scan
        leader = threading.Thread(target=exporter.inventory)
        leader.start()
        self.assertTrue(scan_ready.wait(2))

        def delayed_check():
            if threading.current_thread().name == "expired-result-waiter":
                count = getattr(waiter_checks, "count", 0) + 1
                waiter_checks.count = count
                if count == 3:
                    waiter_at_return_check.set()
                    if not release_waiter.wait(3):
                        raise TimeoutError("test failed to resume expired waiter")
            native_deadline_check()

        def wait_for_result():
            try:
                with bounded(1.0, clock=lambda: waiter_clock[0]):
                    exporter.inventory()
            except TimeoutError:
                errors.append("expired")

        waiter = threading.Thread(target=wait_for_result, name="expired-result-waiter")
        with patch("world_bridge.check", side_effect=delayed_check):
            waiter.start()
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                with exporter._inventory_condition:
                    if len(exporter._inventory_batches) >= 2:
                        break
                time.sleep(0.001)
            else:
                release_scan.set()
                waiter.join(2)
                self.fail("expired waiter did not queue behind completed scan")
            release_scan.set()
            self.assertTrue(waiter_at_return_check.wait(2))
            leader.join(2)
            self.assertFalse(leader.is_alive())
            waiter_clock[0] = 2.0
            release_waiter.set()
            waiter.join(2)
        self.assertFalse(waiter.is_alive())
        self.assertEqual(errors, ["expired"])

    def test_call_before_queued_scan_starts_shares_fresh_scan_after_admission(self):
        root = Path(self.temporary.name) / "queued-not-started-native"
        root.mkdir()
        (root / "initial").write_bytes(b"initial")
        exporter = CompleteContextExporter({"all": root})
        self.addCleanup(exporter.close)
        exporter._inventory_admission_seconds = 0.005
        original = exporter._inventory_scan
        first_scanned, release = threading.Event(), threading.Event()
        calls, results, errors = [], {}, []

        def gated_scan():
            calls.append(len(calls))
            result = original()
            if len(calls) == 1:
                first_scanned.set()
                if not release.wait(3):
                    raise TimeoutError("test did not release first scan")
            return result

        def invoke(name):
            try:
                results[name] = exporter.inventory()
            except BaseException as error:
                errors.append(error)

        def await_waiters(count):
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                with exporter._inventory_condition:
                    if (
                        len(exporter._inventory_batches) == 2
                        and exporter._inventory_batches[-1]["waiters"] == count
                    ):
                        return
                time.sleep(0.001)
            self.fail("caller did not join the queued batch")

        exporter._inventory_scan = gated_scan
        workers = [
            threading.Thread(target=invoke, args=(name,))
            for name in ("first", "second", "third")
        ]
        try:
            workers[0].start()
            self.assertTrue(first_scanned.wait(2))
            workers[1].start()
            await_waiters(1)
            # Ensure the queued admission closes while the first scan remains
            # active. A future file must still be included in the fresh scan.
            time.sleep(0.02)
            (root / "future-added-before-scan").write_bytes(b"complete future file")
            workers[2].start()
            await_waiters(2)
        finally:
            release.set()
            for worker in workers:
                if worker.ident is not None:
                    worker.join(3)
        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertEqual(errors, [])
        self.assertEqual(len(calls), 2)
        for name in ("second", "third"):
            paths = {row["path"] for row in results[name][0]["entries"]}
            self.assertIn("all/future-added-before-scan", paths)
        self.assertIsNot(results["second"][0], results["third"][0])

    def test_late_call_during_queued_batch_starts_a_third_full_scan(self):
        root = Path(self.temporary.name) / "queued-late-native"
        root.mkdir()
        (root / "initial").write_bytes(b"initial")
        exporter = CompleteContextExporter({"all": root})
        self.addCleanup(exporter.close)
        exporter._inventory_admission_seconds = 0.005
        original = exporter._inventory_scan
        scan_finished = [threading.Event(), threading.Event()]
        release_scan = [threading.Event(), threading.Event()]
        calls = []
        results = {}
        errors = []
        calls_lock = threading.Lock()

        def gated_scan():
            with calls_lock:
                index = len(calls)
                calls.append(index)
            result = original()
            if index < 2:
                scan_finished[index].set()
                if not release_scan[index].wait(3):
                    raise TimeoutError("test failed to release queued scan")
            return result

        exporter._inventory_scan = gated_scan

        def invoke(name):
            try:
                results[name] = exporter.inventory()
            except BaseException as error:
                errors.append(error)

        first = threading.Thread(target=invoke, args=("first",))
        first.start()
        self.assertTrue(scan_finished[0].wait(2))
        second = threading.Thread(target=invoke, args=("second",))
        second.start()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            with exporter._inventory_condition:
                if len(exporter._inventory_batches) >= 2:
                    break
            time.sleep(0.001)
        else:
            release_scan[0].set()
            self.fail("second inventory batch was not queued")
        release_scan[0].set()
        self.assertTrue(scan_finished[1].wait(2))
        (root / "added-after-queued-scan.future").write_bytes(b"later full scan")
        third = threading.Thread(target=invoke, args=("third",))
        third.start()
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            with exporter._inventory_condition:
                if len(exporter._inventory_batches) >= 2:
                    break
            time.sleep(0.001)
        else:
            release_scan[1].set()
            self.fail("third inventory batch was not queued")
        release_scan[1].set()
        for worker in (first, second, third):
            worker.join(3)
        self.assertFalse(any(worker.is_alive() for worker in (first, second, third)))
        self.assertEqual(errors, [])
        self.assertEqual(len(calls), 3)
        second_paths = {row["path"] for row in results["second"][0]["entries"]}
        third_paths = {row["path"] for row in results["third"][0]["entries"]}
        self.assertNotIn("all/added-after-queued-scan.future", second_paths)
        self.assertIn("all/added-after-queued-scan.future", third_paths)

    def test_changed_future_file_uses_full_manifest_missing_list_without_asset_status_scan(
        self,
    ):
        root = Path(self.temporary.name) / "provisioned"
        root.mkdir()
        for index in range(300):
            (root / str(index)).write_bytes(f"native-file-{index}".encode())
        exporter = CompleteContextExporter({"all": root})
        self.addCleanup(exporter.close)
        manifest, sources = exporter.inventory()
        store = self.store()
        for entry in manifest["entries"]:
            store.import_file(sources[entry["sha256"]], entry["sha256"], entry["size"])
        (root / "299").write_bytes(b"complete-future-source-changed")
        calls = []
        original = self.transport.request

        def observed(endpoint, payload):
            calls.append((endpoint, payload))
            return original(endpoint, payload)

        self.transport.request = observed
        self.transport.block_bytes = 1024 * 1024
        digest = self.transport.catalog(exporter)
        self.assertEqual(
            store.manifest(digest), dict(complete=True, missing=[], entries=300)
        )
        status = [
            payload for endpoint, payload in calls if endpoint.endswith("/status")
        ]
        self.assertEqual(len(status), 1)
        self.assertEqual(len(status[0]["objects"]), 1)  # Manifest blob, not 300 assets.
        blocks = [payload for endpoint, payload in calls if endpoint.endswith("/block")]
        self.assertEqual(len(blocks), 2)  # Full manifest plus the changed future file.
        self.assertEqual(
            store.read(hashlib.sha256(b"complete-future-source-changed").hexdigest()),
            b"complete-future-source-changed",
        )

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.prior_root = os.environ.get("WAKFU_AI_CONTEXT_ROOT")
        os.environ["WAKFU_AI_CONTEXT_ROOT"] = self.temporary.name
        ai_server._CONTEXT_STORE = None
        self.http = BoundedHTTPServer(("127.0.0.1", 0), Handler)
        self.worker = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.worker.start()
        host, port = self.http.server_address
        self.url = f"http://{host}:{port}"
        self.transport = ContextTransport(self.url, timeout=3, block_bytes=31)

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.worker.join(2)
        if self.prior_root is None:
            os.environ.pop("WAKFU_AI_CONTEXT_ROOT", None)
        else:
            os.environ["WAKFU_AI_CONTEXT_ROOT"] = self.prior_root
        ai_server._CONTEXT_STORE = None
        self.temporary.cleanup()

    def post_raw(self, endpoint, raw):
        request = urllib.request.Request(
            self.url + endpoint, data=raw, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def store(self):
        return ContextStore(self.temporary.name)

    def test_inventory_enumerates_nested_hidden_files_and_file_links_in_order(self):
        root = Path(self.temporary.name) / "enumeration"
        (root / ".hidden" / "deep").mkdir(parents=True)
        (root / "empty").mkdir()
        original = root / ".hidden" / "deep" / "future.opaque"
        original.write_bytes(bytes(range(256)))
        (root / "z-last").write_bytes(b"z")
        (root / "a-link").symlink_to(original)
        exporter = CompleteContextExporter({"all": root})
        self.addCleanup(exporter.close)
        manifest, sources = exporter.inventory()
        self.assertEqual(
            [entry["path"] for entry in manifest["entries"]],
            ["all/.hidden/deep/future.opaque", "all/a-link", "all/z-last"],
        )
        for entry in manifest["entries"]:
            expected = (root / entry["path"].removeprefix("all/")).read_bytes()
            self.assertEqual(sources[entry["sha256"]].read_bytes(), expected)
            self.assertEqual(entry["sha256"], hashlib.sha256(expected).hexdigest())

    def test_inventory_relative_names_preserve_path_order_and_all_bytes(self):
        root = Path(self.temporary.name) / "relative-order-native"
        (root / "a").mkdir(parents=True)
        paths = [root / "a-y", root / "a" / "child.future", root / ".hidden"]
        for index, path in enumerate(paths):
            path.write_bytes(bytes([index]))
        exporter = CompleteContextExporter({"whole": root})
        self.addCleanup(exporter.close)
        manifest, sources = exporter.inventory()
        self.assertEqual(
            [entry["path"] for entry in manifest["entries"]],
            ["whole/" + path.relative_to(root).as_posix() for path in sorted(paths)],
        )
        for entry in manifest["entries"]:
            original = root / entry["path"].removeprefix("whole/")
            self.assertEqual(
                sources[entry["sha256"]].read_bytes(), original.read_bytes()
            )

    def test_inventory_rejects_linked_directory_cycles(self):
        root = Path(self.temporary.name) / "cycle"
        root.mkdir()
        (root / "again").symlink_to(root, target_is_directory=True)
        exporter = CompleteContextExporter({"all": root})
        self.addCleanup(exporter.close)
        with self.assertRaisesRegex(
            ValueError, "Unenumerated linked context directory"
        ):
            exporter.inventory()

    def test_exporter_includes_all_extensions_and_exact_raw_file_bytes(self):
        root = Path(self.temporary.name) / "native"
        (root / "rules").mkdir(parents=True)
        fixtures = {
            "engine.py": b"source\n",
            "rules/new-format.future": b"\x00\xff\x80unknown-extension\n",
            "rules/.hidden.capture": bytes(range(256)),
        }
        for relative, data in fixtures.items():
            (root / relative).write_bytes(data)
        extra = Path(self.temporary.name) / "captured.futurebinary"
        extra.write_bytes(b"unrecognized capture\x00\xfe")
        exporter = CompleteContextExporter(
            {"native": root}, files={"capture/unlisted.futurebinary": extra}
        )

        manifest, sources = exporter.inventory()

        by_path = {entry["path"]: entry for entry in manifest["entries"]}
        self.assertEqual(
            set(by_path),
            {
                "native/engine.py",
                "native/rules/new-format.future",
                "native/rules/.hidden.capture",
                "capture/unlisted.futurebinary",
            },
        )
        self.assertEqual(manifest["format"], "wakfu-complete-context-1")
        for name, payload in fixtures.items():
            entry = by_path["native/" + name]
            self.assertEqual(entry["size"], len(payload))
            self.assertEqual(entry["sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual(sources[entry["sha256"]].read_bytes(), payload)
        entry = by_path["capture/unlisted.futurebinary"]
        self.assertEqual(sources[entry["sha256"]].read_bytes(), extra.read_bytes())

    def test_inventory_physical_cache_keeps_aliases_replacements_and_future_files(self):
        root = Path(self.temporary.name) / "physical-native"
        root.mkdir()
        source = root / "first.future"
        source.write_bytes(b"complete-one")
        alias = root / "hardlink.future"
        os.link(source, alias)
        exporter = CompleteContextExporter({"all": root})
        self.addCleanup(exporter.close)
        if not source.stat().st_ino:
            self.skipTest("Filesystem does not expose physical inode identity")
        with patch.object(
            Path, "resolve", side_effect=AssertionError("Repeated ancestor resolution")
        ):
            first, snapshots = exporter.inventory()
            self.assertEqual(len(first["entries"]), 2)
            self.assertEqual(len(exporter.cache), 1)
            original = first["entries"][0]["sha256"]
            replacement = root / "replacement.tmp"
            replacement.write_bytes(b"complete-two")
            replacement.replace(source)
            (root / "new.future-format").write_bytes(b"all-future-data")
            second, current = exporter.inventory()
        by_name = {row["path"]: row["sha256"] for row in second["entries"]}
        self.assertEqual(len(by_name), 3)
        self.assertEqual(by_name["all/hardlink.future"], original)
        self.assertNotEqual(by_name["all/first.future"], original)
        self.assertEqual(
            current[by_name["all/first.future"]].read_bytes(), b"complete-two"
        )
        self.assertEqual(snapshots[original].read_bytes(), b"complete-one")
        self.assertEqual(
            current[by_name["all/new.future-format"]].read_bytes(), b"all-future-data"
        )

    def test_inventory_rejects_descriptor_inode_change_even_when_size_and_times_match(
        self,
    ):
        root = Path(self.temporary.name) / "inode-race-native"
        root.mkdir()
        source = root / "future.asset"
        source.write_bytes(b"all-native-data")
        status = source.stat()
        changed = SimpleNamespace(
            st_dev=status.st_dev,
            st_ino=status.st_ino + 1,
            st_size=status.st_size,
            st_mtime_ns=status.st_mtime_ns,
            st_ctime_ns=status.st_ctime_ns,
        )
        exporter = CompleteContextExporter({"all": root})
        self.addCleanup(exporter.close)
        with patch("world_bridge.os.fstat", return_value=changed):
            with self.assertRaisesRegex(ValueError, "changed while opening"):
                exporter.inventory()
        self.assertEqual(exporter.cache, {})

    def test_inventory_transfer_sources_remain_exact_after_original_changes(self):
        root = Path(self.temporary.name) / "changing-native"
        root.mkdir()
        source = root / "future.asset"
        source.write_bytes(b"original-complete")
        exporter = CompleteContextExporter({"all": root})
        self.addCleanup(exporter.close)
        manifest, sources = exporter.inventory()
        original = manifest["entries"][0]
        source.write_bytes(b"replacement-complete")
        self.assertEqual(sources[original["sha256"]].read_bytes(), b"original-complete")
        changed, changed_sources = exporter.inventory()
        current = changed["entries"][0]
        self.assertNotEqual(current["sha256"], original["sha256"])
        self.assertEqual(
            changed_sources[current["sha256"]].read_bytes(), source.read_bytes()
        )

    def test_http_full_sender_uploads_catalog_and_instance_graph(self):
        root = Path(self.temporary.name) / "native-tree"
        (root / "subdir").mkdir(parents=True)
        files = [root / "future.capture-v9", root / "subdir" / "opaque.bin"]
        files[0].write_bytes(b"capture\x00\xff" * 100)
        files[1].write_bytes(bytes(range(251)) * 100)
        exporter = CompleteContextExporter({"engine": root})

        manifest_hash = self.transport.catalog(exporter)

        self.assertEqual(
            self.transport.request("/v3/context/manifest", {"sha256": manifest_hash}),
            {"complete": True, "missing": [], "entries": 2},
        )
        self.assertEqual(
            self.transport.request("/v3/context/seal", {"sha256": manifest_hash}),
            {"complete": True, "missing": [], "entries": 2},
        )
        manifest = self.store().json(manifest_hash)
        self.assertEqual(
            {entry["path"] for entry in manifest["entries"]},
            {"engine/future.capture-v9", "engine/subdir/opaque.bin"},
        )
        for entry in manifest["entries"]:
            payload = (root / entry["path"].removeprefix("engine/")).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), entry["sha256"])
            self.assertEqual(self.store().read(entry["sha256"]), payload)

        graph = exporter.instance(
            runtime={"future-runtime-state": [1, 2, b"raw"]},
            authorities={"oracle": "native"},
            policy={"version": 4},
            flags={"native-preview": True},
            source={"unknown-extension": "retained"},
        )
        graph_hash = self.transport.instance(graph)
        compressed_graph = gzip.compress(_json_bytes(graph), compresslevel=1, mtime=0)
        status = self.transport.request(
            "/v3/context/status",
            {"objects": [{"sha256": graph_hash, "size": len(compressed_graph)}]},
        )
        self.assertEqual(status["present"], [graph_hash])
        self.assertEqual(self.store().read(graph_hash), compressed_graph)
        self.assertTrue(self.store().has(graph_hash, len(compressed_graph)))
        self.assertNotEqual(graph_hash, hashlib.sha256(_json_bytes(graph)).hexdigest())
        self.assertEqual(self.store().json(graph_hash), graph)

    def test_large_compressed_snapshot_restores_full_graph_fields_aliases_and_cycles(
        self,
    ):
        import random

        payload = random.Random(771).randbytes(256 * 1024)
        shared = {"future-key": b"shared-extension", 17: "integer-key"}

        class FutureRuntime:
            pass

        runtime = FutureRuntime()
        runtime.payload = payload
        runtime.left = shared
        runtime.right = shared
        runtime.self_reference = runtime
        runtime.future_timestamp = "retained-future-field"
        graph = CompleteContextExporter.instance(
            runtime=runtime,
            authorities={"complete": {"sourceBytes": payload}},
            policy={"unknownPolicyField": {"raw": b"policy"}},
            flags={"futureFlag": True},
            source={"native": "snapshot"},
        )

        digest = self.transport.instance(graph)
        stored = self.store().read(digest)
        self.assertGreater(len(stored), self.transport.block_bytes)
        self.assertTrue(stored.startswith(b"\x1f\x8b"))
        self.assertEqual(digest, hashlib.sha256(stored).hexdigest())
        self.assertTrue(self.store().has(digest, len(stored)))
        restored = NativeGraph(self.store().json(digest))
        root = restored.root
        runtime_ref = restored.field({"ref": restored.data["root"]["ref"]}, "runtime")
        runtime_node = restored.resolve(runtime_ref)
        self.assertEqual(runtime_node["type"], "object")
        self.assertEqual(
            restored.resolve(runtime_node["fields"]["left"]),
            restored.resolve(runtime_node["fields"]["right"]),
        )
        self.assertEqual(runtime_node["fields"]["self_reference"], runtime_ref)
        payload_node = restored.resolve(runtime_node["fields"]["payload"])
        self.assertEqual(payload_node["type"], "bytes")
        self.assertEqual(base64.b64decode(payload_node["value"]), payload)
        self.assertEqual(root["type"], "dict")

    def test_identical_instance_compression_hash_reuses_verified_local_object(self):
        class CountingTransport(ContextTransport):
            def __init__(inner, *args, **kwargs):
                super().__init__(*args, **kwargs)
                inner.uploads = 0
                inner.requests = []

            def request(inner, endpoint, payload):
                inner.requests.append((endpoint, payload))
                return super(CountingTransport, inner).request(endpoint, payload)

            def _upload(inner, *args, **kwargs):
                inner.uploads += 1
                return super(CountingTransport, inner)._upload(*args, **kwargs)

        sender = CountingTransport(self.url, timeout=3, block_bytes=31)
        graph = CompleteContextExporter.instance(
            runtime={"stable": b"same"},
            authorities={},
            policy={},
            flags={},
            source={"revision": 5},
        )
        first = sender.instance(graph)
        uploads_after_first = sender.uploads
        first_requests = len(sender.requests)
        stored_path = self.store()._path(first)
        first_modified = stored_path.stat().st_mtime_ns
        second = sender.instance(graph)
        self.assertEqual(first, second)
        self.assertGreater(uploads_after_first, 0)
        self.assertEqual(sender.uploads, uploads_after_first + 1)
        # One idempotent first-block request replaces the status request and
        # the receiver reuses the complete verified object without rewriting.
        self.assertEqual(len(sender.requests), first_requests + 1)
        self.assertEqual(sender.requests[-1][0], "/v3/context/block")
        self.assertEqual(sender.requests[-1][1]["offset"], 0)
        self.assertFalse(
            any(endpoint == "/v3/context/status" for endpoint, _ in sender.requests)
        )
        self.assertEqual(stored_path.stat().st_mtime_ns, first_modified)
        self.assertTrue(self.store().has(first))

    def test_direct_instance_upload_repairs_corrupted_canonical_content(self):
        graph = CompleteContextExporter.instance(
            runtime={"future": b"complete" * 100},
            authorities={},
            policy={},
            flags={},
            source={"revision": 9},
        )
        digest = self.transport.instance(graph)
        original = self.store().read(digest)
        self.store()._path(digest).write_bytes(b"x" * len(original))
        self.assertFalse(self.store().has(digest))
        self.assertEqual(self.transport.instance(graph), digest)
        self.assertEqual(self.store().read(digest), original)
        self.assertEqual(self.store().json(digest), graph)

    def test_direct_instance_upload_retries_lost_final_ack_without_status_request(self):
        class LoseFinalAck(ContextTransport):
            lost = False
            endpoints = None

            def request(inner, endpoint, payload):
                inner.endpoints.append(endpoint)
                response = super(LoseFinalAck, inner).request(endpoint, payload)
                if (
                    endpoint == "/v3/context/block"
                    and response["complete"]
                    and not inner.lost
                ):
                    inner.lost = True
                    raise urllib.error.URLError("simulated final response loss")
                return response

        sender = LoseFinalAck(self.url, timeout=3, block_bytes=23)
        sender.endpoints = []
        graph = CompleteContextExporter.instance(
            runtime={"future": b"unaltered" * 80},
            authorities={},
            policy={},
            flags={},
            source={"revision": 11},
        )
        digest = sender.instance(graph)
        self.assertTrue(sender.lost)
        self.assertTrue(
            all(endpoint == "/v3/context/block" for endpoint in sender.endpoints)
        )
        self.assertEqual(self.store().json(digest), graph)
        self.assertFalse(self.store().partial)

    def test_instance_deadline_is_checked_before_and_after_compression(self):
        from unittest.mock import patch
        from native_deadline import bounded

        now = [0.0]
        with bounded(1.0, clock=lambda: now[0]):
            now[0] = 2.0
            with patch("world_bridge.gzip.compress") as compress:
                with self.assertRaisesRegex(TimeoutError, "deadline"):
                    self.transport.instance_bytes(b"complete")
                compress.assert_not_called()

        now[0] = 0.0
        original = gzip.compress

        def slow_compress(*args, **kwargs):
            data = original(*args, **kwargs)
            now[0] = 2.0
            return data

        with bounded(1.0, clock=lambda: now[0]):
            with patch("world_bridge.gzip.compress", side_effect=slow_compress):
                with patch.object(self.transport, "_upload") as upload:
                    with self.assertRaisesRegex(TimeoutError, "deadline"):
                        self.transport.instance_bytes(b"complete")
                    upload.assert_not_called()

    def test_sender_retries_after_server_commits_a_block_but_ack_is_lost(self):
        class LoseFirstAck(ContextTransport):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.lost = False

            def request(inner, endpoint, payload):
                response = super(LoseFirstAck, inner).request(endpoint, payload)
                if (
                    endpoint == "/v3/context/block"
                    and payload["offset"] == 0
                    and not inner.lost
                ):
                    inner.lost = True
                    raise urllib.error.URLError("simulated response loss")
                return response

        sender = LoseFirstAck(self.url, timeout=3, block_bytes=23)
        payload = b"payload requiring many blocks" * 40
        digest = sender.bytes(payload)
        self.assertTrue(sender.lost)
        self.assertEqual(self.store().read(digest), payload)

    def test_empty_catalog_seals_as_complete_without_asset_uploads(self):
        root = Path(self.temporary.name) / "empty"
        root.mkdir()
        manifest_hash = self.transport.catalog(
            CompleteContextExporter({"empty-root": root})
        )
        result = self.transport.request(
            "/v3/context/manifest", {"sha256": manifest_hash}
        )
        self.assertEqual(result, {"complete": True, "missing": [], "entries": 0})
        self.assertEqual(
            self.store().json(manifest_hash),
            {"format": "wakfu-complete-context-1", "entries": []},
        )

    def test_http_status_and_manifest_verify_every_full_object_hash(self):
        payload = b"asset verified over HTTP"
        digest = self.transport.bytes(payload)
        self.assertEqual(
            self.transport.request(
                "/v3/context/status",
                {"objects": [{"sha256": digest, "size": len(payload)}]},
            ),
            {"present": [digest]},
        )
        manifest_hash = self.transport.bytes(
            json.dumps(
                {
                    "format": "wakfu-complete-context-1",
                    "entries": [
                        {"path": "asset.bin", "sha256": digest, "size": len(payload)}
                    ],
                },
                separators=(",", ":"),
            ).encode()
        )
        self.assertEqual(
            self.transport.request("/v3/context/manifest", {"sha256": manifest_hash}),
            {"complete": True, "missing": [], "entries": 1},
        )

        (Path(self.temporary.name) / digest).write_bytes(b"x" * len(payload))
        self.assertEqual(
            self.transport.request(
                "/v3/context/status",
                {"objects": [{"sha256": digest, "size": len(payload)}]},
            ),
            {"present": []},
        )
        self.assertEqual(
            self.transport.request("/v3/context/manifest", {"sha256": manifest_hash}),
            {"complete": False, "missing": [digest], "entries": 1},
        )

    def test_malformed_http_block_status_manifest_seal_and_json_requests_fail_closed(
        self,
    ):
        malformed = [
            (
                "/v3/context/block",
                {"sha256": "0" * 64, "size": 1, "offset": 0, "data": "%%%"},
            ),
            (
                "/v3/context/block",
                {
                    "sha256": "0" * 64,
                    "size": 1,
                    "offset": 0,
                    "data": "eA==",
                    "extra": 1,
                },
            ),
            ("/v3/context/status", {"objects": [{"sha256": "bad", "size": 1}]}),
            (
                "/v3/context/status",
                {
                    "objects": [
                        {"sha256": "0" * 64, "size": 1},
                        {"sha256": "0" * 64, "size": 2},
                    ]
                },
            ),
            ("/v3/context/manifest", {"sha256": "bad"}),
            ("/v3/context/manifest", {"sha256": "f" * 64, "extra": True}),
            ("/v3/context/seal", {"sha256": "bad"}),
            ("/v3/context/seal", {"sha256": "f" * 64, "extra": True}),
        ]
        for endpoint, payload in malformed:
            with self.subTest(endpoint=endpoint, payload=payload):
                status, response = self.post_raw(endpoint, json.dumps(payload).encode())
                self.assertEqual(status, 400, response)
        for raw in (
            b'{"sha256":"' + b"0" * 64 + b'","size":0,"offset":0,"data":"","data":""}',
            b"{malformed",
        ):
            status, _ = self.post_raw("/v3/context/block", raw)
            self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
