"""Server-inferred event2128 producer; native routing is delegated intact."""
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from wakfu_server.combat_ordinary_events import (
    OrdinaryDisplacementEvents,
    OrdinaryHealingEvents,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation


class MovementReactionProducerTests(TestCase):
    def setUp(self):
        self.events = object.__new__(OrdinaryDisplacementEvents)
        self.invocation = EffectInvocation(
            reference=10, level=20, caster_id=7, target_id=-7, cell=(1, 0, 0)
        )

    def test_changed_actor_preserves_source_caster_and_identity(self):
        with patch.object(
            OrdinaryHealingEvents, "phase", return_value=("observed",)
        ) as phase:
            result = self.events.displacement_completed(
                {}, self.invocation, uid=99, value=2, moved=[(-7, (3, 0, 0), (1, 0, 0))]
            )
        self.assertEqual(result, ("observed",))
        self.assertEqual(phase.call_args.args[2].caster_id, 7)
        self.assertEqual(phase.call_args.args[2].target_id, -7)
        self.assertEqual(phase.call_args.kwargs["uid"], 99)
        self.assertEqual(phase.call_args.kwargs["_event_ids"], (2128,))
        self.assertEqual(phase.call_args.kwargs["channel"], 3)

    def test_no_movement_has_no_reaction(self):
        with patch.object(OrdinaryHealingEvents, "phase") as phase:
            self.events.displacement_completed(
                {}, self.invocation, uid=99, value=0, moved=[(-7, (1, 0, 0), (1, 0, 0))]
            )
        phase.assert_not_called()

    def test_swap_delivers_once_per_changed_actor(self):
        with patch.object(OrdinaryHealingEvents, "phase", return_value=()) as phase:
            self.events.displacement_completed(
                {},
                self.invocation,
                uid=99,
                value=0,
                moved=[(7, (0, 0, 0), (1, 0, 0)), (-7, (1, 0, 0), (0, 0, 0))],
            )
        self.assertEqual([c.args[2].target_id for c in phase.call_args_list], [7, -7])

    def test_duplicate_actor_rejected_before_delivery(self):
        with patch.object(OrdinaryHealingEvents, "phase") as phase:
            with self.assertRaises(ValueError):
                self.events.displacement_completed(
                    {},
                    self.invocation,
                    uid=99,
                    value=0,
                    moved=[(-7, (0, 0, 0), (1, 0, 0)), (-7, (1, 0, 0), (2, 0, 0))],
                )
        phase.assert_not_called()

    def test_other_caster_fails_original_cinetosis_criterion(self):
        from wakfu_server.combat_conditions import (
            ConditionActor,
            ConditionContext,
            evaluate_condition,
        )

        criterion = "GetTriggeringEffectCaster() == GetEffectCaster()"
        for caster, expected in ((7, True), (8, False)):
            context = ConditionContext(
                {"caster": ConditionActor(actor_id=7)},
                triggering_effect_caster_id=caster,
                triggering_effect_present=True,
            )
            self.assertEqual(evaluate_condition(criterion, context), expected)
