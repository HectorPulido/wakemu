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

    def test_ezr_bcd_uses_definition_a_zl_and_original_listener_pl(self):
        from wakfu_server.combat_ordinary_death import corpse_gate_bypassed

        effect = {
            "effect_class": 304,
            "native_effect_flags": [],
            "target_masks": [None, None, None, None, None, None, None],
        }
        listener_pl = {
            "present": True,
            "type": 11,
            "id": 4593 << 16,
            "is_spell": True,
            "spell_id": 4593,
        }
        invocation = SimpleNamespace(
            state_uid=None,
            native_retained_container=listener_pl,
            native_trigger_context={"event_ids": [1010]},
        )
        # Event IDs belong to the triggering source. bcd reads this definition's
        # PK.aZL instead, so an emitted1010 does not grant the corpse bypass.
        self.assertFalse(corpse_gate_bypassed(effect, invocation=invocation))

        effect_with_a_zl = dict(
            effect, target_masks=[None, None, None, None, None, [1010], None]
        )
        no_1010_source = SimpleNamespace(
            state_uid=None,
            native_retained_container=listener_pl,
            native_trigger_context={"event_ids": []},
        )
        self.assertTrue(
            corpse_gate_bypassed(effect_with_a_zl, invocation=no_1010_source)
        )

    def test_ezr_special_container_uses_original_pl_not_triggering_pl(self):
        from wakfu_server.combat_ordinary_death import corpse_gate_bypassed

        effect = {
            "effect_class": 304,
            "native_effect_flags": [],
            "target_masks": [None] * 7,
        }
        invocation = SimpleNamespace(
            state_uid=None,
            native_retained_container={
                "present": True,
                "type": 11,
                "id": 2040 << 16,
                "is_spell": True,
                "spell_id": 2040,
            },
            native_trigger_context={"container": {"type": 25, "spell_id": 2040}},
        )
        self.assertFalse(corpse_gate_bypassed(effect, invocation=invocation))
        invocation.native_retained_container = {
            "present": True,
            "type": 25,
            "id": 2040 << 16,
            "is_spell": True,
            "spell_id": 2040,
        }
        self.assertTrue(corpse_gate_bypassed(effect, invocation=invocation))

    def test_fresh_pz_is_used_only_when_its_exact_reference_can_affect_bcd(self):
        from wakfu_server.combat_ordinary_death import corpse_gate_bypassed

        effect = {
            "effect_class": 304,
            "native_effect_flags": [],
            "target_masks": [None] * 7,
        }
        ordinary_spell = SimpleNamespace(
            native_active_spell_id=4593,
            native_active_spell_container={
                "present": True,
                "is_spell": True,
                "spell_id": 4593,
                "level": 20,
            },
        )
        self.assertFalse(corpse_gate_bypassed(effect, fight=ordinary_spell))
        unknown_special = SimpleNamespace(
            native_active_spell_id=2040,
            native_active_spell_container={
                "present": True,
                "is_spell": True,
                "spell_id": 2040,
                "level": 20,
            },
        )
        with self.assertRaisesRegex(ValueError, "Dynamic native corpse guard"):
            corpse_gate_bypassed(effect, fight=unknown_special)
        known_special = SimpleNamespace(
            native_active_spell_id=2040,
            native_active_spell_container={
                "present": True,
                "type": 25,
                "is_spell": True,
                "spell_id": 2040,
                "level": 20,
            },
        )
        self.assertTrue(corpse_gate_bypassed(effect, fight=known_special))

    def test_dead_original_listener_is_skipped_when_bcd_is_proven_false(self):
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        fight, target = self.fixture()
        initialize_global_pv_collections(fight, tuple(fight.actors))
        with fight.effect_resolution():
            fight.apply_effect_damage(7, -7, 12)
        event = OrdinaryHealingEvents.__new__(OrdinaryHealingEvents)
        event.preview = fight
        event.adapter = SimpleNamespace(
            actor_authority=lambda _fight, actor: SimpleNamespace(
                targeting={"baG": actor.id == -7, "baK": False}
            )
        )
        fight.native_owned_group_effects = {
            100: {"invocation": {"target_id": -7, "caster_id": 7}}
        }
        invocation = SimpleNamespace(
            caster_id=7,
            target_id=None,
            base_uid=100,
            state_uid=None,
            native_retained_container={
                "present": True,
                "type": 11,
                "id": 4593 << 16,
                "is_spell": True,
                "spell_id": 4593,
            },
            native_trigger_context={"event_ids": []},
        )
        effect = {
            "effect_class": 304,
            "native_effect_flags": [],
            "target_masks": [None] * 7,
        }
        self.assertFalse(event.executable(effect, invocation, None))
        self.assertEqual(target.hp, 0)
