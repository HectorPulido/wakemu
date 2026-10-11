"""Actual held-card casts exercise native passive branches and turn budgets."""
import os
import unittest

import test_ecaflip_hand_passives_pipeline as hand


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class EcaflipCardPassiveSemanticsTests(unittest.TestCase):
    fixture = hand.EcaflipHandPassivesPipelineTests.fixture
    cast = hand.EcaflipHandPassivesPipelineTests.cast
    cards = staticmethod(hand.EcaflipHandPassivesPipelineTests.cards)
    level = staticmethod(hand.EcaflipHandPassivesPipelineTests.level)

    @staticmethod
    def retained(fight, reference):
        from wakfu_server.combat_retained_runtime import (
            native_retained_condition_effects,
        )

        return tuple(
            row
            for row in native_retained_condition_effects(fight, 7)
            if row[0] == reference
        )

    def test_lucky_tarot_uses_actual_card_weight_instead_of_default_seven(self):
        observed = {}
        for equipped in (False, True):
            data = self.fixture(seed=7, passives=(2059,) if equipped else ())
            held = sorted(
                reference for reference in self.cards(data[2]) if reference >= 7939
            )
            self.assertTrue(held)
            reference = held[0]
            before = self.level(data[2], 3683)
            data = self.cast(data, reference)
            delta = self.level(data[2], 3683) - before
            # Native371477..371489 supply the card's indexed contribution;
            # 359822 supplies7 only without2059. No card/state is injected.
            self.assertEqual(delta, min(reference - 7938, 12) if equipped else 7)
            self.assertNotIn(reference, self.cards(data[2]))
            observed[equipped] = delta
        self.assertGreater(observed[True], 0)

    def test_traps_redraws_only_the_first_played_card_in_the_turn(self):
        data = self.fixture(seed=7, passives=(5251,))
        self.assertEqual(len(self.cards(data[2])), 1)
        original = next(iter(self.cards(data[2])))
        data = self.cast(data, original)
        self.assertEqual(len(self.cards(data[2])), 1)
        self.assertTrue(self.retained(data[2], 359838))
        second = next(iter(self.cards(data[2])))
        data = self.cast(data, second)
        self.assertEqual(self.cards(data[2]), set())
        self.assertEqual(len(self.retained(data[2], 359838)), 1)

    def test_prophetic_tarot_same_card_class_rewards_once_per_turn(self):
        # Native359824 classA gives1AP;359827 classB gives25 Racha.
        classes = (
            {7938, 7940, 7942, 7943, 7945, 7947, 7950},
            {7939, 7941, 7944, 7946, 7948, 7949},
        )
        for group, marker in zip(classes, (359832, 359835)):
            for seed in range(24):
                data = self.fixture(seed=seed, passives=(5246, 2068, 2080, 5250))
                matching = sorted(self.cards(data[2]) & group)
                if len(matching) >= 2:
                    break
            else:
                self.fail("No naturally drawn matching card pair")
            data = self.cast(data, matching[0])
            self.assertFalse(self.retained(data[2], marker))
            before = self.level(data[2], 3683)
            data = self.cast(data, matching[1])
            self.assertTrue(self.retained(data[2], marker))
            if marker == 359835:
                # The ordinary card contributes7 in addition to passive25.
                self.assertEqual(self.level(data[2], 3683) - before, 32)

    def test_misfortune_turn_reward_requires_the_actual_unplayed_optional_card(self):
        import test_aniripsa_grant_summon_pipeline as lifecycle

        for played in (False, True):
            for seed in range(24):
                data = self.fixture(seed=seed, passives=(2068, 2080, 5250))
                if 7949 in self.cards(data[2]):
                    break
            else:
                self.fail("No naturally drawn optional Misfortune card")
            if played:
                data = self.cast(data, 7949)
                self.assertNotIn(7949, self.cards(data[2]))
            before = data[2].actors[7].effect_stats[7]
            from unittest.mock import patch
            from wakfu_server.combat_effect_dispatch import EffectDispatcher

            execute = EffectDispatcher.execute
            failure = []

            def trace_failure(dispatcher, invocation, **kwargs):
                try:
                    return execute(dispatcher, invocation, **kwargs)
                except Exception:
                    if not failure:
                        failure.append(
                            {
                                "reference": invocation.reference,
                                "caster": invocation.caster_id,
                                "target": invocation.target_id,
                                "ancestors": repr(kwargs.get("ancestors")),
                                "trigger": repr(invocation.native_trigger_context),
                                "execution_keys": repr(
                                    dispatcher._active_execution_keys
                                ),
                                "qj_keys": repr(
                                    __import__(
                                        "wakfu_server.combat_event_replay",
                                        fromlist=["NativeTriggerHistory"],
                                    )
                                    .NativeTriggerHistory()
                                    .active
                                ),
                            }
                        )
                    raise

            with patch.object(EffectDispatcher, "execute", trace_failure):
                try:
                    lifecycle.AniripsaGrantSummonPipelineTests.end_current_turn(
                        self, data[2], data
                    )
                except Exception as error:
                    self.fail(f"Actual turn replay failed: {error}; path={failure}")
            # Native162572 requires the actual649 grant359526. Its999 child
            # ratio100% selects actual actor level200;371494 grants3*200.
            self.assertEqual(
                data[2].actors[7].effect_stats[7] - before, 0 if played else 600
            )
