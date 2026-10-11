import copy
import unittest
from wakfu_server.maps.dungeon_runtime_config import (
    prepare_configuration,
    plan_from_configuration,
    level_selector,
    pinned_configuration,
    canonical_hash,
)


class RuntimeConfigTests(unittest.TestCase):
    def setUp(self):
        self.route = dict(
            key="test", definition_id=90, template_id=91, start_map_id=1086
        )
        monster = dict(
            name="Native",
            ref_id=1,
            count=3,
            role="monster",
            native_min_level=8,
            native_max_level=12,
            guide_min_level=None,
            guide_max_level=None,
        )
        self.plan = dict(
            slug="test",
            source_url="https://example.test",
            source_sha256="a" * 64,
            document_sha256="b" * 64,
            definition_id=90,
            template_id=91,
            asset_map_id=1086,
            diagnostics=[],
            roster_ready=True,
            rooms=[dict(order=1, diagnostics=[], monsters=[monster])],
        )
        self.topology = dict(
            asset_map_id=1086,
            rooms=[dict(order=1, anchor=[0, 0, 0], cells=[[0, 0, 0], [1, 0, 0]])],
            doors=[],
        )

    def configuration(self):
        return prepare_configuration(
            self.plan,
            self.topology,
            self.route,
            version=1,
            provenance="explicit local-policy:test",
        )

    def test_configuration_preserves_plan_and_explicit_local_policy(self):
        config = self.configuration()
        self.assertEqual(plan_from_configuration(config).rooms[0].monsters[0].ref_id, 1)
        self.assertEqual(config["context_policy"]["allowed_ids"], [])
        self.assertFalse(config["context_policy"]["can_increase_difficulty"])
        self.assertEqual(config["context_policy"]["difficulty_level"], 2)
        self.assertEqual(
            level_selector(config)(
                {"min_level": 8, "max_level": 12}, {"min_level": 8, "max_level": 12}
            ),
            8,
        )

    def test_changed_plan_hash_rejected(self):
        config = self.configuration()
        config["compiled_plan"] = copy.deepcopy(config["compiled_plan"])
        config["compiled_plan"]["rooms"][0]["monsters"][0]["count"] = 4
        with self.assertRaises(ValueError):
            plan_from_configuration(config)

    def test_native_grade_changes_rejected(self):
        with self.assertRaises(ValueError):
            level_selector(self.configuration())(
                {"min_level": 9, "max_level": 12}, {"min_level": 8, "max_level": 12}
            )

    def test_route_identity_conflict_rejected(self):
        self.route["template_id"] = 92
        with self.assertRaises(ValueError):
            self.configuration()

    def test_unresolved_roster_rejected(self):
        self.plan["rooms"][0]["monsters"][0]["count"] = None
        with self.assertRaises(ValueError):
            self.configuration()

    def test_non_native_anchor_rejected(self):
        self.topology["rooms"][0]["anchor"] = [99, 0, 0]
        with self.assertRaises(ValueError):
            self.configuration()

    def test_configuration_normalizes_json_keys_before_hashing_and_copies_inputs(self):
        self.topology["progression_metadata"] = {2: "second", 10: "tenth"}
        config = self.configuration()
        expected = copy.deepcopy(config)
        self.plan["rooms"][0]["monsters"][0]["count"] = 7
        self.route["key"] = "mutated-after-freeze"
        self.topology["progression_metadata"][2] = "mutated-after-freeze"
        self.assertEqual(config, expected)
        self.assertEqual(
            {"2": "second", "10": "tenth"}, config["topology"]["progression_metadata"]
        )
        self.assertEqual(
            config["evidence_hashes"]["topology"],
            canonical_hash(config["topology"]),
        )

    def test_reconnect_loads_pinned_version_without_active_pointer(self):
        config = self.configuration()

        class Cursor:
            def fetchone(self):
                return {"value": config}

        class Database:
            def execute(self, sql, values):
                if values != ("test", 1):
                    raise AssertionError(
                        "Reconnect queried global active configuration"
                    )
                return Cursor()

        self.assertEqual(
            pinned_configuration(Database(), "test", 1, expected_plan_hash="b" * 64),
            config,
        )
        with self.assertRaises(ValueError):
            pinned_configuration(Database(), "test", 1, expected_plan_hash="c" * 64)


if __name__ == "__main__":
    unittest.main()

    def test_larger_rosters_use_native_placement_capacity(self):
        from wakfu_server.maps.dungeon_capacity import MAX_DUNGEON_MONSTERS

        for count in (9, 10, 16, MAX_DUNGEON_MONSTERS):
            self.plan["rooms"][0]["monsters"][0]["count"] = count
            self.assertEqual(
                self.configuration()["compiled_plan"]["rooms"][0]["monsters"][0][
                    "count"
                ],
                count,
            )
        self.plan["rooms"][0]["monsters"][0]["count"] = MAX_DUNGEON_MONSTERS + 1
        with self.assertRaisesRegex(ValueError, "placement capacity"):
            self.configuration()
