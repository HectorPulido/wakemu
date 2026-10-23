"""Native fbd HP0 delivers faV death before completing its actual Qq."""
from contextlib import contextmanager
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_combat_wall_area_retirement import NativeWallRetirementTests
from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
from wakfu_server.combat_wall_area import update_wall_hp
from wakfu_server.combat_effect_area import remove_owned_hour_area


class NativeWallDeathTests(unittest.TestCase):
    def fixture(self):
        fight, row, definition = NativeWallRetirementTests().fixture()
        row.update(
            reference=196, native_qq_bhi=False, native_qq_guard_source="Qq.constructor"
        )
        definition.update(entry_masks=[], exit_masks=[], native_removal_masks=[])
        fight.actors[7] = SimpleNamespace(id=7)
        events = NativeAreaEventRuntime(
            fight, SimpleNamespace(), definitions={"196": definition}
        )
        return fight, row, events

    @contextmanager
    def scope(self, fight, identities):
        # Fixture supplies QI constructor authority only. The integration
        # producer exercises the complete existing PL/Qf selected-PV scope.
        self.assertEqual(tuple(identities), (901,))
        yield

    def test_zero_hp_delivers_once_before_completion_without_inventing_qs_removal(self):
        fight, row, events = self.fixture()
        update_wall_hp(row, row["native_wall_constructor"], 0)
        calls = []

        def delivery(actual, definition, source, event_id):
            self.assertIs(actual, row)
            self.assertIs(source, fight.actors[7])
            self.assertFalse(row["native_qq_bhi"])
            self.assertEqual(event_id, 10014)
            self.assertFalse(events.wall_death(row, 7))
            calls.append(event_id)

        with patch(
            "wakfu_server.combat_state_managers.selected_area_pv_scope", self.scope
        ), patch.object(events, "_deliver_event", side_effect=delivery):
            self.assertTrue(events.wall_death(row, 7))
            self.assertFalse(events.wall_death(row, 7))
        self.assertEqual(calls, [10014])
        self.assertTrue(row["native_qq_bhi"])
        self.assertEqual(row["native_qq_guard_source"], "Qq.b")
        self.assertIs(fight.native_effect_areas[901], row)
        self.assertGreaterEqual(row["native_obstacle_id"], 0)

    def test_alive_wall_and_unknown_source_do_not_gain_death_authority(self):
        fight, row, events = self.fixture()
        with patch.object(events, "_deliver_event") as delivery:
            self.assertFalse(events.wall_death(row, 7))
            delivery.assert_not_called()
        with self.assertRaisesRegex(ValueError, "death source"):
            events.wall_death(row, 999)
        row.pop("native_qq_bhi")
        with self.assertRaisesRegex(ValueError, "completion-state"):
            events.wall_death(row, 7)

    def test_failed_callback_does_not_complete_and_reentrant_guard_is_released(self):
        fight, row, events = self.fixture()
        update_wall_hp(row, row["native_wall_constructor"], 0)
        with patch(
            "wakfu_server.combat_state_managers.selected_area_pv_scope", self.scope
        ), patch.object(
            events, "_deliver_event", side_effect=ValueError("callback failure")
        ):
            with self.assertRaisesRegex(ValueError, "callback failure"):
                events.wall_death(row, 7)
        self.assertFalse(row["native_qq_bhi"])
        self.assertEqual(row["native_qq_guard_source"], "Qq.constructor")
        self.assertEqual(events._dying_area_uids, set())

    def test_server_policy_defers_qi_retirement_until_outer_scope_and_is_idempotent(
        self,
    ):
        fight, row, events = self.fixture()
        slot = row["native_obstacle_id"]
        removed = []
        callbacks = SimpleNamespace(
            removed=lambda actual: removed.append(actual["uid"])
        )
        with patch(
            "wakfu_server.combat_state_managers.selected_area_pv_scope", self.scope
        ), patch.object(events, "_deliver_event"), patch.object(
            events,
            "remove_parent",
            side_effect=lambda actual: remove_owned_hour_area(
                fight, actual["uid"], callbacks=callbacks
            ),
        ):
            with events.wall_retirement_scope():
                update_wall_hp(row, row["native_wall_constructor"], 0)
                with events.wall_retirement_scope():
                    self.assertTrue(events.wall_death(row, 7))
                    self.assertFalse(events.wall_death(row, 7))
                self.assertIs(fight.native_effect_areas[901], row)
                self.assertIsNotNone(fight.native_qi_slots[slot])
            self.assertNotIn(901, fight.native_effect_areas)
            self.assertIsNone(fight.native_qi_slots[slot])
            with events.wall_retirement_scope():
                pass
        self.assertEqual(removed, [901])

    def test_failed_outer_group_does_not_publish_deferred_retirement(self):
        fight, row, events = self.fixture()
        with patch(
            "wakfu_server.combat_state_managers.selected_area_pv_scope", self.scope
        ), patch.object(events, "_deliver_event"), patch.object(
            events, "remove_parent"
        ) as retire:
            with self.assertRaisesRegex(ValueError, "failed child"):
                with events.wall_retirement_scope():
                    update_wall_hp(row, row["native_wall_constructor"], 0)
                    events.wall_death(row, 7)
                    raise ValueError("failed child")
            retire.assert_not_called()
        self.assertIs(fight.native_effect_areas[901], row)
        self.assertEqual(events._dead_wall_retirements, set())


if __name__ == "__main__":
    unittest.main()
