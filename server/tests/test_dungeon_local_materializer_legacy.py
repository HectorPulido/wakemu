import copy
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
import unittest

from wakfu_server.paths import DATA_ROOT
from wakfu_server import native_catalog

SPEC = importlib.util.spec_from_file_location(
    "local_materializer_legacy",
    Path(__file__).resolve().parents[1] / "tools/materialize_local_dungeon_configs.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class LegacyMaterializerTests(unittest.TestCase):
    def setUp(self):
        monster = dict(
            name="fixture",
            ref_id=4,
            count=1,
            role="monster",
            native_min_level=1,
            native_max_level=2,
            guide_min_level=None,
            guide_max_level=None,
        )
        self.draft = dict(
            slug="fixture",
            definition_id=1000010,
            identity_policy="local_legacy_map_registry",
            policy_mode=MODULE.POLICY,
            official=False,
            reviewed_official=False,
            native_species_pool=[],
            species_pool=[4],
            species_pool_provenance="guide_verified_native_references",
            policy="local fixture",
            original_plan=dict(
                source_url="https://example.org",
                source_sha256="0" * 64,
                document_sha256="1" * 64,
            ),
            rooms=[
                dict(
                    order=1,
                    policy_applied=True,
                    monsters=[monster],
                    generated_fields=["count"],
                )
            ],
        )
        self.batch = dict(
            policy_mode=MODULE.POLICY, official=False, drafts=[self.draft], excluded=[]
        )
        self.route = dict(
            key="legacy",
            definition_id=1000010,
            template_id=1000010,
            start_map_id=10,
            registration_policy="local_legacy_map_registry",
            destination_id=2,
            entry_map_id=1,
            entry_object_id=3,
        )
        self.topology = dict(
            asset_map_id=10,
            rooms=[dict(order=1, anchor=[0, 0, 0], cells=[[0, 0, 0]])],
            doors=[],
        )
        self.native = [dict(ref=4, min_level=1, max_level=2)]

    def materialize(self):
        with patch.object(MODULE, "_load_routes"):
            return MODULE.materialize(
                self.batch,
                [self.route],
                dict(fixture=self.topology),
                self.native,
                version=2,
            )

    def test_legacy_pool_provenance_and_non_native_identity_remain_explicit(self):
        original = copy.deepcopy(self.batch)
        bundle, coverage = self.materialize()
        plan = bundle["configurations"][0]["compiled_plan"]
        self.assertIsNone(plan["native_definition_id"])
        self.assertFalse(plan["official"])
        self.assertEqual(
            "guide_verified_native_references", plan["species_pool_provenance"]
        )
        self.assertEqual(original, self.batch)
        self.assertEqual(1, coverage["summary"]["configuration_ready"])

    def test_generated_monster_cannot_escape_legacy_guide_pool(self):
        self.draft["species_pool"] = []
        with self.assertRaisesRegex(ValueError, "species pool"):
            self.materialize()

    def test_legacy_cannot_claim_official_review(self):
        self.draft["reviewed_official"] = True
        with self.assertRaisesRegex(ValueError, "misrepresents"):
            self.materialize()

    def actual_native_legacy_route(self):
        sources = json.loads(
            native_catalog.read_text(DATA_ROOT / "native-generic-teleporters.json")
        )
        for source in sources:
            for destination in source.get("destinations", []):
                map_id = destination.get("map_id")
                if (
                    type(map_id) is int
                    and 0 < map_id <= 32767
                    and type(destination.get("cyZ")) is int
                ):
                    return dict(
                        key=f'test-legacy-{map_id}-{source["id"]}-{destination["destination_id"]}',
                        definition_id=1_000_000 + map_id,
                        template_id=1_000_000 + map_id,
                        entry_map_id=source["map_id"],
                        entry_object_id=source["id"],
                        destination_id=destination["destination_id"],
                        start_map_id=map_id,
                        criterion=destination["criterion"],
                        registration_policy="local_legacy_map_registry",
                        native_definition_id=None,
                        native_template_id=destination["cyZ"],
                        native_localization_key=f"content.77.{map_id}",
                    )
        self.fail(
            "Native teleport catalog has no route suitable for the legacy fixture"
        )

    def actual_materialize(self, routes):
        route = routes[0] if routes else self.actual_native_legacy_route()
        batch = copy.deepcopy(self.batch)
        batch["drafts"][0]["definition_id"] = route["definition_id"]
        topology = copy.deepcopy(self.topology)
        topology["asset_map_id"] = route["start_map_id"]
        return MODULE.materialize(
            batch, routes, {"fixture": topology}, self.native, version=2
        )

    def test_legacy_materializer_requires_an_actual_registered_route(self):
        route = self.actual_native_legacy_route()
        bundle, coverage = self.actual_materialize([])
        self.assertEqual([], bundle["configurations"])
        self.assertEqual(
            ["missing_or_ambiguous_native_route"], coverage["coverage"][0]["reasons"]
        )
        self.assertIsNone(route["native_definition_id"])

    def test_legacy_materializer_rejects_native_transport_route_drift(self):
        route = self.actual_native_legacy_route()
        route["criterion"] += " and false"
        with self.assertRaisesRegex(
            RuntimeError, "route no longer matches the native teleporter catalog"
        ):
            self.actual_materialize([route])

    def test_native_statistics_mismatch_rejected(self):
        self.native[0]["max_level"] = 3
        with self.assertRaisesRegex(ValueError, "native monster bounds"):
            self.materialize()
