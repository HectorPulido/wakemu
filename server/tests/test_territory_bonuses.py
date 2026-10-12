import json
import unittest
from pathlib import Path
from unittest.mock import patch

from wakfu_server import territory_bonuses, territory_cells
from wakfu_server import native_catalog


ROOT = Path(__file__).resolve().parents[2]


class TerritoryBonusesTests(unittest.TestCase):
    def setUp(self):
        policy = patch.object(
            territory_bonuses,
            "control_health_policy",
            return_value={"1915": 1, "1916": 2, "1917": -1},
        )
        policy.start()
        self.addCleanup(policy.stop)

    def test_native_status_edges_and_intermediate_counts(self):
        self.assertIsNone(territory_bonuses.state_id(0, 0))
        self.assertEqual(territory_bonuses.state_id(0, 3), 1917)
        self.assertEqual(territory_bonuses.state_id(1, 3), 1915)
        self.assertEqual(territory_bonuses.state_id(2, 3), 1915)
        self.assertEqual(territory_bonuses.state_id(3, 3), 1916)

    def test_counts_reject_bool_and_invalid_ranges(self):
        for args in ((True, 1), (0, False), (-1, 2), (3, 2), (0, -1)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                territory_bonuses.state_id(*args)

    def test_effect_rows_match_native_state_catalog(self):
        source_path = ROOT / "server/protocol/combat-state-definitions.json"
        protector_path = ROOT / "server/protocol/monster-encyclopedia.json"
        regions_path = ROOT / "server/protocol/ecology-regions.json"
        target_path = ROOT / "server/protocol/territory-protector-bonuses.json"
        with native_catalog.open(source_path, "rt", encoding="utf-8") as stream:
            native = json.load(stream)
        exported = json.loads(native_catalog.read_text(target_path, encoding="utf-8"))

        import hashlib

        self.assertEqual(
            exported["source_sha256"]["combat_state_definitions"],
            hashlib.sha256(native_catalog.read_bytes(source_path)).hexdigest(),
        )
        self.assertEqual(
            exported["source_sha256"]["protector_catalog"],
            hashlib.sha256(native_catalog.read_bytes(protector_path)).hexdigest(),
        )
        self.assertEqual(
            exported["source_sha256"]["map_regions"],
            hashlib.sha256(native_catalog.read_bytes(regions_path)).hexdigest(),
        )
        for state_id in (1915, 1916, 1917):
            expected_state = native["states"][str(state_id)]
            actual_state = territory_bonuses._catalog()["states"][str(state_id)]
            self.assertEqual(actual_state["name"], expected_state["name"])
            self.assertEqual(actual_state["description"], expected_state["description"])
            expected = []
            for effect_id in expected_state["effect_ids"]:
                effect = native["effects"][str(effect_id)]
                expected.append(
                    {
                        "id": effect_id,
                        "effect_class": effect["effect_class"],
                        "variant": effect["variant"],
                        "criteria": effect["criteria"],
                        "parameters": effect["parameters"][: effect["parameter_count"]],
                    }
                )
            self.assertEqual(actual_state["effects"], expected)

        with native_catalog.open(protector_path, "rt", encoding="utf-8") as stream:
            protector_catalog = json.load(stream)
        native_territory = next(
            row
            for row in protector_catalog["territories"]
            if row["territory_id"] == 56601
        )
        exported_territory = exported["territories"]["56601"]
        self.assertEqual(exported_territory["map_id"], 327)
        self.assertEqual(
            exported_territory["monster_wishes"],
            [
                {"family_id": row["aIc"], "minimum": row["ctP"], "maximum": row["ctQ"]}
                for row in native_territory["raw_native"]["ctN"]
            ],
        )
        self.assertEqual(
            exported_territory["plant_wishes"],
            [
                {"family_id": row["aIc"], "minimum": row["ctP"], "maximum": row["ctQ"]}
                for row in native_territory["raw_native"]["ctO"]
            ],
        )

    def test_native_a_md_wishes_map_to_region_and_use_inclusive_ranges(self):
        result = territory_bonuses.evaluate_population(
            56601, {406: 266, 772: 400}, {1: 133}
        )
        self.assertEqual(
            (
                result["map_id"],
                result["satisfied_wishes"],
                result["total_wishes"],
                result["state_id"],
            ),
            (327, 3, 3, 1916),
        )

        partial = territory_bonuses.evaluate_population(
            56601, {406: 265, 772: 400}, {1: 133}
        )
        self.assertEqual((partial["satisfied_wishes"], partial["state_id"]), (2, 1915))

        none = territory_bonuses.evaluate_population(56601, {406: 10, 772: 500}, {1: 0})
        self.assertEqual((none["satisfied_wishes"], none["state_id"]), (0, 1917))

    def test_unknown_map_join_fails_closed_and_no_wishes_have_no_state(self):
        with self.assertRaisesRegex(ValueError, "verified map-region"):
            territory_bonuses.evaluate_population(62501, {}, {})
        empty = territory_bonuses.evaluate_population(59701, {}, {})
        self.assertEqual(
            (empty["map_id"], empty["state_id"], empty["effects"]), (472, None, None)
        )

    def test_all_joined_protector_territories_exist_in_native_cell_grid(self):
        territories = territory_bonuses._catalog()["territories"]
        joined = {
            (row["map_id"], int(territory_id))
            for territory_id, row in territories.items()
            if row["map_id"] is not None
        }
        native_cells = set(territory_cells.territories())
        self.assertEqual(len(joined), 101)
        self.assertTrue(joined.issubset(native_cells))

    def test_population_counts_reject_boolean_and_negative_values(self):
        for counts in ({406: True}, {406: -1}, {True: 2}):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                territory_bonuses.evaluate_population(56601, counts, {})

    def test_empty_region_has_no_state_or_effects(self):
        self.assertIsNone(territory_bonuses.state_effects(0, 0))

    def test_native_planting_and_harvest_xp_effect_percentages(self):
        self.assertEqual(
            territory_bonuses.profession_xp_percent(
                {
                    "state_id": 1915,
                    "effects": territory_bonuses.state_effects(1, 2)["effects"],
                },
                "planting",
            ),
            10,
        )
        self.assertEqual(
            territory_bonuses.profession_xp_percent(
                {
                    "state_id": 1915,
                    "effects": territory_bonuses.state_effects(1, 2)["effects"],
                },
                "harvest",
            ),
            10,
        )
        self.assertEqual(
            territory_bonuses.profession_xp_percent(
                {
                    "state_id": 1916,
                    "effects": territory_bonuses.state_effects(2, 2)["effects"],
                },
                "planting",
            ),
            30,
        )
        self.assertEqual(
            territory_bonuses.profession_xp_percent(
                {
                    "state_id": 1916,
                    "effects": territory_bonuses.state_effects(2, 2)["effects"],
                },
                "harvest",
            ),
            30,
        )
        self.assertEqual(
            territory_bonuses.profession_xp_percent(
                {
                    "state_id": 1917,
                    "effects": territory_bonuses.state_effects(0, 2)["effects"],
                },
                "planting",
            ),
            -10,
        )
        self.assertEqual(territory_bonuses.profession_xp_percent(None, "planting"), 0)
        with self.assertRaises(ValueError):
            territory_bonuses.profession_xp_percent(None, "recipe")

    def test_native_wisdom_and_prospection_modifiers(self):
        self.assertEqual(
            territory_bonuses.stat_bonuses(
                territory_bonuses.evaluate_population(56601, {}, {})
            ),
            {36: -10, 33: -10, 1: -1},
        )
        self.assertEqual(
            territory_bonuses.stat_bonuses(
                territory_bonuses.evaluate_population(
                    56601, {406: 266, 772: 200}, {1: 20}
                )
            ),
            {36: 60, 33: 60, 1: 2},
        )
        self.assertEqual(territory_bonuses.stat_bonuses(None), {})

    def test_attached_character_recomputes_bonus_and_return_to_baseline(self):
        character = {
            "id": 99,
            "map_id": 327,
            "instance_id": 2,
            "x": 0,
            "y": 0,
            "breed": 8,
            "level": 6,
            "hp": 41,
            "inventory_items": [],
            "builds": {0: {"equipment": "", "sheet": "18ffffffffffffffffff01"}},
        }
        partial = {
            "state_id": 1915,
            "effects": territory_bonuses.state_effects(1, 2)["effects"],
        }
        with patch.object(
            territory_bonuses, "current_region", side_effect=[partial, None]
        ):
            entered = territory_bonuses.attach_character(object(), character)
            exited = territory_bonuses.attach_character(object(), character)
        self.assertEqual(entered["territory_stat_bonuses"], {36: 30, 33: 30, 1: 1})
        self.assertEqual(exited["territory_stat_bonuses"], {})
        self.assertNotIn("territory_stat_bonuses", character)

    def test_current_region_uses_instance_snapshot_and_fails_closed_if_incomplete(self):
        character = {"map_id": 327, "instance_id": 9, "x": 0, "y": 0}
        population = {
            "complete": True,
            "regions": {56601: {"monster": {}, "plant": {}}},
        }
        with (
            patch("wakfu_server.territory_cells.region_at", return_value=56601),
            patch(
                "wakfu_server.ecology_population.snapshot", return_value=population
            ) as snapshot,
        ):
            result = territory_bonuses.current_region(object(), character)
        self.assertEqual(result["territory_id"], 56601)
        self.assertEqual(result["map_id"], 327)
        args, kwargs = snapshot.call_args
        self.assertEqual(args[1:3], (327, 9))
        self.assertTrue(callable(kwargs["locate"]))

        with (
            patch("wakfu_server.territory_cells.region_at", return_value=56601),
            patch(
                "wakfu_server.ecology_population.snapshot",
                return_value={**population, "complete": False},
            ),
        ):
            self.assertIsNone(territory_bonuses.current_region(object(), character))

    def test_world_refresh_initializes_changes_and_clears_region_stats(self):
        from unittest.mock import MagicMock

        store = MagicMock()
        character = {
            "id": 99,
            "hp": 420,
            "active_build_index": 2,
            "breed": 8,
            "level": 50,
            "inventory_items": [],
            "builds": {2: {"equipment": "", "sheet": "18ffffffffffffffffff01"}},
        }
        regional = {
            "state_id": 1915,
            "effects": territory_bonuses.state_effects(1, 2)["effects"],
        }
        with (
            patch.object(
                territory_bonuses,
                "current_region",
                side_effect=[regional, regional, None, None],
            ),
            patch.object(
                territory_bonuses, "world_packet", return_value=(13046, b"owned")
            ) as serialize,
        ):
            self.assertEqual(
                territory_bonuses.refresh_world(store, character), [(13046, b"owned")]
            )
            self.assertEqual(
                character["territory_stat_bonuses"], {36: 30, 33: 30, 1: 1}
            )
            self.assertEqual(serialize.call_args.args[0]["active_build_index"], 2)
            self.assertEqual(serialize.call_args.args[0]["hp"], 420)
            self.assertEqual(territory_bonuses.refresh_world(store, character), [])
            self.assertEqual(
                territory_bonuses.refresh_world(store, character), [(13046, b"owned")]
            )
            self.assertEqual(character["territory_stat_bonuses"], {})
            self.assertEqual(territory_bonuses.refresh_world(store, character), [])
            self.assertEqual(serialize.call_count, 2)

    def test_world_refresh_retries_if_serialization_fails(self):
        from unittest.mock import MagicMock

        character = {
            "id": 99,
            "breed": 8,
            "level": 6,
            "hp": 41,
            "inventory_items": [],
            "builds": {0: {"equipment": "", "sheet": "18ffffffffffffffffff01"}},
        }
        with (
            patch.object(territory_bonuses, "current_region", return_value=None),
            patch.object(
                territory_bonuses,
                "world_packet",
                side_effect=ValueError("bad snapshot"),
            ),
            self.assertRaises(ValueError),
        ):
            territory_bonuses.refresh_world(MagicMock(), character)
        self.assertNotIn("_published_territory_stat_bonuses", character)

    def test_world_packet_updates_only_owned_public_characteristics(self):
        import struct

        character = {"id": 99, "direction": 6, "x": 123, "y": 456}
        complete = struct.pack(">HBiiii", 1, 36, 30, -1000, 1000, 0)
        with patch(
            "wakfu_server.wire.owned_public_characteristics", return_value=complete
        ) as public:
            opcode, body = territory_bonuses.world_packet(character)
        self.assertEqual(opcode, 13046)
        self.assertEqual(struct.unpack_from(">qh", body), (99, 1 + len(complete)))
        self.assertEqual(body[10:], b"\x27" + complete)
        public.assert_called_once_with(character)
        # No position, direction, fight or experience fields follow this format.
        self.assertEqual(len(body), 10 + 1 + len(complete))


if __name__ == "__main__":
    unittest.main()
