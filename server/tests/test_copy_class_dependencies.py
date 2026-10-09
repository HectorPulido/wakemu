"""Source-attested empty native copy constructor components."""
import unittest
from wakfu_server.combat_copy_dependencies import (
    native_copy_profiles,
    merge_profile_component,
)
from wakfu_server.combat_summon_spellbook import fresh_action_book, profile_abilities
from wakfu_server.combat_summon_initial_states import (
    native_initial_states,
    initial_state_plan,
)


class CopyDependencyTests(unittest.TestCase):
    def test_original_empty_base_book_and_initial_states_preserved(self):
        source = native_copy_profiles()["2382"]
        self.assertEqual(source["abilities"], [])
        self.assertEqual(source["initial_state_triples"], [])
        self.assertEqual(source["fight_properties"], [15, 108])
        self.assertEqual(source["world_properties"], [7])
        for level in (0, 1, 20, 200, 245, 32767):
            self.assertEqual(fresh_action_book(2382, level)["actions"], [])
            self.assertEqual(
                initial_state_plan(
                    native_initial_states()["2382"]["initial_state_triples"], level
                ),
                (),
            )
        self.assertEqual(profile_abilities()["2382"]["abilities"], [])

    def test_conflict_rejected_without_changing_existing_source(self):
        existing = {"2382": {"abilities": [{"reference": 123}]}}
        with self.assertRaises(ValueError):
            merge_profile_component(existing, "abilities")
        self.assertEqual(existing["2382"]["abilities"], [{"reference": 123}])
