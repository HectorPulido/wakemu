import unittest
from types import SimpleNamespace
from wakfu_server.combat_effect_targets import (
    _native_target_valid,
    native_selector_policy,
    UnsupportedTargetSelector,
)
from wakfu_server.combat_range_conditions import creation_in_play


class TargetLifeSelectorTests(unittest.TestCase):
    def test_original_fcE_positive_identity_and_registered_in_play_matrix(self):
        caster = SimpleNamespace(id=9)
        for identity in (-7, 0, 7):
            actor = SimpleNamespace(id=identity)
            for alive in (False, True):
                for mask in (16, 1 << 40, 16 | (1 << 40)):
                    contexts = {
                        9: {},
                        identity: dict(
                            bEe=True, is_eGj=True, is_Qq=False, is_eHH=False, baF=alive
                        ),
                    }
                    native_selector_policy(
                        {"native_target_selector": {"class": "fcE", "mask": mask}}
                    )
                    expected = (not mask & 16 or identity > 0) and (
                        not mask & (1 << 40) or alive
                    )
                    self.assertEqual(
                        _native_target_valid(mask, caster, actor, contexts), expected
                    )

    def test_unknown_life_and_non_fighter_are_distinct(self):
        actor, caster = SimpleNamespace(id=7), SimpleNamespace(id=9)
        context = dict(bEe=True, is_eGj=True, is_Qq=False)
        with self.assertRaisesRegex(UnsupportedTargetSelector, "baF"):
            _native_target_valid(1 << 40, caster, actor, {7: context, 9: {}})
        context["is_eGj"] = False
        self.assertFalse(
            _native_target_valid(1 << 40, caster, actor, {7: context, 9: {}})
        )

    def test_controller_flags_use_source_relation_not_target_or_team(self):
        caster = SimpleNamespace(id=9)
        contexts = {9: dict(is_eGj=True, dpu_id=7, dpr_id=8)}
        for identity in (7, 8, 10):
            actor = SimpleNamespace(id=identity)
            contexts[identity] = dict(bEe=True, is_Qq=False, is_eHH=False)
            for bit, expected in ((42, 7), (45, 8)):
                native_selector_policy(
                    {"native_target_selector": {"class": "fcE", "mask": 1 << bit}}
                )
                self.assertEqual(
                    _native_target_valid(1 << bit, caster, actor, contexts),
                    identity == expected,
                )

    def test_unknown_controller_is_rejected_and_non_fighter_source_excluded(self):
        actor, caster = SimpleNamespace(id=7), SimpleNamespace(id=9)
        contexts = {7: dict(bEe=True), 9: dict(is_eGj=True)}
        for bit, key in ((42, "dpu_id"), (45, "dpr_id")):
            with self.assertRaisesRegex(UnsupportedTargetSelector, key):
                _native_target_valid(1 << bit, caster, actor, contexts)
        contexts[9]["is_eGj"] = False
        self.assertFalse(_native_target_valid(1 << 42, caster, actor, contexts))

    def test_own_summon_exclusion_matches_original_four_cases(self):
        caster, target = SimpleNamespace(id=9), SimpleNamespace(id=7)
        native_selector_policy(
            {"native_target_selector": {"class": "fcE", "mask": 1 << 34}}
        )
        for summon in (False, True):
            for owner in (9, 10):
                contexts = {
                    9: dict(is_eGj=True),
                    7: dict(
                        bEe=True,
                        is_Qq=False,
                        is_eHH=False,
                        is_eGj=True,
                        dTE=summon,
                        dpu_id=owner,
                    ),
                }
                self.assertEqual(
                    _native_target_valid(1 << 34, caster, target, contexts),
                    not (summon and owner == caster.id),
                )

    def test_own_summon_exclusion_requires_relation_only_for_summons(self):
        caster, target = SimpleNamespace(id=9), SimpleNamespace(id=7)
        contexts = {
            9: dict(is_eGj=True),
            7: dict(bEe=True, is_Qq=False, is_eHH=False, is_eGj=True, dTE=True),
        }
        with self.assertRaisesRegex(UnsupportedTargetSelector, "dpu_id"):
            _native_target_valid(1 << 34, caster, target, contexts)
        contexts[7]["dTE"] = False
        self.assertTrue(_native_target_valid(1 << 34, caster, target, contexts))

    def test_owned_creation_lifecycle_never_infers_unknown_zero_hp_alive(self):
        actor = SimpleNamespace(id=7, hp=10)
        fight = SimpleNamespace(events=[])
        self.assertTrue(creation_in_play(fight, actor))
        actor.hp = 0
        self.assertIsNone(creation_in_play(fight, actor))
        fight.events.append(dict(kind="death", actor_id=7))
        self.assertFalse(creation_in_play(fight, actor))
        actor.hp = 10
        self.assertIsNone(creation_in_play(fight, actor))


if __name__ == "__main__":
    unittest.main()
