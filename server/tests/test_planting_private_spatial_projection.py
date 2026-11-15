"""Native private scene ownership retains nonspatial visitor permissions."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from wakfu_server.planting_location import owned_character
from wakfu_server.world import World


class PlantingPrivateSpatialProjectionTests(unittest.TestCase):
    def test_bag_and_ranch_preserve_visitor_authority_without_position_merge(self):
        for map_id in (9, 1440):
            with self.subTest(map_id=map_id):
                stored = dict(
                    id=7,
                    account_id=8,
                    map_id=1134,
                    instance_id=0,
                    x=90,
                    y=91,
                    z=92,
                    direction=0,
                    haven_bag={"owner_id": 7},
                    inventory_items=[{"uid": 100}],
                )
                live = dict(
                    stored,
                    map_id=map_id,
                    instance_id=11,
                    x=1,
                    y=2,
                    z=0,
                    direction=3,
                    haven_bag={"owner_id": 11},
                    haven_bag_visitor=True,
                    haven_ranch_session=map_id == 1440,
                )
                world = World(lambda _: (0, b""), lambda _: (0, b""), lambda *_: None)
                world.join("private-lease", object(), live)
                positions = SimpleNamespace(merge=Mock())

                projected = owned_character(
                    stored, world, positions, generation="private-lease"
                )

                self.assertEqual(projected["haven_bag"], {"owner_id": 11})
                self.assertIs(projected["haven_bag_visitor"], True)
                self.assertEqual(
                    tuple(
                        projected[key]
                        for key in ("map_id", "instance_id", "x", "y", "z", "direction")
                    ),
                    (map_id, 11, 1, 2, 0, 3),
                )
                self.assertEqual(
                    projected["inventory_items"], stored["inventory_items"]
                )
                if map_id == 1440:
                    self.assertIs(projected["haven_ranch_session"], True)
                positions.merge.assert_not_called()
