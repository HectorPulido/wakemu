"""Additive source compilation for Ereboria's final Cyross return."""

import copy
import gzip
import json
from pathlib import Path
import unittest

from wakfu_server.achievements import conversation_story_authoring

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "server/wakfu_server/maps/native_quest_conversation_contracts.json"
NATIVE_EXPORT = ROOT / ".runtime/quest-extraction/native-quest-definitions.json"
DIALOGUES = ROOT / "database/protocol/npc-dialogues.json.gz"
MANIFEST = (
    ROOT
    / "server/wakfu_server/achievements/conversation_archetypes/ereboria_parent_final_return.json"
)
ACTOR_ID = -2251799934995059


class EreboriaParentFinalReturnTests(unittest.TestCase):
    def test_final_return_compiles_additively_and_requires_earned_cire_momore(self):
        document = json.loads(SOURCE.read_text())
        predecessor = copy.deepcopy(document)
        existing_actor = next(
            row for row in document["placements"] if row["row"]["actor_id"] == ACTOR_ID
        )

        native = json.loads(NATIVE_EXPORT.read_text())
        definitions = {row["d"]: row for row in native["definitions"]}
        dialogues = json.loads(gzip.decompress(DIALOGUES.read_bytes()))
        node_index = {row["id"]: row for row in dialogues["nodes"]}
        speakers = {row["ref"]: row for row in dialogues["speakers"]}
        manifest = json.loads(MANIFEST.read_text())

        result = conversation_story_authoring.extend(
            document, definitions, node_index, speakers, manifest
        )
        compiled_actor = next(
            row for row in result["placements"] if row["row"]["actor_id"] == ACTOR_ID
        )
        self.assertEqual(compiled_actor["row"], existing_actor["row"])
        self.assertEqual(document, predecessor)

        bindings = [row for row in result["bindings"] if row["quest_id"] == 5059]
        self.assertTrue(any(row["objective_id"] == 10540 for row in bindings))
        self.assertFalse(any(row["objective_id"] == 10539 for row in bindings))
        final_binding = next(row for row in bindings if row["objective_id"] == 10540)
        self.assertEqual(
            (
                final_binding["reference_id"],
                final_binding["action_id"],
                final_binding["node_id"],
                final_binding["choice_id"],
            ),
            (5406, 1208, 5696, 13173),
        )

        placement = next(
            row for row in result["placements"] if row["row"]["actor_id"] == ACTOR_ID
        )
        self.assertIn([5598, 13174, 5696], placement["graph"])
        self.assertIn([5696, 13173, 0], placement["graph"])
        guard = next(
            row["criterion"]
            for row in placement["choice_criteria"]
            if row["node_id"] == 5696 and row["choice_id"] == 13173
        )
        self.assertIn("IsAchievementObjectiveComplete(10539)", guard)
        self.assertIn("IsAchievementRunning(5059)", guard)

        self.assertEqual(
            next(row for row in result["definitions"] if row["d"] == 5059)["cjK"],
            definitions[5059]["cjK"],
        )
        self.assertEqual(
            conversation_story_authoring.extend(
                result, definitions, node_index, speakers, manifest
            ),
            result,
        )


if __name__ == "__main__":
    unittest.main()
