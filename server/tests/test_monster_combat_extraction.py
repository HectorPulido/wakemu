import sys
import gzip
import tempfile
import unittest
from pathlib import Path


TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import extract_monster_combat_inventory as extractor


class MonsterCombatExtractionTests(unittest.TestCase):
    def test_dependency_closure_follows_spell_state_grant_and_effect_cycles(self):
        spells = {
            "10": {"levels": [[0, 1, [100]]]},
            "20": {"levels": [[0, 1, [101]]]},
        }
        states = {
            "30": {"effect_ids": [102], "levels": [{"effects": [103]}]},
            "31": {"effect_ids": [], "levels": [{"effects": [100]}]},
        }
        effects = {
            # 100 -> 101 -> 100 is an effect cycle.
            "100": {"effect_class": 1, "children": [101]},
            "101": {"effect_class": 2, "children": [100, 102]},
            # A reachable state producer discovers state 31.
            "102": {
                "effect_class": 304,
                "children": [],
                "parameters_by_level": [[31]],
            },
            # A reachable grant effect discovers spell 20.
            "103": {
                "effect_class": 649,
                "children": [],
                "parameters_by_level": [[0, 0, 20]],
            },
        }

        result = extractor.dependency_closure([10], [30], spells, states, effects)

        self.assertEqual([10, 20], result["spell_ids"])
        self.assertEqual([30, 31], result["state_ids"])
        self.assertEqual([100, 101, 102, 103], result["effect_ids"])
        self.assertEqual([1, 2, 304, 649], result["effect_families"])
        self.assertEqual(
            [
                {
                    "effect_id": 102,
                    "family": 304,
                    "target_kind": "state",
                    "reference": 31,
                },
                {
                    "effect_id": 103,
                    "family": 649,
                    "target_kind": "spell",
                    "reference": 20,
                },
            ],
            result["candidate_links"],
        )
        self.assertEqual([], result["missing_definitions"])

    def test_dependency_closure_reports_missing_definitions_and_deduplicates_roots(
        self,
    ):
        result = extractor.dependency_closure(
            ["7", 7],
            [8],
            {"7": {"levels": [[0, 0, [90, 90, 91]]]}},
            {"8": {"effect_ids": [91], "levels": []}},
            {
                "90": {"effect_class": 1, "children": [92]},
                "91": {"effect_class": 2, "children": []},
            },
        )
        self.assertEqual([7], result["spell_ids"])
        self.assertEqual([8], result["state_ids"])
        self.assertEqual([90, 91, 92], result["effect_ids"])
        self.assertEqual(["effect:92"], result["missing_definitions"])

    def test_dependency_closure_includes_separate_level_zero_roots(self):
        result = extractor.dependency_closure(
            [7],
            [],
            {"7": {"levels": [[1, 2, [90]]], "level_zero_roots": [91]}},
            {},
            {
                "90": {"effect_class": 1, "children": []},
                "91": {"effect_class": 2, "children": [92]},
                "92": {"effect_class": 3, "children": []},
            },
        )
        self.assertEqual([7], result["spell_ids"])
        self.assertEqual([90, 91, 92], result["effect_ids"])
        self.assertEqual([], result["missing_definitions"])

    def test_dependency_closure_uses_distinct_native_level_zero_parameters(self):
        effects = {
            "3040": {
                "effect_class": 304,
                "children": [],
                "parameters_by_level": [[30]],
            },
            "6490": {
                "effect_class": 649,
                "children": [],
                "parameters_by_level": [[0, 0, 20]],
            },
            "2000": {"effect_class": 1, "children": []},
            "2100": {"effect_class": 2, "children": []},
        }
        zero_effects = {
            "3040": {"family": 304, "parameters": [31]},
            "6490": {"family": 649, "parameters": [0, 0, 21]},
        }
        result = extractor.dependency_closure(
            [10],
            [],
            {
                "10": {
                    "levels": [[0, 0, [3040, 6490]]],
                    "level_zero_roots": [3040, 6490],
                },
                "20": {"levels": [[0, 0, [2000]]]},
                "21": {"levels": [[0, 0, [2100]]]},
            },
            {
                "30": {"effect_ids": [], "levels": []},
                "31": {"effect_ids": [], "levels": []},
            },
            effects,
            zero_effects,
        )
        self.assertEqual([10, 20, 21], result["spell_ids"])
        self.assertEqual([30, 31], result["state_ids"])
        self.assertEqual([2000, 2100, 3040, 6490], result["effect_ids"])
        self.assertEqual(
            [
                {
                    "effect_id": 3040,
                    "family": 304,
                    "target_kind": "state",
                    "reference": 30,
                },
                {
                    "effect_id": 3040,
                    "family": 304,
                    "target_kind": "state",
                    "reference": 31,
                },
                {
                    "effect_id": 6490,
                    "family": 649,
                    "target_kind": "spell",
                    "reference": 20,
                },
                {
                    "effect_id": 6490,
                    "family": 649,
                    "target_kind": "spell",
                    "reference": 21,
                },
            ],
            result["candidate_links"],
        )
        self.assertEqual([], result["missing_definitions"])

    def test_dependency_index_preserves_closure_and_fingerprints_opaque_source(self):
        spells = {
            "10": {
                "levels": [[1, 2, [100]], [3, 4, [101, 100]]],
                "level_zero_roots": [102],
            },
            "20": {"levels": [[0, 1, [104]]]},
            "21": {"levels": [[0, 1, []]]},
        }
        states = {
            "30": {"effect_ids": [103], "levels": [{"effects": [103, 104]}]},
        }
        effects = {
            "100": {"effect_class": 1, "children": [101], "parameters_by_level": [[5]]},
            "101": {
                "effect_class": 304,
                "children": [100, 102],
                "parameters_by_level": [[30], [30]],
                "opaque_native_metadata": {"token": "preserve-in-fingerprint"},
            },
            "102": {
                "effect_class": 649,
                "children": [],
                "parameters_by_level": [[0, 0, 20], [0, 0, 20]],
            },
            "103": {"effect_class": 2, "children": [101]},
            "104": {"effect_class": 3, "children": []},
        }
        zero_effects = {"102": {"family": 649, "parameters": [0, 0, 21]}}
        full = extractor.dependency_closure(
            [10], [30], spells, states, effects, zero_effects
        )
        indexed_spells = extractor.dependency_index({"spells": spells})["spells"]
        indexed_states = extractor.dependency_index({"states": states})["states"]
        indexed_effects = extractor.dependency_index({"effects": effects})["effects"]
        indexed = extractor.dependency_closure(
            [10], [30], indexed_spells, indexed_states, indexed_effects, zero_effects
        )
        self.assertEqual(full, indexed)
        self.assertEqual([10, 20, 21], indexed["spell_ids"])
        self.assertEqual([30], indexed["state_ids"])

        raw = {
            "effect_class": 7,
            "children": [],
            "native_hmi_actions": {
                "rzc": [
                    {"id": 17, "native": "HMIAction{m_id=17, particleSystemId=44}"}
                ],
            },
            "opaque_field": {"native": [1, 2, 3]},
        }
        same_semantics = {
            **raw,
            "native_hmi_actions": {
                "rzc": [{"id": 1, "native": "HMIAction{m_id=1, particleSystemId=44}"}],
            },
        }
        changed_opaque = {**same_semantics, "opaque_field": {"native": [1, 2, 4]}}
        fingerprint = extractor.dependency_index({"effects": {"9": raw}})["effects"][
            "9"
        ]["source_fingerprint"]
        self.assertEqual(
            fingerprint,
            extractor.dependency_index({"effects": {"9": same_semantics}})["effects"][
                "9"
            ]["source_fingerprint"],
        )
        self.assertNotEqual(
            fingerprint,
            extractor.dependency_index({"effects": {"9": changed_opaque}})["effects"][
                "9"
            ]["source_fingerprint"],
        )

    def test_initial_state_triples_reject_partial_record(self):
        with self.assertRaisesRegex(ValueError, "Malformed initial-state triples: 42"):
            extractor.initial_states({"ref": 42, "initial_state_triples": [5, -1]})

    def test_duplicate_monster_identity_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Duplicate ref: 1"):
            extractor.build_inventory(
                [{"ref": 1}, {"ref": 1}],
                {},
                {},
                {"effects": {}, "spells": {}},
                {"effects": {}, "states": {}},
                {},
                {"npc_profiles": {}},
                {},
            )

    def test_conflicting_effect_definitions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Conflicting native effect 9"):
            extractor.merge_effects(
                {"9": {"effect_class": 1, "children": []}},
                {"9": {"effect_class": 2, "children": []}},
            )

    def test_supplement_accepts_hmi_process_local_id_allocation_difference(self):
        base = {
            "10113": {
                "effect_class": 7,
                "native_hmi_actions": {
                    "rzc": [
                        {"id": 17, "native": "HMIAction{m_id=17, particleSystemId=44}"}
                    ],
                },
            },
        }
        extra = {
            "10113": {
                "effect_class": 7,
                "native_hmi_actions": {
                    "rzc": [
                        {"id": 1, "native": "HMIAction{m_id=1, particleSystemId=44}"}
                    ],
                },
            },
        }
        self.assertEqual(base, extractor.supplement_effects(base, extra, {}))

    def test_supplement_rejects_hmi_semantic_or_non_id_differences(self):
        base = {
            "10113": {
                "effect_class": 7,
                "native_hmi_actions": {
                    "rzc": [
                        {"id": 17, "native": "HMIAction{m_id=17, particleSystemId=44}"}
                    ],
                },
            },
        }
        for changed in (
            {"id": 1, "native": "HMIAction{m_id=1, particleSystemId=45}"},
            {
                "id": 1,
                "native": "HMIAction{m_id=1, particleSystemId=44}",
                "extra": True,
            },
        ):
            extra = {
                "10113": {
                    "effect_class": 7,
                    "native_hmi_actions": {"rzc": [changed]},
                },
            }
            with self.subTest(changed=changed), self.assertRaisesRegex(
                ValueError, "Conflicting supplemental native effect 10113"
            ):
                extractor.supplement_effects(base, extra, {})

    def test_gzip_write_is_deterministic_and_digest_tracks_compressed_document(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bundle.json.gz"
            value = {"z": [3, 2, 1], "ñ": {"ok": True}}
            extractor.write(path, value)
            first_bytes = path.read_bytes()
            first_digest = extractor.digest(path)
            extractor.write(path, value)
            self.assertEqual(first_bytes, path.read_bytes())
            self.assertEqual(first_digest, extractor.digest(path))
            self.assertEqual(value, extractor.read(path))

    def test_compress_source_preserves_exact_json_and_writes_deterministic_gzip_header(
        self,
    ):
        original = (
            b'{\n  "native": [3, 2, 1],\n  "opaque": "exact bytes \xe2\x98\x83"\n}\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            outputs = []
            for index in (1, 2):
                source = Path(directory) / f"source{index}.json"
                source.write_bytes(original)
                extractor.compress_source(source)
                compressed_path = source.with_suffix(".json.gz")
                self.assertFalse(source.exists())
                compressed = compressed_path.read_bytes()
                self.assertEqual(b"\x1f\x8b", compressed[:2])
                self.assertEqual(0, int.from_bytes(compressed[4:8], "little"))
                self.assertEqual(
                    0, compressed[3] & 0x08, "gzip FNAME header flag must be clear"
                )
                self.assertEqual(original, gzip.decompress(compressed))
                outputs.append(compressed)
            self.assertEqual(outputs[0], outputs[1])

    def test_build_inventory_preserves_raw_metadata_and_computes_ability_levels(self):
        raw_metadata = {"native_curve": [4, 8], "opaque": {"flag": True}}
        monster = {
            "ref": 1,
            "family_id": 12,
            "min_level": 4,
            "max_level": 9,
            "native_abilities": [
                {"spell_id": 100, "level_parameter": -1, "raw_metadata": {"slot": 2}},
                {"spell_id": 200, "level_parameter": 3, "raw_metadata": {"slot": 7}},
            ],
            "initial_state_triples": [30, -1, 5],
            "fight_properties": {"sdR": 4, "opaque": [1, 2]},
            "raw_native": raw_metadata,
        }
        result = extractor.build_inventory(
            [monster],
            {
                "spells": {
                    "100": {"levels": [[0, 0, [10]]]},
                    "200": {"levels": [[0, 0, [20]]]},
                }
            },
            {"spells": {"100": {}, "200": {}}},
            {
                "spells": {
                    "100": {"levels": [[0, 0, [10]]]},
                    "200": {"levels": [[0, 0, [20]]]},
                },
                "effects": {
                    "10": {"effect_class": 1, "children": []},
                    "20": {"effect_class": 2, "children": []},
                },
            },
            {"states": {"30": {"effect_ids": [], "levels": []}}, "effects": {}},
            {"roots": {"10": {}, "20": {}}},
            {"npc_profiles": {"1": {}}},
            {
                "content.7.1": "Test monster",
                "content.3.100": "Scaled spell",
                "content.3.200": "Fixed spell",
            },
        )
        row = result["monsters"][0]
        self.assertEqual(raw_metadata, row.get("raw_native"))
        self.assertEqual({"sdR": 4, "opaque": [1, 2]}, row["fight_properties"])
        self.assertEqual(
            [[4, 9], [3, 3]],
            [ability["effective_level_range"] for ability in row["abilities"]],
        )
        self.assertEqual(
            [
                {"spell_id": 100, "level_parameter": -1, "raw_metadata": {"slot": 2}},
                {"spell_id": 200, "level_parameter": 3, "raw_metadata": {"slot": 7}},
            ],
            [
                {
                    k: v
                    for k, v in ability.items()
                    if k in {"spell_id", "level_parameter", "raw_metadata"}
                }
                for ability in row["abilities"]
            ],
        )
        self.assertEqual(
            [{"state_id": 30, "level_parameter": -1, "native_flag": 5}],
            row["initial_states"],
        )


if __name__ == "__main__":
    unittest.main()
