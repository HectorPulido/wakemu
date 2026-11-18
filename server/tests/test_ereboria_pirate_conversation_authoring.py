"""Native Active guards gain only an explicit reviewed running selector."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from wakfu_server.achievements import conversation_story_authoring


class EreboriaPirateConversationAuthoringTests(unittest.TestCase):
    def inputs(self):
        root = Path(__file__).resolve().parents[1]
        fixture = json.loads(
            (
                Path(__file__).parent / "fixtures/native_ereboria_pirate_followups.json"
            ).read_text()
        )
        manifest = json.loads(
            (
                root
                / "wakfu_server/achievements/conversation_archetypes/ereboria_pirate_investigation.json"
            ).read_text()
        )
        source = dict(
            schema="native-quest-conversation-contracts-v1",
            admission_policy="reconstructed_wakemu_qualified_talk_v1",
            native_source_sha256={"fixture": "a" * 64},
            definitions=[d for d in fixture["definitions"] if d["d"] == 5044],
            placements=[fixture["placement"]],
            bindings=[],
        )
        return (
            source,
            {d["d"]: d for d in fixture["definitions"]},
            {d["id"]: d for d in fixture["nodes"]},
            {d["ref"]: d for d in fixture["speakers"]},
            manifest,
        )

    def test_native_active_path_is_retained_with_explicit_running_selector(self):
        inputs = self.inputs()
        nodes = deepcopy(inputs[2])
        result = conversation_story_authoring.extend(*inputs)
        self.assertEqual(inputs[2], nodes)
        self.assertEqual(
            {
                (b["quest_id"], b["objective_id"], b["choice_id"])
                for b in result["bindings"]
            },
            {(5045, 10390, 12938), (5046, 10398, 12944)},
        )
        guards = result["placements"][0]["choice_criteria"]
        for quest, choice in ((5045, 12938), (5046, 12944)):
            guard = next(g["criterion"] for g in guards if g["choice_id"] == choice)
            self.assertIn(f"IsAchievementActive({quest})", guard)
            self.assertIn(f"IsAchievementRunning({quest})", guard)
        self.assertEqual(
            conversation_story_authoring.extend(result, *inputs[1:]), result
        )

    def test_implicit_or_foreign_running_authority_is_rejected(self):
        for selector in (None, 5046):
            inputs = self.inputs()
            entry = inputs[-1]["speakers"][0]["objectives"][0]
            if selector is None:
                entry.pop("running_branch")
            else:
                entry["running_branch"] = selector
            with self.subTest(selector=selector), self.assertRaises(ValueError):
                conversation_story_authoring.extend(*inputs)

    def test_reviewed_selector_cannot_authorize_an_unrelated_native_choice(self):
        inputs = self.inputs()
        choice = next(c for c in inputs[2][5541]["choices"] if c["id"] == 12936)
        choice["criteria"] = "GetRealLevel() >= 36"
        with self.assertRaises(ValueError):
            conversation_story_authoring.extend(*inputs)
