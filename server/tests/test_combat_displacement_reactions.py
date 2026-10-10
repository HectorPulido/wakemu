"""Native null runners own2128; displacement preserves their single producer."""
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

    def test_changed_actors_do_not_duplicate_native_null_reaction(self):
        # Original416001 reacts to native displacement and emits2128 through
        # child416114. The old synthetic completion was a second producer.
        for moved in (
            [(-7, (3, 0, 0), (1, 0, 0))],
            [(7, (0, 0, 0), (1, 0, 0)), (-7, (1, 0, 0), (0, 0, 0))],
            [(-7, (1, 0, 0), (1, 0, 0))],
        ):
            with patch.object(OrdinaryHealingEvents, "phase") as phase:
                result = self.events.displacement_completed(
                    {}, self.invocation, uid=99, value=2, moved=moved
                )
            self.assertEqual(result, ())
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
