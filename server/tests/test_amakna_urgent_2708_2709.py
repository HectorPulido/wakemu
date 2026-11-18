"""One bounded urgent-room/report source contract; no gameplay mutation."""

from copy import deepcopy
import gzip
import json
from pathlib import Path
import unittest

from tools.publish_conversation_archetypes import preserves
from wakfu_server import owned_story_controller, dungeon_criteria
from wakfu_server.achievements import conversation_story_authoring
from wakfu_server.dungeon_achievement_authority import queries_from_state


ROOT = Path(__file__).resolve().parents[1]


class AmaknaUrgentContractTests(unittest.TestCase):
    def test_native_timed_entry_owned_victory_and_separate_report_preserve_native_rewards(
        self,
    ):
        directory = ROOT / "wakfu_server/maps/owned_story_profiles"
        profile = json.loads((directory / "amakna-urgent-1005.json").read_text())
        manifest = json.loads(
            (directory / "amakna-urgent-1005.instance.json").read_text()
        )
        configuration = json.loads(
            (directory / "amakna-urgent-1005.configuration.json").read_text()
        )
        fixture = json.loads(
            (ROOT / "tests/fixtures/native_amakna_urgent_2708_2709.json").read_text()
        )
        definitions = {row["d"]: row for row in fixture["definitions"]}
        self.assertEqual(manifest["entry"]["source"]["id"], 25481)
        group = manifest["entry"]["program"]["groups"][0]
        self.assertEqual(group["cog"], 3000)
        effect = next(
            effect
            for effect in group["actions"][0]["effects"]
            if effect["action_reference"] == 2410
        )
        self.assertEqual(effect["parameters"], ["{-7,-9,0}", "1005", "7"])
        self.assertEqual(effect["criterion"], manifest["native_entry_criterion"])
        self.assertEqual(profile, configuration["topology"]["owned_story_controller"])
        self.assertIsNone(profile["admission"]["objective_id"])
        selected = owned_story_controller.policy(configuration)
        self.assertEqual(
            [],
            owned_story_controller.plan(
                selected, set(), kind="world_ready", reference=1005
            )["effects"],
        )
        self.assertIsNone(
            owned_story_controller.plan(
                selected, set(), kind="room_victory", reference=1
            )
        )
        self.assertIsNone(
            owned_story_controller.plan(
                selected, {"urgent-ready"}, kind="room_defeat", reference=1
            )
        )
        victory = owned_story_controller.plan(
            selected, {"urgent-ready"}, kind="room_victory", reference=1
        )
        self.assertEqual(
            [dict(kind="quest_objective", quest_id=2708, objective_id=5343)],
            victory["effects"],
        )
        self.assertIsNone(
            owned_story_controller.plan(
                selected,
                {"urgent-ready", "urgent-victory"},
                kind="room_victory",
                reference=1,
            )
        )
        roster = configuration["compiled_plan"]["rooms"][0]["monsters"]
        self.assertEqual(
            [(3813, 2), (3835, 2)], [(row["ref_id"], row["count"]) for row in roster]
        )
        self.assertEqual(
            (50, 101),
            tuple(
                fixture["monsters"][str(ref)]["statistics"]["HP"]["base"]
                for ref in (3813, 3835)
            ),
        )
        self.assertIn(
            5489,
            [
                row["spell_id"]
                for row in fixture["monsters"]["3813"]["native_abilities"]
            ],
        )

        before = json.loads(
            (
                ROOT / "wakfu_server/maps/native_quest_conversation_contracts.json"
            ).read_text()
        )
        declaration = json.loads(
            (
                ROOT
                / "wakfu_server/achievements/conversation_archetypes/amakna_urgent_report_2709.json"
            ).read_text()
        )
        with gzip.open(
            ROOT.parent / "database/protocol/npc-dialogues.json.gz", "rt"
        ) as stream:
            dialogues = json.load(stream)
        nodes = {row["id"]: row for row in dialogues["nodes"]}
        speakers = {row["ref"]: row for row in dialogues["speakers"]}
        frozen = deepcopy(before)
        after = conversation_story_authoring.extend(
            before, definitions, nodes, speakers, declaration
        )
        self.assertEqual(frozen, before)
        self.assertTrue(preserves(before, after))
        bindings = [row for row in after["bindings"] if row["quest_id"] in (2708, 2709)]
        self.assertEqual(
            [(2709, 5344, 3819, 703, 3225, 8083)],
            [
                tuple(
                    row[key]
                    for key in (
                        "quest_id",
                        "objective_id",
                        "reference_id",
                        "action_id",
                        "node_id",
                        "choice_id",
                    )
                )
                for row in bindings
            ],
        )
        for quest in (2708, 2709):
            self.assertEqual(
                definitions[quest],
                next(row for row in after["definitions"] if row["d"] == quest),
            )
            self.assertEqual([3000], definitions[quest]["cjK"][0]["ckl"])
        guard = next(
            row["criteria"] for row in nodes[3225]["choices"] if row["id"] == 8083
        )
        state = dict(
            variables={},
            objectives=[],
            running=[2709],
            completed=[2708],
            tracking=[],
            recent=[],
            completion_dates={},
        )
        self.assertTrue(
            dungeon_criteria.evaluate(
                None, guard, character=dict(level=20), queries=queries_from_state(state)
            )
        )
        self.assertFalse(
            dungeon_criteria.evaluate(
                None,
                guard,
                character=dict(level=20),
                queries=queries_from_state({**state, "running": []}),
            )
        )
        self.assertEqual(
            after,
            conversation_story_authoring.extend(
                after, definitions, nodes, speakers, declaration
            ),
        )
