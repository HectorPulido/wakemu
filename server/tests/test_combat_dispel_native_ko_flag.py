"""The native ID15 permission belongs to shared eligibility, not dispel selection."""
import unittest
from wakfu_server.combat_dispel import dispel_flags, select_dispel
from wakfu_server.combat_retained_effects import RetainedEffect


class DispelNativeKoFlagTests(unittest.TestCase):
    def test_native_ko_permission_is_recognized_without_fabricating_lifecycle(self):
        self.assertEqual(
            dispel_flags({"native_effect_flags": [15]}, event_lifecycle=None), (15,)
        )
        self.assertEqual(
            dispel_flags({"native_effect_flags": [15, 17]}, event_lifecycle=None),
            (15, 17),
        )
        # Recognizing KO eligibility does not change eXe exact-match selection.
        row = RetainedEffect(
            99,
            7,
            400,
            123,
            definition_type=2,
            definition_dispellable=False,
            container_present=False,
        )
        self.assertEqual(select_dispel([row], []), ())
        self.assertEqual(select_dispel([row], [123]), (row,))

    def test_ko_flag_preserves_unknown_and_actual_trigger_lifecycle_guards(self):
        for flags in ([15, 999], [15, 15], [True, 15], [15, 5], [15, 6]):
            with self.subTest(flags=flags), self.assertRaises(ValueError):
                dispel_flags({"native_effect_flags": flags}, event_lifecycle=None)
        lifecycle = object()
        self.assertEqual(
            dispel_flags({"native_effect_flags": [15, 6]}, event_lifecycle=lifecycle),
            (15, 6),
        )
