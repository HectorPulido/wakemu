"""Pinned source batching must leave listener selection and errors unchanged."""
import json
from types import SimpleNamespace
import unittest

from wakfu_server.combat_event_replay import (
    NativeCloneAuthority,
    NativeEventReplay,
    NativeExternalEvent,
    _prefetch_replay_bytes,
)
from wakfu_server import combat_published_catalogs as published
from wakfu_server.native_compiled_catalog import CompiledBatchLimit


class Reader:
    representation = "native_json"

    def __init__(self, rows, *, maximum=128, failure=None):
        self.rows = rows
        self.backend = SimpleNamespace(batch_size=128)
        self.cache = {}
        self.batches = []
        self.maximum = maximum
        self.failure = failure
        self.reads = []

    def get_many_bytes(self, keys):
        keys = tuple(keys)
        if len(keys) > self.maximum:
            raise CompiledBatchLimit("test byte bound")
        if self.failure:
            raise self.failure
        pending = tuple(key for key in keys if key not in self.cache)
        if pending:
            self.batches.append(pending)
        for key in pending:
            if key in self.rows:
                self.cache[key] = json.dumps(self.rows[key]).encode()
        return {key: self.cache[key] for key in keys if key in self.cache}

    def record_bytes(self, key):
        self.reads.append(key)
        if key not in self.cache:
            self.get_many_bytes((key,))
        return self.cache[key]

    def get_many(self, keys):
        return {key: json.loads(raw) for key, raw in self.get_many_bytes(keys).items()}


def sealed(reader, *, collection="test.replay"):
    return published.PublishedStaticMapping(
        dict(
            revision="a" * 64,
            manifest_sha256="a" * 64,
            collection=collection,
            count=len(reader.rows),
        ),
        reader,
        _seal=published._SEAL,
    )


class ReplaySourceBatchTests(unittest.TestCase):
    def test_real_replay_batches_groups_without_changing_scope_or_fresh_decodes(self):
        rows = {
            str(i): dict(
                event_global_subscription=False, event_reverse_subscription=False
            )
            for i in range(1, 75)
        }
        reader = Reader(rows)
        metadata = sealed(reader)
        entries = [
            SimpleNamespace(uid=i, generic_effect=i, manager_id=7) for i in range(1, 75)
        ]
        entries.append(SimpleNamespace(uid=999, generic_effect=999, manager_id=8))
        groups = {
            entry.uid: dict(
                invocation=dict(reference=entry.generic_effect),
                native_subscription_masks=[[] for _ in range(7)],
                native_effect_flags=[],
            )
            for entry in entries
        }
        retention = SimpleNamespace(
            view=lambda: SimpleNamespace(entries=entries),
            metadata={"effects": metadata},
            fight=SimpleNamespace(native_owned_group_effects=groups),
        )
        replay = NativeEventReplay(SimpleNamespace(effects={}), retention)
        authority = NativeCloneAuthority(
            lambda *args: self.fail("no activation"),
            lambda *args: self.fail("no condition"),
        )
        self.assertEqual(
            replay(NativeExternalEvent(7, (1003,), 6), authority=authority), ()
        )
        self.assertEqual(reader.batches, [tuple(str(i) for i in range(1, 75))])
        self.assertEqual(reader.reads, list(str(i) for i in range(1, 75)))
        private = metadata["1"]
        private["event_global_subscription"] = True
        self.assertFalse(metadata["1"]["event_global_subscription"])
        # New events still visit their actual current, explicitly scoped rows.
        self.assertEqual(
            replay(
                NativeExternalEvent(7, (1003,), 6),
                authority=authority,
                eligible_uids=frozenset({74}),
            ),
            (),
        )
        self.assertEqual(reader.reads[-1], "74")
        self.assertEqual(len(reader.batches), 1)

    def test_scalar_removal_prefetch_only_uses_actual_owned_recipient(self):
        entries = [
            SimpleNamespace(uid=uid, generic_effect=uid, manager_id=manager)
            for uid, manager in ((101, 7), (102, 8), (103, 7))
        ]
        metadata = Reader(
            {str(uid): {"subscription": False} for uid in (101, 102, 103)}
        )
        effects = Reader(
            {
                str(uid): {"target_masks": [[] for _ in range(7)]}
                for uid in (101, 102, 103)
            }
        )
        retention = SimpleNamespace(
            view=lambda: SimpleNamespace(entries=entries),
            metadata={"effects": sealed(metadata, collection="test.scalar_metadata")},
            fight=SimpleNamespace(
                native_owned_group_effects={}, owned_stat_effects={101: {}, 102: {}}
            ),
        )
        replay = NativeEventReplay(
            SimpleNamespace(effects=sealed(effects, collection="test.scalar_effects")),
            retention,
        )
        authority = NativeCloneAuthority(
            lambda *args: self.fail("no activation"),
            lambda *args: self.fail("no condition"),
        )
        self.assertEqual(
            replay(NativeExternalEvent(7, (1003,), 4), authority=authority), ()
        )
        self.assertEqual(effects.batches, [("101",)])
        self.assertEqual(effects.reads, ["101"])

    def test_byte_bounds_mutable_sources_and_failure_order(self):
        rows = {str(i): {"value": i} for i in range(6)}
        reader = Reader(rows, maximum=2)
        catalog = sealed(reader)
        _prefetch_replay_bytes(catalog, iter(rows))
        self.assertEqual(set(reader.cache), set(rows))
        self.assertTrue(all(len(batch) <= 2 for batch in reader.batches))
        mutable = dict(rows)
        _prefetch_replay_bytes(mutable, iter(rows))
        mutable["0"]["value"] = 99
        self.assertEqual(mutable["0"]["value"], 99)
        reader = Reader(rows, failure=ValueError("later corrupt source"))
        _prefetch_replay_bytes(sealed(reader), iter(rows))
        self.assertEqual(reader.reads, [])
        with self.assertRaisesRegex(ValueError, "later corrupt source"):
            sealed(reader)["0"]
        with self.assertRaises(TimeoutError):
            _prefetch_replay_bytes(
                sealed(Reader(rows, failure=TimeoutError())), iter(rows)
            )


if __name__ == "__main__":
    unittest.main()
