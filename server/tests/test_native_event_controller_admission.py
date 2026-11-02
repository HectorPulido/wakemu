"""Bounded constructor-state admission against actual published native records."""
import copy
from collections import ChainMap
import unittest
from unittest.mock import patch

from wakfu_server import combat_npc_event_controller as CANDIDATE
from wakfu_server.combat_npc_activation_policy import current_policy

ROWS = {
    str(reference): current_policy()["enabled_monsters"][str(reference)]
    for reference in (4400, 5114, 3433)
}


class NativeEventControllerAdmissionTests(unittest.TestCase):
    def policy(self):
        return {
            "schema": "native-npc-activation-v1",
            "enabled_monsters": copy.deepcopy(ROWS),
        }

    def test_full_native_grades_and_existing_direct_controller(self):
        for reference, grades in (
            (4400, range(203, 209)),
            (5114, range(83, 89)),
            (3433, (200,)),
        ):
            for grade in grades:
                with self.subTest(reference=reference, grade=grade):
                    self.assertIsNotNone(
                        CANDIDATE.event_controller_record(
                            self.policy(), reference, grade
                        )
                    )

    def test_malformed_cycle_deep_chain_and_incorrect_application_reject(self):
        changes = [
            lambda a: a.pop("bootstrap_links"),
            lambda a: a["bootstrap_links"][0].update(state_id=4611),
            lambda a: a["bootstrap_links"][0].update(initial_state_id=4926),
            lambda a: a["bootstrap_links"][0].update(apply_effect_id=188124),
            lambda a: a["bootstrap_links"][0].update(state_level=2),
            lambda a: a["bootstrap_links"][0].update(state_level=True),
            lambda a: a["callback_roots"][0].update(effect_id=188123),
            lambda a: a["callback_roots"][0].update(state_id=[]),
        ]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                policy = self.policy()
                change(policy["enabled_monsters"]["4400"]["event_controller"])
                with self.assertRaises(ValueError):
                    CANDIDATE.event_controller_record(policy, 4400, 203)

    def test_foreign_caster_conditional_random_and_deeper_native_sources_reject(self):
        from wakfu_server.spell_audit import states_catalog

        catalog = states_catalog()
        changes = [
            (188123, {"native_target_selector": {"class": "fcE", "mask": 9}}),
            (217093, {"native_target_selector": {"class": "fcE", "mask": 9}}),
            (217093, {"criteria": 'HasState(1, "caster")'}),
            (188123, {"target_masks": [None, None, None, None, None, [1001], None]}),
            (217093, {"probability_base": 50.0}),
            (217093, {"effect_class": 330, "children": [217093]}),
            (217093, {"area_native": "circle"}),
        ]
        for effect_id, replacement in changes:
            with self.subTest(effect_id=effect_id, replacement=replacement):
                row = dict(catalog["effects"][str(effect_id)])
                row.update(replacement)
                overlay = dict(catalog)
                overlay["effects"] = ChainMap({str(effect_id): row}, catalog["effects"])
                with patch(
                    "wakfu_server.spell_audit.states_catalog", return_value=overlay
                ):
                    with self.assertRaises(ValueError):
                        CANDIDATE.event_controller_record(self.policy(), 4400, 203)

    def test_bootstrap_does_not_authorize_other_npc_or_out_of_native_grade(self):
        policy = self.policy()
        self.assertIsNone(CANDIDATE.event_controller_record(policy, 4400, 202))
        self.assertIsNone(CANDIDATE.event_controller_record(policy, 4400, 209))
        self.assertIsNone(CANDIDATE.event_controller_record(policy, 5114, 82))
        self.assertIsNone(CANDIDATE.event_controller_record(policy, 5114, 89))
        self.assertIsNone(CANDIDATE.event_controller_record(policy, 999999, 1))

    def test_installed_accessors_preserve_immutable_native_policy(self):
        from wakfu_server import native_catalog
        from wakfu_server.paths import DATA_ROOT
        from wakfu_server.combat_npc_attack import npc_spell_catalog
        from wakfu_server.dungeon_monster_admission import (
            current_policy as dungeon_policy,
        )
        from wakfu_server.combat_npc_activation_policy import merge_policy

        path = DATA_ROOT / "native-npc-spell-effect-trees.json"
        original = native_catalog.record(path, "activation_policy", "enabled_monsters")
        before = copy.deepcopy(original)
        merged = dungeon_policy()
        self.assertEqual(merged, npc_spell_catalog()["activation_policy"])
        self.assertIs(merged, dungeon_policy())
        self.assertEqual(len(merged["enabled_monsters"]), len(before) + 2)
        for reference in ("4400", "5114"):
            self.assertNotIn(reference, before)
            self.assertEqual(merged["enabled_monsters"][reference], ROWS[reference])
        for reference, record in before.items():
            self.assertEqual(merged["enabled_monsters"][reference], record)
        self.assertEqual(
            native_catalog.record(path, "activation_policy", "enabled_monsters"), before
        )
        base = dict(merged, enabled_monsters=before)
        self.assertIs(merge_policy(base, revision="f" * 64), base)
        conflicting = copy.deepcopy(base)
        conflicting["enabled_monsters"]["4400"] = {"wrong": "authority"}
        with self.assertRaises(ValueError):
            merge_policy(conflicting, revision=native_catalog.release())


if __name__ == "__main__":
    unittest.main(verbosity=2)
