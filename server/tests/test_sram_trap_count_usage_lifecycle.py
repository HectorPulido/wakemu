"""Trap area lifetime and personal-turn cast budget are independent authorities."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_effect_area_queries import areas_with_base_id
from wakfu_server.combat_effect_area import remove_owned_hour_area
from wakfu_server.combat_spell_usage import validate_usage, consume_usage


class TrapCountUsageLifecycleTests(unittest.TestCase):
    def test_removed_owned_trap_is_not_counted_even_with_retained_manager(self):
        row = dict(
            uid=91,
            reference=778,
            owner_id=15,
            native_area_contract="fbc",
            child_effect_uids={},
        )
        foreign = dict(uid=92, reference=778, owner_id=16, native_area_contract="fbc")
        fight = SimpleNamespace(
            native_effect_areas={91: row, 92: foreign},
            native_retired_area_managers={93: dict(row, uid=93)},
        )
        self.assertEqual(areas_with_base_id(fight, reference=778, owner_id=15), 1)
        self.assertEqual(remove_owned_hour_area(fight, 91), (row,))
        self.assertEqual(areas_with_base_id(fight, reference=778, owner_id=15), 0)
        self.assertEqual(areas_with_base_id(fight, reference=778, owner_id=16), 1)
        self.assertEqual(areas_with_base_id(fight, reference=778, all_owners=True), 1)

    def test_consumption_does_not_refund_cast_budget_and_next_personal_turn_resets(
        self,
    ):
        actor = SimpleNamespace(id=15, turn_count=3)
        fight = SimpleNamespace(
            actors={15: actor},
            native_spell_usage={},
            native_table_turn=3,
            native_effect_areas={},
        )
        # Published/native 5182 baseline: zero per-target, two per-turn, no interval.
        table = {"5182": dict(maximum_level=200, limits=[0, 2, 0, 0], conditional=[])}
        with patch("wakfu_server.combat_spell_usage.native_limits", return_value=table):
            for _ in range(2):
                rule = validate_usage(fight, actor, 5182, 50, (1, 0, 0))
                consume_usage(
                    fight, dict(actor_id=15, spell_id=5182, native_usage=rule)
                )
            self.assertEqual(areas_with_base_id(fight, reference=778, owner_id=15), 0)
            with self.assertRaisesRegex(ValueError, "maximum casts per turn"):
                validate_usage(fight, actor, 5182, 50, (1, 0, 0))
            actor.turn_count += 1
            fight.native_table_turn += 1
            rule = validate_usage(fight, actor, 5182, 50, (1, 0, 0))
            consume_usage(fight, dict(actor_id=15, spell_id=5182, native_usage=rule))
            self.assertEqual(fight.native_spell_usage["15"]["casts"]["5182"], 1)
