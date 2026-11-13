"""Captured Rii conversations progress only their owner's active quest."""
import copy
import struct
import unittest
from contextlib import nullcontext
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from wakfu_server import npc_world, rii_conversation_progress as progress
from test_npc_observed_dialogue import captured_row, SOURCE
from test_npc_protectors import otomai


class RiiConversationTests(unittest.TestCase):
    def setUp(self):
        self.state = {
            "running": [5160],
            "completed": [],
            "objectives": [],
            "tracking": [5160],
            "completion_dates": {},
            "recent": [],
            "variables": {},
        }
        self.definition = {
            "d": 5160,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjJ": [
                {"d": i, "ckc": "", "cke": ""}
                for i in (10612, 10613, 10614, 10615, 10616, 10617, 10618, 10619, 10622)
            ],
            "cjK": [],
        }
        self.db = Mock()
        combat = {
            "d": 5143,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjU": 0,
            "getDuration": 0,
            "cjJ": [
                {"d": i} for i in (10574, 10575, 10576, 10608, 10609, 10610, 10611)
            ],
        }
        from wakfu_server.achievements.rii_ecosystem_activation import OBJECTIVES

        native = {
            5143: combat,
            5146: {"d": 5146, "native_class": "aJM"},
            5154: {
                "d": 5154,
                "native_class": "aJM",
                "aqb": True,
                "isVisible": False,
                "cjK": [],
                "cjJ": [
                    {"d": i, "ckc": "", "cke": "", "ckf": []}
                    for i in (10595, 10596, 10606, 10607)
                ],
            },
        }
        for identity, objectives in OBJECTIVES.items():
            native[identity] = {
                "d": identity,
                "native_class": "aJM",
                "aqb": False,
                "cjI": "",
                "cjU": 0,
                "getDuration": 0,
                "cjJ": [{"d": i} for i in objectives],
            }
        self.db.execute.side_effect = lambda sql, args: Mock(
            fetchone=Mock(
                return_value={"data": {"native": native.get(args[0], self.definition)}}
            )
        )
        self.store = Mock()
        self.store.connection.return_value = nullcontext(self.db)
        self.store.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.patches = [
            patch.object(
                progress.storage,
                "load_locked",
                side_effect=lambda *_: copy.deepcopy(self.state),
            ),
            patch.object(
                progress.storage,
                "store",
                side_effect=lambda db, ident, state: setattr(
                    self, "state", copy.deepcopy(state)
                ),
            ),
            patch.object(progress.storage, "record_event", return_value=True),
            patch("wakfu_server.achievements.service._owner"),
            patch("wakfu_server.achievements.service.drain_rewards", return_value=[]),
            patch(
                "wakfu_server.achievements.rii_starter_seed.grant_if_missing",
                return_value=[],
            ),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def spec(self):
        oto = otomai()
        oto["native_capture_contract"]["source_sha256"] = SOURCE
        return [
            (
                captured_row(-1706442046308322, 5461, 1385, -17, -4, 17, 3, 5765, 1243),
                [
                    (5765, 13275),
                    (5766, 13278),
                    (5767, 13280),
                    (5768, 13281),
                    (5769, 13282),
                    (5783, 13306),
                    (5770, 13283),
                ],
                10612,
            ),
            (oto, [(5772, 13288), (5773, 13289), (5774, 13290)], 10613),
            (
                captured_row(-1706442046308339, 5460, 1388, 0, -19, 3, 3, 5755, 1390),
                [(5755, 13258), (5756, 13260)],
                10614,
            ),
            (
                captured_row(-1706442046308328, 5467, 1385, 12, 32, 1, 1, 5782, 1255),
                [(5782, 13305), (5786, 13318)],
                10615,
            ),
        ]

    def session(self, row, edges):
        character = {k: row[k] for k in ("map_id", "instance_id", "x", "y", "z")}
        character.update(id=1, account_id=2, level=6)
        self.store.character.return_value = character
        session, _ = npc_world.begin(
            lambda: character,
            lambda: [row],
            row["actor_id"],
            row["action_ids"][0],
            facts_provider=lambda: {},
        )
        for node, choice in edges[:-1]:
            session.choose(node, choice)
        node, choice = edges[-1]
        return character, session, {"node_id": node, "choice_id": choice}

    def test_four_captured_dialogues_advance_matching_objective_and_close(self):
        for row, edges, objective in self.spec():
            with self.subTest(objective=objective):
                character, session, request = self.session(row, edges)
                with patch.object(progress.npc_world, "load_scene", return_value=[row]):
                    result = progress.choose(
                        self.store, 2, 1, character, session, request
                    )
                self.assertEqual(result["packet"], (12218, struct.pack(">i", 0)))
                self.assertTrue(any(code == 13832 for code, _ in result["packets"]))
                self.assertIn(objective, self.state["objectives"])
                self.assertIsNone(session.node_id)
        self.assertEqual(
            self.state["objectives"],
            [10595, 10596, 10606, 10607, 10612, 10613, 10614, 10615],
        )
        self.assertIn(5154, self.state["completed"])
        self.assertIn(5143, self.state["running"])
        self.assertIn(5143, self.state["tracking"])
        self.assertIn(5145, self.state["running"])
        self.assertFalse({5155, 5156} & set(self.state["running"]))

    def test_airyna_first_choice_starts_curriculum_before_first_fight(self):
        row, edges, _ = self.spec()[2]
        character = {k: row[k] for k in ("map_id", "instance_id", "x", "y", "z")}
        character.update(id=1, account_id=2, level=6)
        self.store.character.return_value = character
        session, _ = npc_world.begin(
            lambda: character,
            lambda: [row],
            row["actor_id"],
            row["action_ids"][0],
            facts_provider=lambda: {},
        )
        with patch.object(progress.npc_world, "load_scene", return_value=[row]):
            progress.choose(
                self.store,
                2,
                1,
                character,
                session,
                {"node_id": 5755, "choice_id": 13258},
            )
        self.assertEqual(session.node_id, 5756)
        self.assertTrue({10606, 10614}.issubset(self.state["objectives"]))
        self.assertIn(5143, self.state["running"])

    def test_airyna_decline_closes_client_dialogue_without_starting_mission(self):
        row, _, _ = self.spec()[2]
        character = {k: row[k] for k in ("map_id", "instance_id", "x", "y", "z")}
        character.update(id=1, account_id=2, level=6)
        session, _ = npc_world.begin(
            lambda: character,
            lambda: [row],
            row["actor_id"],
            row["action_ids"][0],
            facts_provider=lambda: {},
        )
        request = {"node_id": 5755, "choice_id": 13259}
        self.assertFalse(progress.recognizes(session, request))
        self.assertEqual(session.choose(**request), (12218, struct.pack(">i", 0)))
        self.assertIsNone(session.node_id)
        self.assertNotIn(5143, self.state["running"])

    def test_otomai_lore_branch_advances_talk_on_entry(self):
        row = self.spec()[1][0]
        character, session, request = self.session(
            row, [(5772, 13288), (5773, 13289), (5774, 13307)]
        )
        with patch.object(progress.npc_world, "load_scene", return_value=[row]):
            result = progress.choose(self.store, 2, 1, character, session, request)
        self.assertEqual(result["packet"], (12218, struct.pack(">i", 5775)))
        self.assertTrue({10596, 10613}.issubset(self.state["objectives"]))

    def test_huly_returns_after_intro_with_native_action_and_information(self):
        row = self.spec()[0][0]
        character = {k: row[k] for k in ("map_id", "instance_id", "x", "y", "z")}
        character.update(id=1, account_id=2, level=6)
        with self.assertRaises(ValueError):
            npc_world.begin(
                lambda: character,
                lambda: [row],
                row["actor_id"],
                1241,
                facts_provider=lambda: {10595: False},
            )
        session, packet = npc_world.begin(
            lambda: character,
            lambda: [row],
            row["actor_id"],
            1241,
            facts_provider=lambda: {10595: True},
        )
        self.assertEqual(session.node_id, 5757)
        self.assertEqual(session.choose(5757, 13263), (12218, struct.pack(">i", 5758)))
        self.assertEqual(session.choose(5758, 13266), (12218, struct.pack(">i", 5757)))
        self.assertEqual(session.choose(5757, 13267), (12218, struct.pack(">i", 5759)))
        self.assertEqual(session.choose(5759, 13268), (12218, struct.pack(">i", 5760)))
        self.assertEqual(session.choose(5760, 13271), (12218, struct.pack(">i", 0)))

    def test_no_progress_when_inactive_and_out_of_range_is_rejected(self):
        row, edges, _ = self.spec()[0]
        self.state["running"].clear()
        character, session, request = self.session(row, edges)
        with patch.object(progress.npc_world, "load_scene", return_value=[row]):
            result = progress.choose(self.store, 2, 1, character, session, request)
        self.assertEqual(result["packets"], [])
        self.assertEqual(self.state["objectives"], [])
        character, session, request = self.session(row, edges)
        self.store.character.return_value = dict(character, x=character["x"] + 100)
        with patch.object(progress.npc_world, "load_scene", return_value=[row]):
            with self.assertRaises(ValueError):
                progress.choose(self.store, 2, 1, character, session, request)
        self.assertEqual(session.node_id, request["node_id"])

    def test_failed_receipt_restores_dialogue_session(self):
        row, edges, _ = self.spec()[0]
        character, session, request = self.session(row, edges)
        with patch.object(
            progress.npc_world, "load_scene", return_value=[row]
        ), patch.object(progress.storage, "record_event", return_value=False):
            with self.assertRaises(ValueError):
                progress.choose(self.store, 2, 1, character, session, request)
        self.assertEqual(session.node_id, request["node_id"])
        self.assertEqual(self.state["objectives"], [])

    def test_prior_child_completion_is_reconciled_after_parent_conversation(self):
        self.state["completed"] = [5145]
        row, edges, _ = self.spec()[3]
        character, session, request = self.session(row, edges)
        with patch.object(progress.npc_world, "load_scene", return_value=[row]):
            result = progress.choose(self.store, 2, 1, character, session, request)
        self.assertIn(10615, self.state["objectives"])
        self.assertIn(10617, self.state["objectives"])
        self.assertNotIn(5145, self.state["running"])
        self.assertIn(10607, self.state["objectives"])
        self.assertEqual(sum(code == 13832 for code, _ in result["packets"]), 3)


if __name__ == "__main__":
    unittest.main()
