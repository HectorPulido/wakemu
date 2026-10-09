import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location(
    "bulk", Path(__file__).resolve().parents[1] / "tools/prepare_dungeon_bulk.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BulkPreparationTests(unittest.TestCase):
    def document(self, slug):
        return dict(
            schema_version=1,
            dungeon=dict(
                slug=slug,
                client_definition_id=None,
                client_template_id=None,
                client_asset_map_id=None,
            ),
            source=dict(
                url="https://example.org/" + slug,
                article_sha256="0" * 64,
                client_version_match="unverified",
            ),
            extraction=dict(reviewed=True),
            rooms=[
                dict(
                    order=1,
                    composition_status="complete",
                    monsters=[
                        dict(
                            name="Monster",
                            ref_id=4,
                            count=1,
                            min_level=None,
                            max_level=None,
                            role="monster",
                        )
                    ],
                )
            ],
        )

    def prepare(self, documents, links=(), routes=(), topologies=None):
        return MODULE.prepare_all(
            documents,
            [dict(ref=4, min_level=1, max_level=2)],
            dict(guide_links=list(links)),
            list(routes),
            topologies or {},
            version=1,
            provenance="fixture",
        )

    def test_every_unmatched_guide_retains_coverage(self):
        updated, plans, configs, coverage = self.prepare(
            [self.document("one"), self.document("two")]
        )
        self.assertEqual(2, len(coverage))
        self.assertFalse(configs)
        self.assertTrue(
            all(
                "unresolved_native_dungeon_identity" in row["reasons"]
                for row in coverage
            )
        )

    def test_unknown_composition_never_configured(self):
        doc = self.document("one")
        doc["rooms"][0]["monsters"][0]["count"] = None
        _, _, configs, coverage = self.prepare([doc])
        self.assertFalse(configs)
        self.assertIn("room[1].monster[0].unknown_count", coverage[0]["reasons"])

    def test_native_route_identity_requires_matching_asset(self):
        link = dict(
            guide_slug="one",
            status="exact_unique",
            client_definition_id=7,
            candidates=[dict(raw_aHA=[9], raw_arM=8)],
        )
        route = dict(definition_id=7, start_map_id=10, entry_map_id=8, template_id=11)
        with self.assertRaisesRegex(ValueError, "contradicts"):
            self.prepare([self.document("one")], [link], [route])

    def test_ready_generic_configuration_without_per_dungeon_ids(self):
        link = dict(
            guide_slug="one",
            status="exact_unique",
            client_definition_id=7,
            candidates=[dict(raw_aHA=[9], raw_arM=8)],
        )
        route = dict(
            key="fixture",
            definition_id=7,
            start_map_id=9,
            entry_map_id=8,
            template_id=11,
        )
        topology = dict(
            asset_map_id=9,
            rooms=[dict(order=1, anchor=[0, 0, 0], cells=[[0, 0, 0]])],
            doors=[],
        )
        _, _, configs, coverage = self.prepare(
            [self.document("one")], [link], [route], dict(one=topology)
        )
        self.assertEqual(1, len(configs))
        self.assertTrue(coverage[0]["configuration_ready"])
        self.assertEqual(11, configs[0]["route"]["template_id"])
