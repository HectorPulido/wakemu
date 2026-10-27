"""Selected retained metadata batching; real reader/replay, closed transports.

The Qf corpus is declared input to this component, not a Ready/producer claim.
No listener is activated; all gameplay state must remain exactly unchanged.
"""
from collections import OrderedDict
from collections.abc import Mapping
from concurrent.futures import CancelledError
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from test_external_catalog_backends import CacheRedis
from wakfu_server import combat_event_replay as replay_module
from wakfu_server.combat_event_replay import (
    NativeEventReplay,
    NativeExternalEvent,
    NativeCloneAuthority,
)
from wakfu_server.combat_retained_effects import (
    NativeRetainedEffectView,
    RetainedEffect,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_published_catalogs import resolve_static_catalog_descriptor
from wakfu_server.native_catalog_index import BoundedByteCache
from wakfu_server.native_compiled_catalog import (
    CompiledCatalogBackend,
    canonical_bytes,
    descriptor_for,
)
from wakfu_server.fight_checkpoint_store import snapshot


class SequentialMetadata(Mapping):
    """The existing unsealed path reads each row through the actual reader."""

    def __init__(self, reader):
        self.reader = reader

    def __getitem__(self, key):
        return self.reader[key]

    def __iter__(self):
        raise AssertionError("No whole-catalog iteration permitted")

    def __len__(self):
        return len(self.reader)


class RetainedReplayMetadataBatchTests(unittest.TestCase):
    def setUp(self):
        for name, value in (
            ("_SUBSCRIPTION_CACHE", OrderedDict()),
            ("_SUBSCRIPTION_BYTES", 0),
        ):
            isolated = patch.object(replay_module, name, value)
            isolated.start()
            self.addCleanup(isolated.stop)

    def fixture(
        self,
        *,
        changed=False,
        size=130,
        batch_size=128,
        byte_limit=16384,
        subscribed=None,
        corrupt=None,
        fault=None,
        values_override=None
    ):
        name = "raw/retained/effects"
        values = {
            str(i): dict(subscription=i == subscribed, marker=200 if changed else 100)
            for i in range(1, size + 1)
        }
        if values_override is not None:
            values.update(values_override)
        ordered = list(values)
        manifest = dict(
            policy="wakemu.compiled-combat-catalog.v1",
            source_revision="a" * 64,
            source_inventory_sha256="b" * 64,
            compiler_contract_sha256="c" * 64,
            config_sha256=hashlib.sha256(
                canonical_bytes(
                    dict(
                        values=values,
                        corrupt=corrupt,
                        fault=None if fault is None else type(fault).__name__,
                    )
                )
            ).hexdigest(),
            collections={
                name: dict(
                    collection=name,
                    kind="dict",
                    representation="native_json",
                    count=len(values),
                    ordered_keys_sha256=hashlib.sha256(
                        canonical_bytes(ordered)
                    ).hexdigest(),
                )
            },
        )
        raw_manifest = canonical_bytes(manifest)
        generation = hashlib.sha256(raw_manifest).hexdigest()
        rows = {}
        for ordinal, (key, value) in enumerate(values.items()):
            raw = canonical_bytes(value)
            rows[json.dumps(key)] = dict(
                record_key=json.dumps(key),
                ordinal=ordinal,
                raw=raw,
                sha256=hashlib.sha256(raw).hexdigest(),
                source_bytes=len(raw),
            )
        state = dict(metadata=[], payload=[], batches=[], fail=fault)

        def query(sql, params):
            if sql.startswith("SELECT r.policy,r.source_revision"):
                self.assertEqual(params[0], generation)
                row = {
                    k: manifest[k]
                    for k in (
                        "policy",
                        "source_revision",
                        "source_inventory_sha256",
                        "compiler_contract_sha256",
                        "config_sha256",
                    )
                }
                row.update(manifest=deepcopy(manifest), manifest_raw=raw_manifest)
                return SimpleNamespace(fetchone=lambda: row)
            if sql.startswith("SELECT kind,record_count"):
                self.assertEqual(tuple(params), (generation, name))
                return SimpleNamespace(
                    fetchone=lambda: dict(
                        kind="dict",
                        record_count=len(values),
                        ordered_keys_sha256=manifest["collections"][name][
                            "ordered_keys_sha256"
                        ],
                    )
                )
            self.assertEqual(tuple(params[:2]), (generation, name))
            keys = params[2]
            if sql.startswith("SELECT record_key,ordinal,sha256"):
                state["metadata"].append(tuple(json.loads(k) for k in keys))
                if state["fail"] is not None:
                    raise state["fail"]
                return SimpleNamespace(
                    fetchall=lambda: [deepcopy(rows[k]) for k in keys if k in rows]
                )
            if sql.startswith("SELECT record_key,ordinal,raw"):
                state["payload"].append(tuple(json.loads(k) for k in keys))
                result = [deepcopy(rows[k]) for k in keys if k in rows]
                for row in result:
                    if json.loads(row["record_key"]) == corrupt:
                        row["raw"] = b"corrupt original source"
                return SimpleNamespace(fetchall=lambda: result)
            raise AssertionError(sql)

        database, connection = MagicMock(), MagicMock()
        database.connection.return_value.__enter__.return_value = connection
        connection.execute.side_effect = query
        cache = BoundedByteCache(max_bytes=8 * 1024 * 1024, max_entries=2048)
        backend = CompiledCatalogBackend(
            lambda: database,
            lambda: redis,
            cache=cache,
            batch_size=batch_size,
            max_batch_bytes=byte_limit,
        )
        redis = CacheRedis()
        descriptor = descriptor_for(dict(manifest, generation=generation), name)
        reader = backend.collection(descriptor)
        original_many = reader.get_many

        def observed_many(keys):
            result = original_many(keys)
            state["batches"].append(
                (tuple(keys), sum(len(rows[json.dumps(k)]["raw"]) for k in result))
            )
            return result

        reader.get_many = observed_many
        with patch(
            "wakfu_server.native_compiled_catalog.published_collection",
            return_value=reader,
        ):
            mapping = resolve_static_catalog_descriptor(descriptor)
        return SimpleNamespace(
            mapping=mapping,
            reader=reader,
            state=state,
            values=values,
            generation=generation,
            cache=cache,
        )

    def replay(self, metadata, *, size=130, subscribed=None):
        actors = [
            Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True),
            Actor(8, 1, (1, 0, 0), 20, 6, 3, 5, 1),
        ]
        fight = Fight(
            77, actors, {a.position for a in actors}, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}}
        )
        entries = [
            RetainedEffect(i, 7, 400, i, manager_id=7) for i in range(1, size + 1)
        ]
        entries += [
            RetainedEffect(900, 8, 400, 900, manager_id=8),
            RetainedEffect(901, 7, 400, 777, manager_id=7),
        ]
        view = NativeRetainedEffectView(
            fight, entries, population_verified_complete=True
        )
        retention = SimpleNamespace(
            fight=fight, metadata={"effects": metadata}, view=lambda: view
        )
        replay = NativeEventReplay(SimpleNamespace(), retention)

        def never(*args):
            raise AssertionError("No listener/condition activation expected")

        authority = NativeCloneAuthority(never, never)
        before = snapshot(fight)
        eligible = frozenset(e.uid for e in entries if e.uid != 17)
        try:
            outcome = replay(
                NativeExternalEvent(7, (1003,), 6),
                authority=authority,
                eligible_uids=eligible,
            )
            self.assertEqual(outcome, ())
        finally:
            self.assertEqual(
                snapshot(fight),
                before,
                "Metadata lookup/error must not mutate gameplay",
            )
        return fight

    def test_selected_batches_match_sequential_missing_errors_generation_and_bounds(
        self,
    ):
        sequential, batched = self.fixture(), self.fixture()
        old_fight = self.replay(SequentialMetadata(sequential.reader))
        new_fight = self.replay(batched.mapping)
        self.assertEqual(snapshot(old_fight), snapshot(new_fight))
        self.assertEqual(len(sequential.state["metadata"]), 130)
        self.assertEqual(len(batched.state["metadata"]), 2)
        self.assertEqual(len(batched.state["payload"]), 2)
        selected = [key for keys in batched.state["metadata"] for key in keys]
        self.assertEqual(selected, [str(i) for i in range(1, 131) if i != 17] + ["777"])
        self.assertNotIn("17", selected)
        self.assertNotIn("900", selected)
        self.assertTrue(all(len(keys) <= 128 for keys, _ in batched.state["batches"]))
        # No operation-local dictionary survives return: a new sealed generation
        # must expose its own immutable values, not another preview's projection.
        changed = self.fixture(changed=True)
        self.assertNotEqual(changed.generation, batched.generation)
        self.replay(changed.mapping)
        self.assertEqual(changed.mapping["1"]["marker"], 200)
        self.assertEqual(batched.mapping["1"]["marker"], 100)
        private = changed.mapping["1"]
        private["subscription"] = True
        self.replay(changed.mapping)
        self.assertFalse(changed.mapping["1"]["subscription"])
        limited = self.fixture(size=12, batch_size=5, byte_limit=90)
        self.replay(limited.mapping, size=12)
        self.assertGreater(len(limited.state["batches"]), 1)
        self.assertTrue(
            all(
                len(keys) <= 5 and raw_bytes <= 90
                for keys, raw_bytes in limited.state["batches"]
            )
        )
        self.assertLessEqual(limited.cache.cache_info()["bytes"], 8 * 1024 * 1024)
        # A later source corruption cannot mask the first eligible runner error.
        early = self.fixture(size=2, subscribed=1, corrupt="2")
        with self.assertRaisesRegex(ValueError, "Subscribed retained family.*uid=1"):
            self.replay(early.mapping, size=2)
        corrupt = self.fixture(size=2, corrupt="1")
        with self.assertRaisesRegex(ValueError, "checksum/size mismatch"):
            self.replay(corrupt.mapping, size=2)
        for error in (
            TimeoutError("deadline"),
            CancelledError("cancelled"),
            InterruptedError("interrupted"),
        ):
            cancelled = self.fixture(size=2, fault=error)
            with self.assertRaises(type(error)):
                self.replay(cancelled.mapping, size=2)
            self.assertEqual(
                len(cancelled.state["metadata"]),
                1,
                "Cancellation must not fall back/retry",
            )

    def test_subscription_projection_repeated_phases_generation_errors_and_retention_bounds(
        self,
    ):
        # Independent immutable publication identities; no decoded rows or Qf
        # objects survive replay through the new source-discriminator cache.
        with patch.object(
            replay_module, "_SUBSCRIPTION_CACHE", OrderedDict()
        ), patch.object(replay_module, "_SUBSCRIPTION_BYTES", 0):
            reference = self.fixture(size=130)
            sealed = self.fixture(size=130)
            old = self.replay(SequentialMetadata(reference.reader))
            current = self.replay(sealed.mapping)
            self.assertEqual(snapshot(old), snapshot(current))
            self.assertEqual(len(sealed.state["metadata"]), 2)
            self.assertEqual(len(sealed.state["payload"]), 2)
            before = {
                name: len(sealed.state[name])
                for name in ("metadata", "payload", "batches")
            }
            for _ in range(6):
                # Model unrelated source activity evicting all raw/authority
                # bytes; the verified static discriminator remains bounded.
                sealed.cache.clear()
                self.assertEqual(
                    snapshot(self.replay(sealed.mapping)), snapshot(current)
                )
            self.assertEqual(before, {name: len(sealed.state[name]) for name in before})
            self.assertNotIn(
                "17", [key[-1] for key in replay_module._SUBSCRIPTION_CACHE]
            )
            self.assertNotIn(
                "900", [key[-1] for key in replay_module._SUBSCRIPTION_CACHE]
            )
            self.assertTrue(
                any(
                    key[-1] == "777" and row[0] is None
                    for key, row in replay_module._SUBSCRIPTION_CACHE.items()
                )
            )
            self.assertTrue(
                all(
                    value[0] is None or type(value[0]) is bool
                    for value in replay_module._SUBSCRIPTION_CACHE.values()
                )
            )
            # Fresh raw JSON mutation must not change immutable source data.
            private = sealed.mapping["1"]
            private["subscription"] = True
            self.replay(sealed.mapping)
            changed = self.fixture(size=130, subscribed=1)
            self.assertNotEqual(changed.generation, sealed.generation)
            with self.assertRaisesRegex(
                ValueError, "Subscribed retained family.*uid=1"
            ):
                self.replay(changed.mapping)
            with self.assertRaisesRegex(
                ValueError, "Subscribed retained family.*uid=1"
            ):
                self.replay(changed.mapping)  # Cached True still rejects.
            # Later corrupt source cannot reorder an earlier eligible error.
            early = self.fixture(size=2, subscribed=1, corrupt="2")
            with self.assertRaisesRegex(
                ValueError, "Subscribed retained family.*uid=1"
            ):
                self.replay(early.mapping, size=2)
            corrupt = self.fixture(size=2, corrupt="1")
            with self.assertRaisesRegex(ValueError, "checksum/size mismatch"):
                self.replay(corrupt.mapping, size=2)
            for error in (
                TimeoutError("deadline"),
                CancelledError("cancel"),
                InterruptedError("interrupt"),
            ):
                failed = self.fixture(size=2, fault=error)
                prior = dict(replay_module._SUBSCRIPTION_CACHE)
                with self.assertRaises(type(error)):
                    self.replay(failed.mapping, size=2)
                self.assertEqual(prior, dict(replay_module._SUBSCRIPTION_CACHE))
                self.assertEqual(len(failed.state["metadata"]), 1)
            # Plain mutable mappings preserve fresh values and exact malformed
            # errors, rather than sharing an immutable publication projection.
            plain = {"1": {"subscription": False}, "2": {"subscription": False}}
            self.replay(plain, size=2)
            plain["1"]["subscription"] = True
            with self.assertRaisesRegex(
                ValueError, "Subscribed retained family.*uid=1"
            ):
                self.replay(plain, size=2)
            for malformed in ({}, {"subscription": []}):
                key = ("x", "x", "source", "native_json", "1")
                replay_module._subscription_put(key, malformed)
                self.assertIs(
                    replay_module._subscription_get(key),
                    replay_module._SUBSCRIPTION_MISS,
                )
            plain["1"] = {}
            with self.assertRaises(KeyError):
                self.replay(plain, size=2)
            malformed = self.fixture(size=2, values_override={"1": {}})
            for metadata in (SequentialMetadata(malformed.reader), malformed.mapping):
                with self.assertRaises(KeyError):
                    self.replay(metadata, size=2)
            early_malformed = self.fixture(
                size=2, subscribed=1, values_override={"2": {}}
            )
            with self.assertRaisesRegex(
                ValueError, "Subscribed retained family.*uid=1"
            ):
                self.replay(early_malformed.mapping, size=2)
            # Both limits independently evict; never retain source record rows.
            for key_limit, byte_limit in ((3, 1024 * 1024), (2048, 1200)):
                with patch.object(
                    replay_module, "_SUBSCRIPTION_MAX_ENTRIES", key_limit
                ), patch.object(replay_module, "_SUBSCRIPTION_MAX_BYTES", byte_limit):
                    for index in range(20):
                        key = (
                            "f" * 64,
                            "f" * 64,
                            "retained/effects",
                            "native_json",
                            str(index),
                        )
                        replay_module._subscription_put(key, {"subscription": False})
                    self.assertLessEqual(
                        len(replay_module._SUBSCRIPTION_CACHE), key_limit
                    )
                    self.assertLessEqual(replay_module._SUBSCRIPTION_BYTES, byte_limit)
            self.assertTrue(
                all(len(keys) <= 128 for keys, _ in sealed.state["batches"])
            )

    def test_subscription_interleaving_fill_and_eviction_preserve_true_runner_guard(
        self,
    ):
        # A concurrent immutable fill between outer MISS and lookahead must not
        # remove the current key from the authoritative batch/window.
        current = self.fixture(size=2, subscribed=1)
        original_get = replay_module._subscription_get
        filled = []

        def concurrent_fill(key):
            if key[-1] == "1" and not filled:
                filled.append(key)
                replay_module._subscription_put(key, {"subscription": True})
                return replay_module._SUBSCRIPTION_MISS
            return original_get(key)

        with patch.object(
            replay_module, "_subscription_get", side_effect=concurrent_fill
        ):
            with self.assertRaisesRegex(
                ValueError, "Subscribed retained family.*uid=1"
            ):
                self.replay(current.mapping, size=2)
        self.assertEqual(len(filled), 1)
        self.assertIn("1", current.state["metadata"][0])

        # A lookahead key may already be cached, then disappear before its
        # consumption. A cold/current-miss window must still contain that key.
        later = self.fixture(size=2, subscribed=2)
        descriptor = later.mapping._descriptor
        key2 = replay_module._subscription_key(descriptor, "2")
        replay_module._subscription_put(key2, {"subscription": True})
        original_many = later.reader.get_many
        original_put = replay_module._subscription_put

        def evict():
            with replay_module._SUBSCRIPTION_LOCK:
                previous = replay_module._SUBSCRIPTION_CACHE.pop(key2, None)
                if previous is not None:
                    replay_module._SUBSCRIPTION_BYTES -= previous[1]

        def batch_then_eviction(keys):
            rows = original_many(keys)
            evict()
            return rows

        def store_then_eviction(key, row):
            original_put(key, row)
            if key == key2:
                evict()

        with patch.object(
            later.reader, "get_many", side_effect=batch_then_eviction
        ), patch.object(
            replay_module, "_subscription_put", side_effect=store_then_eviction
        ):
            with self.assertRaisesRegex(
                ValueError, "Subscribed retained family.*uid=2"
            ):
                self.replay(later.mapping, size=2)
        self.assertIn("2", later.state["metadata"][0])
        self.assertIs(original_get(key2), replay_module._SUBSCRIPTION_MISS)
