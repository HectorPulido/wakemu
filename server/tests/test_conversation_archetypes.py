"""Delivery-chain compilation and deferred native follow-up behavior."""

import copy
import gzip
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from wakfu_server.achievements import conversation, conversation_authoring
from wakfu_server import quest_npc

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "server/wakfu_server/maps/native_quest_conversation_contracts.json"
MANIFEST = (
    ROOT
    / "server/wakfu_server/achievements/conversation_archetypes/otomai_hunter_followups.json"
)


class ConversationArchetypeTests(unittest.TestCase):
    def test_payment_predicate_rejects_ambiguity_and_never_infers_quantity(self):
        good = "GetItemQuantity(70)>=5 and IsAchievementRunning(12) and not IsAchievementObjectiveComplete(34)"
        self.assertEqual(
            conversation_authoring.objective_predicates(good, 12, {34}, payment=True),
            (34, (70, 5)),
        )
        for criterion in (
            good + " or True",
            good.replace(">=5", ">5"),
            good.replace("Running(12)", "Running(13)"),
            good + " and GetItemQuantity(71)>=1",
            good.replace("Complete(34)", "Complete(99)"),
        ):
            with self.subTest(criterion=criterion), self.assertRaises(ValueError):
                conversation_authoring.objective_predicates(
                    criterion, 12, {34}, payment=True
                )
        with self.assertRaises(ValueError):
            conversation_authoring.objective_predicates(good, 12, {34}, payment=False)

    def test_shipped_seven_followups_compile_idempotently_with_exact_native_payments(
        self,
    ):
        document = json.loads(SOURCE.read_text())
        native = json.loads(
            gzip.decompress(
                (ROOT / "database/protocol/npc-dialogues.json.gz").read_bytes()
            )
        )
        manifest = json.loads(MANIFEST.read_text())
        definitions, bindings = conversation.validate_rules(document)
        compiled = conversation_authoring.extend_delivery_chain(
            document,
            definitions,
            {node["id"]: node for node in native["nodes"]},
            manifest,
        )
        self.assertEqual(compiled, document)
        identities = {entry["quest_id"] for entry in manifest["quests"]}
        added = [
            binding for binding in bindings.values() if binding.quest_id in identities
        ]
        payments = [
            row
            for row in document["turnins"]
            if any(
                (binding.node_id, binding.choice_id)
                == (row["node_id"], row["choice_id"])
                for binding in added
            )
        ]
        self.assertEqual(len(added), 29)
        self.assertEqual(len(payments), 28)
        self.assertEqual(
            {binding.objective_id for binding in added if binding.quest_id == 4733},
            {9843, 9836, 9838, 9840, 9842},
        )
        self.assertIn("IsAchievementComplete(1707)", definitions[2869]["cjI"])

    def test_followup_defers_native_prerequisite_without_losing_predecessor(self):
        published = (
            {
                "placements": [],
                "activation_links": [{"after_quest": 11, "start_quest": 12}],
            },
            {12: {"d": 12}},
            {},
        )
        with patch.object(quest_npc, "_activate", return_value=[]) as activate:
            result = quest_npc._followups(
                None, None, {"id": 1}, {"actor_id": 2}, published, completed=[11]
            )
        self.assertEqual(result, [])
        self.assertTrue(activate.call_args.kwargs["defer_unavailable"])
        with patch.object(
            quest_npc.storage, "load_locked", return_value={"completed": [11]}
        ), patch.object(quest_npc, "_activate") as activate:
            quest_npc._followups(None, None, {"id": 1}, {"actor_id": 2}, published)
        activate.assert_not_called()

    def test_reopening_npc_retries_only_its_chain_and_selects_real_objective_branch(
        self,
    ):
        document = json.loads(SOURCE.read_text())
        definitions, bindings = conversation.validate_rules(document)
        item = next(
            row for row in document["placements"] if row["row"]["reference_id"] == 2873
        )
        completed = [1695, 1708, 1715, 1717, 1719]
        with patch.object(
            quest_npc.storage, "load_locked", return_value={"completed": completed}
        ), patch.object(quest_npc, "_activate", return_value=[]) as activate:
            quest_npc._followups(
                None, None, {"id": 1}, item["row"], (document, definitions, bindings)
            )
        self.assertIn(2869, [call.args[4]["d"] for call in activate.call_args_list])
        state = {"running": [4733], "completed": [], "objectives": []}
        for completed_talk, root in ((False, 3451), (True, 4814)):
            with patch.object(
                quest_npc,
                "_criterion",
                side_effect=lambda _s, _c, criterion, _a: completed_talk
                != criterion.startswith("not "),
            ):
                self.assertEqual(quest_npc._running_root(None, {}, item, state), root)
        with patch.object(
            quest_npc, "_criterion", return_value=True
        ), self.assertRaises(ValueError):
            quest_npc._running_root(None, {}, item, state)

    def test_publication_upgrade_cannot_replace_a_payment_or_existing_placement(self):
        from tools.publish_conversation_archetypes import preserves

        document = json.loads(SOURCE.read_text())
        previous = copy.deepcopy(document)
        removed = {
            entry["quest_id"] for entry in json.loads(MANIFEST.read_text())["quests"]
        }
        previous["definitions"] = [
            row for row in previous["definitions"] if row["d"] not in removed
        ]
        self.assertTrue(preserves(previous, document))
        changed = copy.deepcopy(document)
        changed["turnins"][0]["quantity"] += 1
        self.assertFalse(preserves(document, changed))
        changed = copy.deepcopy(document)
        changed["placements"][0]["row"]["x"] += 1
        self.assertFalse(preserves(document, changed))


if __name__ == "__main__":
    unittest.main()
