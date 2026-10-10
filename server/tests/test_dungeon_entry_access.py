import unittest
from contextlib import contextmanager

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server.maps import dungeon_entry_access, dungeon_criteria


class Store:
    def __init__(self, policy=None):
        self.value = dict(dungeon_entry_access.DEFAULT) if policy is None else policy

    @contextmanager
    def connection(self):
        yield self

    def execute(self, query, params):
        if params != (dungeon_entry_access.SETTING,):
            raise AssertionError(params)
        return self

    def fetchone(self):
        return {"value": self.value}


class DungeonEntryAccessTests(unittest.TestCase):
    def check(self, expression, level=1, store=None):
        return dungeon_entry_access.evaluate(
            Store() if store is None else store,
            expression,
            character={"id": 1, "level": level},
        )

    def test_positive_negated_and_nested_missions_are_waived(self):
        for expression in (
            "IsAchievementComplete(100)",
            "not IsAchievementRunning(100)",
            "not (IsAchievementRunning(5568) and "
            "IsAchievementObjectiveComplete(11513) and "
            "not IsAchievementObjectiveComplete(11515))",
            "HasState(123)",
            '@("entry") IsAchievementComplete(100)@',
            "#IsAchievementComplete(100)#",
        ):
            with self.subTest(expression=expression):
                self.assertTrue(self.check(expression))

    def test_required_level_still_denies_in_either_operand_order(self):
        for expression in (
            "IsAchievementComplete(100) and GetRealLevel() >= 50",
            "GetRealLevel() >= 50 and not IsAchievementComplete(100)",
        ):
            with self.subTest(expression=expression):
                self.assertFalse(self.check(expression, 49))
                self.assertTrue(self.check(expression, 50))

    def test_mission_alternative_permits_entry_and_negation_stays_unknown(self):
        self.assertTrue(self.check("IsAchievementComplete(100) or GetRealLevel() > 99"))
        self.assertFalse(
            self.check("not (IsAchievementComplete(100) or GetRealLevel() > 0)")
        )
        self.assertTrue(
            self.check("not (IsAchievementComplete(100) and GetRealLevel() > 99)")
        )

    def test_unsupported_predicates_and_malformed_mission_arguments_fail_closed(self):
        for expression in (
            "IsAchievementComplete(100) or IsAdmin()",
            "IsAchievementComplete(0)",
            "IsAchievementComplete(true)",
            "HasState(-1)",
            "IsAchievementRunning()",
            "IsAchievementComplete(100) and GetRealLevel(3) > 0",
        ):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                self.check(expression)

    def test_default_evaluator_remains_strict_for_internal_doors(self):
        with self.assertRaisesRegex(ValueError, "Missing dungeon predicate authority"):
            dungeon_criteria.evaluate(Store(), "IsAchievementComplete(100)")

    def test_malformed_policy_never_defaults_to_open(self):
        for value in (
            {},
            {**dungeon_entry_access.DEFAULT, "extra": True},
            {**dungeon_entry_access.DEFAULT, "version": True},
            {**dungeon_entry_access.DEFAULT, "bypass_mission_prerequisites": 1},
        ):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "policy"
            ):
                self.check("", store=Store(value))

    def test_state_bypass_can_be_disabled_independently(self):
        store = Store(
            {**dungeon_entry_access.DEFAULT, "bypass_state_prerequisites": False}
        )
        with self.assertRaisesRegex(ValueError, "HasState"):
            self.check("HasState(100)", store=store)


class DungeonEntryPolicyPostgresTests(PostgresCase):
    def test_migration_default_and_operator_change_are_read_live(self):
        self.assertEqual(
            dungeon_entry_access.policy(self.store), dungeon_entry_access.DEFAULT
        )
        selected = {
            **dungeon_entry_access.DEFAULT,
            "bypass_mission_prerequisites": False,
        }
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name=%s",
                (Jsonb(selected), dungeon_entry_access.SETTING),
            )
        self.assertEqual(dungeon_entry_access.policy(self.store), selected)
        with self.assertRaisesRegex(ValueError, "achievement authority"):
            dungeon_entry_access.evaluate(
                self.store,
                "IsAchievementComplete(100)",
                character={"id": 999999},
            )

    def test_missing_policy_fails_closed(self):
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM settings WHERE name=%s", (dungeon_entry_access.SETTING,)
            )
        with self.assertRaisesRegex(ValueError, "policy"):
            dungeon_entry_access.evaluate(self.store, "", character={"id": 1})
