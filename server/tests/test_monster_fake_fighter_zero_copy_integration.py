"""Real p9=0 faW areas keep present sgQ with native bounds and identity."""
from copy import deepcopy
import json
import unittest

import test_combat_fake_fighter_area as area_fixture
from wakfu_server.combat_effect_area import native_effect_areas, remove_owned_hour_area
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_fake_fighter_resources import (
    fake_fighter_characteristics,
    fake_fighter_damage_snapshot,
)
from wakfu_server.combat_fake_fighter import verified_fake_fighter
from wakfu_server.combat_group_pv import group_pa
from wakfu_server.combat_area_damage_snapshot import (
    area_has_damage_characteristic,
    copy_area_damage_snapshot,
)
from wakfu_server.combat_damage_handler import (
    NativeDamageHandler,
    DamageExecutionContext,
)
from wakfu_server.combat_effect_area_targets import area_targets
from wakfu_server.combat_target_health_ordering import health_operand_for_pv


class FakeFighterZeroCopyIntegrationTests(unittest.TestCase):
    def create(self, reference=614):
        (
            fight,
            creator,
            allocated,
            packets,
        ) = area_fixture.NativeFakeFighterAreaTests().create()
        creator.fake_fighter_hp_enabled = True
        creator.fake_fighter_zero_copy_enabled = True
        self.assertTrue(
            creator(
                {"effect_class": 315},
                {"parameters": [reference, 55]},
                EffectInvocation(104440, 55, 7, None, (2, 3, 0)),
            )
        )
        return fight, creator, allocated, packets

    def test_all_four_real_definitions_keep_hp_and_zero_copy_damage_pc(self):
        for reference in (614, 616, 617, 618):
            with self.subTest(reference=reference):
                fight, _, allocated, _ = self.create(reference)
                row = fight.native_effect_areas[901]
                definition = native_effect_areas()[str(reference)]
                self.assertEqual(
                    verified_fake_fighter(row, definition)["characteristic_ids"],
                    (1, 20),
                )
                self.assertEqual(group_pa(fight, 901, 1), (100, 100))
                self.assertEqual(group_pa(fight, 901, 20), (0, 50000))
                self.assertIsNone(group_pa(fight, 901, 21))
                self.assertEqual(
                    fake_fighter_damage_snapshot(row, definition)["stats"],
                    {1: 100, 20: 0},
                )
                restored = json.loads(json.dumps(row))
                self.assertEqual(
                    fake_fighter_characteristics(restored, definition),
                    fake_fighter_characteristics(row, definition),
                )
                self.assertTrue(area_has_damage_characteristic(row, definition))
                operand = health_operand_for_pv(fight, area_targets(fight)[0])
                self.assertEqual(
                    (operand.present, operand.current, operand.maximum),
                    (True, 100, 100),
                )
                self.assertEqual(allocated, [901, 902])

    def test_real_damage_preserves_sgq_and_owned_hp_mutability(self):
        fight, _, _, _ = self.create()
        row = fight.native_effect_areas[901]
        definition = native_effect_areas()["614"]
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
        handler = NativeDamageHandler(
            fight,
            [],
            action_id=2,
            allocate_uid=lambda: 950,
            context=lambda *args: DamageExecutionContext(
                False, True, False, True, 11, False, "FRONT"
            ),
            rng=lambda: 0.5,
        )
        effect = dict(
            effect_class=1,
            parameters=[150, 0],
            native_effect_flags=[],
            native_localization_enabled=True,
        )
        self.assertTrue(
            handler(effect, {}, EffectInvocation(100, 55, 7, 901, (2, 3, 0)))
        )
        self.assertEqual(group_pa(fight, 901, 1), (0, 100))
        self.assertEqual(group_pa(fight, 901, 20), (0, 50000))
        self.assertEqual(events[0]["hp"], 0)
        self.assertNotIn(901, fight.actors)
        fight.native_effect_areas[901] = deepcopy(before)
        self.assertEqual(group_pa(fight, 901, 1), (100, 100))
        remove_owned_hour_area(fight, 901)
        self.assertNotIn(901, fight.native_effect_areas)

    def test_damage_pc_bounds_and_provenance_are_not_fighter_defaults(self):
        fight, _, _, _ = self.create()
        row = fight.native_effect_areas[901]
        definition = native_effect_areas()["614"]
        for current in (-5000, 50000):
            row["native_faw_damage_current"] = current
            self.assertEqual(
                fake_fighter_characteristics(row, definition)[20]["current"], current
            )
        for current in (-5001, 50001, True):
            row["native_faw_damage_current"] = current
            with self.subTest(current=current), self.assertRaisesRegex(
                ValueError, "sgQ PA authority"
            ):
                fake_fighter_characteristics(row, definition)

    def test_eyw_copy_requires_real_copy_authority_and_rejects_before_uid(self):
        (
            fight,
            creator,
            allocated,
            _,
        ) = area_fixture.NativeFakeFighterAreaTests().create()
        creator.fake_fighter_hp_enabled = creator.fake_fighter_zero_copy_enabled = True
        with self.assertRaisesRegex(ValueError, "copy authority"):
            creator(
                {"effect_class": 308},
                {"parameters": [614, 55]},
                EffectInvocation(100, 55, 7, None, (2, 3, 0)),
            )
        self.assertEqual(allocated, [])
        fight, _, _, _ = self.create()
        with self.assertRaisesRegex(ValueError, "copy authority"):
            copy_area_damage_snapshot(
                fight.native_effect_areas[901],
                native_effect_areas()["614"],
                source_stats={20: 999},
                container_type=11,
                spell_element_stat=21,
            )
        self.assertEqual(group_pa(fight, 901, 20), (0, 50000))
