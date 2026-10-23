"""Strict source joins, with numeric targets declared as Wakemu reconstruction."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "daily_hunter_target_compiler",
    ROOT / "server/tools/compile_daily_hunter_targets.py",
)
compiler = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compiler)


def inputs():
    objective = "Defeat Lokoko in the Kokokobana Dungeon"
    definition = dict(
        definition_id="4450",
        title_en="Boss Hunt: Lokoko",
        category_id="691",
        calendar_period_seconds="86400",
        calendar_anchor_ms="1475452800000",
        cooldown_seconds="0",
        repeatable="True",
        activation_criteria="",
        eligibility_criteria="",
        objectives=json.dumps([dict(d=9141, native_class="aJN")]),
        rewards=json.dumps(
            [
                dict(
                    reward_id=8302,
                    type_id=5,
                    parameters=[21001, 20],
                    raw_flag_ckk=False,
                ),
                dict(
                    reward_id=8303, type_id=6, parameters=[732590], raw_flag_ckk=False
                ),
            ]
        ),
    )
    observed = dict(
        definition_id=4450,
        objective_id=9141,
        title_en=definition["title_en"],
        title_fr="Chasse le Boss: Grokokolantha",
        native_objective_en=objective,
        public_direct_objective_rows=[
            dict(
                quest_title=definition["title_en"],
                objective=objective,
                minimum_level=51,
                url=compiler.PUBLIC_URL,
                receipt="source.json",
                source_sha256="c" * 64,
            )
        ],
    )
    return dict(
        definitions=[definition],
        observations=[observed],
        translations={
            "en": {"content.7.4731": "Lokoko"},
            "fr": {"content.7.4731": "Grokokolantha"},
            "es": {"content.7.4731": "Grokokolantha"},
        },
        configurations=[
            dict(
                route_key="native_dungeon_141",
                policy_version=2,
                route=dict(definition_id=141, start_map_id=295),
                evidence_hashes={"plan": "d" * 64},
                rooms=[dict(order=1, monsters=[dict(ref_id=4731, role="boss")])],
            )
        ],
        native_monsters=[
            dict(record_key="4731", reference=4731, name_es="Grokokolantha")
        ],
        revision="a" * 64,
        monsters_sha256="b" * 64,
        categories=[dict(id=691, labels={"en": "Boss Hunt [051-065]"})],
        original_dungeons=[dict(id=141, cno=[4731], aHA=[295])],
        original_dungeon_sha256="e" * 64,
    )


class DailyHunterTargetCompilerTests(unittest.TestCase):
    def test_source_qualified_target_keeps_exact_native_reward_order_and_declared_policy(
        self,
    ):
        result = compiler.compile_targets(**inputs())
        self.assertEqual(
            (result["counts"]["qualified"], result["counts"]["pending"]), (1, 0)
        )
        row = result["qualified"][0]
        self.assertEqual(
            (
                row["definition_id"],
                row["objective_id"],
                row["boss_reference"],
                row["dungeon_definition_id"],
            ),
            (4450, 9141, 4731, 141),
        )
        self.assertEqual(
            (row["minimum_level"], row["period_ms"], row["required_distinct"]),
            (51, 86400000, 1),
        )
        self.assertEqual(row["native_reward_order"], [8302, 8303])
        self.assertEqual(row["original_native_rewards"][0]["parameters"], [21001, 20])
        self.assertEqual(row["original_native_rewards"][1]["parameters"], [732590])
        self.assertTrue(
            all(r["raw_flag_ckk"] is False for r in row["original_native_rewards"])
        )
        self.assertEqual(row["derived_variable_name"], "wakemu.daily.boss.4731")
        self.assertIn("Wakemu_reconstruction", row["source_claim"])
        self.assertFalse(row["runtime_acceptance_active"])

    def test_duplicate_boss_names_require_one_original_dungeon_literal_species_and_final_role(
        self,
    ):
        value = inputs()
        value["translations"]["en"].update(
            {"content.7.99": "Lokoko", "content.137.141": "Kokokobana"}
        )
        value["translations"]["fr"].update(
            {"content.7.99": "Grokokolantha", "content.137.141": "Kokokolantha"}
        )
        self.assertEqual(
            compiler.compile_targets(**value)["qualified"][0]["boss_reference"], 4731
        )
        missing = deepcopy(value)
        missing["translations"]["en"]["content.137.141"] = "Another Dungeon"
        missing["translations"]["fr"]["content.137.141"] = "Autre donjon"
        self.assertEqual(compiler.compile_targets(**missing)["qualified"], [])
        ambiguous = deepcopy(value)
        ambiguous["original_dungeons"].append(dict(id=999, cno=[99], aHA=[295]))
        ambiguous["translations"]["en"]["content.137.999"] = "Kokokobana"
        self.assertEqual(compiler.compile_targets(**ambiguous)["qualified"], [])
        predicate = deepcopy(value)
        objective = json.loads(predicate["definitions"][0]["objectives"])
        objective[0]["cke"] = "A new original completion predicate"
        predicate["definitions"][0]["objectives"] = json.dumps(objective)
        self.assertEqual(compiler.compile_targets(**predicate)["qualified"], [])

    def test_name_only_wrong_room_map_catalog_or_public_level_cannot_authorize_a_target(
        self,
    ):
        variations = []
        value = inputs()
        value["observations"][0]["public_direct_objective_rows"] = []
        variations.append(value)
        value = inputs()
        value["observations"][0]["public_direct_objective_rows"][0][
            "objective"
        ] = "Another dungeon"
        variations.append(value)
        value = inputs()
        value["translations"]["en"]["content.7.99"] = "Lokoko"
        value["translations"]["fr"]["content.7.99"] = "Grokokolantha"
        variations.append(value)
        value = inputs()
        value["configurations"][0]["rooms"][0]["monsters"][0]["role"] = "monster"
        variations.append(value)
        value = inputs()
        value["configurations"].append(deepcopy(value["configurations"][0]))
        variations.append(value)
        value = inputs()
        value["native_monsters"][0]["name_es"] = "Unrelated"
        variations.append(value)
        value = inputs()
        value["original_dungeons"][0]["aHA"] = [999]
        variations.append(value)
        value = inputs()
        value["original_dungeons"].append(dict(id=999, cno=[4731], aHA=[295]))
        variations.append(value)
        value = inputs()
        value["observations"][0]["public_direct_objective_rows"][0]["minimum_level"] = 1
        variations.append(value)
        for variant in variations:
            with self.subTest(index=variations.index(variant)):
                result = compiler.compile_targets(**variant)
                self.assertEqual(result["qualified"], [])
                self.assertEqual(result["counts"]["pending"], 1)
