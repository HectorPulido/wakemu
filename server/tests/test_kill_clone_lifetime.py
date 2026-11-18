import unittest
from dataclasses import replace
import os
from unittest.mock import patch

import test_combat_kill as kill_tests
from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider


class KillCloneLifetimeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = kill_tests.NativeKillTests().fixture

    def subscribed(self):
        fight, target, packets, phases, handler, effect, invocation = self.fixture()
        effect["target_masks"] = [None, None, None, None, None, [1010], None]
        invocation = replace(invocation, base_uid=200)
        listener = {
            "effect_class": 28,
            "state_uid": None,
            "native_subscription_masks": effect["target_masks"],
            "invocation": {
                "reference": invocation.reference,
                "level": invocation.level,
            },
        }
        fight.native_owned_group_effects = {200: listener}
        return fight, target, packets, phases, handler, effect, invocation, listener

    def test_clone_executes_unretained_under_its_fresh_uid_and_keeps_listener(self):
        (
            fight,
            target,
            packets,
            phases,
            handler,
            effect,
            invocation,
            listener,
        ) = self.subscribed()
        allocations = []
        handler.allocate_uid = lambda: allocations.append(True) or 999

        prepared = handler.prepare_activation(effect, {}, invocation, clone_uid=301)
        self.assertEqual(prepared.native_running_uid, 301)
        self.assertTrue(handler(effect, {}, prepared))

        self.assertEqual([phase[0] for phase in phases], [1, 2, 3, 4])
        self.assertEqual({phase[1] for phase in phases}, {301})
        self.assertEqual(allocations, [])
        self.assertEqual(target.hp, 0)
        self.assertNotIn(301, fight.owned_stat_effects)
        self.assertNotIn(301, getattr(fight, "native_retained_records", {}))
        self.assertIs(fight.native_owned_group_effects[200], listener)
        self.assertEqual(packets[0][0], 12613)

    def test_prepare_rejects_missing_or_mismatched_listener_and_cleans_partial_state(
        self,
    ):
        invalid = (
            "missing",
            "bad_uid",
            "reference",
            "masks",
            "state",
        )
        for defect in invalid:
            with self.subTest(defect=defect):
                fight, _, _, _, handler, effect, invocation, _ = self.subscribed()
                if defect == "missing":
                    fight.native_owned_group_effects.clear()
                elif defect == "bad_uid":
                    clone_uid = 0
                else:
                    clone_uid = 301
                    listener = fight.native_owned_group_effects[200]
                    if defect == "reference":
                        listener["invocation"]["reference"] += 1
                    elif defect == "masks":
                        listener["native_subscription_masks"] = [None] * 7
                    elif defect == "state":
                        listener["state_uid"] = 44
                if defect != "bad_uid":
                    clone_uid = 301
                with self.assertRaises(ValueError):
                    handler.prepare_activation(
                        effect, {}, invocation, clone_uid=clone_uid
                    )
                self.assertEqual(handler.prepared, {})
                self.assertEqual(handler.runners, {})
                self.assertEqual(handler.clone_lifetimes, {})

    def test_exception_after_activation_cleans_clone_but_preserves_original(self):
        fight, _, _, _, handler, effect, invocation, listener = self.subscribed()
        with patch.object(handler, "_prepare_uid", side_effect=RuntimeError("probe")):
            with self.assertRaisesRegex(RuntimeError, "probe"):
                handler.prepare_activation(effect, {}, invocation, clone_uid=301)
        self.assertEqual(handler.prepared, {})
        self.assertEqual(handler.runners, {})
        self.assertEqual(handler.clone_lifetimes, {})
        self.assertIs(fight.native_owned_group_effects[200], listener)

    def test_timing_provider_skips_clone_duration_lookup_but_normal_context_uses_it(
        self,
    ):
        fight, _, _, _, handler, effect, invocation, _ = self.subscribed()
        provider = NativeEffectTimingProvider({})
        clone_contexts = []

        def clone_context(current_effect, current_invocation):
            context = provider.stat(fight, None, current_effect, current_invocation)
            clone_contexts.append(context)
            return context

        handler.context = clone_context
        with patch(
            "wakfu_server.combat_native_timing_context.native_definition_timing",
            side_effect=AssertionError("clone must not read duration"),
        ):
            clone = handler.prepare_activation(effect, {}, invocation, clone_uid=301)
            self.assertTrue(handler(effect, {}, clone))
        self.assertTrue(clone_contexts)
        self.assertTrue(all(not context.retained for context in clone_contexts))
        self.assertTrue(all(context.timer is None for context in clone_contexts))

        normal_effect = dict(
            effect_class=28,
            native_execution_mode=1,
            native_definition_class="eVH",
            native_timing_definition={"rzv": -1, "rzw": 0},
        )
        normal = replace(invocation, native_running_uid=None)
        handler.context = lambda current_effect, current_invocation: provider.stat(
            fight, None, current_effect, current_invocation
        )
        with patch(
            "wakfu_server.combat_native_timing_context.native_definition_timing",
            wraps=__import__(
                "wakfu_server.combat_native_timing_context",
                fromlist=["native_definition_timing"],
            ).native_definition_timing,
        ) as timing:
            normal_context = handler._context(normal_effect, normal)
        timing.assert_called_once_with(normal_effect, normal.level)
        self.assertTrue(normal_context.retained)
        self.assertIsNone(normal_context.timer)

    @unittest.skipUnless(
        os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1",
        "native catalog transitive combat probe is opt-in",
    )
    def test_natural_3263_state546_25910_replay_clone_is_not_retained(self):
        from wakfu_server import equipment_stats, spells
        from wakfu_server.combat_kill import NativeKillHandler
        from jondo_native_support_probe import build_fixture

        original_effective_character = equipment_stats.effective_character
        activation_calls = []

        def breed19_character(row, **kwargs):
            return original_effective_character(dict(row, breed=19), **kwargs)

        original_prepare_activation = NativeKillHandler.prepare_activation

        def observe_activation(handler, effect, values, invocation, **kwargs):
            activation_calls.append(
                (
                    effect.get("effect_class"),
                    invocation.reference,
                    invocation.base_uid,
                    invocation.state_uid,
                    kwargs.get("clone_uid"),
                )
            )
            return original_prepare_activation(
                handler, effect, values, invocation, **kwargs
            )

        with (
            patch.object(equipment_stats, "effective_character", breed19_character),
            patch.object(
                spells, "default_deck", lambda character: spells.encode_deck([5562])
            ),
            patch.object(NativeKillHandler, "prepare_activation", observe_activation),
        ):
            case = build_fixture(
                3263,
                8,
                map_id=889,
                player_position=(5, -39, -12),
                npc_position=(5, -40, -12),
                allies=((3261, 8, (6, -40, -12)),),
            )
            self.assertEqual(case.fight.actors[-7].hp, 70)
            self.assertEqual(case.fight.actors[-8].hp, 80)

            # Run only native turn advances and paid spell casts. Every state,
            # HP value, revival and retained effect below comes from combat.
            for _ in range(30):
                if case.fight.current.id != 7:
                    case.advance()
                    continue
                case.cast(7, 5562, -7)
                if activation_calls:
                    break
                case.advance()
            else:
                self.fail("Native 25910 replay clone did not execute within 30 actions")

        self.assertEqual(len(activation_calls), 1)
        effect_class, reference, parent_uid, state_uid, clone_uid = activation_calls[0]
        self.assertEqual((effect_class, reference), (28, 25910))
        self.assertIs(type(parent_uid), int)
        self.assertIs(type(clone_uid), int)
        target = case.fight.actors[-7]
        self.assertEqual(target.hp, 0)
        self.assertIn(546, {entry.reference for entry in target.state_ledger.entries})
        original_listener = case.fight.native_owned_group_effects.get(parent_uid)
        self.assertIsNotNone(original_listener)
        self.assertEqual(original_listener["invocation"]["reference"], 25910)
        self.assertEqual(original_listener["state_uid"], state_uid)
        self.assertNotIn(clone_uid, case.fight.owned_stat_effects)
        self.assertNotIn(clone_uid, getattr(case.fight, "native_retained_records", {}))


if __name__ == "__main__":
    unittest.main()
