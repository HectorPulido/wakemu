"""Typed provenance replay preserves aliases and sticky admission boundaries."""
import json
import unittest

from wakfu_server.combat_reproduction_state import (
    encode_state,
    decode_state,
    UnsupportedReproductionState,
)
from wakfu_server.combat_source_provenance_entries import SourceProvenanceEntries


class SourceProvenanceCodecTests(unittest.TestCase):
    def test_roundtrip_preserves_typed_aliases_revocation_and_legacy_dict(self):
        row = {"state_uid": 11}
        native = SourceProvenanceEntries({"11": row})
        revoked = SourceProvenanceEntries({"11": row})
        revoked[7] = row
        del revoked[7]
        legacy = {"11": row}
        graph = dict(
            native=native,
            native_alias=native,
            revoked=revoked,
            legacy=legacy,
            legacy_alias=legacy,
            row=row,
        )
        after = decode_state(json.loads(json.dumps(encode_state(graph))))
        self.assertIs(type(after["native"]), SourceProvenanceEntries)
        self.assertIs(after["native"], after["native_alias"])
        self.assertTrue(after["native"].keys_are_native)
        self.assertFalse(after["revoked"].keys_are_native)
        self.assertEqual(0, after["revoked"]._native_key_serial)
        self.assertIs(type(after["legacy"]), dict)
        self.assertIs(after["legacy"], after["legacy_alias"])
        for name in ("native", "revoked", "legacy"):
            self.assertIs(after[name]["11"], after["row"])
        after["native"][9] = row
        self.assertFalse(after["native"].keys_are_native)
        self.assertTrue(native.keys_are_native)

    def test_tag_requires_boolean_and_cannot_admit_foreign_keys(self):
        source = SourceProvenanceEntries()
        source[7] = "foreign"
        payload = encode_state(source)
        node = next(
            node
            for node in payload["nodes"]
            if node.get("native_retained_storage") == "source_provenance_entries"
        )
        node["native_provenance_keys"] = True
        self.assertFalse(decode_state(payload).keys_are_native)
        node["native_provenance_keys"] = 1
        with self.assertRaises(UnsupportedReproductionState):
            decode_state(payload)
