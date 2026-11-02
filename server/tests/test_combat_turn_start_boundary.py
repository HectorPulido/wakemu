"""Shared START ordering, terminal short-circuit and caller-flag contracts."""
from contextlib import ExitStack
from types import SimpleNamespace
import unittest
from unittest.mock import patch


class TurnStartBoundaryTests(unittest.TestCase):
    def dispatch(
        self, *, objective=True, terminate=None, native_events=True, area_callbacks=True
    ):
        from wakfu_server.combat_turn_start_boundary import deliver_start_boundary

        calls = []
        actor = SimpleNamespace(id=7)
        fight = SimpleNamespace(
            phase="active",
            current=actor,
            native_encounter_objective_policy={} if objective else None,
        )

        def observe(label):
            def callback(*args, **kwargs):
                actual = (
                    "objective:" + kwargs["boundary"] if label == "objective" else label
                )
                calls.append(actual)
                if actual == terminate:
                    fight.phase, fight.current = "finished", None
                    return {"terminal": True}
                return None

            return callback

        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(fight=fight),
            native_area_events=SimpleNamespace(turn_start=observe("area_start")),
        )
        hooks = {
            "combat_encounter_objective.deliver_objective_score_marker": "objective_score",
            "combat_equipment_external_events.deliver_completed_round": "completed_round",
            "combat_encounter_objective.deliver_owned_objective_boundary": "objective",
            "combat_periodic_aptitude.renew_periodic_aptitudes": "aptitudes",
            "combat_npc_phase_controller.deliver_npc_score_result": "score_result",
            "combat_npc_phase_controller.deliver_npc_table_phase": "npc_table",
            "combat_turn_events.deliver_turn_start": "start1001",
            "combat_ogrest_phase_controller.deliver_ogrest_post_turn_start": "ogrest_post_start",
            "combat_encounter_table_listeners.deliver_owned_post_start_listeners": "owned_post_start",
        }
        with ExitStack() as patches:
            for name, label in hooks.items():
                patches.enter_context(
                    patch("wakfu_server." + name, side_effect=observe(label))
                )
            deliver_start_boundary(
                dispatcher,
                actor_id=actor.id,
                native_events=native_events,
                area_callbacks=area_callbacks,
            )
        return calls

    def test_real_dispatch_order_includes_npc_phase_and_post_start_consumers(self):
        self.assertEqual(
            self.dispatch(),
            [
                "objective_score",
                "completed_round",
                "objective:completed_round",
                "aptitudes",
                "score_result",
                "objective:owned_boss_start",
                "npc_table",
                "start1001",
                "ogrest_post_start",
                "owned_post_start",
                "area_start",
            ],
        )

    def test_terminal_objective_and_start_callback_stop_later_consumers(self):
        self.assertEqual(
            self.dispatch(terminate="objective:completed_round"),
            [
                "objective_score",
                "completed_round",
                "objective:completed_round",
            ],
        )
        self.assertEqual(
            self.dispatch(objective=False, terminate="start1001"),
            [
                "completed_round",
                "aptitudes",
                "score_result",
                "npc_table",
                "start1001",
            ],
        )

    def test_native_events_and_area_callbacks_remain_independent_caller_flags(self):
        self.assertEqual(self.dispatch(native_events=False), ["area_start"])
        self.assertEqual(self.dispatch(native_events=False, area_callbacks=False), [])
        self.assertEqual(
            self.dispatch(objective=False, area_callbacks=False),
            [
                "completed_round",
                "aptitudes",
                "score_result",
                "npc_table",
                "start1001",
                "ogrest_post_start",
                "owned_post_start",
            ],
        )


if __name__ == "__main__":
    unittest.main()
