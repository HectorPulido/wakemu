"""Regression checks for unreachable and falsely generated dungeon encounters."""
import copy
import unittest
from server.tools.validate_dungeon_flow_rosters import validate


class DungeonFlowRosterTests(unittest.TestCase):
    def setUp(self):
        cells = [[x, 0, 0] for x in range(6)]
        edges = []
        for a, b in zip(cells, cells[1:]):
            edges.extend([(a, b), (b, a)])
        self.geometry = {"map_id": 1, "cells": cells, "edges": edges}
        self.config = {
            "topology": {
                "asset_map_id": 1,
                "rooms": [
                    {"order": 1, "anchor": [0, 0, 0], "cells": cells[:3]},
                    {"order": 2, "anchor": [4, 0, 0], "cells": cells[4:]},
                ],
                "physical_doors": [
                    {"source_room": 1, "destination_room": 2, "position": [3, 0, 0]}
                ],
            },
            "compiled_plan": {
                "official": False,
                "roster_policy_evidence": {"boss_references": [9]},
                "rooms": [
                    {"order": 1, "monsters": [{"ref_id": 2, "count": 1}]},
                    {"order": 2, "monsters": [{"ref_id": 9, "count": 1}]},
                ],
            },
        }

    @staticmethod
    def formation(geometry, anchor, quantity, **kwargs):
        return [c for c in geometry["cells"] if c != list(anchor)][:quantity]

    def test_stage_opens_prior_gate_without_moving_entry(self):
        result = validate(self.config, self.geometry, self.geometry, self.formation)
        self.assertEqual(result["status"], "candidate_validated")
        self.assertEqual(result["rooms"][1]["boss_count"], 1)

    def test_disconnected_anchor_cannot_be_accepted_by_nearness(self):
        geometry = dict(self.geometry, edges=self.geometry["edges"][:-2])
        config = copy.deepcopy(self.config)
        config["topology"]["rooms"][1]["anchor"] = [5, 0, 0]
        result = validate(config, geometry, self.geometry, self.formation)
        self.assertEqual(result["status"], "unsupported")
        self.assertTrue(any("not_reachable" in r for r in result["reasons"]))

    def test_early_and_duplicate_generated_bosses_are_rejected(self):
        config = copy.deepcopy(self.config)
        config["compiled_plan"]["rooms"][0]["monsters"] = [{"ref_id": 9, "count": 8}]
        result = validate(config, self.geometry, self.geometry, self.formation)
        self.assertTrue(any("early_room" in r for r in result["reasons"]))
        self.assertTrue(any("duplicate_generated_boss" in r for r in result["reasons"]))

    def test_formation_cannot_publish_monsters_outside_its_room(self):
        result = validate(
            self.config,
            self.geometry,
            self.geometry,
            lambda *args, **kwargs: [[99, 0, 0]],
        )
        self.assertEqual(result["status"], "unsupported")
        self.assertTrue(any("leaves_reachable_room" in r for r in result["reasons"]))

    def test_reviewed_composition_is_not_reclassified_as_generated(self):
        config = copy.deepcopy(self.config)
        config["compiled_plan"]["official"] = True
        result = validate(config, self.geometry, self.geometry, self.formation)
        self.assertEqual(
            result["rooms"][0]["roster_authority"], "preserved_reviewed_composition"
        )

    def test_geometrically_valid_roster_with_unresolved_species_is_rejected(self):
        config = copy.deepcopy(self.config)
        config["compiled_plan"]["rooms"][0]["monsters"][0]["ref_id"] = None
        result = validate(config, self.geometry, self.geometry, self.formation)
        self.assertEqual(result["status"], "unsupported")
        self.assertTrue(
            any("unresolved_native_monster_identity" in r for r in result["reasons"])
        )
        self.assertEqual(result["rooms"][0]["monster_positions"], [])

    def test_disconnected_transport_rooms_require_literal_prior_approach(self):
        config = copy.deepcopy(self.config)
        config["topology"]["policy"] = "native_teleport_victory_policy"
        config["topology"]["physical_doors"] = []
        config["topology"]["rooms"][0]["native_arrival"] = [0, 0, 0]
        config["topology"]["rooms"][1]["native_arrival"] = [4, 0, 0]
        config["topology"]["doors"] = [
            dict(
                source_room=1,
                destination_room=2,
                destination_position=[4, 0, 0],
                native_approach_cells=[[2, 0, 0]],
            )
        ]
        geometry = dict(
            self.geometry,
            edges=[e for e in self.geometry["edges"] if 3 not in (e[0][0], e[1][0])],
        )
        result = validate(config, geometry, geometry, self.formation)
        self.assertEqual(result["status"], "candidate_validated")
        config["topology"]["doors"][0]["native_approach_cells"] = [[99, 0, 0]]
        result = validate(config, geometry, geometry, self.formation)
        self.assertEqual(result["status"], "unsupported")
        self.assertTrue(any("approach_unreachable" in r for r in result["reasons"]))
