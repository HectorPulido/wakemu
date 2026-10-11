"""eWu signed C calculation precedes criteria; application remains strict."""
import unittest
from types import SimpleNamespace
from wakfu_server.combat_state_parameters import interpret_state_parameters
from wakfu_server.combat_state_handler import NativeStateHandler
from wakfu_server.combat_effect_dispatch import (
    EffectDispatcher,
    EffectInvocation,
    UnsupportedEffectExecution,
    run_effect_transaction,
)
from wakfu_server.combat_conditions import ConditionContext
from wakfu_server.combat_state import Actor, Fight


class SignedStateCalculationTests(unittest.TestCase):
    def test_calculation_preserves_signed_short_without_authorizing_application(self):
        self.assertEqual(
            interpret_state_parameters([3624, -1, -1], allow_signed_calculation=True)[
                "level"
            ],
            -1,
        )
        with self.assertRaisesRegex(ValueError, "state level"):
            interpret_state_parameters([3624, -1, -1])

    def fixture(self):
        actor = Actor(7, 0, (0, 0, 0), 100, 6, 3, 10, 10, 3, True)
        enemy = Actor(-7, 1, (1, 0, 0), 100, 6, 3, 1, 10)
        fight = Fight(
            1,
            [actor, enemy],
            {actor.position, enemy.position},
            {0: {actor.position}, 1: {enemy.position}},
        )
        fight.ready(3)
        return fight

    def factory(self, criterion):
        def create(preview):
            effect = dict(
                effect_class=304,
                parameters=[3624, 0, -1, 0, -1, 0],
                parameter_count=3,
                probability_base=100,
                probability_per_level=0,
                minimum_level=0,
                maximum_level=32767,
                criteria=criterion,
                children=[],
                target_masks=[[], [], [], [], [], [], []],
            )
            handler = NativeStateHandler(
                preview,
                [],
                {},
                action_id=1,
                allocate_uid=lambda: 901,
                execute_child=None,
                context=None,
                rng=lambda: 0,
            )
            handler.event_lifecycle = SimpleNamespace(phase=lambda *a, **k: None)
            return EffectDispatcher(
                {"1": effect},
                {304: handler},
                resolve=lambda e, i: (i,),
                condition_context=lambda i: ConditionContext({}),
                probability_accepts=lambda p, i: True,
                group_cells=lambda *a: (),
                actor_position=lambda identity: preview.actors[identity].position,
                prepare_effect=handler.prepare,
            )

        return create

    def test_false_criterion_skips_negative_calculation_without_applying(self):
        fight = self.fixture()
        dispatcher = self.factory("False")(fight)
        self.assertFalse(dispatcher.execute(EffectInvocation(1, 0, 7, 7, (0, 0, 0))))
        self.assertEqual(fight.actors[7].state_ledger.entries, ())
        self.assertEqual(fight.state_wire_payloads, {})

    def test_true_criterion_negative_application_still_rejects_atomically(self):
        fight = self.fixture()
        with self.assertRaisesRegex(UnsupportedEffectExecution, "state level"):
            run_effect_transaction(
                fight, [EffectInvocation(1, 0, 7, 7, (0, 0, 0))], self.factory("True")
            )
        self.assertEqual(fight.actors[7].state_ledger.entries, ())
        self.assertEqual(fight.state_wire_payloads, {})
