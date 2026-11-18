"""Otomai item turn-ins settle only through their offered dialogue edge."""

import copy
import json
import struct
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.achievements import conversation
from wakfu_server.maps import quest_npc

CONTRACT = (
    Path(__file__).parents[1]
    / "wakfu_server/maps/native_quest_conversation_contracts.json"
)


class Cursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeDB:
    def __init__(self, row):
        self.row = row

    def execute(self, sql, _params=()):
        return Cursor(copy.deepcopy(self.row) if "world_dialogue_npcs" in sql else None)


class FakeStore:
    def __init__(self, db, character):
        self.db = db
        self.value = character

    def connection(self):
        from contextlib import nullcontext

        return nullcontext(self.db)

    def lock_character(self, *_args, **_kwargs):
        pass

    def character(self, *_args):
        return dict(self.value)

    def now(self):
        return datetime(2026, 1, 1, tzinfo=timezone.utc)


class OfferedChoiceSession:
    def __init__(self, actor_id, node_id, choice_id, publication_sha, offered=True):
        self.quest_conversation_actor_id = actor_id
        self.quest_publication_sha256 = publication_sha
        self.speaker_id = actor_id
        self.node_id = node_id
        self.graph = {(node_id, choice_id): 0}
        self._choice_id = choice_id
        self.offered = offered
        self.choose_calls = 0
        self.quest_nearby = lambda _character, _row: True
        self.authorize_speaker = lambda speaker, _node: speaker == actor_id

    def _node(self, node_id):
        if node_id != self.node_id:
            raise ValueError("wrong current node")
        return {"choices": [{"id": self._choice_id}]}

    def authorize_choice(self, choice):
        return self.offered and choice["id"] == self._choice_id

    def choose(self, *, node_id, choice_id):
        self.choose_calls += 1
        if (node_id, choice_id) not in self.graph:
            raise ValueError("choice was not offered")
        self.node_id = None
        return None


class OtomaiConversationTurnInTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads(CONTRACT.read_text())
        self.definitions, self.bindings = conversation.validate_rules(self.document)
        self.turnins = [
            entry for entry in self.document["turnins"] if entry["reference_id"] == 2873
        ]
        self.placement = next(
            p for p in self.document["placements"] if p["quest_id"] == 1695
        )
        self.row = dict(self.placement["row"])
        self.character = {
            "id": 7,
            "account_id": 8,
            "level": 100,
            "map_id": self.row["map_id"],
            "instance_id": self.row["instance_id"],
            "x": self.row["x"],
            "y": self.row["y"],
            "z": self.row["z"],
        }
        self.published = self.document, self.definitions, self.bindings
        self.publication_sha = conversation._digest(self.document)

    def _settle(self, turnin, state, *, offered=True, criteria_evaluator=None):
        from wakfu_server.achievements import storage

        binding = self.bindings[
            (
                turnin["reference_id"],
                turnin["action_id"],
                turnin["node_id"],
                turnin["choice_id"],
            )
        ]
        session = OfferedChoiceSession(
            self.row["actor_id"],
            turnin["node_id"],
            turnin["choice_id"],
            self.publication_sha,
            offered=offered,
        )
        db = FakeDB(self.row)
        store = FakeStore(db, self.character)
        current_state = copy.deepcopy(state)
        paid_rules = []
        saved_states = []

        def store_state(_db, _character_id, new_state):
            current_state.clear()
            current_state.update(copy.deepcopy(new_state))
            saved_states.append(copy.deepcopy(new_state))

        payment_result = ({}, [(1, b"item-debit")], [])
        with patch.object(
            quest_npc, "publication", return_value=self.published
        ), patch.object(quest_npc, "_owner"), patch(
            "wakfu_server.achievements.service._owner"
        ), patch.object(
            storage,
            "load_locked",
            side_effect=lambda _db, _cid: copy.deepcopy(current_state),
        ), patch.object(
            storage, "store", side_effect=store_state
        ), patch.object(
            storage, "record_event", return_value=True
        ) as record_event, patch.object(
            storage, "claim_reward"
        ) as claim_reward, patch(
            "wakfu_server.achievements.wire.changes", return_value=[(2, b"journal")]
        ), patch(
            "wakfu_server.achievements.service.drain_rewards", return_value=[]
        ), patch(
            "wakfu_server.achievements.mission_toolkit.settle", return_value=[]
        ), patch(
            "wakfu_server.dungeon_criteria.evaluate",
            side_effect=criteria_evaluator or (lambda *_args, **_kwargs: True),
        ), patch(
            "wakfu_server.native_generic_rewards._payment",
            side_effect=lambda _db, _store, _character, rule: (
                paid_rules.append(rule) or payment_result
            ),
        ), patch.dict(
            "sys.modules",
            {"wakfu_server.npc_world": SimpleNamespace(nearby=lambda *_args: True)},
        ):
            try:
                outcome = quest_npc.choose(
                    store,
                    self.character["account_id"],
                    "lease",
                    self.character,
                    session,
                    struct.pack(">ii", turnin["node_id"], turnin["choice_id"]),
                )
            except ValueError as error:
                outcome = error
        return (
            outcome,
            current_state,
            paid_rules,
            saved_states,
            session,
            record_event,
            claim_reward,
        )

    def _state_for(self, quest_id):
        completed = {
            1695: [],
            1708: [1695],
            1715: [1695, 1708],
        }.get(quest_id, [])
        return {
            "variables": {},
            "objectives": [],
            "running": [quest_id],
            "completed": completed,
            "tracking": [quest_id],
            "recent": [],
            "completion_dates": {},
        }

    def test_all_offered_turnins_debit_the_bound_item_and_advance_only_bound_objective(
        self,
    ):
        self.assertEqual(38, len(self.turnins))
        seen = set()
        for turnin in self.turnins:
            binding = self.bindings[
                (
                    turnin["reference_id"],
                    turnin["action_id"],
                    turnin["node_id"],
                    turnin["choice_id"],
                )
            ]
            seen.add(binding.quest_id)
            with self.subTest(quest=binding.quest_id, choice=turnin["choice_id"]):
                outcome, state, paid, saved, session, receipt, claim = self._settle(
                    turnin,
                    self._state_for(binding.quest_id),
                )
                self.assertTrue(outcome["applied"])
                self.assertEqual(
                    [
                        {
                            "group_cod": turnin["item_reference"],
                            "group_coe": turnin["quantity"],
                        }
                    ],
                    paid,
                )
                self.assertIn(binding.objective_id, state["objectives"])
                self.assertEqual([binding.objective_id], outcome["new_objectives"])
                self.assertEqual(1, len(saved))
                self.assertEqual(1, session.choose_calls)
                self.assertEqual(1, receipt.call_count)
                self.assertEqual(0, claim.call_count)
                self.assertFalse(outcome["completed"])
        self.assertEqual(10, len(seen))
        self.assertTrue({1717, 1719, 2869, 2870, 2871, 2872, 4733} <= seen)

    def test_unoffered_choice_or_missing_chain_prerequisite_rejects_before_payment(
        self,
    ):
        cases = [
            # The client cannot redeem a turn-in after its quest is complete or absent.
            (
                self.turnins[0],
                {
                    "variables": {},
                    "objectives": [],
                    "running": [],
                    "completed": [],
                    "tracking": [],
                    "recent": [],
                    "completion_dates": {},
                },
                False,
            ),
            # Native mission chains require the preceding Otomai stage.
            (
                next(
                    t
                    for t in self.turnins
                    if self.bindings[
                        (
                            t["reference_id"],
                            t["action_id"],
                            t["node_id"],
                            t["choice_id"],
                        )
                    ].quest_id
                    == 1708
                ),
                self._state_for(1708) | {"completed": []},
                False,
            ),
            (
                next(
                    t
                    for t in self.turnins
                    if self.bindings[
                        (
                            t["reference_id"],
                            t["action_id"],
                            t["node_id"],
                            t["choice_id"],
                        )
                    ].quest_id
                    == 1715
                ),
                self._state_for(1715) | {"completed": [1695]},
                False,
            ),
        ]
        for turnin, state, offered in cases:
            binding = self.bindings[
                (
                    turnin["reference_id"],
                    turnin["action_id"],
                    turnin["node_id"],
                    turnin["choice_id"],
                )
            ]
            with self.subTest(quest=binding.quest_id, offered=offered):
                outcome, after, paid, saved, _session, _receipt, _claim = self._settle(
                    turnin,
                    state,
                    offered=offered,
                )
                self.assertIsInstance(outcome, ValueError)
                self.assertRegex(str(outcome), "not offered")
                self.assertEqual([], paid)
                self.assertEqual(state, after)
                self.assertEqual([], saved)

    def test_native_chain_prerequisite_failure_does_not_consume_items_even_for_stale_session(
        self,
    ):
        turnin = next(
            t
            for t in self.turnins
            if self.bindings[
                (t["reference_id"], t["action_id"], t["node_id"], t["choice_id"])
            ].quest_id
            == 1708
        )
        binding = self.bindings[
            (
                turnin["reference_id"],
                turnin["action_id"],
                turnin["node_id"],
                turnin["choice_id"],
            )
        ]
        state = self._state_for(1708)
        outcome, after, paid, saved, _session, _receipt, _claim = self._settle(
            turnin,
            state,
            offered=True,
            criteria_evaluator=lambda _store, criterion, **_kwargs: criterion
            != "IsAchievementComplete(1695)",
        )
        self.assertIsInstance(outcome, ValueError)
        self.assertRegex(str(outcome), "prerequisite")
        self.assertEqual([], paid)
        self.assertEqual(state, after)
        self.assertEqual([], saved)


if __name__ == "__main__":
    unittest.main()
