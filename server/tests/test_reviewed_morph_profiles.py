"""Reviewed source dependency does not rewrite immutable native morphology."""
import copy, json, unittest
from unittest.mock import patch
from wakfu_server import combat_morph_spellbook as morph
from wakfu_server.paths import DATA_ROOT


class ReviewedMorphProfilesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = morph.protocol_catalog.load(
            DATA_ROOT / "native-class-morph-profiles.json"
        )

    def test_public_accessor_keeps_eight_profiles_exact_and_adds_native_raw_book(self):
        before = json.dumps(self.base, sort_keys=True)
        profiles = morph.native_morph_profiles()
        self.assertEqual(len(self.base["profiles"]), 8)
        self.assertEqual(len(profiles), 9)
        for key, row in self.base["profiles"].items():
            self.assertEqual(profiles[key], row)
        self.assertEqual(morph.build_morph_book(profiles["2778"], 5), {4019: 5})
        self.assertEqual(json.dumps(self.base, sort_keys=True), before)

    def test_unknown_native_revision_keeps_only_its_original_profiles(self):
        with patch.object(
            morph.protocol_catalog, "release", return_value="f" * 64
        ), patch.object(
            morph.protocol_catalog,
            "record",
            side_effect=AssertionError(
                "Unknown revision must not load a supplement edge"
            ),
        ):
            result = morph._merge_reviewed_morph_profiles(self.base)
        self.assertIs(result, self.base)
        self.assertNotIn("2778", result["profiles"])

    def test_changed_base_or_native_effect_rejects_without_mutation(self):
        altered = dict(
            self.base, native_book_checks=self.base["native_book_checks"] + 1
        )
        with self.assertRaisesRegex(ValueError, "base native source changed"):
            morph._merge_reviewed_morph_profiles(altered)
        with patch.object(
            morph.protocol_catalog,
            "record",
            return_value={"effect_class": 933, "parameters": [999, 0]},
        ):
            with self.assertRaisesRegex(ValueError, "native933 edge"):
                morph._merge_reviewed_morph_profiles(self.base)

    def test_conflicting_profile_identity_and_unattested_edges_reject(self):
        data = copy.deepcopy(morph._reviewed_morph_profiles())
        data["profiles"]["2778"]["profile_id"] = 2887
        with patch.object(morph, "_reviewed_morph_profiles", return_value=data):
            with self.assertRaisesRegex(ValueError, "profile identity"):
                morph._merge_reviewed_morph_profiles(self.base)
        data = copy.deepcopy(morph._reviewed_morph_profiles())
        data["effect_profile_edges"] = []
        with patch.object(morph, "_reviewed_morph_profiles", return_value=data):
            with self.assertRaisesRegex(ValueError, "Incomplete"):
                morph._merge_reviewed_morph_profiles(self.base)

    def test_invalid_book_uid_never_becomes_an_admitted_profile(self):
        data = copy.deepcopy(morph._reviewed_morph_profiles())
        data["profiles"]["2778"]["abilities"][0]["casting_uid"] = 999
        morph.native_morph_profiles.cache_clear()
        try:
            with patch.object(morph, "_reviewed_morph_profiles", return_value=data):
                with self.assertRaisesRegex(ValueError, "bPO identity"):
                    morph.native_morph_profiles()
        finally:
            morph.native_morph_profiles.cache_clear()

    def test_changed_supplement_bytes_reject(self):
        morph._reviewed_morph_profiles.cache_clear()
        try:
            with patch.object(morph.Path, "read_bytes", return_value=b"{}"):
                with self.assertRaisesRegex(ValueError, "supplement changed"):
                    morph._reviewed_morph_profiles()
        finally:
            morph._reviewed_morph_profiles.cache_clear()
