"""Original class morph dependency closure is separate from captured profiles."""
import copy
import unittest
from unittest.mock import patch
from wakfu_server import combat_morph_spellbook as morph
from wakfu_server import combat_morph_dependencies as dependencies
from wakfu_server.paths import DATA_ROOT


class MorphSourceDomainTests(unittest.TestCase):
    def test_class_only_profiles_preserve_original_eight_rows(self):
        raw = morph.protocol_catalog.load(
            DATA_ROOT / "native-class-morph-profiles.json"
        )
        before = copy.deepcopy(raw)
        original = morph.native_class_morph_profiles()
        merged = morph.native_morph_profiles()
        self.assertEqual(original, raw["profiles"])
        self.assertEqual(len(original), 8)
        self.assertEqual(len(merged), 9)
        self.assertNotIn("2778", original)
        self.assertEqual(morph.build_morph_book(merged["2778"], 5), {4019: 5})
        self.assertEqual(raw, before)

    def test_actual_class_effect_closure_keeps_original_seal(self):
        source = dependencies.effect_catalog()
        original_refs = {
            row["reference"]
            for profile in morph.native_class_morph_profiles().values()
            for row in profile["abilities"]
        }
        self.assertEqual(set(source["spell_reference_closure"]), original_refs)
        self.assertNotIn(4019, original_refs)
        self.assertEqual(source["class_id"], 11)
        from wakfu_server.combat_published_catalogs import offline_catalog_compilation

        with offline_catalog_compilation():
            from wakfu_server.combat_casting_context import casting_root_catalog
            from wakfu_server.combat_scoped_casting_roots import morph_casting_roots

            zero = dependencies.zero_catalog()
            scoped = morph_casting_roots()
            actual = casting_root_catalog()
        self.assertEqual(set(map(int, zero["spells"])), original_refs)
        self.assertEqual(set(scoped["spell_references"]), original_refs)
        self.assertFalse(
            set(scoped["roots"]) - set(actual["roots"]),
            "Class morph casting roots missing from actual offline compiler catalog",
        )
        altered = copy.deepcopy(source)
        altered["spell_reference_closure"].append(4019)
        with patch.object(dependencies.protocol_catalog, "load", return_value=altered):
            with self.assertRaisesRegex(
                ValueError, "Unattested original class morph dependency closure"
            ):
                dependencies.effect_catalog.__wrapped__()

    def test_both_domains_use_the_same_profile_validation(self):
        invalid = copy.deepcopy(
            morph.protocol_catalog.load(DATA_ROOT / "native-class-morph-profiles.json")
        )
        invalid["profiles"][next(iter(invalid["profiles"]))]["abilities"][0][
            "casting_uid"
        ] = -1
        with self.assertRaisesRegex(ValueError, "bPO identity"):
            morph._validate_morph_profiles(invalid)
        invalid = copy.deepcopy(
            morph._merge_reviewed_morph_profiles(morph._native_class_morph_document())
        )
        invalid["profiles"]["2778"]["abilities"][0]["casting_uid"] = -1
        with self.assertRaisesRegex(ValueError, "bPO identity"):
            morph._validate_morph_profiles(invalid)


class MorphEagerCompilationTests(unittest.TestCase):
    def test_real_eager_player_compilation_keeps_both_morph_domains(self):
        # This is the publisher's first real compile_manifest stage, not a
        # mocked compiler or a lookup of an older published generation.
        from wakfu_server.combat_published_catalogs import offline_catalog_compilation

        with offline_catalog_compilation():
            from wakfu_server.combat_server_spell import compile_runtime_catalog_eager

            compiled = compile_runtime_catalog_eager()
        self.assertGreater(len(compiled.effects), 0)
        original_effects = set(
            map(str, dependencies.effect_catalog()["effect_reference_closure"])
        )
        self.assertFalse(
            original_effects - set(compiled.effects),
            "Original class effect closure missing from actual eager compiler",
        )
        self.assertEqual(len(morph.native_class_morph_profiles()), 8)
        self.assertEqual(len(morph.native_morph_profiles()), 9)
        self.assertEqual(
            set(dependencies.effect_catalog()["spell_reference_closure"]),
            {
                row["reference"]
                for profile in morph.native_class_morph_profiles().values()
                for row in profile["abilities"]
            },
        )
