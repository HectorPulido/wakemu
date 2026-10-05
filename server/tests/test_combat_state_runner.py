import unittest
from wakfu_server.combat_state_runner import NativeRunnerStateLevel
from wakfu_server.combat_state_handler import NativeStateHandler
from wakfu_server.combat_effect_dispatch import EffectInvocation


class NativeStateRunnerTests(unittest.TestCase):
    def runner(self, level=10, rng=lambda: 0.25):
        return NativeRunnerStateLevel(
            901, rng=rng, reference=3442, level=level, value=77
        )

    def test_short_mutation_preserves_amount_and_raw_reference(self):
        runner = self.runner(32767)
        runner.mutate(4, 1, False)
        self.assertEqual(runner.pending_level, -32768)
        self.assertEqual(runner.seed_level, -32768)
        self.assertEqual(runner.packed, (3442 << 16) + 32768)
        self.assertEqual(runner.value, 77)
        runner.mutate(1, 10, True)
        self.assertEqual(runner.pending_level, -32768)

    def test_percentage_uses_shared_rng_and_has_no_cap(self):
        samples = []

        def rng():
            samples.append(1)
            return 0.25

        runner = self.runner(3, rng)
        runner.mutate(7, 50, True)
        self.assertEqual(runner.pending_level, 2)
        self.assertEqual(samples, [1])
        runner.seed(3442, 399)
        runner.mutate(4, 101, False)
        self.assertEqual(runner.pending_level, 500)

    def test_rejects_other_native_owner(self):
        with self.assertRaisesRegex(ValueError, "eWu owner"):
            NativeRunnerStateLevel(901, 1013, rng=lambda: 0)

    def test_phase_order_reseed_and_replay_mutation(self):
        applied, phases = [], []

        class Handler(NativeStateHandler):
            def apply_reference(self, effect, invocation, reference, level, **kwargs):
                applied.append((reference, level))
                return True

        class Events:
            def phase(self, effect, invocation, **kwargs):
                runner = kwargs["runner_modifier"]
                phases.append(
                    (kwargs["channel"], runner.pending_level, kwargs["value"])
                )
                if kwargs["channel"] == 1:
                    runner.mutate(4, 3, False)
                if kwargs["channel"] == 2:
                    runner.mutate(4, 2, False)

        handler = Handler(
            None,
            [],
            {},
            action_id=1,
            allocate_uid=lambda: 901,
            context=None,
            execute_child=None,
            rng=lambda: 0,
        )
        handler.event_lifecycle = Events()
        invocation = EffectInvocation(1, 1, 7, 8, (0, 0, 0))
        effect = {"effect_class": 304, "target_masks": [[], [], [], [], [], [], []]}
        values = {"parameters": [3442, 9, -1]}
        prepared = handler.prepare(effect, values, invocation)
        self.assertTrue(handler(effect, values, prepared))
        self.assertEqual(applied.pop(), (3442, 11))
        self.assertEqual(phases, [(1, 0, 0), (2, 9, 0), (3, 11, 0), (4, 11, 0)])
        phases.clear()
        self.assertTrue(handler(effect, values, invocation))
        self.assertEqual(applied.pop(), (3442, 14))
        self.assertEqual(phases, [(1, 9, 0), (2, 12, 0), (3, 14, 0), (4, 14, 0)])


if __name__ == "__main__":
    unittest.main()
