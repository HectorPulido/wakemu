"""Actual cold-source wrappers coalesce only equal immutable identities."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
from threading import Barrier, Event
import time
import unittest
from unittest.mock import patch


class NativeCatalogSingleflightTests(unittest.TestCase):
    def test_real_wrappers_keyed_cohorts_independent_io_failures_and_revision(self):
        from wakfu_server import native_catalog as catalog
        from wakfu_server import combat_sn_path as sn
        from wakfu_server.native_source_singleflight import NativeSourceFlights

        after = []
        for kind in ("catalog", "sn"):
            with self.subTest(wrapper=kind), ExitStack() as stack:
                flights = NativeSourceFlights()
                gates, failures, counts = {}, set(), Counter()

                @lru_cache(maxsize=4)
                def loader(*args):
                    key = args[-1]
                    counts[key] += 1
                    if key in gates:
                        entered, release = gates[key]
                        entered.set()
                        if not release.wait(5):
                            raise TimeoutError("bounded source IO hold")
                    if key in failures:
                        raise ValueError("original source decoding failure")
                    return object()

                stack.enter_context(
                    patch.object(catalog, "release", return_value="a" * 64)
                )
                if kind == "catalog":
                    stack.enter_context(
                        patch.object(catalog, "_live", return_value=True)
                    )
                    stack.enter_context(
                        patch.object(catalog, "_key", side_effect=lambda path: path)
                    )
                    stack.enter_context(patch.object(catalog, "_decoded", loader))
                    stack.enter_context(
                        patch.object(catalog, "_decode_flights", flights)
                    )
                    invoke = catalog.load
                    group, cold, warm, distinct, failing = (
                        "group",
                        "cold",
                        "warm",
                        "distinct",
                        "failure",
                    )
                else:
                    stack.enter_context(patch.object(sn, "_published_columns", loader))
                    stack.enter_context(
                        patch.object(sn, "_published_column_flights", flights)
                    )
                    invoke = sn.NativeSnColumns.from_published
                    group, cold, warm, distinct, failing = 10, 11, 12, 13, 14

                def cohort(key, *, fail):
                    gates[key] = (Event(), Event())
                    if fail:
                        failures.add(key)
                    barrier = Barrier(7)
                    shared_before = flights.statistics()["shared_calls"]

                    def query():
                        barrier.wait(timeout=5)
                        try:
                            return invoke(key)
                        except ValueError as error:
                            return error

                    with ThreadPoolExecutor(max_workers=6) as pool:
                        pending = [pool.submit(query) for _ in range(6)]
                        barrier.wait(timeout=5)
                        self.assertTrue(gates[key][0].wait(2))
                        deadline = time.monotonic() + 3
                        while flights.statistics()["shared_calls"] - shared_before < 5:
                            self.assertLess(
                                time.monotonic(),
                                deadline,
                                "all six callers must join the held source",
                            )
                            Event().wait(0.001)
                        gates[key][1].set()
                        values = [future.result(timeout=3) for future in pending]
                    self.assertEqual(counts[key], 1)
                    self.assertTrue(all(value is values[0] for value in values))
                    self.assertIsInstance(
                        values[0], ValueError
                    ) if fail else self.assertNotIsInstance(values[0], Exception)
                    self.assertEqual(flights.statistics()["active"], 0)
                    gates.pop(key)
                    return values[0]

                same = cohort(group, fail=False)
                self.assertIs(invoke(group), same)
                self.assertEqual(counts[group], 1)
                preserved_warm = invoke(warm)
                gates[cold] = (Event(), Event())
                warm_done, different_done = Event(), Event()

                def query_while_held(key, completed):
                    started = time.perf_counter_ns()
                    try:
                        return invoke(key), time.perf_counter_ns() - started
                    finally:
                        completed.set()

                with ThreadPoolExecutor(max_workers=3) as pool:
                    blocked = pool.submit(invoke, cold)
                    self.assertTrue(gates[cold][0].wait(2))
                    fast = pool.submit(query_while_held, warm, warm_done)
                    independent = pool.submit(
                        query_while_held, distinct, different_done
                    )
                    try:
                        self.assertTrue(
                            warm_done.wait(2),
                            "unrelated warm source must finish before cold IO is released",
                        )
                        self.assertTrue(
                            different_done.wait(2),
                            "unrelated cold key must not wait for another key's IO",
                        )
                    finally:
                        gates[cold][1].set()
                    blocked.result(timeout=3)
                    value, warm_ns = fast.result(timeout=3)
                    _, distinct_ns = independent.result(timeout=3)
                self.assertIs(value, preserved_warm)
                self.assertEqual(counts[warm], 1)
                original_error = cohort(failing, fail=True)
                failures.remove(failing)
                retry = invoke(failing)
                self.assertNotIsInstance(retry, Exception)
                self.assertEqual(counts[failing], 2)
                self.assertIsNot(retry, original_error)
                self.assertEqual(flights.statistics()["active"], 0)
                after.append(
                    dict(
                        wrapper=kind,
                        warm_completed_before_unrelated_cold_io_release=True,
                        different_key_completed_before_cold_io_release=True,
                        warm_query_elapsed_ns=warm_ns,
                        different_key_elapsed_ns=distinct_ns,
                        statistics=flights.statistics(),
                    )
                )

        # None is a valid cached result; recursive same-key work must fail, not
        # deadlock. A failure never poisons the coordinator's future retries.
        flights = NativeSourceFlights()
        self.assertIsNone(flights.run("none", lambda: None))
        with self.assertRaisesRegex(RuntimeError, "Recursive"):
            flights.run("recursive", lambda: flights.run("recursive", lambda: 1))
        self.assertEqual(flights.statistics()["active"], 0)
        self.assertEqual(flights.run("recursive", lambda: 9), 9)
        with self.assertRaises(TypeError):
            flights.run("noncallable", None)

        # Use the actual Sn LRU and original release-before/after guards here;
        # the concurrent fixture above replaces only its bounded IO producer.
        sn._published_columns.cache_clear()
        self.addCleanup(sn._published_columns.cache_clear)
        columns = sn.NativeSnColumns(
            dict(
                schema="native-Sn-Vy-columns-v1",
                map_id=1,
                source_sha256="b" * 64,
                chunks=[],
            ),
            map_id=1,
            source_sha256="b" * 64,
        )
        with patch.object(
            catalog, "release", side_effect=("a" * 64, "a" * 64, "c" * 64)
        ), patch.object(sn.NativeSnColumns, "_load_published", return_value=columns):
            with self.assertRaisesRegex(ValueError, "changed during"):
                sn.NativeSnColumns.from_published(1)
        self.assertEqual(sn._published_columns.cache_info().currsize, 0)
        with patch.object(catalog, "release", return_value="a" * 64), patch.object(
            sn.NativeSnColumns, "_load_published", return_value=columns
        ) as producer:
            first = sn.NativeSnColumns.from_published(1)
            self.assertIs(sn.NativeSnColumns.from_published(1), first)
            self.assertEqual(producer.call_count, 1)
            self.assertIs(deepcopy(first), first)
            self.assertEqual(set(vars(first)), {"chunks", "map_id", "source_sha256"})
        for invalid in (True, 0, -1, "1"):
            with self.assertRaises(ValueError):
                sn.NativeSnColumns.from_published(invalid)
        receipt = dict(
            schema="wakemu-cold-entry-keyed-flight-after-v1",
            scope="Actual wrappers with bounded synthetic IO barriers; no CPU/GIL or real DB latency claim",
            observations=after,
            source_pins={
                str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (Path(catalog.__file__), Path(sn.__file__))
            },
        )
        output = os.environ.get("WAKFU_COLD_ENTRY_RECEIPT")
        if output:
            path = Path(output)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(receipt, indent=2) + "\n")
        print("keyed_source_flight_measurement " + json.dumps(after), flush=True)
