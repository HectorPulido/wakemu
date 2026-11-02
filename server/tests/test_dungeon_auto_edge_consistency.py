"""Final authoring anchors agree with new links; legacy pins stay readable."""
import copy
import unittest

from wakfu_server import dungeon_runtime_config
from wakfu_server.dungeon_auto_edges import (
    finalize_local_auto_edges,
    validate_auto_edges,
)
from wakfu_server.dungeon_auto_transition import next_anchor


class AutoEdgeConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.topology = dict(
            asset_map_id=1369,
            policy="local_accessible_anchor_policy",
            doors=[],
            rooms=[
                dict(order=1, anchor=[-2, -20, 0], cells=[[-2, -20, 0]]),
                dict(order=2, anchor=[-5, -55, -15], cells=[[-5, -55, -15]]),
            ],
            auto_edges=[dict(source_room=1, destination_room=2, anchor=[-4, -55, -17])],
        )
        monster = dict(
            name="Native fixture",
            ref_id=1,
            count=1,
            role="monster",
            native_min_level=1,
            native_max_level=1,
            guide_min_level=None,
            guide_max_level=None,
        )
        self.plan = dict(
            slug="anchor-fixture",
            source_url="https://example.invalid/anchor",
            source_sha256="a" * 64,
            document_sha256="b" * 64,
            definition_id=184,
            template_id=185,
            asset_map_id=1369,
            diagnostics=[],
            roster_ready=True,
            rooms=[
                dict(order=n, diagnostics=[], monsters=[copy.deepcopy(monster)])
                for n in (1, 2)
            ],
        )
        self.route = dict(
            key="anchor-fixture", definition_id=184, template_id=185, start_map_id=1369
        )

    def prepare(self, topology):
        return dungeon_runtime_config.prepare_configuration(
            self.plan,
            topology,
            self.route,
            version=6,
            provenance="Explicit isolated final-anchor authoring fixture",
        )

    def test_stale_link_rejected_before_new_configuration_can_be_frozen(self):
        with self.assertRaisesRegex(ValueError, "final room anchor"):
            self.prepare(self.topology)

    def test_explicit_final_authoring_copies_input_and_authorizes_next_anchor(self):
        before = copy.deepcopy(self.topology)
        self.topology["auto_edges"][0]["reviewed_source"] = "retained"
        final = finalize_local_auto_edges(self.topology)
        self.assertEqual(self.topology["auto_edges"][0]["anchor"], [-4, -55, -17])
        self.assertEqual(final["auto_edges"][0]["reviewed_source"], "retained")
        self.assertEqual(final["auto_edges"][0]["anchor"], [-5, -55, -15])
        final["auto_edges"][0]["anchor"][0] = 99
        self.assertEqual(self.topology["rooms"][1]["anchor"], [-5, -55, -15])
        final = finalize_local_auto_edges(before)
        config = self.prepare(final)
        self.assertEqual(
            config["evidence_hashes"]["topology"],
            dungeon_runtime_config.canonical_hash(final),
        )
        self.assertEqual(
            next_anchor(dict(victory=True, completed=False, current_room=2), final),
            dict(map_id=1369, x=-5, y=-55, z=-15),
        )

    def test_bad_route_structure_fails_without_converting_native_policy(self):
        for mutate in (
            lambda t: t["auto_edges"].append(copy.deepcopy(t["auto_edges"][0])),
            lambda t: t["auto_edges"][0].update(source_room=True),
            lambda t: t["auto_edges"][0].update(destination_room=3),
            lambda t: t.update(auto_edges=[]),
        ):
            topology = finalize_local_auto_edges(self.topology)
            mutate(topology)
            with self.assertRaises(ValueError):
                validate_auto_edges(topology)
        physical = dict(
            self.topology,
            policy="native_physical_door_victory_policy",
            auto_edges=[],
            physical_doors=[dict(source_id=7)],
        )
        self.assertEqual(finalize_local_auto_edges(physical), physical)
        self.assertEqual(
            finalize_local_auto_edges(
                dict(physical, policy="native_mixed_victory_policy")
            )["physical_doors"],
            physical["physical_doors"],
        )
        physical["auto_edges"] = self.topology["auto_edges"]
        with self.assertRaisesRegex(ValueError, "explicit local policy"):
            finalize_local_auto_edges(physical)

    def test_legacy_pinned_mismatch_remains_hash_checked_and_readable_for_recovery(
        self,
    ):
        config = self.prepare(finalize_local_auto_edges(self.topology))
        config["version"] = 5
        config["context_policy"]["policy_version"] = 5
        config["topology"] = copy.deepcopy(self.topology)
        config["evidence_hashes"]["topology"] = dungeon_runtime_config.canonical_hash(
            config["topology"]
        )
        before = copy.deepcopy(config)

        class Database:
            def execute(self, *args):
                return self

            def fetchone(self):
                return dict(value=config)

        loaded = dungeon_runtime_config.pinned_configuration(
            Database(),
            self.route["key"],
            5,
            expected_plan_hash=self.plan["document_sha256"],
        )
        self.assertEqual(loaded, before)
        self.assertEqual(config, before)
