"""Selected advisory costs retain native source, level and modifier semantics."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_ai.bridge import actor_casting_metadata as metadata
from wakfu_ai.bridge.actor_repertoires import actor_repertoires
from wakfu_server import combat_native_spell_casting as casting
from wakfu_server.combat_published_catalogs import PublishedStaticMapping, POLICY, _SEAL


class ActorCastingMetadataTests(unittest.TestCase):
    def test_selected_native_costs_are_bounded_revision_scoped_and_actor_private(self):
        path = (
            Path(__file__).resolve().parents[3]
            / ".runtime/native-casting-selected-level/original-records.json"
        )
        fixture = json.loads(path.read_text())
        rows = {
            r["key"]: r["payload"]
            for r in fixture["records"]
            if r["path"] == "native-spell-casting.json"
        }
        raw = {
            key: json.dumps(row, separators=(",", ":")).encode()
            for key, row in rows.items()
        }
        reads = []

        class Reader:
            representation = "native_json"

            def record_bytes(self, key):
                reads.append(key)
                return raw[key]

        def source(revision):
            return PublishedStaticMapping(
                dict(
                    policy=POLICY,
                    revision=revision * 64,
                    manifest_sha256=revision * 64,
                    collection="native-spell-casting.json/spells",
                    count=len(rows),
                    ordered_keys_sha256=hashlib.sha256(
                        json.dumps(list(rows)).encode()
                    ).hexdigest(),
                ),
                Reader(),
                _seal=_SEAL,
            )

        current = [source("a")]
        metadata.selected_cost_metadata.cache_clear()
        self.addCleanup(metadata.selected_cost_metadata.cache_clear)
        with patch.object(casting, "catalog", side_effect=lambda: current[0]):
            first = metadata.selected_cost_metadata(5623, 130)
            expected = rows["5623"]
            self.assertEqual(
                first.options,
                tuple(
                    tuple(row[:3])
                    for row in [
                        expected["costs"][129],
                        *[rule["levels"][129] for rule in expected["conditional"]],
                    ]
                ),
            )
            self.assertEqual(first.categories, tuple(expected["categories"]))
            self.assertTrue(first.conditional)
            self.assertIs(metadata.selected_cost_metadata(5623, 130), first)
            self.assertEqual(reads, ["5623"])
            self.assertIsNot(metadata.selected_cost_metadata(5623, 1), first)
            self.assertEqual(reads, ["5623", "5623"])
            before = len(reads)
            current[0] = source("b")
            self.assertEqual(metadata.selected_cost_metadata(5623, 130), first)
            self.assertEqual(len(reads), before + 1)
            for level in (-1, True, 1.5):
                with self.subTest(level=level), self.assertRaises(ValueError):
                    metadata.selected_cost_metadata(5623, level)
            with self.assertRaises(ValueError):
                metadata.selected_cost_metadata(5623, 10000)

        # Caller-provided mutable dictionaries never gain static publication authority.
        private = deepcopy(rows)
        private["5623"]["categories"] = [7, 7]
        with patch.object(casting, "catalog", return_value=private):
            row = metadata.selected_cost_metadata(5623, 130)
            self.assertEqual(row.categories, (7, 7))
            private["5623"]["costs"][129][0] += 9
            self.assertEqual(
                metadata.selected_cost_metadata(5623, 130).options[0][0],
                row.options[0][0] + 9,
            )
            with patch.object(metadata, "_MAX_BYTES", 1):
                self.assertEqual(
                    metadata.selected_cost_metadata(5623, 130).categories, (7, 7)
                )

            fight = SimpleNamespace(
                sequence=1, actors={1: SimpleNamespace(spell_ap_cost_modifiers={7: -1})}
            )
            oracle = SimpleNamespace(owned_spells=lambda *_: {5623: 130})

            def book():
                return actor_repertoires(
                    oracle,
                    fight,
                    [dict(id=1, hp=100)],
                    source_state="state",
                    capabilities=lambda *_: {},
                )["1"]["spells"][0]

            first = book()
            expected_options = sorted(
                {
                    (max(0, values[0] - 2), max(0, values[1]), max(0, values[2]))
                    for values in [
                        private["5623"]["costs"][129],
                        *[r["levels"][129] for r in private["5623"]["conditional"]],
                    ]
                }
            )
            self.assertEqual(
                first["costOptions"],
                [dict(ap=a, mp=m, wp=w) for a, m, w in expected_options],
            )
            first["costOptions"][0]["ap"] = 999
            fight.actors[1].spell_ap_cost_modifiers[7] = 0
            self.assertNotEqual(book()["costOptions"], first["costOptions"])
            # Unknown live modifiers remain unresolved on every lookup.
            fight.actors[1].spell_ap_cost_modifiers = None
            self.assertEqual(book()["costBasis"], "native_table_before_actor_modifiers")
            private["5623"]["costs"][129][0] = True
            self.assertIn("missing_native_cost_table", book()["costUncertainties"])

        zero = deepcopy(rows["7962"])
        zero["levels"], zero["costs"], zero["conditional"] = (
            [zero["levels"][0]],
            [zero["costs"][0]],
            [],
        )
        select = casting.native_casting_table
        with patch.object(
            casting,
            "catalog",
            side_effect=AssertionError("Zero cannot alias positive catalog"),
        ), patch.object(
            casting,
            "native_casting_table",
            side_effect=lambda spell, level, **kwargs: select(
                spell, level, zero_casting={"7962": zero}, **kwargs
            ),
        ):
            before_zero = metadata.selected_cost_metadata(7962, 0)
            zero["costs"][0][0] += 1
            self.assertEqual(
                metadata.selected_cost_metadata(7962, 0).options[0][0],
                before_zero.options[0][0] + 1,
            )

        with patch.object(casting, "catalog", side_effect=lambda: current[0]):
            metadata.selected_cost_metadata.cache_clear()
            with patch.object(metadata, "_MAX_ENTRIES", 1):
                for level in (1, 2, 1):
                    metadata.selected_cost_metadata(5623, level)
                self.assertEqual(len(metadata._RECORDS), 1)
            metadata.selected_cost_metadata.cache_clear()
            with patch.object(metadata, "_MAX_BYTES", 1):
                metadata.selected_cost_metadata(5623, 130)
                self.assertFalse(metadata._RECORDS)
