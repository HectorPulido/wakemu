"""Singleton repair removes generated copies without rewriting pinned evidence."""
import copy
import unittest

from tools.prepare_supreme_singleton_configuration import prepare
from wakfu_server.dungeon_runtime_config import prepare_configuration, canonical_hash


class SupremeSingletonConfigurationTests(unittest.TestCase):
    def baseline(self):
        boss = dict(
            ref_id=42,
            name="Magmog",
            count=1,
            role="boss",
            native_min_level=110,
            native_max_level=110,
            guide_min_level=None,
            guide_max_level=None,
        )
        filler = dict(boss, role="monster")
        plan = dict(
            slug="reviewed-arena",
            definition_id=6,
            template_id=10,
            asset_map_id=365,
            roster_ready=True,
            diagnostics=[],
            policy_mode="generated_native_species_policy",
            generated_fields=[{}],
            rooms=[
                dict(order=1, monsters=[filler], diagnostics=[]),
                dict(order=2, monsters=[boss, filler], diagnostics=[]),
            ],
        )
        topology = dict(
            asset_map_id=365,
            policy="local_accessible_anchor_policy",
            doors=[],
            auto_edges=[dict(source_room=1, destination_room=2, anchor=[3, 0, 20])],
            rooms=[
                dict(order=1, anchor=[0, -20, 20], cells=[[0, -20, 20]]),
                dict(order=2, anchor=[3, 0, 20], cells=[[3, 0, 20], [4, 0, 20]]),
            ],
            completion_destination=dict(map_id=1137, x=-25, y=-170, z=67),
        )
        route = dict(
            key="native_dungeon_6",
            definition_id=6,
            template_id=10,
            start_map_id=365,
            entry_map_id=1137,
        )
        self.native = dict(
            ref=42, min_level=110, max_level=110, raw_visual_arrays=dict(csc=[49])
        )
        return prepare_configuration(
            plan, topology, route, version=2, provenance="Explicit generated baseline"
        )

    def build(self, base, **kwargs):
        return prepare(
            base,
            self.native,
            version=kwargs.get("version", 3),
            source_url="https://example.invalid/observational-guide",
            authority="Explicit Wakemu singleton reconstruction",
        )

    def test_repair_preserves_baseline_route_exit_and_final_terrain(self):
        base = self.baseline()
        frozen = copy.deepcopy(base)
        result = self.build(base)
        self.assertEqual(base, frozen)
        self.assertEqual(result["version"], 3)
        self.assertEqual(result["context_policy"]["policy_version"], 3)
        self.assertEqual(result["route"], base["route"])
        self.assertEqual(
            result["topology"]["completion_destination"],
            base["topology"]["completion_destination"],
        )
        self.assertEqual(
            result["topology"]["rooms"], [dict(base["topology"]["rooms"][1], order=1)]
        )
        self.assertEqual(result["topology"]["auto_edges"], [])
        self.assertEqual(
            result["compiled_plan"]["rooms"][0]["monsters"],
            [base["compiled_plan"]["rooms"][1]["monsters"][0]],
        )
        self.assertEqual(
            result["evidence_hashes"]["route"], base["evidence_hashes"]["route"]
        )
        self.assertNotEqual(
            result["evidence_hashes"]["plan"], base["evidence_hashes"]["plan"]
        )

    def test_mixed_species_cannot_be_silently_removed(self):
        base = self.baseline()
        base["compiled_plan"]["rooms"][0]["monsters"][0]["ref_id"] = 7
        base["evidence_hashes"]["plan"] = canonical_hash(base["compiled_plan"])
        with self.assertRaisesRegex(ValueError, "Mixed species"):
            self.build(base)

    def test_rejects_overwrite_and_changed_frozen_baseline(self):
        base = self.baseline()
        with self.assertRaisesRegex(ValueError, "fresh later version"):
            self.build(base, version=2)
        base["topology"]["rooms"][1]["anchor"] = [99, 0, 20]
        with self.assertRaisesRegex(ValueError, "Frozen baseline"):
            self.build(base)
