"""Actual HP-owning Qq creation, damage, resources, wire and rollback."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

import test_combat_fake_fighter_area as area_fixture
from wakfu_server.combat_effect_area import native_effect_areas, remove_owned_hour_area
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_fake_fighter import verified_fake_fighter
from wakfu_server.combat_fake_fighter_resources import (
    fake_fighter_hp_state,
    fake_fighter_hp_wire,
    fake_fighter_damage_snapshot,
)
from wakfu_server.combat_damage_handler import (
    NativeDamageHandler,
    DamageExecutionContext,
)
from wakfu_server.combat_group_pv import group_pa
from wakfu_server.combat_qi_registry import NativeQIRegistry
from wakfu_server.combat_area_authority import area_guards
from wakfu_server.combat_area_damage_snapshot import area_has_damage_characteristic
from wakfu_server.combat_state_managers import registered_area_pv


class FakeFighterHpIntegrationTests(unittest.TestCase):
    def create(self):
        (
            fight,
            creator,
            allocated,
            packets,
        ) = area_fixture.NativeFakeFighterAreaTests().create()
        creator.fake_fighter_hp_enabled = True
        self.assertTrue(
            creator(
                {"effect_class": 339},
                {"parameters": [566, 141]},
                EffectInvocation(101928, 141, 7, None, (2, 3, 0)),
            )
        )
        return fight, creator, allocated, packets

    def test_real_area566_has_owned_pa_and_preserves_absent_characteristics(self):
        fight, _, allocated, packets = self.create()
        row = fight.native_effect_areas[901]
        definition = native_effect_areas()["566"]
        self.assertEqual(
            verified_fake_fighter(row, definition)["characteristic_ids"], (1,)
        )
        self.assertEqual(group_pa(fight, 901, 1), (8, 8))
        self.assertIsNone(group_pa(fight, 901, 29))
        self.assertEqual(fake_fighter_damage_snapshot(row, definition)["stats"], {1: 8})
        self.assertFalse(area_has_damage_characteristic(row, definition))
        self.assertIsNotNone(registered_area_pv(fight, 901))
        self.assertNotIn(901, fight.actors)
        self.assertEqual(allocated, [901, 902])
        self.assertEqual(len(packets), 1)
        self.assertEqual(
            fake_fighter_hp_wire(row, definition).hex(), "0000000800000008"
        )

    def test_actual_damage_handler_hp0_keeps_qi_until_owned_removal_and_rolls_back(
        self,
    ):
        fight, _, _, _ = self.create()
        row = fight.native_effect_areas[901]
        definition = native_effect_areas()["566"]
        before = deepcopy(row)
        source = fight.actors[7]
        source.hp = source.max_hp = 100
        source.physical_radius = 0
        source.effect_stats = {
            1: 100,
            20: 0,
            21: 0,
            22: 0,
            23: 0,
            24: 0,
            52: 0,
            92: 0,
            97: 0,
            100: 0,
        }
        source.effect_maxima = {1: 100, 92: 0}
        source.effect_frozen = frozenset()
        fight.phase = "active"
        fight.current = 7
        events = []
        fight._event = lambda kind, **values: events.append(dict(kind=kind, **values))
        packets = []
        handler = NativeDamageHandler(
            fight,
            packets,
            action_id=2,
            allocate_uid=lambda: 950,
            context=lambda *args: DamageExecutionContext(
                False, True, False, True, 11, False, "FRONT"
            ),
            rng=lambda: 0.5,
        )
        effect = dict(
            effect_class=1,
            parameters=[5, 0],
            native_effect_flags=[],
            native_localization_enabled=True,
        )
        invocation = EffectInvocation(100, 141, 7, 901, (2, 3, 0))
        self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual(fake_fighter_hp_state(row, definition)["current"], 3)
        self.assertEqual(
            fake_fighter_hp_wire(row, definition).hex(), "0000000800000003"
        )
        self.assertTrue(handler(effect, {}, invocation))
        self.assertEqual(group_pa(fight, 901, 1), (0, 8))
        self.assertEqual(
            fake_fighter_hp_wire(row, definition).hex(), "0000000800000000"
        )
        self.assertEqual(area_guards(fight, 901), dict(baG=False, baK=False, baF=True))
        slot = row["native_obstacle_id"]
        self.assertIsNotNone(
            NativeQIRegistry(fight.native_qi_snapshot, fight.native_qi_slots).slots[
                slot
            ]
        )
        self.assertEqual([event["hp"] for event in events], [3, 0])
        self.assertEqual([opcode for opcode, _ in packets], [12613, 12613])
        self.assertNotIn(901, fight.actors)
        fight.native_effect_areas[901] = deepcopy(before)
        self.assertEqual(group_pa(fight, 901, 1), (8, 8))
        remove_owned_hour_area(fight, 901)
        self.assertIsNone(fight.native_qi_slots[slot])

    def test_checkpoint_resource_receipt_roundtrip_and_tamper_rejection(self):
        from wakfu_server.fight_checkpoint_store import _plain

        fight, _, _, _ = self.create()
        row = fight.native_effect_areas[901]
        definition = native_effect_areas()["566"]
        restored = json.loads(json.dumps(_plain(row)))
        self.assertEqual(fake_fighter_hp_state(restored, definition)["current"], 8)
        restored["native_faw_hp_constructor"]["hp"]["maximum"] = 999
        with self.assertRaisesRegex(ValueError, "authority"):
            fake_fighter_hp_state(restored, definition)

    def test_default_creation_stays_disabled_and_damage_pc_branch_is_rejected(self):
        (
            fight,
            creator,
            allocated,
            packets,
        ) = area_fixture.NativeFakeFighterAreaTests().create()
        with self.assertRaisesRegex(ValueError, "characteristic"):
            creator(
                {"effect_class": 339},
                {"parameters": [566, 141]},
                EffectInvocation(101928, 141, 7, None, (2, 3, 0)),
            )
        self.assertEqual(allocated, [])
        creator.fake_fighter_hp_enabled = True
        with self.assertRaises(ValueError):
            creator(
                {"effect_class": 315},
                {"parameters": [614, 55]},
                EffectInvocation(104440, 55, 7, None, (2, 3, 0)),
            )
        self.assertEqual(allocated, [])
