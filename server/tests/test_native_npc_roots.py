"""Conditional native greetings reuse real nation/world authority for all guards."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from wakfu_server import native_npc_roots, quest_npc, npc_world
from wakfu_server.achievements import conversation_story_authoring

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "server/wakfu_server"


def fixtures():
    data = json.loads(
        (ROOT / "server/tests/fixtures/native_astrub_mercenary_guards.json").read_text()
    )
    manifest = json.loads(
        (
            BASE / "achievements/conversation_archetypes/astrub_mercenary_guards.json"
        ).read_text()
    )
    return data, manifest


def state(completed=False):
    return dict(
        running=[],
        completed=[2143] if completed else [],
        objectives=[],
        active=[2143] if completed else [],
        active_periods={},
    )


class NativeNpcRootTests(unittest.TestCase):
    def test_guard_manifest_compiles_idempotently_without_payment_or_npc_admission(
        self,
    ):
        data, manifest = fixtures()
        source = json.loads(
            (BASE / "maps/native_quest_conversation_contracts.json").read_text()
        )
        definitions = {2143: data["definition"]}
        nodes = {n["id"]: n for n in data["nodes"]}
        speakers = {s["ref"]: s for s in data["speakers"]}
        result = conversation_story_authoring.extend(
            source, definitions, nodes, speakers, manifest
        )
        self.assertEqual(
            result,
            conversation_story_authoring.extend(
                result, definitions, nodes, speakers, manifest
            ),
        )
        bindings = [b for b in result["bindings"] if b["quest_id"] == 2143]
        self.assertEqual(len(bindings), 8)
        self.assertEqual(
            {b["objective_id"] for b in bindings}, {4242, 4243, 4244, 4245}
        )
        self.assertEqual(result.get("turnins", []), source.get("turnins", []))
        actors = {s["actor_id"]: s for s in manifest["speakers"]}
        for placement in result["placements"]:
            if placement["row"]["actor_id"] not in actors:
                continue
            declaration = actors[placement["row"]["actor_id"]]
            self.assertEqual(
                placement["native_opening_roots"], declaration["native_opening_roots"]
            )
            self.assertEqual(placement["activation_policy"], "already_running")
            self.assertEqual(placement.get("available_quests_on_open", []), [])
            self.assertEqual(placement.get("choice_starts", []), [])

    def test_every_nation_uses_its_literal_native_guard_greeting_even_after_completion(
        self,
    ):
        data, manifest = fixtures()
        nodes = {n["id"]: n for n in data["nodes"]}
        nations = {1322: 30, 1324: 31, 1437: 32, 1592: 33}
        with patch.object(
            quest_npc.npc_dialogue, "catalog", return_value={"node_index": nodes}
        ):
            for declaration in manifest["speakers"]:
                guard_nation = nations[declaration["placement"]["row"]["reference_id"]]
                for nation in (0, 30, 31, 32, 33, 34):
                    for completed in (False, True):
                        with self.subTest(
                            guard=guard_nation, nation=nation, completed=completed
                        ):
                            actual = quest_npc._native_opening_root(
                                None,
                                dict(nation_id=nation, map_id=527),
                                declaration,
                                state(completed),
                            )
                            roots = declaration["native_opening_roots"]
                            self.assertEqual(
                                actual, roots[1] if nation == guard_nation else roots[0]
                            )

    def test_missing_or_malformed_owned_context_never_becomes_neutral_authority(self):
        data, manifest = fixtures()
        nodes = {n["id"]: n for n in data["nodes"]}
        with patch.object(
            quest_npc.npc_dialogue, "catalog", return_value={"node_index": nodes}
        ):
            for character in (
                dict(map_id=527),
                dict(map_id=527, nation_id=False),
                dict(map_id=527, nation_id=999),
                dict(nation_id=0),
                dict(map_id=546, nation_id=0),
            ):
                with self.subTest(character=character), self.assertRaises(ValueError):
                    quest_npc._native_opening_root(
                        None, character, manifest["speakers"][0], state()
                    )

    def test_ambiguous_or_unknown_roots_fail_closed_without_priority_guessing(self):
        nodes = {1: {"criteria": "True"}, 2: {"criteria": "True"}}
        for roots in ([1, 1], [True], [], [3]):
            with self.subTest(roots=roots), self.assertRaises(ValueError):
                native_npc_roots.validate(roots, nodes)
        for authority in (lambda _: True, lambda _: False, lambda _: 1):
            with self.assertRaises(ValueError):
                native_npc_roots.select([1, 2], nodes, available=authority)

    def test_native_open_requests_allow_only_same_actor_qualified_alternatives(self):
        _data, manifest = fixtures()
        declaration = manifest["speakers"][0]
        row = deepcopy(declaration["placement"]["row"])
        actor = row["actor_id"]
        normal = dict(speaker_type=2, speaker_id=actor, node_id=2154)
        alternative = dict(normal, node_id=2155)
        self.assertTrue(npc_world.matches_open_request(row, normal))
        self.assertFalse(npc_world.matches_open_request(row, alternative))
        placement = dict(row=deepcopy(row), native_opening_roots=[2154, 2155])
        row["_quest_publication"] = ({"placements": [placement]}, {}, {})
        self.assertTrue(npc_world.matches_open_request(row, alternative))
        # Stage roots are also exact reviewed roots for this same actor; the
        # owned begin handler still chooses the currently running stage.
        placement.pop("native_opening_roots")
        placement["running_roots"] = {"2143": 2155}
        self.assertTrue(npc_world.matches_open_request(row, alternative))
        for request in (
            dict(alternative, speaker_type=1),
            dict(alternative, speaker_id=actor - 1),
            dict(alternative, node_id=2156),
        ):
            with self.subTest(request=request):
                self.assertFalse(npc_world.matches_open_request(row, request))
        row["x"] += 1
        self.assertFalse(npc_world.matches_open_request(row, alternative))

    def test_authoring_cannot_replace_a_published_conditional_root_set(self):
        data, manifest = fixtures()
        source = json.loads(
            (BASE / "maps/native_quest_conversation_contracts.json").read_text()
        )
        definitions = {2143: data["definition"]}
        nodes = {n["id"]: n for n in data["nodes"]}
        speakers = {s["ref"]: s for s in data["speakers"]}
        result = conversation_story_authoring.extend(
            source, definitions, nodes, speakers, manifest
        )
        changed = deepcopy(manifest)
        changed["speakers"][0]["native_opening_roots"] = [2155]
        with self.assertRaisesRegex(ValueError, "replace native opening roots"):
            conversation_story_authoring.extend(
                result, definitions, nodes, speakers, changed
            )


if __name__ == "__main__":
    unittest.main()
