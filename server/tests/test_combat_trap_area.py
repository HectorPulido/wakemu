import unittest
from wakfu_server.combat_trap_area import (
    trap_constructor,
    trap_characteristics,
    install_trap_characteristics,
    verified_trap_characteristics,
    trap_owner_movement_allowed,
    retire_exhausted_trap,
)
from wakfu_server.combat_area_damage_snapshot import copy_area_damage_snapshot


class NativeTrapAreaTests(unittest.TestCase):
    def test_failed_activation_does_not_run_exhaustion_cleanup(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime

        row, definition = self.fixture()
        row.update(
            uid=91,
            owner_id=7,
            level=1,
            cell=(2, 3, 0),
            remaining_activations=1,
            executing=False,
        )
        definition["effect_ids"] = [17]
        fight = SimpleNamespace(
            actors={7: object()},
            native_effect_areas={91: row},
            native_retained_records={},
        )

        def fail_child(invocation):
            self.assertEqual(invocation.cell, (2, 3, 0))
            raise ValueError("Child failed")

        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(synchronize=lambda: None),
            execute=fail_child,
        )
        runtime = NativeAreaEventRuntime(
            fight, dispatcher, definitions={"778": definition}
        )
        with patch("wakfu_server.combat_effect_area.remove_owned_hour_area") as remove:
            with self.assertRaisesRegex(ValueError, "Child failed"):
                runtime._activate(row, definition, None)
            remove.assert_not_called()
        self.assertFalse(row["executing"])
        self.assertIs(fight.native_effect_areas[91], row)

    def test_exhaustion_policy_requires_actual_inactive_zero_charge_row(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        row = dict(
            uid=91, native_area_contract="fbc", remaining_activations=0, executing=True
        )
        fight = SimpleNamespace(native_effect_areas={91: row})
        callbacks = object()
        with patch("wakfu_server.combat_effect_area.remove_owned_hour_area") as remove:
            self.assertFalse(retire_exhausted_trap(fight, row, callbacks=callbacks))
            row["executing"] = False
            row["remaining_activations"] = -1
            self.assertFalse(retire_exhausted_trap(fight, row, callbacks=callbacks))
            row["remaining_activations"] = 0
            self.assertTrue(retire_exhausted_trap(fight, row, callbacks=callbacks))
            remove.assert_called_once_with(fight, 91, callbacks=callbacks)
        fight.native_effect_areas.clear()
        self.assertFalse(retire_exhausted_trap(fight, row, callbacks=callbacks))

    def fixture(self, parameters=(1, 0), properties=(3, 9, 12)):
        definition = dict(
            type="TRAP",
            native_class="bcY",
            native_type_id=3,
            native_container_type=3,
            raw_bdh=list(parameters),
            native_area_properties=properties,
        )
        row = dict(native_area_contract="fbc", owner_id=7)
        install_trap_characteristics(row, definition)
        return row, definition

    def test_actual_native_subset_and_constructor_flags(self):
        row, definition = self.fixture()
        values = verified_trap_characteristics(row, definition)
        self.assertEqual(set(values), {18, 20, 21, 22, 23, 24, 103, 104, 105, 106})
        self.assertTrue(all(v == 0 for v in values.values()))
        self.assertNotIn(1, values)  # No invented HP resource.
        self.assertTrue(row["native_trap_constructor"]["owner_activation"])
        self.assertTrue(row["native_trap_constructor"]["fqx"])
        _, definition = self.fixture((0, 1))
        self.assertFalse(trap_constructor(definition)["owner_activation"])
        self.assertFalse(trap_constructor(definition)["fqx"])

    def test_owner_movement_guard_is_current_turn_and_event_specific(self):
        row, definition = self.fixture((0, 0))
        for event in (10001, 10008, 10002):
            self.assertFalse(
                trap_owner_movement_allowed(
                    row, definition, target_id=7, current_id=7, event_ids=(event,)
                )
            )
            self.assertTrue(
                trap_owner_movement_allowed(
                    row, definition, target_id=7, current_id=8, event_ids=(event,)
                )
            )
            self.assertTrue(
                trap_owner_movement_allowed(
                    row, definition, target_id=8, current_id=7, event_ids=(event,)
                )
            )
        self.assertTrue(
            trap_owner_movement_allowed(
                row, definition, target_id=7, current_id=7, event_ids=(10000,)
            )
        )

    def test_copy_preserves_ordered_nG_delta_and_native_bounds(self):
        row, definition = self.fixture()
        source = {
            18: 7,
            20: 100,
            21: 50001,
            22: 30,
            23: -5001,
            24: 44,
            103: 33,
            104: 34,
            105: 35,
            106: 36,
        }
        self.assertTrue(copy_area_damage_snapshot(row, definition, source_stats=source))
        values = verified_trap_characteristics(row, definition)
        self.assertEqual(values[18], 37)  # sgP + sgS, not overwrite.
        self.assertEqual(values[20], 100)
        self.assertEqual(values[21], 50000)
        self.assertEqual(values[23], -5000)
        self.assertEqual(values[103], 33)
        self.assertEqual(source[21], 50001)

    def test_original_java_pa_setter_observations(self):
        for stat, row in trap_characteristics()["characteristics"].items():
            for observed in row["setter_observations"]:
                with self.subTest(stat=stat, requested=observed["requested"]):
                    current = max(
                        row["minimum"],
                        min(row["maximum"], row["current"] + observed["requested"]),
                    )
                    self.assertEqual(current, observed["current"])

    def test_missing_or_corrupted_pc_population_rejects(self):
        row, definition = self.fixture()
        del row["native_trap_characteristics"][20]
        with self.assertRaises(ValueError):
            verified_trap_characteristics(row, definition)
        with self.assertRaises(ValueError):
            copy_area_damage_snapshot(row, definition, source_stats={})
