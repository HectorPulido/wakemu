import unittest
from contextlib import contextmanager

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server.maps import dungeon_criteria


class _DB:
    def __init__(self, value):
        self.value = value

    def execute(self, query, params):
        if query != "SELECT value FROM settings WHERE name=%s":
            raise AssertionError(query)
        if params != (dungeon_criteria.SETTING,):
            raise AssertionError(params)
        return self

    def fetchone(self):
        return None if self.value is None else {"value": self.value}


class _Store:
    def __init__(self, value):
        self.db = _DB(value)

    @contextmanager
    def connection(self):
        yield self.db


class DungeonCriteriaTests(unittest.TestCase):
    def test_explicit_normal_mode_satisfies_only_negative_neo_criterion(self):
        store = _Store({"version": 1, "is_neo_server": False})
        self.assertFalse(dungeon_criteria.is_neo_server(store))
        self.assertTrue(dungeon_criteria.evaluate(store, "not IsNeoServer()"))
        self.assertFalse(dungeon_criteria.evaluate(store, "IsNeoServer()"))

    def test_explicit_neo_mode_satisfies_only_positive_neo_criterion(self):
        store = _Store({"version": 1, "is_neo_server": True})
        self.assertTrue(dungeon_criteria.is_neo_server(store))
        self.assertTrue(dungeon_criteria.evaluate(store, "IsNeoServer()"))
        self.assertFalse(dungeon_criteria.evaluate(store, "not IsNeoServer()"))

    def test_missing_or_malformed_mode_fails_closed(self):
        for value in (
            None,
            {"version": 2, "is_neo_server": False},
            {"version": 1, "is_neo_server": 0},
            {"version": 1, "is_neo_server": False, "unexpected": True},
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "mode"):
                    dungeon_criteria.is_neo_server(_Store(value))

    def test_unsupported_criteria_are_not_treated_as_true(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            dungeon_criteria.evaluate(
                _Store({"version": 1, "is_neo_server": False}),
                "not IsAdmin()",
            )


class DungeonCriteriaPostgresTests(PostgresCase):
    def test_migration_seeds_explicit_native_default_and_setting_is_live(self):
        self.assertFalse(dungeon_criteria.is_neo_server(self.store))
        self.assertTrue(dungeon_criteria.evaluate(self.store, "not IsNeoServer()"))
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name=%s",
                (
                    Jsonb({"version": 1, "is_neo_server": True}),
                    dungeon_criteria.SETTING,
                ),
            )
        self.assertTrue(dungeon_criteria.is_neo_server(self.store))
        self.assertTrue(dungeon_criteria.evaluate(self.store, "IsNeoServer()"))
        self.assertFalse(dungeon_criteria.evaluate(self.store, "not IsNeoServer()"))

    def test_missing_mode_setting_fails_closed(self):
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM settings WHERE name=%s", (dungeon_criteria.SETTING,)
            )
        with self.assertRaisesRegex(ValueError, "not configured"):
            dungeon_criteria.evaluate(self.store, "not IsNeoServer()")


if __name__ == "__main__":
    unittest.main()
