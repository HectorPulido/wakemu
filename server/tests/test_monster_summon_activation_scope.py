"""Imported summon books must never authorize unrelated parents or levels."""
from copy import deepcopy
import unittest
from prepare_monster_spell_activation import attach_summon_dependencies


class MonsterSummonActivationScopeTests(unittest.TestCase):
    def test_dependency_scope_is_parent_owned_and_cannot_activate_high_level_species(
        self,
    ):
        npc = {"activation_policy": {"enabled_monsters": {"2819": {}, "6": {}}}}
        candidates = [dict(ref=2819, spell_ids=[4625]), dict(ref=6, spell_ids=[5790])]
        closure = {
            "spell_summon_profiles": {
                "4625": {
                    "735": dict(
                        level_domain_exact=True, descriptor_levels=[8], spell_ids=[1948]
                    ),
                    "999": dict(
                        level_domain_exact=True, descriptor_levels=[95], spell_ids=[1]
                    ),
                }
            }
        }
        attach_summon_dependencies(npc, candidates, closure, 9)
        policy = npc["activation_policy"]["enabled_monsters"]
        self.assertEqual(set(policy), {"2819", "6"})
        self.assertEqual(set(policy["2819"]["registered_summon_profiles"]), {"735"})
        self.assertEqual(policy["6"], {})
        self.assertEqual(
            policy["2819"]["registered_summon_profiles"]["735"]["descriptor_levels"],
            [8],
        )

    def test_scoped_policy_preserves_existing_parent_authority(self):
        npc = {
            "activation_policy": {
                "enabled_monsters": {
                    "2819": dict(min_level=5, max_level=5, spell_ids=[4625])
                }
            }
        }
        original = deepcopy(npc)
        attach_summon_dependencies(
            npc, [dict(ref=2819, spell_ids=[4625])], {"spell_summon_profiles": {}}, 9
        )
        self.assertEqual(npc, original)

    def test_invalid_book_does_not_grant_any_scope(self):
        npc = {"activation_policy": {"enabled_monsters": {"2819": {}}}}
        closure = {
            "spell_summon_profiles": {
                "4625": {
                    "735": dict(
                        level_domain_exact=True, descriptor_levels=[8], spell_ids=[]
                    )
                }
            }
        }
        with self.assertRaisesRegex(ValueError, "book scope"):
            attach_summon_dependencies(
                npc, [dict(ref=2819, spell_ids=[4625])], closure, 9
            )
        self.assertEqual(npc["activation_policy"]["enabled_monsters"]["2819"], {})

    def test_unknown_descriptor_domain_is_withheld(self):
        npc = {"activation_policy": {"enabled_monsters": {"2819": {}}}}
        closure = {
            "spell_summon_profiles": {
                "4625": {
                    "735": dict(
                        level_domain_exact=False,
                        descriptor_levels=[8],
                        spell_ids=[1948],
                    )
                }
            }
        }
        attach_summon_dependencies(npc, [dict(ref=2819, spell_ids=[4625])], closure, 9)
        self.assertEqual(npc["activation_policy"]["enabled_monsters"]["2819"], {})
