import unittest
from types import SimpleNamespace
from wakfu_server.combat_ordinary_death import registered_ordinary_death
from wakfu_server.combat_ordinary_events import OrdinaryHealingEvents
from wakfu_server.combat_state import Actor, Fight


class OrdinaryDeathTests(unittest.TestCase):
    def fixture(self):
        first = Actor(7, 0, (0, 0, 0), 50, 6, 3, 10, 1, 3, True)
        target = Actor(-7, 1, (1, 0, 0), 12, 6, 3, 1, 1)
        fight = Fight(
            78,
            [first, target],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        fight.ready(3)
        return fight, target

    def test_only_owned_damage_death_is_known(self):
        fight, target = self.fixture()
        self.assertFalse(registered_ordinary_death(fight, target))
        with fight.effect_resolution():
            fight.apply_effect_damage(7, -7, 20)
            self.assertTrue(registered_ordinary_death(fight, target))
        self.assertEqual(target.hp, 0)

    def test_arbitrary_zero_hp_and_inconsistent_death_remain_errors(self):
        fight, target = self.fixture()
        target.hp = 0
        with self.assertRaisesRegex(ValueError, "no owned"):
            registered_ordinary_death(fight, target)
        fight._event("death", actor_id=-7)
        with self.assertRaisesRegex(ValueError, "Unverified"):
            registered_ordinary_death(fight, target)

    def test_original_group_override_permits_known_corpse_without_exception(self):
        fight, target = self.fixture()
        event = OrdinaryHealingEvents.__new__(OrdinaryHealingEvents)
        event.preview = fight
        event.adapter = SimpleNamespace(
            actor_authority=lambda *a: SimpleNamespace(
                targeting={"baG": False, "baK": False}
            )
        )
        fight.native_owned_group_effects = {100: {"invocation": {"target_id": -7}}}
        invocation = SimpleNamespace(caster_id=7, target_id=-7, base_uid=100)
        self.assertTrue(event.executable({"effect_class": 330}, invocation, None))
        with fight.effect_resolution():
            fight.apply_effect_damage(7, -7, 12)
            self.assertTrue(event.executable({"effect_class": 330}, invocation, None))
            self.assertTrue(event.executable({"effect_class": 400}, invocation, None))
        self.assertEqual(target.hp, 0)

    def test_prototype_override_is_not_guessed_for_dynamic_guards(self):
        from wakfu_server.combat_ordinary_death import corpse_gate_bypassed

        self.assertTrue(corpse_gate_bypassed({"effect_class": 330}))
        self.assertTrue(corpse_gate_bypassed({"effect_class": 400}))
        with self.assertRaisesRegex(ValueError, "Dynamic"):
            corpse_gate_bypassed({"effect_class": 48, "native_effect_flags": ()})
        self.assertTrue(
            corpse_gate_bypassed({"effect_class": 48, "native_effect_flags": (15,)})
        )
        with self.assertRaisesRegex(ValueError, "Missing"):
            corpse_gate_bypassed({"effect_class": 999999})
