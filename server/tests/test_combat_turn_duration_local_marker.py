"""One compound regression for indexed duration marker selection and fallback."""
from dataclasses import asdict
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from wakfu_server import combat_turn_duration as duration_module


class DurationRows(dict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.values_calls = 0

    def values(self):
        self.values_calls += 1
        return super().values()


class TurnDurationLocalMarkerTests(unittest.TestCase):
    def test_indexed_locality_first_marker_order_and_legacy_fallback(self):
        # Real owned routing has one unrelated manager row. The current
        # manager has no eWL; the indexed gate must leave the other row alone.
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_retained_effects import RetainedEffect

        actors = (
            Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 20),
            Actor(8, 1, (1, 0, 0), 100, 6, 3, 10, 20),
        )
        walkable = {(0, 0, 0), (1, 0, 0)}
        fight = Fight(901, actors, walkable, {0: {(0, 0, 0)}, 1: {(1, 0, 0)}})
        fight.phase, fight.order, fight.turn_index, fight.turn_id = (
            "active",
            [7, 8],
            0,
            1,
        )
        fight.native_retained_records.install_owned(
            91, asdict(RetainedEffect(91, 8, 777, 1200, manager_id=8))
        )
        fight.owned_stat_effects[91] = {"effect_class": 777, "family": "other"}
        fight.native_retained_order.append(91)

        def forbidden_values():
            raise AssertionError("global effect rows were scanned")

        fight.owned_stat_effects.values = forbidden_values
        self.assertEqual(duration_module.current_turn_duration(fight, 30000), 30000)

        # The real native condition reader keeps selected manager order: a
        # later marker with the opposite policy cannot override the first.
        from test_retained_local_query import fixture as retained_fixture, payload

        selected, _ = retained_fixture()
        selected.phase = "active"
        selected.order = [2, 1]
        selected.turn_id, selected.turn_index = 2, 1
        selected.native_turn_duration_policy = {
            "source": duration_module.POLICY,
            "duration_ms": 20000,
            "turn_id": 1,
            "actor_id": 2,
        }
        for uid, add_previous in ((11, False), (12, True)):
            selected.owned_stat_effects[uid] = {
                "effect_class": 668,
                "family": "eWL",
                "native_turn_duration_add_previous": add_previous,
                "target_id": 1,
                "payload": payload(uid, 1, 101),
            }
            selected.native_retained_records[uid] = asdict(
                RetainedEffect(uid, 1, 668, 101, manager_id=1)
            )
            selected.native_retained_order.append(uid)
        self.assertEqual(duration_module.current_turn_duration(selected, 30000), 20000)

        # Uncertified/custom storage retains the old global gate and condition
        # reader; no-marker legacy state still avoids the condition query.
        fallback_rows = DurationRows(
            {
                50: {
                    "effect_class": 668,
                    "family": "eWL",
                    "native_turn_duration_add_previous": True,
                },
            }
        )
        legacy = SimpleNamespace(
            current=SimpleNamespace(id=7),
            turn_id=2,
            turn_index=1,
            native_turn_duration_policy={
                "source": duration_module.POLICY,
                "duration_ms": 20000,
                "turn_id": 1,
                "actor_id": 8,
            },
            owned_stat_effects=fallback_rows,
        )
        with patch.object(
            duration_module, "_local_duration_marker_presence", return_value=None
        ), patch(
            "wakfu_server.combat_retained_runtime.native_retained_condition_effects",
            return_value=((100, 668, 50),),
        ) as condition_read:
            self.assertEqual(
                duration_module.current_turn_duration(legacy, 30000), 50000
            )
        self.assertEqual(fallback_rows.values_calls, 1)
        condition_read.assert_called_once_with(legacy, 7)

        fallback_rows_no_marker = DurationRows(
            {
                51: {"effect_class": 777, "family": "other"},
            }
        )
        legacy.turn_id = 3
        legacy.owned_stat_effects = fallback_rows_no_marker
        with patch.object(
            duration_module, "_local_duration_marker_presence", return_value=None
        ), patch(
            "wakfu_server.combat_retained_runtime.native_retained_condition_effects",
            side_effect=AssertionError("legacy no-marker query changed"),
        ):
            self.assertEqual(
                duration_module.current_turn_duration(legacy, 30000), 30000
            )
        self.assertEqual(fallback_rows_no_marker.values_calls, 1)


if __name__ == "__main__":
    unittest.main()
