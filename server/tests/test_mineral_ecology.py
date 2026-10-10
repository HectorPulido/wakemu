import unittest
from unittest.mock import MagicMock, Mock, patch

from wakfu_server import ecology_population, flora_ecology
from wakfu_server.planting import RESOURCES
from wakfu_server.resource_domains import is_mineral
from wakfu_server import planting_cells


class MineralEcologyTests(unittest.TestCase):
    def test_depleted_enabled_mineral_slot_remains_reserved_for_planting(self):
        store = MagicMock()
        db = store.connection.return_value.__enter__.return_value
        db.execute.return_value.fetchone.return_value = {"?column?": 1}
        with patch.object(
            planting_cells,
            "cells",
            return_value={
                (3, 4): [{"z": 0, "region_id": 1, "ground_id": 0}],
            },
        ), self.assertRaisesRegex(ValueError, "reserved for a mineral vein"):
            planting_cells.authorize(
                store,
                {"map_id": 1134, "instance_id": 0},
                {"x": 3, "y": 4},
                {},
                {},
                open_test_policy=True,
            )
        sql, parameters = db.execute.call_args.args
        self.assertIn("mining_vein_slots", sql)
        self.assertIn("AND enabled", sql)
        self.assertNotIn("active", sql)
        self.assertEqual((1134, 0, 3, 4), parameters)

    def test_native_mining_actions_define_domain_not_kind_zero(self):
        minerals = [ref for ref in RESOURCES if is_mineral(ref)]
        self.assertTrue(minerals)
        self.assertTrue(
            any(
                row["kind"] == 0 and not row["monster_resource"] and not is_mineral(ref)
                for ref, row in RESOURCES.items()
            )
        )
        for value in (None, True, "73", -1, 2**63):
            self.assertFalse(is_mineral(value))
        for ref in minerals:
            self.assertFalse(RESOURCES[ref]["monster_resource"])

    def test_mineral_actions_never_query_population_or_change_affinity(self):
        mineral = next(ref for ref in RESOURCES if is_mineral(ref))
        db = Mock()
        for action in ("plant", "remove", "harvest"):
            result = flora_ecology.change(
                db,
                1,
                {"resource_reference": mineral},
                operation="mining:test",
                action=action,
            )
            self.assertEqual(
                {"packets": [], "reason": "mineral_not_ecological"}, result
            )
        db.execute.assert_not_called()

    def test_minerals_do_not_count_or_make_flora_snapshot_incomplete(self):
        mineral = next(ref for ref in RESOURCES if is_mineral(ref))
        plant = next(
            ref
            for ref, row in RESOURCES.items()
            if not row["monster_resource"] and not is_mineral(ref)
        )
        db = Mock()
        db.execute.return_value = [
            dict(resource_uid=1, resource_reference=mineral, x=999, y=0, z=0),
            dict(resource_uid=2, resource_reference=plant, x=0, y=0, z=0),
        ]
        locate = Mock(return_value={"region_id": 1})
        result = ecology_population.snapshot(
            db, 1134, 0, kinds=("plant",), locate=locate
        )
        self.assertTrue(result["complete"])
        self.assertEqual(1, sum(result["regions"][1]["plant"].values()))
        locate.assert_called_once_with(1134, 0, 0, 0)

    def test_monster_resource_with_mining_action_is_not_a_mineral(self):
        with patch.dict(
            RESOURCES,
            {
                999999: {
                    "monster_resource": True,
                    "stage_definitions": [{"actions": [{"profession_id": 73}]}],
                }
            },
        ):
            self.assertFalse(is_mineral(999999))
