"""Native node authority qualifies reviewed paths without weakening predicates."""

from copy import deepcopy
import unittest

from wakfu_server.achievements.conversation_authoring import objective_predicates
from wakfu_server.achievements.conversation_story_authoring import (
    native_objective_authority,
)


class NativeNodeQualifiedAuthoringTests(unittest.TestCase):
    def fixture(self):
        nodes = {
            3267: {
                "id": 3267,
                "criteria": "IsAchievementRunning(2702) && !IsAchievementComplete(2929) && GetInstanceId() != 1095",
                "choices": [{"id": 8066, "criteria": ""}],
            },
            3274: {
                "id": 3274,
                "criteria": "",
                "choices": [{"id": 8073, "criteria": ""}],
            },
        }
        path = [[3267, 8066, 3274], [3274, 8073, 0]]
        placement = {"row": {"dialogue_root": 3267}, "graph": []}
        declaration = {"graph": path}
        entry = {"native_guard_path": path}
        return nodes, path, placement, declaration, entry

    def test_inherited_guard_qualifies_one_objective_and_is_preserved_for_final_recheck(
        self,
    ):
        nodes, _, placement, declaration, entry = self.fixture()
        # Native dialogues can repeat the same running guard at the terminal.
        nodes[3274]["criteria"] = "IsAchievementRunning(2702)"
        original = deepcopy(nodes)
        expression, guard = native_objective_authority(
            entry, nodes[3274], nodes[3274]["choices"][0], nodes, placement, declaration
        )
        self.assertEqual(
            objective_predicates(
                expression, 2702, {5336}, payment=False, single_objective=True
            ),
            (5336, None),
        )
        self.assertIn(nodes[3267]["criteria"], guard)
        self.assertIn("GetInstanceId() != 1095", expression)
        self.assertEqual(nodes, original)

    def test_direct_node_guard_is_opt_in_and_unqualified_choice_stays_rejected(self):
        nodes, _, placement, declaration, _ = self.fixture()
        node = nodes[3267]
        for entry, succeeds in (({}, False), ({"native_node_qualified": True}, True)):
            expression, guard = native_objective_authority(
                entry, node, node["choices"][0], nodes, placement, declaration
            )
            if succeeds:
                self.assertEqual(
                    objective_predicates(
                        expression, 2702, {5336}, payment=False, single_objective=True
                    ),
                    (5336, None),
                )
            else:
                with self.assertRaises(ValueError):
                    objective_predicates(
                        expression, 2702, {5336}, payment=False, single_objective=True
                    )
                self.assertIsNone(guard)

    def test_unrelated_opening_cannot_bypass_inherited_authority(self):
        nodes, _, placement, declaration, entry = self.fixture()
        nodes[9] = {"id": 9, "criteria": "", "choices": [{"id": 8, "criteria": ""}]}
        placement["native_opening_roots"] = [9, 3267]
        declaration["graph"] = declaration["graph"] + [[9, 8, 3274]]
        with self.assertRaisesRegex(ValueError, "bypassed"):
            native_objective_authority(
                entry,
                nodes[3274],
                nodes[3274]["choices"][0],
                nodes,
                placement,
                declaration,
            )

    def test_choice_guard_on_path_is_inherited_and_same_opening_bypass_is_rejected(
        self,
    ):
        nodes, _, placement, declaration, entry = self.fixture()
        nodes[3267]["criteria"] = "GetInstanceId() != 1095"
        nodes[3267]["choices"][0]["criteria"] = "IsAchievementRunning(2702)"
        expression, guard = native_objective_authority(
            entry, nodes[3274], nodes[3274]["choices"][0], nodes, placement, declaration
        )
        self.assertEqual(
            objective_predicates(
                expression, 2702, {5336}, payment=False, single_objective=True
            ),
            (5336, None),
        )
        self.assertIn("IsAchievementRunning(2702)", guard)
        nodes[3267]["choices"].append({"id": 99, "criteria": ""})
        declaration["graph"] = declaration["graph"] + [[3267, 99, 3274]]
        with self.assertRaisesRegex(ValueError, "alternate predecessor"):
            native_objective_authority(
                entry,
                nodes[3274],
                nodes[3274]["choices"][0],
                nodes,
                placement,
                declaration,
            )

    def test_missing_edge_foreign_choice_and_unpublished_guard_fail_closed(self):
        for change in ("edge", "choice", "opening", "empty_guard"):
            with self.subTest(change=change):
                nodes, _, placement, declaration, entry = self.fixture()
                if change == "edge":
                    declaration["graph"] = []
                if change == "choice":
                    nodes[3267]["choices"] = []
                if change == "opening":
                    placement["row"]["dialogue_root"] = 99
                if change == "empty_guard":
                    nodes[3267]["criteria"] = ""
                with self.assertRaises(ValueError):
                    native_objective_authority(
                        entry,
                        nodes[3274],
                        nodes[3274]["choices"][0],
                        nodes,
                        placement,
                        declaration,
                    )

    def test_native_disjunction_cannot_create_single_quest_authority(self):
        nodes, _, placement, declaration, entry = self.fixture()
        nodes[3267][
            "criteria"
        ] = "IsAchievementRunning(2702) || IsAchievementRunning(2703)"
        expression, _ = native_objective_authority(
            entry, nodes[3274], nodes[3274]["choices"][0], nodes, placement, declaration
        )
        with self.assertRaises(ValueError):
            objective_predicates(
                expression, 2702, {5336}, payment=False, single_objective=True
            )


class ReviewedNativeSitePlacementTests(unittest.TestCase):
    def test_native_source_and_connected_floor_are_mandatory_without_claiming_a_marker(
        self,
    ):
        from wakfu_server.achievements.conversation_story_authoring import (
            validate_reviewed_site_placement,
        )

        declaration = {
            "reviewed_site_placement": {
                "source_id": 25603,
                "geometry_sha256": "a" * 64,
                "evidence": "Explicit reviewed scientist presence beside native temple source.",
            }
        }
        placement = {
            "row": {
                "map_id": 1003,
                "x": -9,
                "y": -5,
                "z": -15,
                "provenance": "wakemu.qualified-quest-conversation.v1: REVIEWED SITE-DERIVED RECONSTRUCTION",
            },
            "interaction_anchor": {"x": -9, "y": -4, "z": -15},
        }
        sources = {25603: {"id": 25603, "map_id": 1003}}
        floor = {
            1003: {
                "source_sha256": "a" * 64,
                "cells": [[-9, -5, -15], [-9, -4, -15], [-8, -4, -15]],
                "edges": [
                    [[-9, -4, -15], [-8, -4, -15]],
                    [[-8, -4, -15], [-9, -4, -15]],
                ],
            }
        }
        validate_reviewed_site_placement(declaration, placement, sources, floor)
        for change in (
            "missing_source",
            "foreign_map",
            "wrong_pin",
            "isolated",
            "false_marker",
        ):
            with self.subTest(change=change):
                candidate, candidate_sources, candidate_floor = (
                    deepcopy(placement),
                    deepcopy(sources),
                    deepcopy(floor),
                )
                if change == "missing_source":
                    candidate_sources.clear()
                if change == "foreign_map":
                    candidate_sources[25603]["map_id"] = 527
                if change == "wrong_pin":
                    candidate_floor[1003]["source_sha256"] = "b" * 64
                if change == "isolated":
                    candidate_floor[1003]["edges"] = []
                if change == "false_marker":
                    candidate["row"]["provenance"] = "native waypoint"
                with self.assertRaises(ValueError):
                    validate_reviewed_site_placement(
                        declaration, candidate, candidate_sources, candidate_floor
                    )
