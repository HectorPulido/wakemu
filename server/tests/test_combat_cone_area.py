import json, unittest
from pathlib import Path
from types import SimpleNamespace
from wakfu_server.combat_area_geometry import (
    native_area_shape,
    oriented_area_offsets,
    native_area_contains,
)
from wakfu_server.combat_group_cells import group_cells
from wakfu_server.combat_effect_targets import select_native_effect_targets


class NativeConeAreaTests(unittest.TestCase):
    def test_native_rows_include_tip_and_end_before_height(self):
        effect = dict(area_class="anv", area_native="cone-2")
        self.assertEqual(
            native_area_shape(effect), (((0, 0), (1, -1), (1, 0), (1, 1)), False)
        )
        for height in (-1, 0):
            self.assertEqual(
                native_area_shape(dict(effect, area_native="cone-" + str(height))),
                ((), False),
            )

    def test_native_orientations_and_physical_radii(self):
        rows = json.loads(
            (
                Path(__file__).parents[1] / "protocol/native-cone-area-fixture.json"
            ).read_text()
        )
        self.assertEqual(len(rows), 108)
        for row in rows:
            effect = dict(area_class="anv", area_native=row["native"])
            reference = tuple(-v for v in row["vector"])
            direction = row["fallback_direction"]
            self.assertEqual(
                oriented_area_offsets(
                    effect, origin=(0, 0), reference=reference, direction=direction
                ),
                tuple(dict.fromkeys(tuple(p) for p in row["cells"])),
            )
            for radius, key in [(0, "membership"), (1, "1"), (2, "2")]:
                expected = set(
                    map(
                        tuple,
                        row[key] if radius == 0 else row["radius_memberships"][key],
                    )
                )
                actual = {
                    (x, y)
                    for x in range(-6, 7)
                    for y in range(-6, 7)
                    if native_area_contains(
                        effect,
                        origin=(0, 0),
                        reference=reference,
                        direction=direction,
                        point=(x, y),
                        radius=radius,
                    )
                }
                self.assertEqual(
                    actual, expected, (row["native"], reference, direction, radius)
                )

    def test_actor_and_cell_routes_share_cone_geometry(self):
        effect = dict(area_class="anv", area_native="cone-2")
        caster = SimpleNamespace(
            id=1, team=0, position=(0, 0, 0), direction=1, hp=10, physical_radius=0
        )
        fight = SimpleNamespace(
            actors={1: caster},
            walkable={(2, 0, 5), (3, -1, 7), (3, 0, 8), (3, 1, 9), (4, 0, 0)},
        )
        self.assertEqual(
            group_cells(fight, effect, (2, 0, 0), caster_id=1),
            ((2, 0, 5), (3, -1, 7), (3, 0, 8), (3, 1, 9)),
        )
        self.assertTrue(
            native_area_contains(effect, origin=(2, 0), reference=(0, 0), point=(3, 1))
        )
        self.assertFalse(
            native_area_contains(effect, origin=(2, 0), reference=(0, 0), point=(4, 0))
        )

        actors = [
            caster,
            SimpleNamespace(id=2, team=1, position=(3, 1, 9), hp=10, physical_radius=0),
            SimpleNamespace(id=3, team=1, position=(4, 0, 0), hp=10, physical_radius=0),
        ]
        effect["native_target_selector"] = {"class": "fcE", "mask": 1}
        contexts = {
            a.id: dict(bEe=True, is_Qq=False, is_eGj=False, is_eHH=False)
            for a in actors
        }
        selected = select_native_effect_targets(
            effect, caster, (2, 0, 0), actors, native_context=contexts
        )
        self.assertEqual([a.id for a in selected], [2])
