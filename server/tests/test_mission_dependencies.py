import unittest
from unittest.mock import patch

from wakfu_server.achievements.mission_dependencies import reconcile, settle


def quest(identity, objectives):
    return {
        "d": identity,
        "native_class": "aJM",
        "aqb": False,
        "cjI": "",
        "cjJ": [
            {"d": identity_, "ckc": criterion, "cke": ""}
            for identity_, criterion in objectives
        ],
        "cjK": [],
    }


def snapshot(*, running, completed=(), objectives=()):
    return {
        "running": list(running),
        "completed": list(completed),
        "objectives": list(objectives),
        "tracking": list(running),
        "completion_dates": {},
        "recent": [],
    }


class MissionDependenciesTest(unittest.TestCase):
    def setUp(self):
        self.definitions = {
            10: quest(10, [(100, "IsAchievementObjectiveComplete(101)"), (101, "")]),
            20: quest(20, [(200, "")]),
            30: quest(30, [(300, "")]),
        }
        self.links = ((10, 100, 20), (30, 300, 10))
        self.character = {"id": 1, "account_id": 2}

    def apply(self, state, links=None):
        return reconcile(
            state,
            self.definitions,
            self.links if links is None else links,
            character=self.character,
            store=None,
            now_ms=123,
        )

    def test_prerequisite_waits_then_completion_cascades_and_is_idempotent(self):
        original = snapshot(running=(10, 30), completed=(20,))
        waiting, intents, objectives, completed = self.apply(original)
        self.assertEqual((intents, objectives, completed), ([], [], []))
        self.assertEqual(original, waiting)
        waiting["objectives"].append(101)
        result, intents, objectives, completed = self.apply(waiting)
        self.assertEqual(objectives, [100, 300])
        self.assertEqual(completed, [10, 30])
        self.assertEqual(result["running"], [])
        self.assertEqual(result["completed"], [10, 20, 30])
        self.assertEqual(self.apply(result)[1:], ([], [], []))

    def test_never_starts_parent_or_uses_incomplete_child(self):
        state = snapshot(running=(10,), objectives=(101,))
        self.assertEqual(self.apply(state), (state, [], [], []))
        state = snapshot(running=(), completed=(20,), objectives=(101,))
        self.assertEqual(self.apply(state), (state, [], [], []))

    def test_invalid_or_conflicting_edges_are_rejected(self):
        state = snapshot(running=(10,), completed=(20,))
        for links in (
            ((10, 999, 20),),
            ((10, 100, 20), (10, 100, 30)),
            ((10, 100, 10),),
            ((10, 100, 99),),
        ):
            with self.subTest(links=links), self.assertRaises(ValueError):
                self.apply(state, links)

    def test_atomic_settlement_includes_producer_and_cascaded_changes(self):
        before = snapshot(running=(10, 20, 30), objectives=(101,))
        before["variables"] = {}
        planned = snapshot(running=(10, 30), completed=(20,), objectives=(101, 200))
        planned["variables"] = {}
        with patch("wakfu_server.achievements.service._owner") as owner, patch(
            "wakfu_server.achievements.service.drain_rewards", return_value=[]
        ) as drain, patch("wakfu_server.achievements.storage.store") as persist:
            outcome = settle(
                object(),
                None,
                self.character,
                before,
                (planned, [], [200], [20]),
                self.definitions,
                self.links,
                now_ms=123,
            )
        owner.assert_called_once()
        drain.assert_called_once()
        persist.assert_called_once()
        self.assertEqual(outcome["new_objectives"], [200, 100, 300])
        self.assertEqual(outcome["completed"], [20, 10, 30])
        self.assertEqual([opcode for opcode, _ in outcome["packets"]].count(13832), 3)
        self.assertEqual([opcode for opcode, _ in outcome["packets"]].count(13422), 3)

    def test_final_combat_lesson_claims_child_and_parent_rewards(self):
        child = quest(5143, [(10611, "")])
        parent = quest(5160, [(10616, "")])
        child["cjK"] = [{"d": 21, "aeV": 3, "ckl": [20016]}]
        parent["cjK"] = [{"d": 22, "aeV": 2, "ckl": [755]}]
        before = snapshot(running=(5143, 5160))
        before["variables"] = {}
        planned_state = snapshot(
            running=(5160,), completed=(5143,), objectives=(10611,)
        )
        planned_state["variables"] = {}
        planned = (planned_state, [(5143, child["cjK"][0])], [10611], [5143])
        with patch("wakfu_server.achievements.service._owner"), patch(
            "wakfu_server.achievements.service.drain_rewards", return_value=[]
        ) as drain, patch(
            "wakfu_server.achievements.storage.claim_reward", return_value=True
        ) as claim, patch(
            "wakfu_server.achievements.storage.store"
        ) as persist:
            outcome = settle(
                object(),
                None,
                self.character,
                before,
                planned,
                {5143: child, 5160: parent},
                ((5160, 10616, 5143),),
                now_ms=123,
            )
        self.assertEqual(outcome["completed"], [5143, 5160])
        self.assertEqual(outcome["new_objectives"], [10611, 10616])
        self.assertEqual([call.args[2] for call in claim.call_args_list], [5143, 5160])
        persist.assert_called_once()
        drain.assert_called_once()


if __name__ == "__main__":
    unittest.main()
