"""Focused preparation utility without synthetic state grants or cast bypasses."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat_ai_state_progress import progress, state_threshold


def actor(*states, controlled=False):
    return SimpleNamespace(
        hp=10,
        controlled=controlled,
        state_ledger=SimpleNamespace(
            entries=[
                SimpleNamespace(reference=reference, level=level)
                for reference, level in states
            ]
        ),
    )


class OwnedStateProgressTests(unittest.TestCase):
    def test_native_standalone_caster_threshold(self):
        self.assertEqual(state_threshold("GetStateLevel(2621) >=30"), (2621, 30))
        self.assertEqual(
            state_threshold('GetStateLevel(2621, "caster") > 29'), (2621, 30)
        )

    def test_ambiguous_or_nonmonotonic_conditions_have_no_reward(self):
        for criterion in (
            "False and GetStateLevel(2621) >=30",
            'GetStateLevel(2621, "target") >=30',
            "GetStateLevel(2621) ==30",
            "GetStateLevel(2621) <30",
            "GetStateLevel(2621) >=0",
            "GetStateLevel(2621) >=32768",
            "GetStateLevel(2621) >=True",
        ):
            self.assertIsNone(state_threshold(criterion), criterion)

    def test_only_owned_native_prerequisite_receives_capped_progress(self):
        casting = {
            "4187": {"cast_criterion_raw": "GetStateLevel(2621)>=30"},
            "9999": {"cast_criterion_raw": "GetStateLevel(8000)>=20"},
        }
        self.assertEqual(progress(actor((2621, 5), (8000, 20)), [4187], casting), 5)
        self.assertEqual(progress(actor((2621, 31)), [4187], casting), 30)
        self.assertEqual(progress(actor((2621, 1)), [], casting), 0)

    def test_native_first_matching_entry_is_not_summed_or_maximized(self):
        casting = {"4187": {"cast_criterion_raw": "GetStateLevel(2621)>=30"}}
        self.assertEqual(progress(actor((2621, 2), (2621, 30)), [4187], casting), 2)
        self.assertEqual(progress(actor((8000, 30)), [4187], casting), 0)

    def test_class_controlled_actors_receive_no_new_utility(self):
        casting = {"4187": {"cast_criterion_raw": "GetStateLevel(2621)>=30"}}
        self.assertEqual(
            progress(actor((2621, 30), controlled=True), [4187], casting), 0
        )


if __name__ == "__main__":
    unittest.main()
