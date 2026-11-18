"""Offline authoring refuses ambiguous guards, random loot and false markers."""
from copy import deepcopy
import unittest

from tools import classify_native_quest_pickups as classifier


class NativeQuestPickupClassifierTests(unittest.TestCase):
    def test_literal_guards_require_conjunction_without_activation_inference(self):
        self.assertEqual(
            classifier.guards(
                "IsAchievementRunning(2048) and GetItemQuantity(18689) <= 0"
            )["quests"],
            [2048],
        )
        for expression in (
            "False and IsAchievementRunning(2048)",
            "IsAchievementRunning(1) or IsAchievementRunning(2)",
            "not IsAchievementRunning(2048)",
            "IsAchievementActive(2048)",
            "IsAchievementRunning(2048) and GetItemQuantity(1) > 0",
            "IsAchievementRunning(2048) and GetInstanceId() == 1122",
        ):
            with self.subTest(expression=expression):
                self.assertIsNone(classifier.guards(expression))
        self.assertEqual(
            classifier.guards(
                "IsAchievementRunning(2048)\r\nand IsAchievementObjectiveComplete(1)\r\nand not IsAchievementObjectiveComplete(2)"
            )["incomplete"],
            [2],
        )

    def test_loot_must_be_single_unconditional_deterministic_item(self):
        effect = dict(effect_type=4, parameters=["2435"])
        table = dict(
            d=2435,
            czg=1,
            gBN=[
                dict(
                    native_class="fFe",
                    d=3047,
                    aAi=18689,
                    bfh=1,
                    cmY=1.0,
                    cqA=False,
                    cqy=1,
                    cqz=1,
                    csE=1,
                    czk="",
                    czl=0,
                    gBO=[],
                )
            ],
        )
        self.assertEqual(
            classifier.deterministic_item(effect, {2435: table})["reference"], 18689
        )
        for key, value in (
            ("cqA", True),
            ("cmY", 0.5),
            ("cqz", 2),
            ("czk", "False"),
            ("gBO", [123]),
            ("czl", 1),
        ):
            bad = deepcopy(table)
            bad["gBN"][0][key] = value
            with self.subTest(key=key):
                self.assertIsNone(classifier.deterministic_item(effect, {2435: bad}))
        bad = deepcopy(table)
        bad["gBN"].append(deepcopy(bad["gBN"][0]))
        self.assertIsNone(classifier.deterministic_item(effect, {2435: bad}))

    def test_exact_unique_source_marker_is_review_only_and_displays_lowest_first(self):
        effect = dict(
            effect_type=12,
            parameters=["1", "1"],
            criterion="IsAchievementRunning(2048)",
            action_reference=123,
        )
        action = dict(native_id=497, wire_action=0, criterion="", effects=[effect])
        descriptor = dict(
            descriptor_id=447,
            groups=[dict(cod=0, coe=0, cnd=0, cog=0, actions=[action])],
        )
        source = dict(descriptor_id=447, id=23033, map_id=527, x=-121, y=64, z=0)
        native = dict(
            d=2048,
            cjP=35,
            cjJ=[dict(d=4135, ckd=[dict(ckj=527, ckg=-121, ckh=64, cki=0)])],
        )
        context = dict(definitions=[dict(definition_id=2048, data=dict(native=native))])

        def run(objects):
            return classifier.classify(
                dict(descriptors=[descriptor]), dict(tables=[]), objects, context
            )

        report = run([source])
        row = report["candidates"][0]
        self.assertEqual(row["status"], "source_qualified_review_candidate")
        self.assertEqual(row["published_activation_paths"], {})
        self.assertNotIn("bindings", report)
        self.assertEqual(run([dict(source, z=1)])["candidates"][0]["status"], "blocked")
        self.assertEqual(
            run([source, dict(source, id=23034)])["candidates"][0]["status"], "blocked"
        )
