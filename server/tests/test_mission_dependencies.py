import unittest
import struct
from unittest.mock import patch

from wakfu_server.achievements.mission_dependencies import (
    reconcile,
    settle,
    _dependency_packet_order,
)


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

    def test_ordinary_packets_and_already_known_child_keep_their_order(self):
        packets = [
            (13295, b"counter"),
            (13832, struct.pack(">qi", 1, 100)),
            (13371, b"tracking"),
        ]
        self.assertIs(_dependency_packet_order(packets, self.definitions, ()), packets)
        self.assertIs(
            _dependency_packet_order(packets, self.definitions, self.links), packets
        )

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
            ((10, 100, 20), (10, 100, 20)),
            ((10, 100, 10),),
            ((10, 100, 99),),
        ):
            with self.subTest(links=links), self.assertRaises(ValueError):
                self.apply(state, links)

    def test_alternative_children_complete_shared_objective_once_without_starting_parent(
        self,
    ):
        links = ((10, 100, 20), (10, 100, 30))
        for completed_children in ((20,), (30,), (20, 30)):
            with self.subTest(completed_children=completed_children):
                current = snapshot(
                    running=(10,), completed=completed_children, objectives=(101,)
                )
                result, intents, objectives, completed = self.apply(current, links)
                self.assertEqual(objectives, [100])
                self.assertEqual(completed, [10])
                self.assertEqual(result["running"], [])
                self.assertEqual(result["completed"], sorted((10, *completed_children)))
                self.assertEqual(len(objectives), 1)

        # Child completion alone never activates an absent parent.
        absent = snapshot(running=(), completed=(20, 30), objectives=(101,))
        self.assertEqual(self.apply(absent, links), (absent, [], [], []))

        # Both candidate child completions precede the one shared objective
        # and its parent completion in the emitted causal facts.
        packets = [
            (13832, struct.pack(">qi", 7, 100)),
            (13422, struct.pack(">qiii", 7, 10, 0, 0)),
            (13422, struct.pack(">qiii", 7, 20, 0, 0)),
            (13422, struct.pack(">qiii", 7, 30, 0, 0)),
        ]
        ordered = _dependency_packet_order(packets, self.definitions, links)
        facts = [
            (opcode, struct.unpack_from(">i", body, 8)[0])
            for opcode, body in ordered
            if opcode in (13832, 13422)
        ]
        self.assertEqual(
            facts,
            [(13422, 20), (13422, 30), (13832, 100), (13422, 10)],
        )

    def test_atomic_settlement_includes_producer_and_cascaded_changes(self):
        before = snapshot(running=(10, 20, 30), objectives=(101,))
        before["variables"] = {}
        planned = snapshot(running=(10, 30), completed=(20,), objectives=(101, 200))
        planned["variables"] = {}
        db = object()
        with patch(
            "wakfu_server.achievements.mission_toolkit.settle_completions",
            return_value=[],
        ) as hook, patch("wakfu_server.achievements.service._owner") as owner, patch(
            "wakfu_server.achievements.service.drain_rewards", return_value=[]
        ) as drain, patch(
            "wakfu_server.achievements.storage.store"
        ) as persist, patch(
            "wakfu_server.achievements.storage.load_locked", return_value=planned
        ):
            outcome = settle(
                db,
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
        hook.assert_called_once_with(db, None, self.character, [20, 10, 30])
        self.assertEqual(outcome["new_objectives"], [100, 200, 300])
        self.assertEqual(outcome["completed"], [10, 20, 30])
        self.assertEqual([opcode for opcode, _ in outcome["packets"]].count(13832), 3)
        self.assertEqual([opcode for opcode, _ in outcome["packets"]].count(13422), 3)
        facts = [
            (opcode, struct.unpack_from(">i", body, 8)[0])
            for opcode, body in outcome["packets"]
            if opcode in (13832, 13422)
        ]
        self.assertEqual(
            facts,
            [
                (13832, 200),
                (13422, 20),
                (13832, 100),
                (13422, 10),
                (13832, 300),
                (13422, 30),
            ],
        )

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
        db = object()
        with patch(
            "wakfu_server.achievements.mission_toolkit.settle_completions",
            return_value=[],
        ) as hook, patch("wakfu_server.achievements.service._owner"), patch(
            "wakfu_server.achievements.service.drain_rewards", return_value=[]
        ) as drain, patch(
            "wakfu_server.achievements.storage.claim_reward", return_value=True
        ) as claim, patch(
            "wakfu_server.achievements.storage.store"
        ) as persist, patch(
            "wakfu_server.achievements.storage.load_locked", return_value=planned_state
        ):
            outcome = settle(
                db,
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
        facts = [
            (opcode, struct.unpack_from(">i", body, 8)[0])
            for opcode, body in outcome["packets"]
            if opcode in (13832, 13422)
        ]
        self.assertEqual(
            facts, [(13832, 10611), (13422, 5143), (13832, 10616), (13422, 5160)]
        )
        self.assertEqual([call.args[2] for call in claim.call_args_list], [5143, 5160])
        hook.assert_called_once_with(db, None, self.character, [5143, 5160])
        persist.assert_called_once()
        drain.assert_called_once()


if __name__ == "__main__":
    unittest.main()
