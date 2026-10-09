import unittest
from dataclasses import replace
from types import SimpleNamespace
from wakfu_server.combat_death_script import (
    NativeDeathScriptHandler,
    remove_death_script,
)
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_runner_callbacks import runner_value_scope


class DeathScriptTests(unittest.TestCase):
    def fixture(self, amount=37, *, retained=True, executable=True, mutation=None):
        actor = SimpleNamespace(id=1, hp=0, native_death_script_id=42)
        fight = SimpleNamespace(
            id=4, phase="active", actors={1: actor}, owned_stat_effects={}
        )
        packets, phases = [], []
        sequence = iter(range(101, 120))
        handler = NativeDeathScriptHandler(
            fight,
            packets,
            action_id=5,
            allocate_uid=lambda: next(sequence),
            context=lambda *args: StatExecutionContext(
                executable, True, None, retained, b"", None
            ),
            rng=lambda: 0,
        )

        class Events:
            def phase(self, effect, invocation, **kwargs):
                phases.append(
                    (
                        kwargs["channel"],
                        kwargs["uid"],
                        kwargs["value"],
                        kwargs["_event_ids"],
                    )
                )
                if mutation:
                    mutation(kwargs["channel"], kwargs["runner_modifier"], handler)

            def register_applied(self, effect, invocation, uid):
                self.registered = uid

        handler.event_lifecycle = Events()
        effect = dict(
            effect_class=1099,
            parameters=[amount, 0],
            target_masks=[[] for _ in range(7)],
        )
        invocation = EffectInvocation(185395, 20, 1, 1, (0, 0, 0))
        return actor, fight, packets, phases, handler, effect, invocation

    def test_native_signed_assignments_and_dead_target_allowed(self):
        for amount in [-(2**31), -1, 0, 37, 2**31 - 1]:
            with self.subTest(amount=amount):
                (
                    actor,
                    fight,
                    packets,
                    phases,
                    handler,
                    effect,
                    invocation,
                ) = self.fixture(amount)
                invocation = handler.prepare(effect, {}, invocation)
                self.assertEqual(actor.native_death_script_id, 42)
                self.assertTrue(handler(effect, {}, invocation))
                self.assertEqual(actor.native_death_script_id, amount)
                self.assertEqual([p[0] for p in phases], [1, 2, 3, 4])
                self.assertEqual({p[1] for p in phases}, {101})
                self.assertTrue(all(p[3] == (0,) for p in phases))
                self.assertEqual(packets[0][0], 12613)
                self.assertEqual(handler.runners, {})

    def test_immediate_and_retained_delivery_preserve_distinct_native_execution_paths(
        self,
    ):
        from wakfu_server.combat_death_script_snapshot import (
            immediate_death_script_packet,
        )

        for retained in (False, True):
            with self.subTest(retained=retained):
                (
                    actor,
                    fight,
                    packets,
                    phases,
                    handler,
                    effect,
                    invocation,
                ) = self.fixture(amount=1100010, retained=retained)
                self.assertTrue(
                    handler(effect, {}, handler.prepare(effect, {}, invocation))
                )
                self.assertEqual(actor.native_death_script_id, 1100010)
                self.assertEqual(packets[0][0], 12613)
                self.assertEqual(packets[0][1][12], int(not retained))
                self.assertEqual(bool(fight.owned_stat_effects), retained)
                snapshot = immediate_death_script_packet(fight, actor, 5)
                if retained:
                    self.assertIsNone(snapshot)
                    self.assertIsNone(actor.native_immediate_death_script)
                else:
                    self.assertEqual(snapshot[0], 12613)
                    self.assertEqual(
                        snapshot[1],
                        next(packet for opcode, packet in packets if opcode == 12613),
                    )
                    self.assertEqual(actor.native_immediate_death_script["uid"], 101)

    def test_immediate_snapshot_rejects_changed_value_and_retained_uid_collision(self):
        from wakfu_server.combat_death_script_snapshot import (
            immediate_death_script_packet,
        )

        actor, fight, packets, phases, handler, effect, invocation = self.fixture(
            amount=1100010, retained=False
        )
        self.assertTrue(handler(effect, {}, invocation))
        actor.native_death_script_id += 1
        with self.assertRaisesRegex(ValueError, "no longer matches"):
            immediate_death_script_packet(fight, actor, 5)

        actor.native_death_script_id = 1100010
        fight.owned_stat_effects[101] = dict(effect_class=1)
        with self.assertRaisesRegex(ValueError, "UID is retained"):
            immediate_death_script_packet(fight, actor, 5)

    def test_removal_resets_minus_one_instead_of_restoring_previous_or_overlay(self):
        actor, fight, packets, phases, handler, effect, invocation = self.fixture()
        handler(effect, {}, handler.prepare(effect, {}, invocation))
        actor.native_death_script_id = 99
        remove_death_script(handler, 101)
        self.assertEqual(actor.native_death_script_id, -1)
        self.assertEqual(packets[-1][0], 13560)
        self.assertEqual(fight.owned_stat_effects, {})

    def test_l2_mutation_applies_live_value_and_l3_only_changes_runner_observer(self):
        def mutate(channel, runner, handler):
            if channel == 2:
                runner.set_applied(88)
            elif channel == 3:
                runner.set_applied(99)

        actor, fight, packets, phases, handler, effect, invocation = self.fixture(
            mutation=mutate
        )
        observed = []
        with runner_value_scope(
            lambda invocation, value: observed.append(value)
        ) as scope:
            invocation = replace(invocation, native_value_scope=scope)
            handler(effect, {}, handler.prepare(effect, {}, invocation))
        self.assertEqual(actor.native_death_script_id, 88)
        self.assertEqual(observed, [99])
        self.assertEqual(fight.owned_stat_effects[101]["actual"], 99)

    def test_l2_cancel_revalidates_before_mutating_actor(self):
        def mutate(channel, runner, handler):
            if channel == 2:
                handler.context = lambda *args: StatExecutionContext(
                    False, True, None, True, b"", None
                )

        actor, fight, packets, phases, handler, effect, invocation = self.fixture(
            mutation=mutate
        )
        self.assertFalse(handler(effect, {}, handler.prepare(effect, {}, invocation)))
        self.assertEqual(actor.native_death_script_id, 42)
        self.assertEqual(packets, [])
        self.assertEqual(fight.owned_stat_effects, {})
        self.assertEqual(handler.runners, {})

    def test_no_trigger_context_override_and_unused_parameter_pairs(self):
        actor, fight, packets, phases, handler, effect, invocation = self.fixture()
        effect["parameters"].extend([123, 0])
        # eWE.C never delegates to eZR.n/context forced-value handling.
        invocation = replace(invocation, native_context_hex="08ff01")
        self.assertTrue(handler(effect, {}, handler.prepare(effect, {}, invocation)))
        self.assertEqual(actor.native_death_script_id, 37)

    def test_unknown_nonfighter_delivery_rejects_before_uid_or_mutation(self):
        actor, fight, packets, phases, handler, effect, invocation = self.fixture()
        for target in [None, -9]:
            with self.subTest(target=target), self.assertRaisesRegex(
                ValueError, "non-fighter/null-target"
            ):
                handler.prepare(effect, {}, replace(invocation, target_id=target))
        self.assertEqual(phases, [])
        self.assertEqual(actor.native_death_script_id, 42)

    def test_shared_stat_removal_dispatch_validates_native_codec(self):
        from wakfu_server.combat_stat_handler import NativeStatHandler
        from wakfu_server.combat_effect_removal import running_effect_removal

        actor, fight, packets, phases, handler, effect, invocation = self.fixture()
        handler(effect, {}, handler.prepare(effect, {}, invocation))
        entry = fight.owned_stat_effects[101]
        expected = running_effect_removal(
            fight.id,
            5,
            effect_class=1099,
            target_id=1,
            uid=101,
            running_effect_payload=bytes.fromhex(entry["payload"]),
        )
        stat = NativeStatHandler(
            fight,
            packets,
            {"effects": {}},
            action_id=5,
            allocate_uid=lambda: 999,
            context=lambda *args: None,
        )
        stat.remove(101)
        self.assertEqual(packets[-1], (13560, expected))
        self.assertEqual(actor.native_death_script_id, -1)
        self.assertEqual(fight.owned_stat_effects, {})

    def test_malformed_removal_payload_does_not_reset_actor_or_remove_owned_identity(
        self,
    ):
        actor, fight, packets, phases, handler, effect, invocation = self.fixture()
        handler(effect, {}, handler.prepare(effect, {}, invocation))
        fight.owned_stat_effects[101]["payload"] = "00"
        before = list(packets)
        with self.assertRaises(ValueError):
            remove_death_script(handler, 101)
        self.assertEqual(actor.native_death_script_id, 37)
        self.assertIn(101, fight.owned_stat_effects)
        self.assertEqual(packets, before)

    def test_prepare_failure_and_explicit_cancellation_release_runner(self):
        actor, fight, packets, phases, handler, effect, invocation = self.fixture()
        invocation = handler.prepare(effect, {}, invocation)
        handler.cancel_prepared(invocation)
        self.assertEqual(handler.prepared, {})
        self.assertEqual(handler.runners, {})

        def fail(*args, **kwargs):
            raise ValueError("failed native callback")

        handler.event_lifecycle.phase = fail
        with self.assertRaisesRegex(ValueError, "failed native callback"):
            handler.prepare(effect, {}, replace(invocation, native_running_uid=None))
        self.assertEqual(handler.runners, {})
        self.assertEqual(actor.native_death_script_id, 42)


if __name__ == "__main__":
    unittest.main()
