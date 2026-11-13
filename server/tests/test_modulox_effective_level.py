"""Modulox relies on the winner's actual level, not leaderboard selection."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.objectives import environmental_modulox_contracts as module


class Result:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class DB:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.proof = None

    def execute(self, sql, params):
        if "SELECT e.instance_id" in sql:
            return Result(
                dict(
                    instance_id=10,
                    room_order=2,
                    encounter_status="victory",
                    result={"completed": True},
                    definition_id=12,
                    team=0,
                    fight_status="finished",
                    fight_kind="pve",
                    selection_revision=1,
                    snapshot=self.snapshot,
                )
            )
        if "INSERT INTO recurring_modulox_victory_proofs" in sql:
            keys = (
                "definition_id",
                "version",
                "fight_id",
                "character_id",
                "account_id",
                "instance_id",
                "dungeon_definition_id",
                "effective_level",
                "target_effective_level",
                "selection_revision",
            )
            self.proof = dict(zip(keys, params[:-1]))
            self.proof["difficulty_snapshot"] = self.snapshot
            return Result(None)
        if "SELECT * FROM recurring_modulox_victory_proofs" in sql:
            return Result(self.proof)
        raise AssertionError(sql)


class ModuloxLevelTests(unittest.TestCase):
    def test_same_dungeon_at_level_in_both_modes_and_reject_overlevel(self):
        authority = dict(
            definition_id=4100,
            version=1,
            target_effective_level=80,
            dungeon_definition_id=12,
            final_room_order=2,
        )
        character = dict(id=16, account_id=2)
        for competitive, cap, level, expected in (
            (False, 0, 80, True),
            (True, 80, 80, True),
            (False, 0, 81, False),
            (True, 80, 81, False),
        ):
            with self.subTest(competitive=competitive, level=level):
                snapshot = dict(
                    instance_id=10,
                    selection_revision=1,
                    competitive=competitive,
                    competitive_max_level=cap,
                    stasis_level=2,
                )
                db = DB(snapshot)
                actor = SimpleNamespace(
                    controlled=True,
                    owner_id=2,
                    team=0,
                    effective_level=level,
                    pve_withdrawn=False,
                )
                fight = SimpleNamespace(
                    id=467, phase="finished", winner=0, actors={16: actor}
                )
                with patch.object(module, "_transaction"):
                    self.assertEqual(
                        module.victory(db, character, fight, authority), expected
                    )
                self.assertEqual(db.proof is not None, expected)


class ModuloxScaledRateTests(unittest.TestCase):
    def test_native_base_then_server_rate_with_signed_overflow_guard(self):
        from wakfu_server.achievements.scaled_xp import _rounded, _scaled_amount

        base = _rounded(2000, 1234)
        self.assertEqual(base, 24680)
        self.assertEqual(_scaled_amount(base, 100000), 246800)
        self.assertEqual(_scaled_amount(base, 10000), base)
        self.assertEqual(_scaled_amount(5, 15000), 8)
        with self.assertRaises(ValueError):
            _scaled_amount(2**62, 100000)
