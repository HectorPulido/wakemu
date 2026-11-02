import unittest

from wakfu_server import dungeon_criteria, dungeon_entry_access
from wakfu_server.instance_entry_level import SETTING as LEVEL_SETTING


MADRAGUE = (
    '@("quest.Madrague.event.termine") '
    "(IsAfter(27,07,2027,10,00,00) and "
    "IsBefore(31,08,2027,10,00,00))@ and "
    '@("quest.Madrague.boussole") GetItemQuantity(20389) > 0@'
)


class _SettingsDB:
    def __init__(self, *, entry_policy=None, minimum_enforced=True):
        self.entry_policy = (
            dict(dungeon_entry_access.DEFAULT) if entry_policy is None else entry_policy
        )
        self.minimum_enforced = minimum_enforced

    def execute(self, _query, params):
        self.setting = params[0]
        return self

    def fetchone(self):
        if self.setting == dungeon_entry_access.SETTING:
            return {"value": self.entry_policy}
        if self.setting == LEVEL_SETTING:
            return {
                "value": {
                    "version": 1,
                    "enforce_minimum_level": self.minimum_enforced,
                }
            }
        raise AssertionError(self.setting)


class _Store:
    def __init__(self, *, entry_policy=None, minimum_enforced=True):
        self.db = _SettingsDB(
            entry_policy=entry_policy, minimum_enforced=minimum_enforced
        )

    def connection(self):
        from contextlib import contextmanager

        @contextmanager
        def opened():
            yield self.db

        return opened()

    def clock(self):
        return 1_800_000_000.0


def _actor(*, level=36, compass=1):
    return {
        "id": 17,
        "account_id": 23,
        "level": level,
        "inventory_items": (
            []
            if not compass
            else [{"uid": 31, "reference": 20389, "quantity": compass}]
        ),
        "quest_items": [],
        "account_quest_items": [],
        "exploration_secrets": {"account_item_refs": []},
    }


class DungeonUnrestrictedEntryTests(unittest.TestCase):
    def test_actual_madrague_entry_waives_future_window_but_keeps_compass(self):
        store = _Store()
        actor = _actor()
        self.assertTrue(
            dungeon_entry_access.evaluate(
                store, MADRAGUE, character=actor, destination_map_id=1075
            )
        )
        self.assertFalse(
            dungeon_entry_access.evaluate(
                store,
                MADRAGUE,
                character=_actor(compass=0),
                destination_map_id=1075,
            )
        )

    def test_unrestricted_offer_waives_calendar_mission_not_minimum(self):
        store = _Store(minimum_enforced=True)
        with store.connection() as db:
            self.assertTrue(
                dungeon_entry_access.unrestricted_offer_allowed(
                    db,
                    '@("quest.Madrague.event.termine") '
                    "(IsAfter(27,07,2027,10,00,00) and "
                    "IsBefore(31,08,2027,10,00,00))@",
                    character=_actor(level=36, compass=0),
                    destination_map_id=1075,
                )
            )
        self.assertFalse(
            dungeon_entry_access.evaluate(
                store,
                "GetRealLevel() >= 51 and GetItemQuantity(20389) > 0",
                character=_actor(level=50),
                destination_map_id=1075,
            )
        )

    def test_direct_criteria_keeps_calendar_and_mission_authority_strict(self):
        store = _Store()
        self.assertFalse(
            dungeon_criteria.evaluate(
                store,
                "IsAfter(27,07,2027,10,00,00)",
                character=_actor(),
                now_ms=1_800_000_000_000,
            )
        )
        self.assertFalse(
            dungeon_criteria.evaluate(
                store,
                "GetDate(01,01,2029,10,00,00) < GetDate()",
                character=_actor(),
                now_ms=1_800_000_000_000,
            )
        )
        with self.assertRaisesRegex(ValueError, "Missing dungeon predicate authority"):
            dungeon_criteria.evaluate(store, "IsAchievementComplete(836)")

    def test_negated_mission_is_waived_only_for_entry(self):
        store = _Store()
        self.assertTrue(
            dungeon_entry_access.evaluate(
                store,
                "not IsAchievementComplete(836)",
                character=_actor(),
                destination_map_id=1075,
            )
        )
        with self.assertRaisesRegex(ValueError, "Missing dungeon predicate authority"):
            dungeon_criteria.evaluate(store, "not IsAchievementComplete(836)")

    def test_invalid_dates_and_unknown_predicates_fail_closed(self):
        store = _Store()
        for criterion in (
            "IsAfter(31,02,2027,10,00,00)",
            "GetDate(31,02,2027,10,00,00) > 0",
            "IsAfter(01,01,2027,0,0,0) and UnknownPredicate()",
            "GetDate(1,1,2029) > 0",
        ):
            with self.subTest(criterion=criterion), self.assertRaises(ValueError):
                dungeon_entry_access.evaluate(
                    store, criterion, character=_actor(), destination_map_id=1075
                )

    def test_malformed_entry_policy_fails_closed(self):
        for policy in (
            {},
            {**dungeon_entry_access.DEFAULT, "unexpected": True},
            {**dungeon_entry_access.DEFAULT, "bypass_mission_prerequisites": 1},
        ):
            with self.subTest(policy=policy), self.assertRaisesRegex(
                ValueError, "policy"
            ):
                dungeon_entry_access.evaluate(
                    _Store(entry_policy=policy), "", character=_actor()
                )
