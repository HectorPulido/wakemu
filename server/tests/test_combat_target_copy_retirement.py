"""Actual994 caster ownership stays separate from the copied player target."""
import unittest
import test_combat_summon_retirement as existing_fixture
from wakfu_server.combat_summon_retirement import _registration


class TargetCopyRetirementTests(unittest.TestCase):
    def fixture(self):
        fight, target, caster, copied = existing_fixture.SummonRetirementTests().fight(
            origin="copied"
        )
        copied.controlled = caster.controlled
        copied.owner_id = caster.owner_id
        copied.native_controller_id = copied.native_master_id = caster.id
        copied.native_summon_source.update(
            ref=2349,
            caster_id=caster.id,
            controller_id=caster.id,
            native_character_copy_source="eZq994.faB.eHI.bPl",
            native_symbiot_source="eZq994.new_eHI.pRO_false",
            native_copy_source_actor_id=target.id,
        )
        copied.native_copy_pa_source.update(
            profile=2349, source_actor_id=target.id, native_copy_family=994
        )
        row = fight.native_summon_registrations[copied.id]
        row.update(caster_id=caster.id, controller_id=caster.id)
        row["authority"].update(breed_id=2349, native_controller_id=caster.id)
        return fight, caster, target, copied

    def test_actual_copied_creature_ko_retires_under_creator_not_target(self):
        fight, caster, target, copied = self.fixture()
        self.assertNotEqual(caster.id, target.id)
        self.assertEqual(_registration(fight, copied.id)[-2:], (False, True))
        fight.apply_effect_damage(target.id, copied.id, copied.hp)
        self.assertEqual(
            fight.native_global_pv_collections["fighter_status"][str(copied.id)],
            "OUT_OF_PLAY",
        )
        self.assertTrue(fight.native_summon_retirements[copied.id]["copied"])
        self.assertIn(caster.id, fight.actors)
        self.assertIn(target.id, fight.actors)

    def test_forged_source_profile_family_or_removed_creator_fail_closed(self):
        for mutate in (
            lambda fight, caster, target, copied: copied.native_copy_pa_source.update(
                source_actor_id=caster.id
            ),
            lambda fight, caster, target, copied: copied.native_copy_pa_source.update(
                profile=2382
            ),
            lambda fight, caster, target, copied: copied.native_copy_pa_source.update(
                native_copy_family=1002
            ),
            lambda fight, caster, target, copied: fight.actors.pop(caster.id),
        ):
            fight, caster, target, copied = self.fixture()
            mutate(fight, caster, target, copied)
            with self.assertRaises(ValueError):
                _registration(fight, copied.id)
