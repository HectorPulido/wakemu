import copy
import unittest

from wakfu_server.dungeon_legacy_catalog import (
    register,
    policy_definition,
    registered_routes,
    validate_legacy_route,
)
from wakfu_server.dungeon_local_roster_policy import draft


class DungeonLegacyCatalogTests(unittest.TestCase):
    def setUp(self):
        self.destination = {
            "destination_id": 10,
            "map_id": 312,
            "criterion": "HasState(3)",
            "cyZ": 122,
            "item_reference": 7,
        }
        self.sources = [{"id": 1, "map_id": 527, "destinations": [self.destination]}]
        self.evidence = {
            "asset_map_id": 312,
            "guide_slug": "legacy",
            "native_dungeon_definition_id": None,
            "native_localization_key": "content.77.312",
            "native_localization_value": "Native name",
            "incoming_native_routes": [
                {"source_id": 1, "source_map_id": 527, "destination": self.destination}
            ],
        }
        self.document = {
            "dungeon": {"slug": "legacy"},
            "rooms": [{"order": 1, "monsters": [{"ref_id": 2}]}],
        }
        self.native = [{"ref": 2, "min_level": 1, "max_level": 3}]

    def test_local_identity_and_route_guards_are_preserved(self):
        result = register(self.evidence, self.document, self.sources, self.native)
        self.assertEqual(result["runtime_definition_id"], 1000312)
        self.assertIsNone(result["native_definition_id"])
        self.assertEqual(result["entry_routes"][0]["destination"], self.destination)
        self.assertFalse(result["official_native_definition"])
        definition = policy_definition(result)
        self.assertNotIn("raw_cno", definition)
        plan = {
            "slug": "legacy",
            "rooms": [
                {
                    "order": 1,
                    "diagnostics": ["partial"],
                    "monsters": [{"ref_id": 2, "count": 9}],
                }
            ],
        }
        generated = draft(plan, definition, self.native)
        self.assertEqual(
            generated["species_pool_provenance"], "guide_verified_native_references"
        )
        self.assertEqual(generated["native_species_pool"], [])
        self.assertEqual(generated["rooms"][0]["monsters"][0]["count"], 9)

    def test_forged_route_criteria_localization_and_native_claim_reject(self):
        for field, value in [
            ("criterion", ""),
            ("cyZ", 0),
            ("item_reference", 0),
            ("map_id", 443),
        ]:
            evidence = copy.deepcopy(self.evidence)
            evidence["incoming_native_routes"][0]["destination"][field] = value
            with self.assertRaises(ValueError):
                register(evidence, self.document, self.sources, self.native)
        for field, value in [
            ("native_localization_key", "content.77.443"),
            ("native_dungeon_definition_id", 12),
            ("guide_slug", "other"),
        ]:
            with self.assertRaises(ValueError):
                register(
                    {**self.evidence, field: value},
                    self.document,
                    self.sources,
                    self.native,
                )
        with self.assertRaises(ValueError):
            register(
                self.evidence,
                self.document,
                self.sources,
                self.native,
                native_definition_ids=[1000312],
            )

    def test_unresolved_guide_pool_and_invalid_native_bounds_reject(self):
        with self.assertRaises(ValueError):
            register(self.evidence, self.document, self.sources, [])
        with self.assertRaises(ValueError):
            register(
                self.evidence,
                self.document,
                self.sources,
                [{"ref": 2, "min_level": 0, "max_level": 1}],
            )

    def test_route_adapter_preserves_actual_native_template_and_rejects_forgery(self):
        entry = register(self.evidence, self.document, self.sources, self.native)
        route = registered_routes(entry)[0]
        self.assertEqual(route["native_template_id"], 122)
        self.assertEqual(
            validate_legacy_route(route, self.sources)["template_id"], 1000312
        )
        for field, value in [
            ("criterion", ""),
            ("native_template_id", -1),
            ("start_map_id", 443),
            ("definition_id", 12),
            ("native_definition_id", 12),
            ("registration_policy", "native"),
        ]:
            with self.assertRaises(ValueError):
                validate_legacy_route({**route, field: value}, self.sources)
