"""Actual hostile AP removal and distance-qualified Xelor subscriptions."""
import unittest
from unittest.mock import patch
import test_xelor_runtime_pipeline as helpers


class XelorAPLossPassiveRuntimeTests(unittest.TestCase):
    def observe_slowdown(self, passive, distance):
        from wakfu_server.combat_effect_dispatch import EffectDispatcher

        helper = helpers.XelorRuntimePipelineTests()
        data = helper.fixture(passives=(passive,) if passive else (), seed=17)
        fight = data[2]
        if distance == 2:
            fight.move(3, 7, [(-7, -7, -1)])
        self.assertEqual(
            abs(fight.actors[7].position[0] - fight.actors[-7].position[0])
            + abs(fight.actors[7].position[1] - fight.actors[-7].position[1]),
            distance,
        )
        before = dict(
            ap=fight.actors[-7].ap,
            wp=fight.actors[7].effect_stats[4],
            hp=fight.actors[-7].hp,
        )
        trace = []
        execute = EffectDispatcher.execute

        def observe(dispatcher, invocation, **kwargs):
            result = execute(dispatcher, invocation, **kwargs)
            if invocation.reference in (
                349651,
                349652,
                349653,
                314331,
                314333,
                314334,
                314321,
                314330,
                314322,
                314328,
                314329,
            ):
                trace.append(
                    (
                        invocation.reference,
                        invocation.caster_id,
                        invocation.target_id,
                        result,
                    )
                )
            return result

        with patch.object(EffectDispatcher, "execute", observe):
            tx = helper.cast(data, 775, fight.actors[-7].position, action_id=10)
        after = tx.fight
        evidence = dict(
            passive=passive,
            distance=distance,
            before=before,
            after_ap=after.actors[-7].ap,
            after_wp=after.actors[7].effect_stats[4],
            states=helper.states(after.actors[-7]),
            trace=trace,
        )
        cancelled = (passive == 7193 and distance == 2) or (
            passive == 7195 and distance == 3
        )
        if cancelled:
            # Actual430 -100% cancels the triggering AP loss, then applies the state.
            self.assertEqual(after.actors[-7].ap, before["ap"], evidence)
            self.assertTrue(
                any(ref in (314333, 314322) and ok for ref, _, _, ok in trace), evidence
            )
        else:
            self.assertLess(after.actors[-7].ap, before["ap"], evidence)
        return before, after, trace, evidence

    def test_time_theft_wp_reward_requires_owned_passive_and_actual_removal(self):
        for passive in (None, 5351):
            with self.subTest(passive=passive):
                before, after, trace, evidence = self.observe_slowdown(passive, 3)
                reward = sum(ref == 349652 and bool(ok) for ref, _, _, ok in trace)
                self.assertEqual(reward, 1 if passive else 0, evidence)
                self.assertEqual(
                    after.actors[7].effect_stats[4], before["wp"] - 1 + reward, evidence
                )

    def test_close_removal_branch_has_actual_near_and_far_controls(self):
        for distance in (2, 3):
            with self.subTest(distance=distance):
                (
                    baseline_before,
                    baseline_after,
                    _,
                    baseline_evidence,
                ) = self.observe_slowdown(None, distance)
                self.assertLess(
                    baseline_after.actors[-7].ap,
                    baseline_before["ap"],
                    baseline_evidence,
                )
                _, selected, trace, evidence = self.observe_slowdown(7193, distance)
                self.assertEqual(
                    helpers.XelorRuntimePipelineTests.states(selected.actors[-7]).get(
                        7790
                    ),
                    3 if distance == 2 else None,
                    evidence,
                )
                successful = {ref for ref, _, _, ok in trace if ok}
                self.assertEqual(314334 in successful, distance == 2, evidence)

    def test_distant_removal_branch_has_actual_near_and_far_controls(self):
        for distance in (2, 3):
            with self.subTest(distance=distance):
                (
                    baseline_before,
                    baseline_after,
                    _,
                    baseline_evidence,
                ) = self.observe_slowdown(None, distance)
                self.assertLess(
                    baseline_after.actors[-7].ap,
                    baseline_before["ap"],
                    baseline_evidence,
                )
                _, selected, trace, evidence = self.observe_slowdown(7195, distance)
                self.assertEqual(
                    helpers.XelorRuntimePipelineTests.states(selected.actors[-7]).get(
                        6774
                    ),
                    20 if distance == 3 else None,
                    evidence,
                )
                successful = {ref for ref, _, _, ok in trace if ok}
                self.assertEqual(314328 in successful, distance == 3, evidence)

    def test_time_theft_reward_does_not_erase_victim_ap_loss_at_turn_boundaries(self):
        import test_aniripsa_grant_summon_pipeline as turn_helpers

        helper = helpers.XelorRuntimePipelineTests()
        turns = turn_helpers.AniripsaGrantSummonPipelineTests()
        for passive in (None, 5351):
            with self.subTest(passive=passive):
                data = helper.fixture(passives=(passive,) if passive else (), seed=17)
                source = data[2]
                target = source.actors[-7]
                before_ap, maximum_ap = target.ap, target.max_ap
                before_wp = source.actors[7].effect_stats[4]
                self.assertEqual(before_ap, maximum_ap)
                paid = helper.cast(data, 775, target.position, action_id=40)
                data = helper.adopt(data, paid.fight)
                fight = data[2]
                loss = before_ap - fight.actors[-7].ap
                self.assertGreater(loss, 0)
                self.assertEqual(
                    fight.actors[7].effect_stats[4],
                    before_wp - 1 + int(passive is not None),
                )
                hp = fight.actors[-7].hp

                turns.end_current_turn(fight, data)
                self.assertEqual(fight.current.id, -7)
                self.assertEqual(fight.actors[-7].ap, before_ap - loss)
                self.assertEqual(fight.actors[-7].max_ap, maximum_ap)
                self.assertEqual(fight.actors[-7].hp, hp)

                # The victim's completed turn expires the loss and restores its
                # next budget. No second cast or synthetic expiration is used.
                turns.end_current_turn(fight, data)
                self.assertEqual(fight.current.id, 7)
                self.assertEqual(fight.actors[-7].ap, maximum_ap)
                self.assertEqual(fight.actors[-7].hp, hp)
                turns.end_current_turn(fight, data)
                self.assertEqual(fight.current.id, -7)
                self.assertEqual(fight.actors[-7].ap, maximum_ap)
                self.assertEqual(fight.actors[-7].max_ap, maximum_ap)
                self.assertEqual(fight.actors[-7].hp, hp)
