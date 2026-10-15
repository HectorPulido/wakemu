"""Retired wall callbacks retain constructor authority without a live QI slot."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_effect_area import remove_owned_hour_area
from wakfu_server.combat_qi_registry import NativeQIRegistry
from wakfu_server.combat_wall_area import verified_wall_constructor, wall_constructor


def wall_definition():
    return {
        "type": "WALL",
        "native_class": "bcZ",
        "native_type_id": 7,
        "native_container_type": 3,
        "raw_bdh": [10, 0, 1, 0],
    }


class NativeWallRetirementTests(unittest.TestCase):
    def fixture(self):
        fight = SimpleNamespace(
            native_effect_areas={},
            actors={},
            native_qi_snapshot={
                "x": 0,
                "y": 0,
                "width": 4,
                "height": 4,
                "cell_masks": [0] * 16,
            },
            native_qi_slots=[None] * 127,
            native_qi_touched_cells=[],
            native_qi_byte_topology={},
        )
        definition = wall_definition()
        constructor = wall_constructor(definition, 1)
        registry = NativeQIRegistry(
            fight.native_qi_snapshot,
            fight.native_qi_slots,
            touched_cells=fight.native_qi_touched_cells,
            byte_topology=fight.native_qi_byte_topology,
        )
        slot = registry.register(
            {
                "identity": ("effect_area", 901),
                "position": (2, 2),
                "radius": 0,
                "indexed": False,
                "movement_blocking": constructor["movement_blocking"],
            }
        )
        fight.native_qi_slots = registry.serialized_slots()
        fight.native_qi_touched_cells = registry.serialized_cells()
        fight.native_qi_byte_topology = registry.serialized_byte_topology()
        row = {
            "uid": 901,
            "native_area_contract": "fbd",
            "native_type_id": 7,
            "native_running_effect_manager": True,
            "level": 1,
            "native_wall_constructor": constructor,
            "native_wall_hp_current": constructor["hp_initial"],
            "native_wall_hp_source": "fbd.PA.sgC.aYS",
            "native_obstacle_id": slot,
            "native_obstacle_source": "QI.f(QK)",
        }
        fight.native_effect_areas[901] = row
        return fight, row, definition

    def test_retired_callback_accepts_qi_g_slot_after_real_area_removal(self):
        fight, row, definition = self.fixture()
        callback_rows = []

        def on_removed(removed):
            self.assertIs(removed, row)
            self.assertEqual(removed["native_obstacle_id"], -1)
            self.assertEqual(removed["native_obstacle_source"], "QI.g(QK)")
            self.assertEqual(
                verified_wall_constructor(removed, definition, fight=fight),
                row["native_wall_constructor"],
            )
            detached_copy = dict(removed)
            with self.assertRaisesRegex(
                ValueError, "registered native bcZ QI obstacle"
            ):
                verified_wall_constructor(detached_copy, definition, fight=fight)
            callback_rows.append(removed)

        removed = remove_owned_hour_area(
            fight, 901, callbacks=SimpleNamespace(removed=on_removed)
        )
        self.assertEqual(removed, (row,))
        self.assertEqual(callback_rows, [row])
        self.assertNotIn(901, fight.native_effect_areas)

    def test_unregistered_or_constructor_only_slot_cannot_masquerade_as_retired(self):
        fight, row, definition = self.fixture()
        for slot, source in (
            (-1, "QI.f(QK)"),
            (-1, "QI.g(QK)"),
            (-1, "fbm.constructor"),
            (127, "QI.g(QK)"),
        ):
            with self.subTest(slot=slot, source=source):
                candidate = dict(
                    row, native_obstacle_id=slot, native_obstacle_source=source
                )
                with self.assertRaises(ValueError):
                    verified_wall_constructor(candidate, definition, fight=fight)

        detached = dict(row, native_obstacle_id=-1, native_obstacle_source="QI.g(QK)")
        fight.native_effect_areas.pop(row["uid"])
        with self.assertRaisesRegex(ValueError, "registered native bcZ QI obstacle"):
            verified_wall_constructor(detached, definition, fight=fight)

    def test_selected_pv_scope_authorizes_exact_retired_wall_only_until_scope_exit(
        self,
    ):
        from wakfu_server.combat_state_managers import (
            retained_area_pv_row,
            selected_area_pv_scope,
        )

        fight, row, definition = self.fixture()
        with patch(
            "wakfu_server.combat_state_managers.registered_area_pv",
            return_value=object(),
        ):
            with selected_area_pv_scope(fight, (901,)):
                remove_owned_hour_area(fight, 901)
                self.assertNotIn(901, fight.native_effect_areas)
                self.assertIs(retained_area_pv_row(fight, 901), row)
                self.assertEqual(
                    verified_wall_constructor(row, definition, fight=fight),
                    row["native_wall_constructor"],
                )

        self.assertIsNone(retained_area_pv_row(fight, 901))
        with self.assertRaisesRegex(ValueError, "registered native bcZ QI obstacle"):
            verified_wall_constructor(row, definition, fight=fight)


if __name__ == "__main__":
    unittest.main()
