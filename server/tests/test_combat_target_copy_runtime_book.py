"""Native994 selection rechecks installed roots/flags and borrowed UID identity."""
from copy import deepcopy
from dataclasses import asdict
import unittest
from wakfu_server.combat_character_copy_book import CopyBookAction
from wakfu_server.combat_target_copy_runtime_book import validated_target_selection


class TargetCopyRuntimeBookTests(unittest.TestCase):
    def fixture(self):
        first = CopyBookAction(9001, 101, 1, False, True, False)
        excluded = CopyBookAction(9002, 102, 1, False, True, False)
        proof = dict(
            producer="eZq994.faD.actual_target_book",
            source_actions=[asdict(first), asdict(excluded)],
            copied_actions=[asdict(first)],
        )
        definitions = {
            "101": {"levels": [[0, 0, [1]]]},
            "102": {"levels": [[0, 0, [2]]]},
        }
        effects = {"1": {"effect_class": 2}, "2": {"effect_class": 307}}
        flags = {
            str(ref): dict(
                native_elO=False, native_elemental_copy=True, native_neutral_copy=False
            )
            for ref in (101, 102)
        }
        return proof, dict(definitions=definitions, effects=effects, flags=flags), first

    def test_borrowed_uid_and_native_root_exclusion_are_recomputed(self):
        proof, metadata, first = self.fixture()
        self.assertEqual(validated_target_selection(proof, **metadata), (first,))
        self.assertEqual(validated_target_selection(proof, **metadata)[0].uid, 9001)

    def test_forged_clone_uid_flags_or_missing_installed_root_are_rejected(self):
        proof, metadata, first = self.fixture()
        forged = deepcopy(proof)
        forged["copied_actions"][0]["uid"] = 99999
        with self.assertRaises(ValueError):
            validated_target_selection(forged, **metadata)
        forged = deepcopy(proof)
        forged["source_actions"][0]["elemental"] = False
        with self.assertRaises(ValueError):
            validated_target_selection(forged, **metadata)
        metadata["effects"].pop("1")
        with self.assertRaises(ValueError):
            validated_target_selection(proof, **metadata)
