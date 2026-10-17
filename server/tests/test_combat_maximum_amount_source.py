import unittest
from dataclasses import asdict, replace
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_event_replay import NativeEventSource
from wakfu_server.combat_final_modifier import final_modifier_source
from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount
from wakfu_server.combat_value_transfer import transfer_value_context
from wakfu_server.combat_maximum_resource import maximum_application_amount
import test_combat_maximum_resource as resource_tests


class MaximumAmountSourceTests(unittest.TestCase):
    def invocation(self, **changes):
        return replace(EffectInvocation(999, 1, 7, 7, (0, 0, 0)), **changes)

    def source(self, value=9, **changes):
        return NativeEventSource(
            100,
            500,
            value,
            7,
            7,
            (0, 0, 0),
            (0,),
            1,
            7,
            None,
            False,
            False,
            False,
            True,
            effect_action_id=31,
            **changes
        )

    def descriptor(self, source):
        row = asdict(replace(source, runner_modifier=None))
        row.pop("runner_modifier")
        row.pop("final_modifier")
        return row

    def test_forced_transfer_precedes_minus_one_substitution(self):
        source = self.source()
        for forced in (7, 0):
            invocation = self.invocation(
                native_context_hex=transfer_value_context(b"", forced).hex(),
                native_trigger_context=self.descriptor(source),
            )
            self.assertEqual(maximum_application_amount(-1, invocation), forced)

    def test_literal_minus_one_without_actual_qe_remains_literal(self):
        self.assertEqual(maximum_application_amount(-1, self.invocation()), -1)
        fixture = resource_tests.MaximumResourceTests()
        fixture.setUp()
        from wakfu_server.combat_stat_handler import StatExecutionContext

        fixture.handler.context = lambda *args: StatExecutionContext(
            True, True, 9, False, b"", None
        )
        self.assertTrue(fixture.apply(amount=-1))
        self.assertEqual(
            (
                fixture.actor.mp,
                fixture.actor.max_mp,
                fixture.actor.effect_base_maxima[3],
            ),
            (1, 2, 2),
        )

    def test_actual_source_snapshot_and_live_modified_value(self):
        source = self.source(value=9)
        invocation = self.invocation(native_trigger_context=self.descriptor(source))
        self.assertEqual(maximum_application_amount(-1, invocation), 9)
        runner = NativeRunnerAmount(100, 31, rng=lambda: 0, value=7)
        live = replace(source, runner_modifier=runner)
        with final_modifier_source(live):
            self.assertEqual(maximum_application_amount(-1, invocation), 7)

    def test_present_incomplete_source_and_identity_mismatch_reject(self):
        source = self.source()
        descriptor = self.descriptor(source)
        descriptor.pop("value")
        with self.assertRaisesRegex(ValueError, "authority"):
            maximum_application_amount(
                -1, self.invocation(native_trigger_context=descriptor)
            )
        with final_modifier_source(replace(source, uid=101)):
            with self.assertRaisesRegex(ValueError, "identity"):
                maximum_application_amount(
                    -1, self.invocation(native_trigger_context=self.descriptor(source))
                )

    def test_minus_two_transform_stays_unknown_even_forced(self):
        with self.assertRaisesRegex(ValueError, "container transform"):
            maximum_application_amount(
                -2,
                self.invocation(
                    native_context_hex=transfer_value_context(b"", 7).hex()
                ),
            )

    def test_context_amount_preserves_raw_effective_maximum_caps(self):
        for forced, flags, expected in ((7, (), 8), (7, (17,), 10), (0, (), 3)):
            with self.subTest(forced=forced, flags=flags):
                fixture = resource_tests.MaximumResourceTests()
                fixture.setUp()
                fixture.invocation = replace(
                    fixture.invocation,
                    native_context_hex=transfer_value_context(b"", forced).hex(),
                    native_trigger_context=self.descriptor(self.source()),
                )
                self.assertTrue(fixture.apply(amount=-1, flags=flags))
                self.assertEqual(fixture.actor.effect_base_maxima[3], expected)
                self.assertEqual(fixture.actor.effect_maxima[3], expected)
                self.assertEqual(fixture.actor.effect_minima[3], 0)
