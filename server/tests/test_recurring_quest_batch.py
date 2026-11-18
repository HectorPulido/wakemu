"""Compiler regressions for native daily hunter and Modulox batches."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest

from tools import recurring_quest_batch as batch


def candidate_fixture(*, modulox=False):
    quest_id, objective_id, category_id = (
        (71001, 71002, 701) if modulox else (70001, 70002, 70)
    )
    boss_id, dungeon_id, start_map = 72001, 73001, 74001
    category_name = "Modulox" if modulox else "Boss Hunt [050-060]"
    native = {
        "d": quest_id,
        "native_class": "aJM",
        "aqb": False,
        "cjG": category_id,
        "cjU": 86400,
        "cjL": 0,
        "getDuration": 0,
        "cjR": True,
        "cjJ": [{"d": objective_id, "ckc": "", "ckd": [], "cke": "", "ckf": []}],
        "cjK": [
            {"d": 74011, "aeV": 5, "ckk": False, "ckl": [20001, 2]},
            {"d": 74012, "aeV": 17 if modulox else 6, "ckk": False, "ckl": [1]},
        ],
        "cjT": 1784000000000,
        "aHe": f"IsAchievementRunning({quest_id})" if modulox else "",
        "cjI": "GetRealLevel() >= 65" if modulox else "",
    }
    quest_text = (
        "Complete Example Dungeon at level 120"
        if modulox
        else "Complete Example Dungeon by defeating Tokki"
    )
    translations = {
        language: {
            f"content.61.{category_id}": category_name,
            f"content.62.{quest_id}": f"Hunt: Tokki",
            f"content.64.{objective_id}": quest_text,
            f"content.7.{boss_id}": "Tokki",
            f"content.137.{dungeon_id}": "Example Dungeon",
        }
        for language in ("en", "fr", "es")
    }
    translation_sources = {
        f"client/contents/i18n/i18n_{language}.jar": f"{language}0" * 32
        for language in ("en", "fr", "es")
    }
    translations["source_sha256"] = translation_sources
    monsters = {"monsters": [{"ref": boss_id, "raw_visual_arrays": {"csc": [43]}}]}
    dungeons = {
        "source_sha256": {"client/lib/wakfu-client.jar": "a" * 64},
        "definitions": [
            {
                "d": dungeon_id,
                "native_class": "aKU",
                "aHA": [start_map],
                "cno": [boss_id],
            }
        ],
    }
    plan = {
        "definition_id": dungeon_id,
        "rooms": [
            {"order": 9, "monsters": [{"ref_id": boss_id, "role": "boss", "count": 1}]}
        ],
    }
    routes = [
        {
            "route_key": "example-route",
            "policy_version": 1,
            "configuration": {
                "route": {"start_map_id": start_map},
                "compiled_plan": plan,
            },
        }
    ]
    context = {
        "known_ids": [],
        "modulox_categories": [
            {
                "category_id": category_id,
                "offer_minimum_level": 60,
                "offer_node_id": 1,
                "offer_choice_id": 2,
                "offer_criterion": "",
                "offer_source_sha256": "e" * 64,
            }
        ]
        if modulox
        else [],
        "native_revision": "f" * 64,
        "monsters_sha256": "a" * 64,
    }
    quests = {
        "source_sha256": {
            "client/lib/wakfu-client.jar": "a" * 64,
            **translation_sources,
        },
        "definitions": [native],
        "translations": {
            language: {
                f"content.61.{category_id}": category_name,
                f"content.62.{quest_id}": f"Hunt: Tokki",
                f"content.64.{objective_id}": quest_text,
            }
            for language in ("en", "fr", "es")
        },
    }
    return quests, dungeons, monsters, routes, translations, context


class RecurringQuestBatchCompilerTests(unittest.TestCase):
    def compile(self, *args):
        return batch.compile_batch(*args)

    def test_daily_compilation_preserves_native_calendar_and_level_bracket(self):
        manifest = self.compile(*candidate_fixture())
        self.assertEqual(
            manifest["counts"], {"qualified": 1, "daily": 1, "modulox": 0, "pending": 0}
        )
        row = manifest["qualified"][0]
        self.assertEqual(row["anchor_ms"], 1784000000000)
        self.assertEqual(row["period_ms"], 86400000)
        self.assertEqual(row["minimum_level"], 50)
        self.assertEqual(row["original_eligibility_criterion"], "")

    def test_modulox_preserves_native_level_gate_offer_floor_and_target_level(self):
        manifest = self.compile(*candidate_fixture(modulox=True))
        row = manifest["qualified"][0]
        self.assertEqual(row["minimum_level"], 65)
        self.assertEqual(row["target_effective_level"], 120)
        self.assertEqual(row["original_eligibility_criterion"], "GetRealLevel() >= 65")
        self.assertEqual(row["rewards"][1]["aeV"], 17)

    def test_ambiguous_native_boss_pair_stays_pending(self):
        args = list(candidate_fixture())
        monsters, dungeons, translations = args[2], args[1], args[4]
        duplicate = deepcopy(monsters["monsters"][0])
        duplicate["ref"] += 1
        monsters["monsters"].append(duplicate)
        dungeons["definitions"][0]["cno"].append(duplicate["ref"])
        for language in ("en", "fr", "es"):
            translations[language][f"content.7.{duplicate['ref']}"] = "Tokki"
        manifest = self.compile(*args)
        self.assertEqual(manifest["qualified"], [])
        self.assertEqual(
            manifest["pending"][0]["reason"], "native_dungeon_boss_pair_not_unique"
        )

    def test_missing_native_dungeon_or_active_final_room_stays_pending(self):
        args = list(candidate_fixture())
        args[1]["definitions"] = [
            dict(args[1]["definitions"][0], native_class="not-aKU")
        ]
        manifest = self.compile(*args)
        self.assertEqual(
            manifest["pending"][0]["reason"], "native_dungeon_boss_pair_not_unique"
        )

        args = list(candidate_fixture())
        args[3] = []
        manifest = self.compile(*args)
        self.assertEqual(
            manifest["pending"][0]["reason"], "active_final_room_not_unique_strict_boss"
        )

    def test_native_reward_family_change_is_pending(self):
        args = list(candidate_fixture())
        args[0]["definitions"][0]["cjK"][1]["aeV"] = 17
        manifest = self.compile(*args)
        self.assertEqual(manifest["qualified"], [])
        self.assertEqual(
            manifest["pending"][0]["reason"], "native_reward_family_changed"
        )

    def test_native_calendar_change_is_pending_instead_of_being_normalized(self):
        args = list(candidate_fixture())
        args[0]["definitions"][0]["cjU"] = 7 * 86400
        manifest = self.compile(*args)
        self.assertEqual(manifest["qualified"], [])
        self.assertEqual(
            manifest["pending"][0]["reason"],
            "unsupported_native_lifecycle_or_objective",
        )

    def test_known_existing_contract_is_excluded_without_synthesizing_activation(self):
        args = list(candidate_fixture())
        args[5]["known_ids"] = [args[0]["definitions"][0]["d"]]
        manifest = self.compile(*args)
        self.assertEqual(manifest["qualified"], [])
        self.assertEqual(manifest["pending"], [])

    def test_mismatched_client_or_localization_versions_are_rejected(self):
        args = list(candidate_fixture())
        args[1]["source_sha256"]["client/lib/wakfu-client.jar"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "client versions differ"):
            self.compile(*args)

        args = list(candidate_fixture())
        args[4]["source_sha256"]["client/contents/i18n/i18n_fr.jar"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "localization versions differ"):
            self.compile(*args)

    def test_shipped_manifest_is_versioned_unique_and_matches_its_counts(self):
        path = (
            Path(__file__).parents[1]
            / "wakfu_server/achievements/mission_batches/recurring-hunts-v1.json"
        )
        manifest = json.loads(path.read_text())
        rows = manifest["qualified"]
        identities = [row["definition_id"] for row in rows]
        self.assertEqual(manifest["schema"], batch.SCHEMA)
        self.assertEqual(len(rows), 67)
        self.assertEqual(len(identities), len(set(identities)))
        self.assertEqual(
            manifest["counts"],
            {
                "qualified": 67,
                "daily": 34,
                "modulox": 33,
                "pending": len(manifest["pending"]),
            },
        )
        self.assertTrue(all(len(row["plan_sha256"]) == 64 for row in rows))
        self.assertTrue(all(len(row["proof_sha256"]) == 64 for row in rows))
        self.assertTrue(all(len(row["native_definition_sha256"]) == 64 for row in rows))

    def test_opt_in_recovers_only_exact_name_head_before_comma(self):
        args = list(candidate_fixture())
        for language in ("en", "fr"):
            args[4][language]["content.7.72001"] = "Tokki, the original"
        strict = self.compile(*args)
        self.assertEqual(strict["qualified"], [])
        reconstructed = batch.compile_batch(*args, reconstruct_native_aliases=True)
        row = reconstructed["qualified"][0]
        self.assertIn(
            "exact-native-name-head-before-comma-in-at-least-two-locales",
            row["proof"]["reviewed_binding_extensions"],
        )

        fuzzy = list(candidate_fixture())
        for language in ("en", "fr", "es"):
            fuzzy[4][language]["content.7.72001"] = "Tokki the original"
        self.assertEqual(
            batch.compile_batch(*fuzzy, reconstruct_native_aliases=True)["qualified"],
            [],
        )

    def test_opt_in_unique_aKU_membership_can_recover_changed_dungeon_label(self):
        args = list(candidate_fixture())
        for language in ("en", "fr", "es"):
            args[4][language]["content.137.73001"] = "Renamed dungeon"
        result = batch.compile_batch(*args, reconstruct_native_aliases=True)
        row = result["qualified"][0]
        self.assertIn(
            "unique-native-boss-to-aKU-membership-plus-actual-final-room",
            row["proof"]["reviewed_binding_extensions"],
        )

        ambiguous = list(candidate_fixture())
        ambiguous[1]["definitions"].append(
            {"d": 73002, "native_class": "aKU", "aHA": [74002], "cno": [72001]}
        )
        for language in ("en", "fr", "es"):
            ambiguous[4][language]["content.137.73001"] = "Renamed dungeon"
        rejected = batch.compile_batch(*ambiguous, reconstruct_native_aliases=True)
        self.assertEqual(rejected["qualified"], [])
        self.assertEqual(
            rejected["pending"][0]["reason"], "native_dungeon_boss_pair_not_unique"
        )

    def test_only_daily_missions_can_target_named_boss_in_multiple_boss_final_room(
        self,
    ):
        daily = list(candidate_fixture())
        other_boss = 72002
        daily[2]["monsters"].append(
            {"ref": other_boss, "raw_visual_arrays": {"csc": [43]}}
        )
        daily[1]["definitions"][0]["cno"].append(other_boss)
        daily[3][0]["configuration"]["compiled_plan"]["rooms"][0]["monsters"].append(
            {"ref_id": other_boss, "role": "boss", "count": 1}
        )
        daily_result = batch.compile_batch(*daily, reconstruct_native_aliases=True)
        daily_row = daily_result["qualified"][0]
        self.assertIn(
            "named-native-boss-occurrence-in-completed-multiple-boss-final-room",
            daily_row["proof"]["reviewed_binding_extensions"],
        )

        modulox = list(candidate_fixture(modulox=True))
        modulox[2]["monsters"].append(
            {"ref": other_boss, "raw_visual_arrays": {"csc": [43]}}
        )
        modulox[1]["definitions"][0]["cno"].append(other_boss)
        modulox[3][0]["configuration"]["compiled_plan"]["rooms"][0]["monsters"].append(
            {"ref_id": other_boss, "role": "boss", "count": 1}
        )
        modulox_result = batch.compile_batch(*modulox, reconstruct_native_aliases=True)
        self.assertEqual(modulox_result["qualified"], [])
        self.assertEqual(
            modulox_result["pending"][0]["reason"],
            "active_final_room_not_unique_strict_boss",
        )

    def test_plan_digest_uses_sorted_canonical_utf8_json(self):
        plan = {"ñ": "Café", "a": [1, 2]}
        canonical = json.dumps(
            plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
        self.assertEqual(batch.plan_digest(plan), sha256(canonical).hexdigest())
        self.assertEqual(
            batch.plan_digest(plan), batch.plan_digest({"a": [1, 2], "ñ": "Café"})
        )
        self.assertNotEqual(batch.plan_digest(plan), batch.digest(plan))


if __name__ == "__main__":
    unittest.main()
