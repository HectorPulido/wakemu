"""Actual monster state selectors use eNC's full selected-actor reader."""
import unittest
from copy import deepcopy
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class ChallengerTriggerPredicateTests(unittest.TestCase):
    def test_installed_native_oracle_player_companion_other_and_null(self):
        # Installed eNC/eII oracle: PLAYER_CHARACTER and COMPANION return0;
        # other kinds and proven null return-1, for both triggering aliases.
        for selector in ("triggeringCaster", "triggeringTarget"):
            for challenger in (False, True):
                context = ConditionContext(
                    {selector.lower(): ConditionActor(is_challenger=challenger)},
                    triggering_effect_present=True,
                )
                self.assertEqual(
                    evaluate_condition(f'IsChallenger("{selector}")', context),
                    challenger,
                )
            self.assertFalse(
                evaluate_condition(
                    f'IsChallenger("{selector}")',
                    ConditionContext({}, triggering_effect_present=False),
                )
            )

    def test_actual_non_ehg_area_is_native_null(self):
        self.assertFalse(
            evaluate_condition(
                'IsChallenger("triggeringTarget")',
                ConditionContext(
                    {"triggeringtarget": ConditionActor(is_native_ehg=False)},
                    triggering_effect_present=True,
                ),
            )
        )

    def test_actual_chafer265825_and_yokai283717_criteria(self):
        # Actual initialstate5620/child265825 (monster4744) and
        # initialstate6051/child283717 (monsters5056/5265), sealed catalog.
        criterion = (
            'IsChallenger("triggeringTarget")\r\n'
            'and not HasEffectWithSpecificId("caster", 283718)\r\n'
            "and GetTriggeringEffectValue() > 0"
        )
        for challenger in (False, True):
            context = ConditionContext(
                {
                    "triggeringtarget": ConditionActor(is_challenger=challenger),
                    "caster": ConditionActor(retained_effect_ids=frozenset()),
                },
                triggering_effect_present=True,
                triggering_effect_value=5,
            )
            self.assertEqual(
                evaluate_condition('IsChallenger("triggeringTarget")', context),
                challenger,
            )
            self.assertEqual(evaluate_condition(criterion, context), challenger)

    def test_real_native_event_replay_uses_selected_trigger_actor(self):
        import test_combat_event_replay as source_fixture
        from wakfu_server.combat_event_replay import (
            NativeCloneAuthority,
            NativeExternalEvent,
        )

        fixture = source_fixture.NativeEventReplayTests()
        fixture.setUpClass()
        fixture.fixture = deepcopy(fixture.fixture)
        for row in fixture.fixture["retained_metadata"]["effects"].values():
            row["event_execution_count_per_level"] = 0.0
        fixture.setUp()
        # Keep the sealed retained/PL engine fixture; substitute actual265825
        # criterion to test its native replay guard without certifying a mob.
        fixture.effects["308265"]["criteria"] = 'IsChallenger("triggeringTarget")'
        row = fixture.fight.native_owned_group_effects[900]
        row["native_subscription_masks"][5] = [1003]
        fixture.retention.metadata["effects"]["308265"][
            "event_reverse_subscription"
        ] = False
        calls = []
        fixture.dispatcher.handlers[400] = lambda *args: (calls.append(args) or True)
        context = ConditionContext(
            {"triggeringtarget": ConditionActor(is_challenger=True)},
            triggering_effect_present=True,
        )
        authority = NativeCloneAuthority(lambda *args: True, lambda *args: context)
        fixture.replay(NativeExternalEvent(7, (1002,), 6), authority=authority)
        self.assertEqual(calls, [])
        fixture.replay(NativeExternalEvent(7, (1003,), 6), authority=authority)
        self.assertEqual(len(calls), 1)

    def test_unknown_kind_source_and_selector_remain_rejected(self):
        for context in (
            ConditionContext({}),
            ConditionContext(
                {"triggeringtarget": ConditionActor()}, triggering_effect_present=True
            ),
        ):
            with self.assertRaises(UnknownCondition):
                evaluate_condition('IsChallenger("triggeringTarget")', context)
        with self.assertRaisesRegex(UnknownCondition, "IsChallenger selector"):
            evaluate_condition('IsChallenger("unsupported")', ConditionContext({}))
        with self.assertRaisesRegex(UnknownCondition, "IsInFight selector"):
            evaluate_condition('IsInFight("eventTarget")', ConditionContext({}))
