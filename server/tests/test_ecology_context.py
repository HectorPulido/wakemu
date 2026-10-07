import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server import ecology_context


class EcologyContextTests(unittest.TestCase):
    def setUp(self):
        self.db = object()
        self.store = SimpleNamespace(connection=lambda: nullcontext(self.db))
        self.character = dict(map_id=1134, instance_id=18, x=1, y=2, z=50)

    def test_packet_uses_only_current_region_and_instance(self):
        snapshot = {
            "complete": True,
            "regions": {
                7: {"plant": {1: 3}, "monster": {2: 4}},
                8: {"plant": {1: 999}, "monster": {2: 999}},
            },
        }
        with patch.object(
            ecology_context.territory_cells, "region_at", return_value=7
        ), patch.object(
            ecology_context.ecology_population, "snapshot", return_value=snapshot
        ) as counts, patch.object(
            ecology_context.planting_cells,
            "region_context",
            return_value=(12789, b"regional"),
        ) as encode:
            self.assertEqual(
                ecology_context.packet(self.store, self.character), (12789, b"regional")
            )
            self.assertEqual(counts.call_args.args, (self.db, 1134, 18))
            self.assertEqual(encode.call_args.kwargs["plant_counts"], {1: 3})
            self.assertEqual(encode.call_args.kwargs["monster_counts"], {2: 4})
            self.assertEqual(
                counts.call_args.kwargs["locate"](1134, 9, 10, -100), {"region_id": 7}
            )

    def test_incomplete_snapshot_cannot_publish_false_zero_population(self):
        with patch.object(
            ecology_context.territory_cells, "region_at", return_value=7
        ), patch.object(
            ecology_context.ecology_population,
            "snapshot",
            return_value={"complete": False, "regions": {}},
        ), patch.object(
            ecology_context.planting_cells, "region_context"
        ) as encode:
            with self.assertRaisesRegex(ValueError, "incomplete"):
                ecology_context.packet(self.store, self.character)
            encode.assert_not_called()

    def test_real_encoder_publishes_known_region_from_nonplantable_position(self):
        character = dict(map_id=1134, instance_id=18, x=-54, y=54, z=0)
        region_id = ecology_context.territory_cells.region_at(1134, -54, 54)
        expected = ecology_context.planting_cells.bootstrap(1134, region_id)
        with patch.object(
            ecology_context.ecology_population,
            "snapshot",
            return_value={"complete": True, "regions": {}},
        ), patch.object(
            ecology_context.planting_cells,
            "surface",
            side_effect=AssertionError("Plantable surface must not be required"),
        ):
            self.assertEqual(ecology_context.packet(self.store, character), expected)

    def test_known_empty_region_is_encoded_without_other_region_counts(self):
        with patch.object(
            ecology_context.territory_cells, "region_at", return_value=7
        ), patch.object(
            ecology_context.ecology_population,
            "snapshot",
            return_value={"complete": True, "regions": {8: {"plant": {1: 90}}}},
        ), patch.object(
            ecology_context.planting_cells, "region_context"
        ) as encode:
            ecology_context.packet(self.store, self.character, open_test_policy=True)
            self.assertEqual(
                encode.call_args.kwargs,
                dict(monster_counts={}, plant_counts={}, open_test_policy=True),
            )


from postgres_case import PostgresCase
from wakfu_server import planting


class DurableEcologyContextTests(PostgresCase):
    def test_native_grid_counts_persisted_entities_without_plantable_cell_requirement(
        self,
    ):
        character = dict(map_id=1134, instance_id=18, x=-23, y=-143, z=70)
        region_id = ecology_context.territory_cells.region_at(1134, -23, -143)
        other_region = ecology_context.territory_cells.region_at(1134, -39, -72)
        self.assertNotEqual(region_id, other_region)
        seed_ref = next(
            ref for ref, row in planting.RESOURCES.items() if row["monster_resource"]
        )
        with self.store.connection() as db:
            for uid, instance, x, y, stage, reference in (
                (91001, 18, -23, -143, 2, 60),
                (91002, 18, -24, -143, 0, 60),
                (91003, 18, -25, -143, 16, 60),
                (91004, 18, -26, -143, 1, seed_ref),
                (91005, 19, -23, -143, 2, 60),
                (91006, 18, -39, -72, 2, 60),
            ):
                db.execute(
                    "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,"
                    "resource_reference,stage,creation_time) VALUES(%s,1134,%s,%s,%s,300,%s,%s,0)",
                    (uid, instance, x, y, reference, stage),
                )
        with patch.object(
            ecology_context.planting_cells,
            "region_context",
            return_value=(12789, b"regional"),
        ) as encode:
            self.assertEqual(
                ecology_context.packet(self.store, character), (12789, b"regional")
            )
            self.assertEqual(
                encode.call_args.kwargs["plant_counts"],
                {planting.RESOURCES[60]["family_id"]: 1},
            )
            self.assertEqual(encode.call_args.kwargs["monster_counts"], {})
