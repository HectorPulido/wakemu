"""Exclusive native quest variants share a choice without implicit priority."""
from copy import deepcopy
from pathlib import Path
import json
import unittest
from unittest.mock import patch

from wakfu_server import quest_npc
from wakfu_server.achievements import conversation, conversation_story_authoring


def fixture():
    data = json.loads(
        (
            Path(__file__).parent / "fixtures/native_kelba_exclusive_intros.json"
        ).read_text()
    )
    definitions = {d["d"]: d for d in data["definitions"]}
    nodes = {n["id"]: n for n in data["nodes"]}
    row = dict(
        actor_id=-2251799934962534,
        reference_id=1147,
        map_id=943,
        instance_id=0,
        x=-99,
        y=0,
        z=-47,
        direction=3,
        dialogue_root=278,
        action_ids=[61],
        interaction_range=4,
        enabled=True,
        provenance=quest_npc.PREFIX + " reviewed native Kelba introduction fixture",
    )
    placement = dict(
        quest_id=2534, activation_policy="already_running", row=row, graph=[]
    )
    manifest = dict(
        schema="native-story-conversations-v1",
        speakers=[
            dict(
                actor_id=row["actor_id"],
                action_id=61,
                quest_ids=[2534, 2533],
                available_quests_on_open=[],
                native_marker=dict(quest_id=2534, objective_id=5090),
                placement=placement,
                graph=[[278, 7687, 0]],
                objectives=[
                    dict(
                        quest_id=q,
                        objective_id=o,
                        node_id=278,
                        choice_id=7687,
                        archetype="talk",
                        single_objective=True,
                        running_branch=q,
                        branch_binding=True,
                    )
                    for q, o in ((2534, 5090), (2533, 5089))
                ],
            )
        ],
    )
    source = dict(
        schema="native-quest-conversation-contracts-v1",
        admission_policy="reconstructed_wakemu_qualified_talk_v1",
        native_source_sha256={"fixture": "a" * 64},
        definitions=[],
        placements=[],
        bindings=[],
    )
    result = conversation_story_authoring.extend(
        source, definitions, nodes, {s["ref"]: s for s in data["speakers"]}, manifest
    )
    return data, definitions, nodes, manifest, result


class ConditionalConversationBindingTests(unittest.TestCase):
    def test_native_exclusive_branches_compile_additively_and_idempotently(self):
        data, definitions, nodes, manifest, result = fixture()
        self.assertEqual(len(result["bindings"]), 1)
        self.assertEqual(len(result["alternative_bindings"]), 1)
        self.assertEqual(result["definitions"], [definitions[q] for q in (2534, 2533)])
        self.assertEqual(result["placements"][0].get("choice_criteria", []), [])
        self.assertEqual(
            result,
            conversation_story_authoring.extend(
                result,
                definitions,
                nodes,
                {s["ref"]: s for s in data["speakers"]},
                manifest,
            ),
        )

    def publication(self, result, data, nodes):
        class DB:
            def execute(self, *_args):
                return self

            def fetchone(self):
                return {"value": result}

        with patch.object(
            quest_npc,
            "source_contract_digest",
            return_value=conversation._digest(result),
        ), patch.object(
            quest_npc.npc_dialogue,
            "catalog",
            return_value={"node_index": nodes, "speakers": data["speakers"]},
        ):
            return quest_npc.publication(DB())

    def test_runtime_selects_only_actual_running_branch_and_never_prioritizes(self):
        data, _, nodes, _, result = fixture()
        _, _, bindings = self.publication(result, data, nodes)
        key = (1147, 61, 278, 7687)
        for running in ([2533], [2534], [], [2533, 2534]):
            state = dict(
                running=running,
                completed=[],
                objectives=[],
                active=running,
                active_periods={},
            )
            if len(running) == 1:
                self.assertEqual(
                    quest_npc.select_binding(bindings, key, state).quest_id, running[0]
                )
            else:
                with self.assertRaises(ValueError):
                    quest_npc.select_binding(bindings, key, state)
        self.assertEqual(
            quest_npc.select_binding({key: bindings[key]}, key, None), bindings[key]
        )

    def test_foreign_quest_or_replaced_native_predicate_cannot_add_authority(self):
        data, _, nodes, _, result = fixture()
        for change in ("predicate", "duplicate", "placement"):
            with self.subTest(change=change):
                candidate, native = deepcopy(result), deepcopy(nodes)
                if change == "predicate":
                    next(c for c in native[278]["choices"] if c["id"] == 7687)[
                        "criteria"
                    ] = "IsAchievementRunning(2534)"
                elif change == "duplicate":
                    candidate["alternative_bindings"].append(
                        candidate["alternative_bindings"][0]
                    )
                else:
                    candidate["alternative_bindings"][0]["placement_sha256"] = "b" * 64
                with self.assertRaises(ValueError):
                    self.publication(candidate, data, native)

    def test_same_native_npc_in_two_contexts_uses_actual_placement_before_running_branch(
        self,
    ):
        data, definitions, nodes, manifest, result = fixture()
        second = deepcopy(result["placements"][0])
        second["row"].update(
            actor_id=second["row"]["actor_id"] - 1, map_id=945, x=3, y=1, z=0
        )
        second["graph"] = []
        result["placements"].append(second)
        declaration = deepcopy(manifest)
        speaker = declaration["speakers"][0]
        speaker["actor_id"] = second["row"]["actor_id"]
        speaker["placement"] = deepcopy(second)
        speaker["quest_ids"] = [2534]
        speaker["objectives"] = [speaker["objectives"][0]]
        result = conversation_story_authoring.extend(
            result,
            definitions,
            nodes,
            {s["ref"]: s for s in data["speakers"]},
            declaration,
        )
        _, _, bindings = self.publication(result, data, nodes)
        key = (1147, 61, 278, 7687)
        signature = conversation.placement_signature(second["row"])
        state = dict(
            running=[2534],
            completed=[],
            objectives=[],
            active=[2534],
            active_periods={},
        )
        self.assertEqual(
            quest_npc.select_binding(
                bindings, key, state, placement_sha256=signature
            ).placement_sha256,
            signature,
        )
        with self.assertRaises(ValueError):
            quest_npc.select_binding(bindings, key, state)
        state.update(running=[2533], active=[2533])
        with self.assertRaises(ValueError):
            quest_npc.select_binding(bindings, key, state, placement_sha256=signature)
