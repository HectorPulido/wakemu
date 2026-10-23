"""Owned production end dispatch preserves atomic, once-only phase ordering."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from test_combat_turn_events import OwnedTurnEndTests
from wakfu_server.combat_server_spell import prepare_server_turn_end
from wakfu_server.fight_checkpoint_store import snapshot


class EncounterTurnEndCallerTests(TestCase):
    def _factory(self, seen, *, fail_event=None):
        def factory(preview, plan):
            def replay(event, **kwargs):
                seen.append(event.event_ids[0])
                if event.event_ids == (fail_event,):
                    raise ValueError("second phase deliberately rejected")
                return ()

            return (
                SimpleNamespace(
                    native_retention=SimpleNamespace(fight=preview),
                    native_clone_authority=object(),
                    replay_event=replay,
                ),
                [],
            )

        return factory

    def test_production_caller_uses_selected_order_and_preserves_legacy_default(self):
        for order in ((1002, 1037), (1037, 1002)):
            with self.subTest(order=order):
                fight, _, _ = OwnedTurnEndTests().fixture()
                before = snapshot(fight)
                seen = []
                with patch(
                    "wakfu_server.combat_server_spell.server_runtime",
                    return_value=(self._factory(seen), None),
                ), patch(
                    "wakfu_server.combat_encounter_turn_end_order.turn_end_event_order",
                    return_value=order,
                ) as select_order:
                    candidate, _ = prepare_server_turn_end(
                        {},
                        {},
                        fight,
                        b"",
                        actor_id=7,
                        action_id=1,
                    )
                self.assertEqual(seen, [order[0]] * 4 + [order[1]] * 4)
                select_order.assert_called_once()
                self.assertEqual(select_order.call_args.kwargs, {"actor_id": 7})
                self.assertEqual(snapshot(fight), before)
                self.assertEqual(
                    set(candidate.native_turn_event_deliveries),
                    {"1:7:end", "1:7:regeneration"},
                )
                again = []
                with patch(
                    "wakfu_server.combat_server_spell.server_runtime",
                    return_value=(self._factory(again), None),
                ), patch(
                    "wakfu_server.combat_encounter_turn_end_order.turn_end_event_order",
                    return_value=order,
                ), self.assertRaisesRegex(
                    ValueError, "already delivered"
                ):
                    prepare_server_turn_end(
                        {}, {}, candidate, b"", actor_id=7, action_id=2
                    )
                self.assertFalse(again)

    def test_reversed_second_phase_failure_rolls_back_first_phase_delivery(self):
        fight, _, _ = OwnedTurnEndTests().fixture()
        before = snapshot(fight)
        seen = []
        with patch(
            "wakfu_server.combat_server_spell.server_runtime",
            return_value=(self._factory(seen, fail_event=1002), None),
        ), patch(
            "wakfu_server.combat_encounter_turn_end_order.turn_end_event_order",
            return_value=(1037, 1002),
        ), self.assertRaisesRegex(
            ValueError, "second phase deliberately rejected"
        ):
            prepare_server_turn_end({}, {}, fight, b"", actor_id=7, action_id=1)
        self.assertEqual(seen, [1037] * 4 + [1002])
        self.assertEqual(snapshot(fight), before)
