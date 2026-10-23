import copy
from dataclasses import asdict
import unittest
from unittest.mock import patch

from wakfu_server.dungeon_instances import _load_routes
from wakfu_server.maps.dungeon_runtime_config import canonical_hash
from tools.materialize_local_dungeon_configs import POLICY, materialize


def native_route_payload(route):
    payload = asdict(route)
    if payload.get("native_template_id") is None:
        payload.pop("native_template_id", None)
    return payload


class MaterializeLocalDungeonConfigsTests(unittest.TestCase):
    def setUp(self):
        admission = patch(
            "wakfu_server.dungeon_monster_admission.current_policy",
            return_value={
                "schema": "native-npc-activation-v1",
                "enabled_monsters": {
                    "7001": {"min_level": 1, "max_level": 32767, "spell_ids": [549]}
                },
            },
        )
        admission.start()
        self.addCleanup(admission.stop)
        self.route = native_route_payload(_load_routes()["jalato_normal"])
        self.monster = {
            "name": "Native monster",
            "ref_id": 7001,
            "count": 2,
            "role": "monster",
            "native_min_level": 10,
            "native_max_level": 20,
            "guide_min_level": None,
            "guide_max_level": None,
        }
        self.draft = {
            "slug": "reviewed-guide",
            "definition_id": self.route["definition_id"],
            "official": False,
            "reviewed_official": False,
            "policy_mode": POLICY,
            "native_species_pool": [7001],
            "policy": {"requested_count": 2},
            "original_plan": {
                "source_url": "https://example.test/guide/",
                "source_sha256": "a" * 64,
                "document_sha256": "b" * 64,
                "definition_id": None,
                "template_id": None,
                "asset_map_id": None,
                "rooms": [{"order": 1, "monsters": [], "diagnostics": ["unresolved"]}],
            },
            "rooms": [
                {
                    "order": 1,
                    "policy_applied": True,
                    "generated_fields": ["count"],
                    "monsters": [copy.deepcopy(self.monster)],
                }
            ],
        }
        self.batch = {
            "policy_mode": POLICY,
            "official": False,
            "drafts": [self.draft],
            "excluded": [],
        }
        self.topology = {
            "asset_map_id": self.route["start_map_id"],
            "rooms": [{"order": 1, "anchor": [1, 2, 0], "cells": [[1, 2, 0]]}],
            "doors": [],
        }
        self.native = [
            {
                "ref": 7001,
                "min_level": 10,
                "max_level": 20,
                "native_abilities": [{"spell_id": 549}],
            }
        ]

    def materialize(self, *, batch=None, routes=None, topology=None, native=None):
        return materialize(
            self.batch if batch is None else batch,
            [self.route] if routes is None else routes,
            {"reviewed-guide": self.topology if topology is None else topology},
            self.native if native is None else native,
            version=1,
        )

    def test_preserves_original_guide_evidence_and_marks_local_provenance(self):
        before = copy.deepcopy(self.batch)
        bundle, coverage = self.materialize()

        self.assertEqual(self.batch, before)
        config = bundle["configurations"][0]
        plan = config["compiled_plan"]
        self.assertEqual(plan["source_url"], self.draft["original_plan"]["source_url"])
        self.assertEqual(
            plan["source_sha256"], self.draft["original_plan"]["source_sha256"]
        )
        self.assertEqual(
            plan["original_guide_document_sha256"],
            self.draft["original_plan"]["document_sha256"],
        )
        self.assertEqual(plan["document_sha256"], canonical_hash(self.draft))
        self.assertFalse(plan["official"])
        self.assertFalse(plan["reviewed_official"])
        self.assertEqual(plan["policy_mode"], POLICY)
        self.assertIn("official=false", config["provenance"])
        self.assertEqual(coverage["official"], False)
        self.assertEqual(coverage["runtime_imported"], False)

    def test_output_is_deterministic(self):
        first = self.materialize()
        second = self.materialize()
        self.assertEqual(first, second)

    def test_rejects_nonofficial_policy_drift(self):
        batch = copy.deepcopy(self.batch)
        batch["official"] = True
        with self.assertRaisesRegex(ValueError, "Explicit non-official"):
            self.materialize(batch=batch)

    def test_rejects_species_outside_explicit_native_pool(self):
        batch = copy.deepcopy(self.batch)
        batch["drafts"][0]["native_species_pool"] = [7002]
        with self.assertRaisesRegex(ValueError, "leaves native dungeon species pool"):
            self.materialize(batch=batch)

    def test_rejects_grade_bounds_that_disagree_with_native_species(self):
        batch = copy.deepcopy(self.batch)
        batch["drafts"][0]["rooms"][0]["monsters"][0]["native_max_level"] = 21
        with self.assertRaisesRegex(ValueError, "contradicts native monster bounds"):
            self.materialize(batch=batch)

    def test_rejects_route_without_matching_reviewed_definition(self):
        route = copy.deepcopy(self.route)
        route["definition_id"] += 10000
        bundle, coverage = self.materialize(routes=[route])
        self.assertEqual([], bundle["configurations"])
        self.assertEqual(
            ["missing_or_ambiguous_native_route"], coverage["coverage"][0]["reasons"]
        )

    def test_rejects_matching_route_that_no_longer_matches_native_catalog(self):
        route = copy.deepcopy(self.route)
        route["start_map_id"] += 1
        with self.assertRaisesRegex(RuntimeError, "route no longer matches"):
            self.materialize(routes=[route])

    def test_stale_generated_ordinary_slot_cannot_materialize_native_ultimate(self):
        self.native[0]["raw_visual_arrays"] = dict(csc=[49])
        with self.assertRaisesRegex(
            ValueError, "explicit encounter composition required"
        ):
            self.materialize()


if __name__ == "__main__":
    unittest.main()
