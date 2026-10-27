"""Unit coverage for typed faV sources; native scene qualification is separate."""
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_damage_source import native_damage_source
from wakfu_server.combat_damage_parameters import damage_mastery_context
import test_combat_damage_handler as actor_fixture


class AreaDamageSourceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = actor_fixture.DamageHandlerTests()
        self.fixture.setUp()
        self.fight = self.fixture.fight
        self.source = SimpleNamespace(
            id=-300,
            position=(0, 0, 0),
            native_is_area=True,
            native_characteristics=None,
        )
        self.row = {"native_area_contract": "faP"}
        self.addCleanup(patch.stopall)
        patch(
            "wakfu_server.combat_state_managers.registered_area_pv",
            side_effect=lambda fight, identity: self.source
            if identity == -300
            else None,
        ).start()
        patch(
            "wakfu_server.combat_state_managers.retained_area_pv_row",
            return_value=self.row,
        ).start()

    def test_actual_area_identity_survives_arithmetic_consumption_and_event(self):
        invocation = replace(self.fixture.invocation, caster_id=-300)
        self.assertTrue(self.fixture.handler(self.fixture.effect, {}, invocation))
        self.assertEqual(self.fight.actors[-7].hp, 49)
        self.assertEqual(self.fight.actors[7].effect_stats[100], 15)
        self.assertFalse(hasattr(self.source, "effect_stats"))
        self.assertNotIn(-300, self.fight.actors)
        damage = [event for event in self.fight.events if event["kind"] == "damage"]
        self.assertEqual(damage[-1]["source_id"], -300)

    def test_unknown_missing_or_characteristic_bearing_source_rejected(self):
        for contract in ("fbc", "fbd", "faW", "unknown"):
            self.row["native_area_contract"] = contract
            with self.assertRaises(ValueError):
                native_damage_source(self.fight, -300)
        with self.assertRaises(ValueError):
            native_damage_source(self.fight, -999)

    def test_source_percent_hp_rejected_without_inventing_hp(self):
        self.fixture.effect["parameters"] = [10, 0, 3, 0, 1, 0]
        with self.assertRaisesRegex(ValueError, "percent-HP"):
            self.fixture.handler(
                self.fixture.effect,
                {},
                replace(self.fixture.invocation, caster_id=-300),
            )
        self.assertEqual(self.fight.actors[-7].hp, 100)
        self.assertFalse(hasattr(self.source, "hp"))

    def test_absent_berserk_has_no_hp_operand_and_player_path_stays_strict(self):
        result = damage_mastery_context(
            [],
            source_xy=(0, 0),
            target_xy=(1, 0),
            source_radius=0,
            target_radius=0,
            source_total_hp=None,
            source_total_max_hp=None,
            source_has_berserk=False,
        )
        self.assertFalse(result["berserk"])
        with self.assertRaises(ValueError):
            self.fight.apply_damage(-300, -7, 1)
        with self.assertRaises(ValueError):
            self.fight.apply_effect_damage(-300, -7, 1)
