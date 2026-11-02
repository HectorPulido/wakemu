"""Live and forecast AI end boundaries honor the admitted native scene order."""
import random
import unittest
from unittest.mock import patch

import test_combat_encounter_turn_end_order as boundary_fixtures
import test_combat_turn_events as turn_fixtures
from wakfu_ai.native.native_oracle import NativeOracle
from wakfu_server.fight_checkpoint_store import snapshot


class NativeOracleTurnEndOrderTests(unittest.TestCase):
    def invoke(self, fight, seen, *, forecast, fail_event=None):
        oracle = object.__new__(NativeOracle)
        factory = boundary_fixtures.EncounterTurnEndCallerTests()._factory(
            seen, fail_event=fail_event
        )
        with patch.object(
            oracle, "factory", return_value=(factory, None)
        ), patch.object(oracle, "_rng", return_value=random.Random(7)):
            if forecast:
                return oracle.end_boundary(fight, actor_id=7, action_id=1)
            return oracle.live_end_boundary(fight, actor_id=7, action_id=1)

    def test_live_and_forecast_share_selected_order_without_mutating_source(self):
        for forecast in (True, False):
            for order in ((1002, 1037), (1037, 1002)):
                with self.subTest(forecast=forecast, order=order):
                    fight, _, _ = turn_fixtures.OwnedTurnEndTests().fixture()
                    before, seen = snapshot(fight), []
                    with patch(
                        "wakfu_server.combat_encounter_turn_end_order.turn_end_event_order",
                        return_value=order,
                    ) as selected:
                        candidate, _ = self.invoke(fight, seen, forecast=forecast)
                    self.assertEqual(seen, [order[0]] * 4 + [order[1]] * 4)
                    selected.assert_called_once()
                    self.assertEqual(selected.call_args.kwargs, {"actor_id": 7})
                    self.assertEqual(snapshot(fight), before)
                    self.assertEqual(
                        set(candidate.native_turn_event_deliveries),
                        {"1:7:end", "1:7:regeneration"},
                    )

    def test_second_phase_rejection_rolls_back_live_and_forecast_boundary(self):
        for forecast in (True, False):
            with self.subTest(forecast=forecast):
                fight, _, _ = turn_fixtures.OwnedTurnEndTests().fixture()
                before, seen = snapshot(fight), []
                with patch(
                    "wakfu_server.combat_encounter_turn_end_order.turn_end_event_order",
                    return_value=(1037, 1002),
                ), self.assertRaisesRegex(
                    ValueError, "second phase deliberately rejected"
                ):
                    self.invoke(fight, seen, forecast=forecast, fail_event=1002)
                self.assertEqual(seen, [1037] * 4 + [1002])
                self.assertEqual(snapshot(fight), before)

    def test_live_and_forecast_preserve_normal_end_hooks_and_objective_stop(self):
        from contextlib import ExitStack
        from wakfu_server.combat_server_spell import prepare_server_turn_end

        for forecast in (True, False):
            for objective_terminal in (None, "completed"):
                with self.subTest(
                    forecast=forecast, objective_terminal=objective_terminal
                ):
                    recorded = []
                    for caller in ("ordinary", "oracle"):
                        fight, _, _ = turn_fixtures.OwnedTurnEndTests().fixture()
                        fight.native_encounter_objective_policy = {"test": "owned"}
                        fight.native_ogrest_phase_context = {"test": "owned"}
                        seen = []
                        hooks = (
                            (
                                "combat_encounter_objective.deliver_objective_score_marker",
                                "objective_score",
                            ),
                            (
                                "combat_npc_phase_controller.deliver_npc_score_result",
                                "npc_score",
                            ),
                            (
                                "combat_ogrest_phase_controller.finish_ogrest_player_turn",
                                "ogrest_end",
                            ),
                            (
                                "combat_encounter_terminal_cleanup.deliver_terminal_helper_cleanup",
                                "cleanup",
                            ),
                            ("dungeon_optional_votes.observe_turn", "vote_observation"),
                        )
                        with ExitStack() as stack:
                            for path, label in hooks:
                                stack.enter_context(
                                    patch(
                                        "wakfu_server." + path,
                                        side_effect=lambda *args, _label=label, **kwargs: seen.append(
                                            _label
                                        ),
                                    )
                                )

                            def objective(*args, **kwargs):
                                seen.append("objective:" + kwargs["boundary"])
                                return objective_terminal

                            stack.enter_context(
                                patch(
                                    "wakfu_server.combat_encounter_objective.deliver_owned_objective_boundary",
                                    side_effect=objective,
                                )
                            )
                            stack.enter_context(
                                patch(
                                    "wakfu_server.combat_encounter_turn_end_order.turn_end_event_order",
                                    return_value=(1002, 1037),
                                )
                            )
                            if caller == "ordinary":
                                factory = boundary_fixtures.EncounterTurnEndCallerTests()._factory(
                                    seen
                                )
                                stack.enter_context(
                                    patch(
                                        "wakfu_server.combat_server_spell.server_runtime",
                                        return_value=(factory, None),
                                    )
                                )
                                prepare_server_turn_end(
                                    {}, {}, fight, b"", actor_id=7, action_id=1
                                )
                            else:
                                self.invoke(fight, seen, forecast=forecast)
                        self.assertFalse(
                            getattr(fight, "native_turn_event_deliveries", {})
                        )
                        recorded.append(seen)
                    expected = [
                        "objective_score",
                        "npc_score",
                        *([1002] * 4),
                        "ogrest_end",
                        "objective:owned_player_end",
                    ]
                    if objective_terminal is None:
                        expected += [1037] * 4
                    expected += ["cleanup", "vote_observation"]
                    self.assertEqual(recorded[0], expected)
                    self.assertEqual(recorded[1], recorded[0])
