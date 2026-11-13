import unittest
from unittest.mock import patch
from wakfu_server.achievements import ruel_hunts


class RuelHuntTests(unittest.TestCase):
    def setUp(self):
        self.hunts = ruel_hunts.load_catalog()
        self.state = {
            "variables": {},
            "objectives": [],
            "running": [],
            "completed": [3974],
            "tracking": [],
            "recent": [],
            "completion_dates": {},
        }
        self.now = 172800000

    def test_catalog_and_native_level_gates(self):
        self.assertEqual(56, len(self.hunts))
        for level, choice, limit in [
            (15, 10346, 3),
            (35, 10451, 5),
            (50, 10452, 7),
            (65, 10453, 11),
            (80, 10454, 15),
            (95, 10455, 19),
            (110, 10456, 22),
            (125, 10457, 26),
            (140, 10458, 30),
            (155, 10459, 33),
            (170, 10461, 36),
            (200, 10462, 57),
        ]:
            self.assertEqual(choice, ruel_hunts.native_choice(level, limit - 1))
            self.assertIsNone(ruel_hunts.native_choice(level, limit))
        self.assertIsNone(ruel_hunts.native_choice(14, 0))

    def test_assigned_only_prerequisite_no_parallel_and_daily(self):
        choice, offers = ruel_hunts.available(
            self.state, self.hunts, level=35, now_ms=self.now
        )
        self.assertEqual(10451, choice)
        self.assertTrue(offers)
        self.assertTrue(all(x["minimum_level"] <= 35 for x in offers))
        state, hunt = ruel_hunts.assign(
            self.state,
            self.hunts,
            character_id=7,
            level=35,
            offered_choice=choice,
            now_ms=self.now,
        )
        self.assertEqual([hunt["quest_id"]], state["running"])
        self.assertEqual([hunt["quest_id"]], state["tracking"])
        self.assertEqual(
            (None, []),
            ruel_hunts.available(state, self.hunts, level=35, now_ms=self.now),
        )
        state["running"] = []
        state["completed"].append(hunt["quest_id"])
        state["completion_dates"][str(hunt["quest_id"])] = self.now
        self.assertEqual(
            (None, []),
            ruel_hunts.available(state, self.hunts, level=35, now_ms=self.now),
        )
        self.assertTrue(
            ruel_hunts.available(
                state, self.hunts, level=35, now_ms=self.now + 86400000
            )[1]
        )
        state["completed"].remove(3974)
        self.assertEqual(
            (None, []),
            ruel_hunts.available(
                state, self.hunts, level=35, now_ms=self.now + 86400000
            ),
        )

    def test_only_assigned_target_counts_once(self):
        h = self.hunts[0]
        state = dict(self.state, running=[h["quest_id"]], tracking=[h["quest_id"]])
        definition = {
            "d": h["quest_id"],
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjJ": [{"d": h["objective_id"], "ckc": "", "cke": ""}],
            "cjK": [{"d": 91}],
        }
        defs = {h["quest_id"]: definition}
        with patch("wakfu_server.dungeon_criteria.evaluate", return_value=True):
            self.assertEqual(
                (state, [], [], []),
                ruel_hunts.complete(
                    state,
                    self.hunts,
                    defs,
                    {"original_breeds": [h["target_id"] + 1]},
                    character={"id": 7},
                    store=None,
                    now_ms=self.now,
                ),
            )
            after, rewards, objectives, completed = ruel_hunts.complete(
                state,
                self.hunts,
                defs,
                {"original_breeds": [h["target_id"]]},
                character={"id": 7},
                store=None,
                now_ms=self.now,
            )
            self.assertEqual([h["quest_id"]], completed)
            self.assertEqual([h["objective_id"]], objectives)
            self.assertEqual(1, after["variables"]["693"])
            self.assertEqual([(h["quest_id"], {"d": 91})], rewards)
            self.assertEqual(
                (after, [], [], []),
                ruel_hunts.complete(
                    after,
                    self.hunts,
                    defs,
                    {"original_breeds": [h["target_id"]]},
                    character={"id": 7},
                    store=None,
                    now_ms=self.now,
                ),
            )


if __name__ == "__main__":
    unittest.main()
