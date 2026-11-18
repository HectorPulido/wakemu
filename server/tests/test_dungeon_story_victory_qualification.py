"""One focused durable retry case for source-qualified story victories."""
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest

from wakfu_server import dungeon_progression


PROFILE_DIR = (
    Path(__file__).parents[1] / "wakfu_server" / "maps" / "owned_story_profiles"
)


class _Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class _DB:
    def __init__(self, controller, *, source=True):
        self.run = dict(
            instance_id=500,
            status="active",
            current_room=1,
            revision=4,
            rooms=[
                {"order": 1, "monsters": [{"ref_id": 2803, "count": 1}]},
                {"order": 2, "monsters": [{"ref_id": 2803, "count": 1}]},
            ],
        )
        self.encounter = dict(
            fight_id=900,
            instance_id=500,
            room_order=1,
            player_team=0,
            status="active",
            encounter_scope="main",
            result=None,
        )
        self.authority = dict(created_by_character_id=7, controller=controller)
        self.source = (
            None
            if source is False
            else dict(
                asset_map_id=720,
                group_id=71,
                members=[dict(id=-2803, ref=2803, count=1)],
                status="defeated",
                fight_id=None,
            )
        )
        self.rearms = 0

    def execute(self, sql, params=()):
        if "SELECT * FROM dungeon_room_encounters" in sql:
            return _Result(self.encounter)
        if "SELECT * FROM dungeon_room_runs" in sql:
            return _Result(self.run)
        if "SELECT i.created_by_character_id" in sql:
            return _Result(self.authority)
        if "SELECT s.asset_map_id,s.group_id" in sql:
            return _Result(self.source)
        if sql.startswith("UPDATE dungeon_room_runs"):
            self.run.update(
                current_room=params[0], status=params[1], revision=params[2]
            )
            return _Result()
        if sql.startswith("UPDATE dungeon_room_encounters SET status="):
            self.encounter.update(
                status=params[0],
                result_revision=params[1],
                result=json.loads(params[2]),
            )
            return _Result()
        if sql.startswith("UPDATE combat_groups SET status='available'"):
            self.rearms += 1
            if self.source is None or self.source["status"] != "defeated":
                return _Result()
            self.source.update(status="available", fight_id=None)
            return _Result({"group_id": self.source["group_id"]})
        raise AssertionError(f"Unexpected dungeon settlement SQL: {sql}")


class DungeonStoryVictoryQualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = json.loads(
            (PROFILE_DIR / "wild-estate-cure-720.configuration.json").read_text()
        )
        cls.controller = config["topology"]["owned_story_controller"]

    def fight(self, *, cause=107114):
        members = [dict(id=-2803, ref=2803, count=1)]
        events = [
            dict(
                kind="kill_hp_minimum_update",
                effect_class=28,
                generic_effect=cause,
                source_id=600,
                target_id=-2803,
                hp_before=100,
                hp=0,
                minimum=0,
                uid=77,
            ),
            dict(kind="death", actor_id=-2803),
        ]
        return (
            SimpleNamespace(
                id=900,
                phase="finished",
                winner=0,
                map_id=720,
                events=events,
                actors={
                    7: SimpleNamespace(id=7, hp=100, team=0, controlled=True),
                    -2803: SimpleNamespace(id=-2803, hp=0, team=1, controlled=False),
                },
                native_summon_registrations={},
                native_environment_glyph_constructors=[
                    dict(
                        uid=600,
                        reference=630,
                        neutral_faw_constructor={"source": "actual630"},
                    )
                ],
            ),
            members,
        )

    def test_qualification_retry_preserves_native_result_and_only_rearms_original_group_once(
        self,
    ):
        qualifying, members = self.fight()
        db = _DB(self.controller)
        native = dungeon_progression.settle_encounter(db, qualifying)
        self.assertTrue(native["victory"])
        self.assertEqual(native["current_room"], 2)
        self.assertEqual((db.run["current_room"], db.run["status"]), (2, "active"))
        self.assertEqual(db.rearms, 0)

        ordinary, _ = self.fight(cause=107115)
        ordinary_db = _DB(None, source=False)
        ordinary_result = dungeon_progression.settle_encounter(ordinary_db, ordinary)
        self.assertTrue(ordinary_result["victory"])
        self.assertEqual(ordinary_db.run["current_room"], 2)
        self.assertEqual(ordinary_db.rearms, 0)

        wrong_cause, originals = self.fight(cause=107115)
        retry_db = _DB(self.controller)
        retry = dungeon_progression.settle_encounter(retry_db, wrong_cause)
        self.assertTrue(wrong_cause.phase == "finished" and wrong_cause.winner == 0)
        self.assertTrue(retry["native_victory"])
        self.assertFalse(retry["qualified"])
        self.assertFalse(retry["victory"])
        self.assertEqual(
            (
                retry_db.encounter["status"],
                retry_db.run["current_room"],
                retry_db.run["status"],
            ),
            ("victory", 1, "active"),
        )
        self.assertEqual(retry_db.source["status"], "available")
        self.assertIsNone(retry_db.source["fight_id"])
        self.assertEqual(retry_db.source["members"], originals)
        replay = dungeon_progression.settle_encounter(retry_db, wrong_cause)
        self.assertTrue(replay["replay"])
        self.assertEqual(retry_db.rearms, 1)

        for source in (False, "foreign"):
            invalid, _ = self.fight(cause=107115)
            invalid_db = _DB(self.controller, source=source is not False)
            if source == "foreign":
                invalid_db.source["members"] = [dict(id=-2802, ref=2802, count=1)]
            with self.subTest(source=source), self.assertRaisesRegex(
                ValueError, "original formation"
            ):
                dungeon_progression.settle_encounter(invalid_db, invalid)
            self.assertEqual(invalid_db.rearms, 0)
            self.assertEqual(invalid_db.run["current_room"], 1)


if __name__ == "__main__":
    unittest.main()
