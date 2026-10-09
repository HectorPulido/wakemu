from types import SimpleNamespace
import unittest

from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    set_global_fighter_status,
)
from wakfu_server.combat_ordinary_death import (
    owned_fighter_guards,
    registered_ordinary_death,
)


class NativeFighterLifeAuthorityTests(unittest.TestCase):
    def fight(self, hp=100):
        actor = SimpleNamespace(id=7, hp=hp)
        fight = SimpleNamespace(actors={7: actor}, events=[])
        initialize_global_pv_collections(fight, (7,))
        return fight, actor

    def test_off_play_is_native_registry_status_even_with_positive_hp(self):
        fight, actor = self.fight()
        set_global_fighter_status(fight, 7, "OFF_PLAY")
        self.assertEqual(
            owned_fighter_guards(fight, actor), dict(baF=False, baG=True, baK=False)
        )

    def test_zero_hp_does_not_replace_actual_in_play_registry(self):
        fight, actor = self.fight(hp=0)
        self.assertEqual(
            owned_fighter_guards(fight, actor), dict(baF=True, baG=False, baK=False)
        )

    def test_out_of_play_and_off_play_are_distinct(self):
        fight, actor = self.fight()
        set_global_fighter_status(fight, 7, "OUT_OF_PLAY")
        self.assertEqual(
            owned_fighter_guards(fight, actor), dict(baF=False, baG=False, baK=True)
        )

    def test_missing_explicit_status_does_not_fall_back_to_hp(self):
        fight, actor = self.fight()
        fight.native_global_pv_collections["fighter_status"].clear()
        with self.assertRaisesRegex(ValueError, "fighter status"):
            owned_fighter_guards(fight, actor)

    def test_legacy_arbitrary_hp0_remains_unknown(self):
        fight, actor = self.fight(hp=0)
        del fight.native_global_pv_collections
        self.assertIsNone(owned_fighter_guards(fight, actor)["baG"])

    def test_legacy_owned_death_registration_proves_off_play(self):
        fight, actor = self.fight(hp=0)
        del fight.native_global_pv_collections
        fight.events = [
            dict(kind="damage", target_id=7, source_id=7, hp=0, sequence=1),
            dict(kind="death", actor_id=7, sequence=2),
        ]
        self.assertEqual(
            owned_fighter_guards(fight, actor), dict(baF=False, baG=True, baK=False)
        )

    def test_percentage_corpse_proof_rejects_other_runner_and_nonpositive_origin(self):
        fight, actor = self.fight(hp=0)
        source = dict(
            kind="percentage_hp_update",
            target_id=7,
            source_id=7,
            hp=0,
            hp_before=30,
            maximum=70,
            uid=101,
            effect_class=986,
            sequence=1,
        )
        death = dict(kind="death", actor_id=7, sequence=2)
        fight.events = [source, death]
        self.assertTrue(registered_ordinary_death(fight, actor))
        for field, value in (
            ("effect_class", 20),
            ("hp_before", 0),
            ("uid", 0),
            ("source_id", 99),
            ("sequence", 0),
            ("maximum", -1),
        ):
            with self.subTest(field=field):
                fight.events = [{**source, field: value}, death]
                with self.assertRaisesRegex(ValueError, "Unverified"):
                    registered_ordinary_death(fight, actor)
