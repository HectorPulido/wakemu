"""Otomai's reconstructed fresco conversation uses native dialogue nodes."""
import copy
import struct
from unittest import TestCase
from unittest.mock import Mock, patch

from wakfu_server import npc_world, rii_otomai_fresco as fresco
from test_rii_conversation_progress import RiiConversationTests


class RiiOtomaiFrescoTests(TestCase):
    spec = RiiConversationTests.spec
    session = RiiConversationTests.session

    def setUp(self):
        RiiConversationTests.setUp(self)
        self.fresco_definition = {
            "d": 5163,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjU": 0,
            "getDuration": 0,
            "cjJ": [{"d": value} for value in (10628, 10629, 10630)],
        }
        self.db.execute.side_effect = lambda sql, args: Mock(
            fetchone=Mock(
                return_value={
                    "data": {
                        "native": self.fresco_definition
                        if args[0] == 5163
                        else self.definition
                    }
                }
            )
        )

    def test_fresco_branch_activates_and_persists_only_once(self):
        row = self.spec()[1][0]
        edges = [(5772, 13288), (5773, 13289), (5774, 13307), (5775, 13295)]
        character, session, request = self.session(row, edges)
        with patch.object(npc_world, "load_scene", return_value=[row]):
            result = fresco.choose(self.store, 2, 1, character, session, request)
        self.assertEqual(result["packet"], (12218, struct.pack(">i", 5781)))
        self.assertIn(5163, self.state["running"])
        self.assertIn(5163, self.state["tracking"])
        self.assertIn(10613, self.state["objectives"])
        self.assertIn(13312, [code for code, _ in result["packets"]])
        session.choose(5781, 13303)
        with patch.object(npc_world, "load_scene", return_value=[row]):
            result = fresco.choose(self.store, 2, 1, character, session, request)
        self.assertEqual(result["packets"], [])
        self.assertEqual(self.state["running"].count(5163), 1)

    def test_failed_receipt_rolls_back_dialogue(self):
        row = self.spec()[1][0]
        character, session, request = self.session(
            row, [(5772, 13288), (5773, 13289), (5774, 13307), (5775, 13295)]
        )
        with patch.object(npc_world, "load_scene", return_value=[row]), patch.object(
            fresco.storage, "record_event", return_value=False
        ):
            with self.assertRaises(ValueError):
                fresco.choose(self.store, 2, 1, character, session, request)
        self.assertEqual(session.node_id, 5775)
        self.assertNotIn(5163, self.state["running"])

    def test_captured_intro_can_close_without_starting_fresco_mission(self):
        row = self.spec()[1][0]
        character, session, request = self.session(
            row, [(5772, 13288), (5773, 13289), (5774, 13290)]
        )
        self.assertFalse(fresco.recognizes(session, request))
        self.assertEqual(session.choose(**request), (12218, struct.pack(">i", 0)))
        self.assertNotIn(5163, self.state["running"])

    def test_journal_recovers_original_acceptance_date(self):
        from wakfu_server.achievements import service

        class Db:
            def execute(self, query, args):
                self.args = args
                return self

            def fetchall(self):
                return []

            def fetchone(self):
                if self.args == (1, "rii-fresco-activation:5163"):
                    return {"payload": {"accepted_at_ms": 1234567}}
                return None

        state = dict(self.state, running=[5163], tracking=[5163])
        with patch.object(service.wire, "section") as section:
            service._journal_section(Db(), state, {}, 1)
        self.assertEqual(section.call_args.kwargs["activation_dates"], {5163: 1234567})
