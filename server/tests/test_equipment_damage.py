import unittest
from wakfu_server.equipment_damage import damage, resistance_multiplier, inputs
from wakfu_server.wire import proto_field

CONTEXT = dict(
    critical=False,
    single_target=False,
    area=False,
    melee=True,
    berserk=False,
    front=True,
)


class EquipmentDamageTests(unittest.TestCase):
    def test_native_fau_vectors_general_and_elemental_mastery_and_resistance(self):
        # Offline actual fau.fSy, fake owned PV characteristics, no effects.
        self.assertEqual(damage(80, 3, {20: 25}, {}, **CONTEXT), 100)
        self.assertEqual(damage(80, 3, {23: 25}, {}, **CONTEXT), 100)
        self.assertEqual(damage(80, 3, {}, {}, **CONTEXT), 80)
        self.assertEqual(damage(100, 3, {}, {30: 100}, **CONTEXT), 81)
        self.assertEqual(resistance_multiplier(100), 0.81)
        self.assertEqual(resistance_multiplier(2000), 0.1)
        # Running effect4 is WATER, unlike eVg4 which means AIR.
        self.assertEqual(damage(80, 4, {22: 25, 24: 1000}, {}, **CONTEXT), 100)

    def test_stochastic_rounding_uses_authoritative_fraction_not_round(self):
        # 80 * float(1.09) = about87.2: native UP.bt may yield87 or88.
        self.assertEqual(damage(80, 3, {20: 9}, {}, rng=lambda: 0.99, **CONTEXT), 87)
        self.assertEqual(damage(80, 3, {20: 9}, {}, rng=lambda: 0, **CONTEXT), 88)
        with self.assertRaises(ValueError):
            damage(80, 3, {20: 9}, {}, rng=lambda: 1, **CONTEXT)

    def test_critical_is_explicit_and_does_not_invent_variant_damage(self):
        self.assertEqual(
            damage(80, 3, {52: 25}, {}, **dict(CONTEXT, critical=True)), 100
        )
        self.assertEqual(damage(80, 3, {52: 25}, {}, **CONTEXT), 80)
        self.assertEqual(
            damage(100, 3, {}, {95: 100}, **dict(CONTEXT, critical=True)), 81
        )
        with self.assertRaises(ValueError):
            damage(80, 3, {}, {}, **dict(CONTEXT, front=False))

    def test_equipment_inputs_retain_true_critical_chance_and_stat_bonuses(self):
        sheet = proto_field(10, proto_field(8, 1000) + proto_field(16, 4)).hex()
        char = dict(
            id=1,
            level=6,
            inventory_items=[
                dict(uid=1000, character_id=1, reference=2021, quantity=1)
            ],
            builds={
                0: dict(equipment=sheet, sheet=proto_field(24, (1 << 64) - 1).hex())
            },
        )
        result = inputs(char)
        self.assertEqual(result["critical_chance"], 2)
        self.assertEqual(result["stats"][20], 9)
        self.assertEqual(result["unsupported"], [])
