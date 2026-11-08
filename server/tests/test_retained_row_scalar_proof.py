"""Row proof uses real local queries and preserves the actual terminal GC seam."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from wakfu_server import combat_retained_query as query
from wakfu_server import combat_retained_gc_boundary as boundary
from wakfu_server.combat_source_parent_index import OwnedStateSourceRow
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from test_retained_indexed_query import fixture
from test_retained_gc_boundary import RetainedGCBoundaryTests


class RetainedRowScalarProofTests(unittest.TestCase):
    def test_repeated_queries_alias_revocation_codec_fingerprint_and_gc(self):
        fight, _ = fixture()
        source = OwnedStateSourceRow(fight.native_owned_group_effects[10])
        fight.native_owned_group_effects[10] = source
        with patch.object(query, "_scalar", wraps=query._scalar) as scalar:
            expected = query.manager_query(fight, 1).entries
            cold = scalar.call_count
            scalar.reset_mock()
            self.assertEqual(query.manager_query(fight, 1).entries, expected)
            self.assertLess(scalar.call_count, cold)
        payload = source["payload"]
        source["payload"] = object()
        self.assertIsNone(query.manager_query(fight, 1))
        source["payload"] = payload
        self.assertEqual(query.manager_query(fight, 1).entries, expected)
        record = fight.native_retained_records[10]
        record["generic_effect"] = object()
        self.assertIsNone(query.manager_query(fight, 1))
        record["generic_effect"] = 101
        self.assertEqual(query.manager_query(fight, 1).entries, expected)

        def reentrant_update():
            dict.__setitem__(record, "generic_effect", object())
            self.assertIsNone(query.manager_query(fight, 1))
            yield ("generic_effect", 101)

        record.update(reentrant_update())
        self.assertEqual(query.manager_query(fight, 1).entries, expected)

        def source_update():
            self.assertEqual(query.manager_query(fight, 1).entries, expected)
            yield ("payload", object())

        source.update(source_update())
        self.assertIsNone(query.manager_query(fight, 1))
        source["payload"] = payload
        self.assertEqual(query.manager_query(fight, 1).entries, expected)
        source.get = lambda *args: (_ for _ in ()).throw(
            AssertionError("custom getter")
        )
        self.assertIsNone(query.manager_query(fight, 1))
        # An opaque reader can have bypassed the native mutation gateway.
        dict.__setitem__(source, "payload", object())
        del source.get
        self.assertIsNone(query.manager_query(fight, 1))
        source["payload"] = payload
        self.assertEqual(query.manager_query(fight, 1).entries, expected)
        replacement = OwnedStateSourceRow(source)
        fight.native_owned_group_effects[10] = replacement
        self.assertIsNone(vars(replacement).get("_scalar_eligibility"))
        self.assertEqual(query.manager_query(fight, 1).entries, expected)
        copied = deepcopy(fight)
        restored = decode_state(encode_state(fight))
        for current in (copied, restored):
            self.assertIsNone(
                vars(current.native_owned_group_effects[10]).get("_scalar_eligibility")
            )
            self.assertIsNone(
                vars(current.native_retained_records[10]).get("_scalar_eligibility")
            )
            self.assertEqual(query.manager_query(current, 1).entries, expected)

        from wakfu_ai.context.native_fingerprint import fingerprint

        isolated = OwnedStateSourceRow(uid=42, payload="00")
        before = fingerprint(isolated)
        self.assertTrue(
            query._row_scalar_proof(isolated, source=True, native_methods=True)
        )
        self.assertEqual(fingerprint(isolated), before)

        previous, current, runtime, dead, uid = RetainedGCBoundaryTests().fixture()
        owner = current.actors.owner
        metadata = current.native_retained_records[uid]
        current.native_retained_records = owner.records
        current.native_retained_order = owner.order
        owner.records.install_owned(uid, metadata)
        owner.order.append(uid)
        row = OwnedStateSourceRow(current.native_owned_group_effects[uid])
        current.native_owned_group_effects[uid] = row
        self.assertTrue(query._row_scalar_proof(row, source=True, native_methods=True))
        self.assertTrue(boundary._canonical_graph(current))
        boundary.prepare_retired_gc(previous, current, runtime, ())
        self.assertNotIn(uid, current.native_retained_records)
        self.assertNotIn(uid, current.native_owned_group_effects)
        self.assertIn(dead, current.actors)
