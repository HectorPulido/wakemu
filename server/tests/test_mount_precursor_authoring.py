"""Reviewed precursor fragments must preserve real missing prerequisites."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from wakfu_server import npc_dialogue, quest_npc
from wakfu_server.achievements import (
    conversation,
    conversation_authoring,
    conversation_story_authoring,
    mission_toolkit_contract,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = (
    ROOT
    / "server/wakfu_server/achievements/conversation_archetypes/astrub_mount_precursors.json"
)


class MountPrecursorAuthoringTests(unittest.TestCase):
    def compile(self, manifest=None):
        document = json.loads(
            (
                ROOT
                / "server/wakfu_server/maps/native_quest_conversation_contracts.json"
            ).read_text()
        )
        definitions, _ = conversation.validate_rules(document)
        definitions.update(
            {
                d["d"]: d
                for d in json.loads(
                    (
                        ROOT
                        / "server/tests/fixtures/native_mount_precursor_definitions.json"
                    ).read_text()
                )["definitions"]
            }
        )
        native = npc_dialogue.catalog()
        declaration = json.loads(MANIFEST.read_text()) if manifest is None else manifest
        return (
            conversation_story_authoring.extend(
                document,
                definitions,
                native["node_index"],
                {s["ref"]: s for s in native["speakers"]},
                declaration,
            ),
            definitions,
            native,
            declaration,
        )

    def test_fragment_is_idempotent_and_only_bag_is_paid(self):
        result, definitions, native, manifest = self.compile()
        self.assertEqual(
            result,
            conversation_story_authoring.extend(
                result,
                definitions,
                native["node_index"],
                {s["ref"]: s for s in native["speakers"]},
                manifest,
            ),
        )
        payments = [
            p for p in result["turnins"] if p["reference_id"] in (2622, 2805, 2775)
        ]
        self.assertEqual(
            [
                (p["node_id"], p["choice_id"], p["item_reference"], p["quantity"])
                for p in payments
            ],
            [(2315, 6534, 18689, 1)],
        )
        melmac = next(
            p for p in result["placements"] if p["row"]["reference_id"] == 2622
        )
        self.assertEqual(melmac["available_quests_on_open"], [2013, 2018, 2027])
        self.assertIn("GetRealLevel() >= 35", melmac["opening_quest_criteria"]["2013"])
        self.assertEqual(melmac["choice_starts"][0]["quest_id"], 2015)
        yeast = next(
            p for p in result["placements"] if p["row"]["reference_id"] == 2775
        )
        self.assertIn(
            "IsAchievementObjectiveComplete(4084)",
            yeast["choice_criteria"][0]["criterion"],
        )
        self.assertEqual(yeast["interaction_anchor"], {"x": 25, "y": -35, "z": 4})
        self.assertFalse(
            any(
                b["quest_id"] == 2016 and b["objective_id"] == 4084
                for b in result["bindings"]
            )
        )

    def test_native_branch_is_explicit_and_other_running_branch_is_not_inferred(self):
        expression = "(IsAchievementRunning(2013) or IsAchievementRunning(5594)) and GetInstanceId() <> 879"
        with self.assertRaises(ValueError):
            conversation_authoring.objective_predicates(
                expression, 2013, {4073}, payment=False, single_objective=True
            )
        self.assertEqual(
            conversation_authoring.objective_predicates(
                expression,
                2013,
                {4073},
                payment=False,
                single_objective=True,
                running_branch=2013,
            ),
            (4073, None),
        )
        with self.assertRaises(ValueError):
            conversation_authoring.objective_predicates(
                expression,
                2013,
                {4073},
                payment=False,
                single_objective=True,
                running_branch=5594,
            )

    def test_parent_book_links_validate_native_quests_and_do_not_emit_items(self):
        _, definitions, _, _ = self.compile()
        profile = json.loads(
            (
                ROOT
                / "server/wakfu_server/achievements/mission_profiles/astrub-mount-books.json"
            ).read_text()
        )
        mission_toolkit_contract.validate(profile, definitions)
        self.assertEqual(profile["bindings"], [])
        self.assertEqual(profile["activations"], [])
        self.assertEqual(
            [
                (r["parent_quest_id"], r["objective_id"], r["child_quest_id"])
                for r in profile["links"]
            ],
            [(2015, 4076, 2048), (2015, 4077, 2016), (2015, 4078, 2017)],
        )

    def test_publication_validates_all_reviewed_start_guards(self):
        document, _, native, _ = self.compile()

        class Connection:
            def execute(self, *_args):
                return self

            def fetchone(self):
                return {"value": document}

        with patch.object(
            quest_npc,
            "source_contract_digest",
            return_value=conversation._digest(document),
        ):
            quest_npc.publication(Connection())
            declaration = next(
                p for p in document["placements"] if p["row"]["reference_id"] == 2622
            )["choice_starts"][0]
            declaration["quest_id"] = 9999999
            with patch.object(
                quest_npc,
                "source_contract_digest",
                return_value=conversation._digest(document),
            ):
                with self.assertRaises(ValueError):
                    quest_npc.publication(Connection())


if __name__ == "__main__":
    unittest.main()
