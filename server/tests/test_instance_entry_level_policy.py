"""Entrance-only lower-bound waiver keeps real levels and other predicates."""
from contextlib import contextmanager
from copy import deepcopy
import unittest

import test_dungeon_entry_access as access_fixture
from wakfu_server.maps import (
    dungeon_criteria,
    dungeon_entry_access,
    instance_entry_level,
)


class InstanceEntryLevelPolicyTests(unittest.TestCase):
    def test_only_admission_minimum_is_waived_with_typed_policy_and_real_operands(self):
        character = dict(
            id=7,
            level=1,
            real_level=1,
            hp=49,
            max_hp=60,
            inventory_items=[],
            quest_inventory=[],
        )
        before = deepcopy(character)
        store = access_fixture.Store(minimum_enforced=False)
        store.clock = lambda: 1_800_000_000
        for expression in (
            "GetRealLevel() >= 200",
            "200 <= GetRealLevel()",
            "GetRealLevel() > 200",
            "not (GetRealLevel() < 200)",
            "not (200 > GetRealLevel())",
            "IsAchievementComplete(99) and GetRealLevel() >= 200",
        ):
            with self.subTest(expression=expression):
                self.assertTrue(
                    dungeon_entry_access.evaluate(
                        store, expression, character=character
                    )
                )
        for expression in (
            "GetRealLevel() >= 200 and false",
            "GetRealLevel() > 200 and 2 > 3",
            "GetRealLevel() >= 200 and GetRealLevel() <= 0",
            "GetRealLevel() == 200",
            "GetRealLevel() != 1",
            "not (GetRealLevel() >= 1)",
            "0 <= GetRealLevel() <= 0",
            "GetRealLevel() >= 200 and IsBefore(1,1,2000,0,0,0)",
        ):
            with self.subTest(expression=expression):
                self.assertFalse(
                    dungeon_entry_access.evaluate(
                        store, expression, character=character
                    )
                )
        # Internal doors retain their strict default; admission never edits data.
        self.assertFalse(
            dungeon_criteria.evaluate(
                store, "GetRealLevel() >= 200", character=character
            )
        )
        self.assertTrue(
            instance_entry_level.minimum_level_allowed(1, 200, enforce_minimum=False)
        )
        self.assertFalse(
            instance_entry_level.minimum_level_allowed(1, 200, enforce_minimum=True)
        )
        self.assertTrue(
            instance_entry_level.minimum_level_allowed(245, 200, enforce_minimum=True)
        )
        for args in (
            (True, 200, False),
            (1, True, False),
            (1, 200, 0),
            (0, 200, False),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                instance_entry_level.minimum_level_allowed(
                    args[0], args[1], enforce_minimum=args[2]
                )
        for malformed in (
            {},
            {"version": True, "enforce_minimum_level": False},
            {"version": 1, "enforce_minimum_level": 0},
            {"version": 1, "enforce_minimum_level": False, "extra": True},
        ):

            class Connection:
                def execute(self, *_):
                    return self

                def fetchone(self):
                    return {"value": malformed}

            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                instance_entry_level.enforced(Connection())
        for expression in (
            "GetRealLevel(1) >= 200",
            "GetRealLevel() >= true",
            "GetRealLevel() + 1 >= 200",
        ):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                dungeon_entry_access.evaluate(store, expression, character=character)
        self.assertEqual(character, before)
