"""Focal automatic acceptance coverage for daily and Modulox hunter catalogs."""
from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from wakfu_server.objectives import environmental_recurring_storage as recurring
from wakfu_server.objectives import recurring_combat_auto as automatic


class Cursor:
    def __init__(self, row=None, rows=()):
        self.row = row
        self.rows = list(rows)

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class AcceptanceDB:
    def __init__(self, event, catalog):
        self.event = event
        self.catalog = catalog
        self.accepted = set()
        self.inserts = []
        self.candidate_level = None

    def execute(self, sql, args=()):
        if "FROM settings" in sql:
            return Cursor({"value": {"policy": automatic.POLICY, "enabled": True}})
        if "FROM character_achievement_events" in sql:
            return Cursor(
                {
                    "payload": self.event,
                    "created_at": datetime(2026, 2, 20, 12, tzinfo=timezone.utc),
                }
            )
        if "FROM dungeon_room_encounters" in sql:
            return Cursor(
                {
                    "rooms": [
                        {"order": 4, "monsters": [{"ref_id": 900, "role": "boss"}]}
                    ],
                    "room_order": 4,
                }
            )
        if "FROM recurring_hunter_contracts c" in sql:
            policies, _references, self.candidate_level = args
            rows = [
                {"definition_id": identity, "version": 1}
                for identity, row in sorted(self.catalog.items())
                if row["policy"] in policies
                and row["minimum_level"] <= self.candidate_level
            ]
            return Cursor(rows=rows)
        if "FROM recurring_hunter_acceptances" in sql:
            return Cursor(
                {"present": True} if (args[1], args[2]) in self.accepted else None
            )
        if sql.startswith("INSERT INTO recurring_hunter_acceptances"):
            self.accepted.add((args[1], args[3]))
            self.inserts.append(args)
            return Cursor()
        return Cursor()


class RecurringCombatAutoTests(unittest.TestCase):
    def setUp(self):
        self.event = {
            "fight_id": 77,
            "completed_dungeon_id": 88,
            "original_monsters": [[7001, 900]],
            "original_breeds": [900],
        }
        self.fight = type("Fight", (), {"id": 77})()
        self.character = {"id": 10, "account_id": 20, "level": 100}
        self.store = object()
        self.state = {
            "variables": {},
            "objectives": [],
            "running": [],
            "completed": [],
            "tracking": [],
            "recent": [],
            "completion_dates": {},
        }
        self.catalog = {}
        self.loaded = {}
        self.daily_ids = list(range(5000, 5065))
        self.modulox_ids = list(range(6000, 6064))
        for identity in self.daily_ids + self.modulox_ids:
            is_modulox = identity in self.modulox_ids
            policy = recurring.MODULOX_POLICY if is_modulox else recurring.DAILY_POLICY
            source = {
                "interpretation_policy": policy,
                "daily_target_authority": {
                    "dungeon_definition_id": 88,
                    "boss_reference": 900,
                    "category_id": identity if is_modulox else 700,
                },
            }
            contract = type(
                "Contract",
                (),
                {
                    "definition_id": identity,
                    "boss_references": (900,),
                    "period": lambda _self, _when: 4,
                },
            )()
            self.catalog[identity] = {
                "policy": policy,
                "minimum_level": 50,
                "source": source,
                "contract": contract,
            }
            self.loaded[(identity, 1)] = (source, contract, [])
        self.db = AcceptanceDB(self.event, self.catalog)

    def invoke(
        self,
        *,
        is_day=True,
        event=None,
        character=None,
        category_allowed=True,
        victory=True,
    ):
        event = self.event if event is None else event
        self.db.event = event
        state = {**self.state, "running": [], "tracking": []}
        from wakfu_server.achievements import service, storage, wire

        with patch.object(automatic, "_owner"), patch.object(
            service, "_event", return_value=event
        ), patch.object(
            recurring, "_milliseconds", return_value=1_000_000
        ), patch.object(
            recurring, "_now", return_value=1_000_001
        ), patch(
            "wakfu_server.world_clock.daytime", return_value=is_day
        ), patch(
            "wakfu_server.world_clock.configured_offset_ms", return_value=0
        ), patch.object(
            recurring, "synchronize", return_value=[]
        ), patch.object(
            recurring,
            "_load",
            side_effect=lambda _db, identity, version: self.loaded[(identity, version)],
        ), patch.object(
            storage, "load_locked", return_value=state
        ), patch.object(
            storage, "record_event", return_value=True
        ) as record, patch.object(
            storage, "store"
        ) as save, patch.object(
            wire, "changes", return_value=[(1, b"accepted")]
        ), patch(
            "wakfu_server.objectives.environmental_modulox_contracts.native_boss_targets",
            return_value={900},
        ), patch(
            "wakfu_server.objectives.environmental_modulox_contracts.accept_category",
            return_value=category_allowed,
        ), patch(
            "wakfu_server.objectives.environmental_modulox_contracts.victory",
            return_value=victory,
        ):
            packets = automatic.accept_matching(
                self.db,
                self.store,
                self.character if character is None else character,
                self.fight,
                event,
            )
        updated = save.call_args.args[2] if save.called else state
        return packets, record, save, updated

    def test_accepts_all_65_daily_and_64_modulox_contracts_on_qualified_day(self):
        packets, record, save, state = self.invoke(is_day=True)
        self.assertEqual(129, len(self.db.inserts))
        self.assertEqual(set(self.daily_ids + self.modulox_ids), set(state["running"]))
        self.assertEqual(set(self.daily_ids + self.modulox_ids), set(state["tracking"]))
        self.assertEqual(129, record.call_count)
        save.assert_called_once()
        self.assertEqual([(1, b"accepted")], packets)
        self.assertEqual(100, self.db.candidate_level)

    def test_night_only_blocks_daily_hunts_while_modulox_uses_its_victory_gate(self):
        packets, _, _, state = self.invoke(is_day=False)
        self.assertEqual(set(self.modulox_ids), set(state["running"]))
        self.assertEqual(64, len(self.db.inserts))
        self.assertEqual([(1, b"accepted")], packets)

    def test_level_and_dungeon_gates_reject_candidates(self):
        _, _, save, state = self.invoke(character={**self.character, "level": 40})
        self.assertEqual([], self.db.inserts)
        self.assertEqual([], state["running"])
        save.assert_not_called()

        wrong_dungeon = {**self.event, "completed_dungeon_id": 999}
        _, _, save, state = self.invoke(event=wrong_dungeon)
        self.assertEqual([], self.db.inserts)
        self.assertEqual([], state["running"])
        save.assert_not_called()

    def test_modulox_category_or_victory_gate_failure_blocks_only_modulox(self):
        self.invoke(category_allowed=False, victory=True)
        self.assertEqual(
            set(self.daily_ids), {identity for identity, _ in self.db.accepted}
        )
        self.db.accepted.clear()
        self.db.inserts.clear()
        self.invoke(category_allowed=True, victory=False)
        self.assertEqual(
            set(self.daily_ids), {identity for identity, _ in self.db.accepted}
        )

    def test_repeated_receipt_does_not_create_duplicate_acceptance_rows(self):
        self.invoke()
        first_count = len(self.db.inserts)
        packets, record, save, _ = self.invoke()
        self.assertEqual(129, first_count)
        self.assertEqual(first_count, len(self.db.inserts))
        record.assert_not_called()
        save.assert_not_called()
        self.assertEqual([], packets)


if __name__ == "__main__":
    unittest.main()
