"""Source-only third-year registrar extension preserves native final authority."""

from copy import deepcopy
import gzip
import json
from pathlib import Path
import unittest

from tools.publish_conversation_archetypes import preserves
from wakfu_server.achievements import conversation_story_authoring
from wakfu_server import dungeon_criteria
from wakfu_server.dungeon_achievement_authority import queries_from_state


ROOT = Path(__file__).resolve().parents[1]


class SchoolYear3ConversationContractTests(unittest.TestCase):
    def test_additive_registrar_requires_all_actual_children_and_reconciled_objectives(
        self,
    ):
        before = json.loads(
            (
                ROOT / "wakfu_server/maps/native_quest_conversation_contracts.json"
            ).read_text()
        )
        declarations = json.loads(
            (
                ROOT
                / "wakfu_server/achievements/conversation_archetypes/huppermage_school_year3_registrar.json"
            ).read_text()
        )
        native = json.loads(
            (ROOT / "tests/fixtures/native_school_year3_definitions.json").read_text()
        )
        with gzip.open(
            ROOT.parent / "database/protocol/npc-dialogues.json.gz", "rt"
        ) as source:
            dialogues = json.load(source)
        nodes = {row["id"]: row for row in dialogues["nodes"]}
        speakers = {row["ref"]: row for row in dialogues["speakers"]}
        definitions = {row["d"]: row for row in native["definitions"]}
        unchanged = deepcopy(before)
        after = conversation_story_authoring.extend(
            before, definitions, nodes, speakers, declarations
        )
        self.assertEqual(unchanged, before)
        self.assertTrue(preserves(before, after))
        final = [row for row in after["bindings"] if row["quest_id"] == 2797]
        self.assertEqual(1, len(final))
        self.assertEqual(
            (5643, 3913, 722, 3309, 8328),
            tuple(
                final[0][key]
                for key in (
                    "objective_id",
                    "reference_id",
                    "action_id",
                    "node_id",
                    "choice_id",
                )
            ),
        )
        self.assertEqual(
            definitions[2797],
            next(row for row in after["definitions"] if row["d"] == 2797),
        )
        placement = next(
            row for row in after["placements"] if row["row"]["reference_id"] == 3913
        )
        guard = next(
            row["criterion"]
            for row in placement["choice_criteria"]
            if (row["node_id"], row["choice_id"]) == (3309, 8328)
        )
        ready = dict(
            variables={},
            objectives=[5646, 5647, 5648],
            running=[2797],
            completed=[2790, 2791, 2792],
            tracking=[],
            recent=[],
            completion_dates={},
        )
        native_guard = next(
            choice["criteria"]
            for choice in nodes[3309]["choices"]
            if choice["id"] == 8328
        )

        def offered(state):
            queries = queries_from_state(state)
            return all(
                dungeon_criteria.evaluate(
                    None, criterion, character=dict(level=130), queries=queries
                )
                for criterion in (native_guard, guard)
            )

        self.assertTrue(offered(ready))
        for missing in (2790, 2791, 2792):
            self.assertFalse(
                offered(
                    {
                        **ready,
                        "completed": [q for q in ready["completed"] if q != missing],
                    }
                )
            )
        for missing in (5646, 5647, 5648):
            self.assertFalse(
                offered(
                    {
                        **ready,
                        "objectives": [q for q in ready["objectives"] if q != missing],
                    }
                )
            )
        self.assertFalse(
            offered({**ready, "running": [], "completed": [*ready["completed"], 2797]})
        )
        self.assertEqual(
            after,
            conversation_story_authoring.extend(
                after, definitions, nodes, speakers, declarations
            ),
        )
