"""Native area BitSet masks stay authoritative for forced movement events."""
import os
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class ForcedAreaEventMaskMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from wakfu_server.combat_effect_area import native_effect_areas

        cls.definitions = native_effect_areas()

    def _area_runtime(self, reference):
        from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
        from wakfu_server.combat_effect_area_geometry import registered_area_cells
        from wakfu_server.combat_state import Actor, Fight

        definition = self.definitions[str(reference)]
        actor = Actor(-7, 1, (6, 0, 0), 100, 6, 6, 10, 200, physical_radius=0)
        owner = Actor(7, 0, (-6, 0, 0), 100, 6, 6, 10, 200)
        walkable = {(x, y, 0) for x in range(-8, 9) for y in range(-8, 9)}
        fight = Fight(
            89001, [owner, actor], walkable, {0: {(-6, 0, 0)}, 1: {(6, 0, 0)}}
        )
        cells = registered_area_cells(definition, (0, 0, 0), 0)
        row = {
            "uid": 100,
            "effect_uid": 101,
            "reference": reference,
            "owner_id": 7,
            "level": 1,
            "cell": (0, 0, 0),
            "direction": 0,
            "native_cells_xy": list(cells),
            "native_area_contract": "faY" if definition["type"] == "GLYPH" else "fbc",
            "remaining_activations": -1,
            "child_effect_uids": {},
        }
        fight.native_effect_areas[100] = row

        class RecordingRuntime(NativeAreaEventRuntime):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.deliveries = []

            def _activate(self, row, definition, target, *, trigger=None):
                self.deliveries.append(("entry", definition["type"], target.id))
                return True

            def _exit(self, row, target):
                self.deliveries.append(("exit", row["reference"], target.id))
                return True

            def _remove_on_masks(self, row, definition, event_ids):
                self.deliveries.append(("remove", row["reference"], tuple(event_ids)))
                return True

        runtime = RecordingRuntime(fight, object(), definitions=self.definitions)
        return runtime, actor

    def test_native_glyph_entry_exit_masks_exclude_inside_movement(self):
        # Ref 889 is an installed GLYPH with real entry/exit subscriptions, but
        # no 10008 subscription. Its native shape is a point, so the inside to
        # inside callback is represented by remaining on that occupied cell.
        runtime, actor = self._area_runtime(889)
        definition = self.definitions["889"]
        self.assertEqual(definition["type"], "GLYPH")
        self.assertIn(10001, definition["entry_masks"])
        self.assertIn(10002, definition["exit_masks"])
        self.assertNotIn(10008, definition["entry_masks"])

        runtime.movement(-7, from_cell=(2, 0, 0), to_cell=(0, 0, 0))
        self.assertEqual(runtime.deliveries, [("entry", "GLYPH", -7)])

        runtime.deliveries.clear()
        actor.position = (0, 0, 0)
        runtime.movement(-7, from_cell=(0, 0, 0), to_cell=(0, 0, 0))
        self.assertEqual(runtime.deliveries, [])

        runtime.movement(-7, from_cell=(0, 0, 0), to_cell=(2, 0, 0))
        self.assertEqual(runtime.deliveries, [("exit", 889, -7)])

    def test_native_glyph_inside_movement_uses_its_10008_subscription(self):
        runtime, actor = self._area_runtime(1113)
        definition = self.definitions["1113"]
        footprint = list(runtime.fight.native_effect_areas[100]["native_cells_xy"])
        self.assertEqual(definition["type"], "GLYPH")
        self.assertIn(10001, definition["entry_masks"])
        self.assertIn(10008, definition["entry_masks"])
        self.assertGreaterEqual(len(footprint), 2)

        first, second = footprint[:2]
        runtime.movement(-7, from_cell=(6, 0, 0), to_cell=(*first, 0))
        self.assertEqual(runtime.deliveries, [("entry", "GLYPH", -7)])
        actor.position = (*first, 0)
        runtime.deliveries.clear()
        runtime.movement(-7, from_cell=(*first, 0), to_cell=(*second, 0))
        self.assertEqual(runtime.deliveries, [("entry", "GLYPH", -7)])

    def test_other_native_trap_and_damage_trap_have_movement_masks(self):
        # Ref 779 is a distinct installed damage trap (cast by real Sram spell
        # 5183). Keep its two native transition subscriptions explicit.
        trap = self.definitions["779"]
        self.assertEqual(trap["type"], "TRAP")
        self.assertTrue({10001, 10008}.issubset(set(trap["entry_masks"])))

    def test_other_native_trap_routes_real_entry_mask(self):
        from unittest.mock import patch

        runtime, _ = self._area_runtime(779)
        trap = self.definitions["779"]
        self.assertEqual(trap["type"], "TRAP")
        with patch(
            "wakfu_server.combat_trap_area.trap_owner_movement_allowed",
            return_value=True,
        ):
            runtime.movement(-7, from_cell=(2, 0, 0), to_cell=(0, 0, 0))
        self.assertEqual(runtime.deliveries, [("entry", "TRAP", -7)])

    def test_bomb_only_2145_subscription_is_not_a_movement_producer(self):
        from wakfu_server.combat_area_contracts import AREA_CONTRACTS

        bomb = self.definitions["970"]
        self.assertEqual(bomb["type"], "BOMB")
        self.assertEqual(bomb["entry_masks"], [2145])
        self.assertFalse({10001, 10008, 10002} & set(bomb["entry_masks"]))
        self.assertNotIn("BOMB", AREA_CONTRACTS)
        combo = self.definitions["973"]
        self.assertEqual(combo["type"], "BOMB_COMBO")
        self.assertNotIn("BOMB_COMBO", AREA_CONTRACTS)

    def test_roublard_wall_and_powder_glyphs_do_not_gain_movement_events(self):
        wall = self.definitions["1818"]
        powder = self.definitions["1335"]
        self.assertEqual(wall["type"], "GLYPH")
        self.assertEqual(wall["entry_masks"], [])
        self.assertEqual(wall["exit_masks"], [])
        self.assertEqual(powder["type"], "GLYPH")
        self.assertEqual(powder["entry_masks"], [10000])

        runtime, _ = self._area_runtime(1818)
        runtime.movement(-7, from_cell=(6, 0, 0), to_cell=(0, 0, 0))
        self.assertEqual(runtime.deliveries, [])


if __name__ == "__main__":
    unittest.main()
