"""Native eYZ hook arguments do not imply a working server spell executor."""
import unittest

from wakfu_server.combat_delivery_owners import native_owner_flags
from wakfu_server.combat_triggered_spell import (
    execute_native_triggered_spell,
    native_triggered_spell_request,
)


class NativeTriggeredSpellTests(unittest.TestCase):
    def request(self, parameters, **overrides):
        options = dict(
            caster_id=123, target_cell=[7, 8, 9], caster_is_native_fighter=True
        )
        options.update(overrides)
        return native_triggered_spell_request(parameters, 17, **options)

    def test_spell_id_fixed_level_and_private_flag_runner_level(self):
        request = self.request([100, 2, 1, 9, -16, 1])
        self.assertEqual(request.spell_id, 102)
        self.assertTrue(request.native_rhe)
        self.assertEqual(request.caster_id, 123)
        self.assertEqual(request.cell, (7, 8, 9))
        self.assertFalse(self.request([100, 2, 1, 9, 0, 1]).native_rhe)

    def test_owner_uses_raw_mode_and_extra_parameters_are_ignored(self):
        for raw, expected in (
            (1, (False, True)),
            (0, (True, False)),
            (2, (True, False)),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(
                    native_owner_flags(
                        dict(effect_class=426, parameters=[5, 0, raw, 999])
                    ),
                    expected,
                )
        self.assertEqual(
            native_owner_flags(dict(effect_class=426, parameters=[5, 0])), (True, False)
        )
        self.assertTrue(self.request([5, 0, 0, 0, 1, 0, 99, 0]).native_rhe)

    def test_cell_is_copied_and_fresh_requests_reset_private_flag(self):
        cell = [1, 2, 3]
        request = self.request([5, 0, 0, 0, 0, 0], target_cell=cell)
        cell[0] = 99
        self.assertEqual(request.cell, (1, 2, 3))
        self.assertFalse(request.native_rhe)
        self.assertTrue(self.request([5, 0]).native_rhe)

    def test_nonfighter_suppresses_hook_and_missing_executor_rejects(self):
        self.assertIsNone(self.request([5, 0], caster_is_native_fighter=False))
        with self.assertRaisesRegex(ValueError, "source-proven"):
            execute_native_triggered_spell(self.request([5, 0]))
        calls = []
        request = self.request([5, 0])
        execute_native_triggered_spell(request, server_executor=calls.append)
        self.assertEqual(calls, [request])

    def test_malformed_native_authority_is_rejected(self):
        for parameters in ([], [1], [1, 0, 2]):
            with self.subTest(parameters=parameters), self.assertRaises(ValueError):
                self.request(parameters)
        with self.assertRaises(ValueError):
            self.request([1, 0], caster_is_native_fighter=None)
        with self.assertRaises(ValueError):
            self.request([1, 0], target_cell=[1, 2, 32768])
