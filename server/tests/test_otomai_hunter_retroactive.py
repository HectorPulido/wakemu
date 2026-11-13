"""Regression for previously earned Otomai boss objectives."""
import copy
import unittest
from unittest.mock import patch

from wakfu_server.achievements import combat_mission_activation
from wakfu_server.achievements import otomai_hunter_retroactive as retro


class RetroactiveHunterTests(unittest.TestCase):
    def setUp(self):
        self.state = {
            "variables": {},
            "objectives": [],
            "running": [1695],
            "completed": [],
            "tracking": [1695],
            "recent": [],
            "completion_dates": {},
        }
        self.rules = [
            {
                "quest_id": 1695,
                "objective_id": 6189,
                "kind": "monster",
                "target_id": 44,
                "count": 1,
                "evidence": "native boss",
                "acceptance": "explicit",
            }
        ]
        self.definitions = {
            1695: {
                "d": 1695,
                "native_class": "aJM",
                "aqb": False,
                "cjI": "",
                "cjJ": [
                    {"d": 6189, "ckc": "", "cke": ""},
                    {"d": 6190, "ckc": "", "cke": ""},
                ],
                "cjK": [],
            }
        }

    def test_explicit_boss_does_not_start_quest_automatically(self):
        state = copy.deepcopy(self.state)
        state["running"], state["tracking"] = [], []
        after, started = combat_mission_activation.auto_accept(
            state,
            {"original_breeds": [44]},
            self.rules,
            self.definitions,
            character={"level": 200},
            store=None,
            now_ms=1,
        )
        self.assertEqual((state, []), (after, started))

    @patch("wakfu_server.dungeon_criteria.evaluate", return_value=True)
    def test_previously_earned_boss_from_authenticated_receipt_only(self, _):
        class DB:
            def execute(self, *args):
                return self

            def fetchall(self):
                return [
                    {"event_key": "fight:22", "payload": {"original_breeds": [44]}},
                    {"event_key": "fight:23", "payload": {"original_breeds": [2]}},
                ]

        recorded, written = [], []

        def record(db, char_id, key, fact):
            recorded.append((key, fact))
            return True

        with patch("wakfu_server.achievements.service._owner"), patch(
            "wakfu_server.achievements.service.drain_rewards", return_value=[]
        ), patch(
            "wakfu_server.achievements.storage.load_locked",
            return_value=copy.deepcopy(self.state),
        ), patch(
            "wakfu_server.achievements.storage.record_event", side_effect=record
        ), patch(
            "wakfu_server.achievements.storage.store",
            side_effect=lambda db, c, s: written.append(s),
        ), patch(
            "wakfu_server.achievements.combat_missions.load",
            return_value=(self.rules, self.definitions),
        ):
            packets = retro.reconcile(
                DB(), object(), {"id": 7, "account_id": 2}, now_ms=123
            )
        self.assertEqual([6189], written[0]["objectives"])
        self.assertEqual("fight:22", recorded[0][1]["victory_receipt"])
        self.assertEqual(13832, packets[0][0])
        self.assertEqual([1695], written[0]["running"])


if __name__ == "__main__":
    unittest.main()
