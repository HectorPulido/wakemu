"""Native eZI maximum percentages compose with gear and aptitude percentages."""
import copy
import unittest
from unittest.mock import patch

from wakfu_server.consumable_characteristics import bonuses
from wakfu_server.equipment_stats import effective_character
from wakfu_server.health import maximum
from wakfu_server.wire import proto_field


def percentage_state(level=1, amount=None):
    params = [0.0, -10.0] if amount is None else [float(amount), 0.0]
    value = -10 * level if amount is None else amount
    node = dict(
        id=254573,
        generic=986,
        runner="eZI",
        stat_id=None,
        params=params,
        values=[value],
        level=level,
        children=[],
        criteria="",
        subscription=False,
        native_metadata=dict(
            native_target_selector={"class": "fcE", "mask": 1}, target_masks=[None] * 7
        ),
    )
    return dict(
        state_id=981,
        level=level,
        remaining_ms=240000,
        clock="online",
        effect_ids=[254573],
        metadata=dict(native_effects={"254573": node}),
    )


class ConsumableHPPercentageTests(unittest.TestCase):
    def test_native_percentage_is_not_flat_hp_and_recomputes_level(self):
        row = percentage_state(1)
        row["level"] = 9
        self.assertEqual(
            bonuses({"consumable_states": [row]}),
            dict(stats={}, percentages={1: -90}, unsupported=[]),
        )
        self.assertEqual(
            bonuses({"consumable_states": [percentage_state(10, -99)]})["percentages"],
            {1: -99},
        )
        for change in (
            dict(generic=1),
            dict(children=[1]),
            dict(params=[0.0, -10.0, 1.0, 0.0]),
        ):
            invalid = copy.deepcopy(row)
            invalid["metadata"]["native_effects"]["254573"].update(change)
            self.assertTrue(bonuses({"consumable_states": [invalid]})["unsupported"])

    def test_native_resource_reduction_is_negative_and_contextual_copies_reject(self):
        row = percentage_state()
        node = row["metadata"]["native_effects"]["254573"]
        node.update(generic=192, runner="eWO", params=[3.0, 0.0], values=[3])
        self.assertEqual(
            bonuses({"consumable_states": [row]}), dict(stats={4: -3}, unsupported=[])
        )
        for amount in (-1, -2):
            node.update(params=[float(amount), 0.0], values=[amount])
            self.assertTrue(bonuses({"consumable_states": [row]})["unsupported"])

    def test_world_percentage_composes_with_aptitudes_preserving_gear_and_wounds(self):
        equipment = proto_field(10, proto_field(8, 1000) + proto_field(16, 4)).hex()
        char = dict(
            id=1,
            breed=8,
            level=6,
            hp=41,
            max_hp=maximum(8, 6),
            hp_damage=7,
            health_dead=False,
            inventory_items=[
                dict(uid=1000, character_id=1, reference=2021, quantity=1)
            ],
            builds={
                0: dict(equipment=equipment, sheet=proto_field(24, (1 << 64) - 1).hex())
            },
            consumable_states=[percentage_state(3)],
        )
        original = copy.deepcopy(char)
        with patch(
            "wakfu_server.aptitudes.bonuses",
            return_value=dict(stats={}, percentages={1: 10}, unsupported=[]),
        ):
            base = effective_character(char)
            world = effective_character(char, include_consumable_buffs=True)
        flat = maximum(8, 6) + 6  # Actual equipped amulet's native flat HP.
        self.assertEqual(base["max_hp"], flat + flat * 10 // 100)
        self.assertEqual(world["max_hp"], flat - flat * 20 // 100)
        self.assertEqual(world["hp"], max(1, world["max_hp"] - 7))
        self.assertEqual(char, original)
