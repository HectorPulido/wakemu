"""Native story reconstruction and pre-mutation offered-choice authority."""

import copy
import gzip
import json
from pathlib import Path
import unittest

from wakfu_server import npc_dialogue, quest_npc
from wakfu_server.achievements import (
    conversation,
    conversation_authoring,
    conversation_story_authoring,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "server/wakfu_server/maps/native_quest_conversation_contracts.json"
MANIFEST = (
    ROOT
    / "server/wakfu_server/achievements/conversation_archetypes/native_story_deliveries.json"
)


class StoryConversationArchetypeTests(unittest.TestCase):
    def test_native_story_manifest_is_idempotent_and_preserves_exact_payments(self):
        document = json.loads(SOURCE.read_text())
        native = json.loads(
            gzip.decompress(
                (ROOT / "database/protocol/npc-dialogues.json.gz").read_bytes()
            )
        )
        definitions, bindings = conversation.validate_rules(document)
        result = conversation_story_authoring.extend(
            document,
            definitions,
            {node["id"]: node for node in native["nodes"]},
            {speaker["ref"]: speaker for speaker in native["speakers"]},
            json.loads(MANIFEST.read_text()),
        )
        self.assertEqual(result, document)
        forge = next(
            item
            for item in result["placements"]
            if item["row"]["actor_id"] == -2251799934992017
        )
        self.assertEqual(forge["interaction_anchor"], {"x": 4, "y": 49, "z": 0})
        self.assertEqual(
            (forge["row"]["x"], forge["row"]["y"], forge["row"]["z"]), (4, 50, 0)
        )
        missy = next(
            item for item in result["placements"] if item["row"]["reference_id"] == 2777
        )
        self.assertEqual(missy["interaction_anchor"], {"x": -37, "y": 2, "z": 3})
        self.assertEqual(
            (missy["row"]["x"], missy["row"]["y"], missy["row"]["z"]), (-36, 2, 3)
        )
        additions = [
            binding
            for binding in bindings.values()
            if binding.quest_id in (1109, 1112, 5277, 2017, 2019, 2025, 2026)
        ]
        self.assertEqual(len(additions), 10)
        payments = [
            row
            for row in document["turnins"]
            if row["reference_id"] in (5411, 2776, 2777)
        ]
        self.assertEqual(
            {(row["item_reference"], row["quantity"]) for row in payments},
            {(30775, 10), (24029, 700), (31592, 10), (18782, 5), (8414, 5)},
        )
        self.assertEqual(
            definitions[5277]["cjI"],
            "GetRealLevel() >= 216\r\nand IsAchievementComplete(5276)",
        )
        self.assertEqual(
            definitions[1112]["cjI"],
            "GetRealLevel() >= 100 and IsAchievementComplete(1111)",
        )

    def test_own_acceptance_may_invalidate_source_node_but_not_destination(self):
        for destination, allowed in ((0, True), (20, False), (10, False)):
            with self.subTest(destination=destination):
                state = {"active": False}
                node = {
                    "id": 10,
                    "criteria": "!IsAchievementActive(2158)",
                    "choices": [
                        {"id": 15249, "criteria": "!IsAchievementActive(2158)"}
                    ],
                }
                nodes = {10: node, 20: {"id": 20, "criteria": "False", "choices": []}}
                session = npc_dialogue.DialogueSession(
                    nodes,
                    {(10, 15249): destination},
                    authorize_node=lambda row: not state["active"]
                    if row["id"] == 10
                    else False,
                    authorize_choice=lambda _row: not state["active"],
                )
                session.open(10, 100, lambda *_args: True)
                request = dict(node_id=10, choice_id=15249)
                offered = quest_npc._offered_mutation_choice(session, request)
                state["active"] = True
                if allowed:
                    quest_npc._choose_after_mutation(session, request, offered)
                    self.assertIsNone(session.node_id)
                else:
                    with self.assertRaisesRegex(
                        ValueError, "unavailable dialogue node"
                    ):
                        quest_npc._choose_after_mutation(session, request, offered)
                self.assertFalse(session.authorize_node(node))
                self.assertFalse(session.authorize_choice(node["choices"][0]))

    def test_one_objective_active_predicate_cannot_name_multiple_possible_targets(self):
        criterion = "IsAchievementActive(1109) && !IsAchievementComplete(1109)"
        self.assertEqual(
            conversation_authoring.objective_predicates(
                criterion, 1109, {2046}, payment=False, single_objective=True
            ),
            (2046, None),
        )
        for expression, ids, identity in (
            (criterion, {2046, 999}, 1109),
            (criterion + " or True", {2046}, 1109),
            (criterion, {2046}, 1112),
        ):
            with self.subTest(
                expression=expression, identity=identity
            ), self.assertRaises(ValueError):
                conversation_authoring.objective_predicates(
                    expression, identity, ids, payment=False, single_objective=True
                )

    def test_new_npc_must_match_its_exact_native_marker_and_action(self):
        document = json.loads(SOURCE.read_text())
        definitions, _ = conversation.validate_rules(document)
        native = json.loads(
            gzip.decompress(
                (ROOT / "database/protocol/npc-dialogues.json.gz").read_bytes()
            )
        )
        nodes = {node["id"]: node for node in native["nodes"]}
        speakers = {speaker["ref"]: speaker for speaker in native["speakers"]}
        manifest = json.loads(MANIFEST.read_text())
        actor = -2251799934995277
        predecessor = copy.deepcopy(document)
        predecessor["placements"] = [
            row for row in predecessor["placements"] if row["row"]["actor_id"] != actor
        ]
        declaration = next(
            row for row in manifest["speakers"] if row["actor_id"] == actor
        )
        declaration["placement"]["row"]["x"] += 1
        with self.assertRaisesRegex(ValueError, "native marker"):
            conversation_story_authoring.extend(
                predecessor, definitions, nodes, speakers, manifest
            )

    def test_actual_offered_acceptance_survives_its_own_state_change_and_checks_target(
        self,
    ):
        state = {"active": False, "nearby": True}
        nodes = {
            1: {"id": 1, "choices": [{"id": 10, "criteria": "not active"}]},
            2: {"id": 2, "criteria": "active", "choices": []},
        }
        session = npc_dialogue.DialogueSession(
            nodes,
            {(1, 10): 2},
            authorize_node=lambda node: not node.get("criteria") or state["active"],
            authorize_choice=lambda _choice: not state["active"],
        )
        session.open(1, 20, lambda actor, _node: actor == 20 and state["nearby"])
        request = dict(node_id=1, choice_id=10)
        offered = quest_npc._offered_mutation_choice(session, request)
        state["active"] = True
        with self.assertRaisesRegex(ValueError, "not offered"):
            session.choose(**request)
        packet = quest_npc._choose_after_mutation(session, request, offered)
        self.assertEqual(packet[0], npc_dialogue.NODE_RESPONSE)
        self.assertEqual(session.node_id, 2)
        self.assertFalse(session.authorize_choice(nodes[1]["choices"][0]))

    def test_cached_choice_does_not_bypass_a_changed_speaker_or_destination(self):
        state = {"nearby": True, "destination": True}
        nodes = {1: {"id": 1, "choices": [{"id": 10}]}, 2: {"id": 2, "choices": []}}
        for invalid in ("nearby", "destination"):
            with self.subTest(invalid=invalid):
                state.update(nearby=True, destination=True)
                session = npc_dialogue.DialogueSession(
                    nodes,
                    {(1, 10): 2},
                    authorize_node=lambda node: node["id"] != 2 or state["destination"],
                )
                session.open(1, 20, lambda _actor, _node: state["nearby"])
                request = dict(node_id=1, choice_id=10)
                offered = quest_npc._offered_mutation_choice(session, request)
                state[invalid] = False
                with self.assertRaises(ValueError):
                    quest_npc._choose_after_mutation(session, request, offered)

    def test_item_absence_is_not_a_payment_and_reward_can_change_its_own_guard(self):
        criterion = "IsAchievementRunning(2026) && GetItemQuantity(18631) == 0"
        self.assertEqual(
            conversation_authoring.objective_predicates(
                criterion,
                2026,
                {4101},
                payment=False,
                single_objective=True,
                item_absence_guard=True,
            ),
            (4101, None),
        )
        for expression, enabled in (
            (criterion, False),
            (criterion.replace("== 0", ">= 0"), True),
        ):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                conversation_authoring.objective_predicates(
                    expression,
                    2026,
                    {4101},
                    payment=False,
                    single_objective=True,
                    item_absence_guard=enabled,
                )
        state = dict(running=True, quantity=0)
        nodes = {
            2301: {"id": 2301, "choices": [{"id": 6516, "criteria": criterion}]},
            2714: {"id": 2714, "choices": []},
        }
        session = npc_dialogue.DialogueSession(
            nodes,
            {(2301, 6516): 2714},
            authorize_choice=lambda _choice: state["running"]
            and state["quantity"] == 0,
        )
        session.open(2301, 20, lambda *_args: True)
        request = dict(node_id=2301, choice_id=6516)
        offered = quest_npc._offered_mutation_choice(session, request)
        state.update(running=False, quantity=1)
        quest_npc._choose_after_mutation(session, request, offered)
        self.assertEqual(session.node_id, 2714)
        self.assertFalse(session.authorize_choice(nodes[2301]["choices"][0]))


if __name__ == "__main__":
    unittest.main()
