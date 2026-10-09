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


class GeneralDungeonCriteriaTests(unittest.TestCase):
    def setUp(self):
        self.store = _Store({"version": 1, "is_neo_server": False})

    def test_empty_and_native_beta_mode_need_no_character_snapshot(self):
        self.assertTrue(dungeon_criteria.evaluate(self.store, ""))
        self.assertTrue(
            dungeon_criteria.evaluate(
                self.store,
                'not GetBooleanSystemConfiguration("beta.mode") and not IsNeoServer()',
            )
        )

    def test_calendar_annotations_and_leading_zero_dates(self):
        from wakfu_server.combat.combat_inventory_date_conditions import (
            calendar_milliseconds,
        )

        now = calendar_milliseconds((20, 10, 2026, 10, 0, 0))
        text = '@("event.expired") (IsAfter(16,10,2026,10,00,00) and IsBefore(03,11,2026,10,00,00))@ and #HasState(1536)#'
        self.assertTrue(
            dungeon_criteria.evaluate(
                self.store,
                text,
                now_ms=now,
                queries={"HasState": lambda identity: identity == 1536},
            )
        )
        self.assertFalse(
            dungeon_criteria.evaluate(
                self.store, text, now_ms=0, queries={"HasState": lambda identity: True}
            )
        )

    def test_sharp_annotation_preserves_native_predicate_arguments(self):
        arguments = []

        def has_state(identity):
            arguments.append(identity)
            return True

        self.assertTrue(
            dungeon_criteria.evaluate(
                self.store, "#HasState(1536)#", queries={"HasState": has_state}
            )
        )
        self.assertEqual([1536], arguments)

    def test_unmatched_sharp_annotation_fails_closed(self):
        for text in (
            "HasState(1536)#",
            "#HasState(1536)",
            "IsNeoServer()#",
            "#IsNeoServer()",
        ):
            with self.subTest(text=text), self.assertRaisesRegex(
                ValueError, "SHARP annotation"
            ):
                dungeon_criteria.evaluate(self.store, text)

    def test_sharp_annotation_still_requires_predicate_authority(self):
        with self.assertRaisesRegex(
            ValueError, "Missing dungeon predicate authority: HasState"
        ):
            dungeon_criteria.evaluate(self.store, "#HasState(1536)#")

    def test_missing_state_and_achievement_authority_fails_closed_even_negated(self):
        for text in (
            "not HasState(5724)",
            "not IsAchievementRunning(5335)",
            "IsAchievementComplete(836)",
        ):
            with self.subTest(text=text), self.assertRaisesRegex(
                ValueError, "Missing dungeon predicate authority"
            ):
                dungeon_criteria.evaluate(self.store, text)

    def test_level_and_inventory_use_complete_owned_snapshots(self):
        self.assertTrue(
            dungeon_criteria.evaluate(
                self.store, "GetRealLevel() >= 36", character={"level": 36}
            )
        )
        self.assertFalse(
            dungeon_criteria.evaluate(
                self.store, "GetRealLevel() >= 36", character={"level": 35}
            )
        )
        actor = {"inventory_items": [{"uid": 1, "reference": 20389, "quantity": 2}]}
        self.assertTrue(
            dungeon_criteria.evaluate(
                self.store,
                '@("missing.compass") GetItemQuantity(20389) > 0@',
                character=actor,
            )
        )
        with self.assertRaises(ValueError):
            dungeon_criteria.evaluate(
                self.store, "GetItemQuantity(20389) > 0", character={}
            )

    def test_malformed_or_unknown_predicates_cannot_be_short_circuited(self):
        for text in (
            "not IsNeoServer() or IsAdmin()",
            '@("bad") IsNeoServer()',
            "IsAfter(31,02,2026,10,00,00)",
            "HasState(True)",
            '__import__("os")',
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                dungeon_criteria.evaluate(self.store, text)
