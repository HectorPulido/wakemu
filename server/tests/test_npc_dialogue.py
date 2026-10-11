import struct
import unittest
from wakfu_server.maps.npc_dialogue import DialogueSession, decode_request


class NpcDialogueTests(unittest.TestCase):
    def setUp(self):
        self.nodes = {
            1: {"id": 1, "criteria": "", "choices": [{"id": 5, "criteria": ""}]},
            2: {"id": 2, "criteria": "", "choices": []},
        }

    def test_native_open_and_choice_layout(self):
        session = DialogueSession(self.nodes, {(1, 5): 2})
        opcode, body = session.open(1, 100, lambda speaker, node: speaker == 100)
        self.assertEqual(opcode, 12969)
        self.assertEqual(
            decode_request(12535, body),
            {"node_id": 1, "speaker_type": 2, "speaker_id": 100},
        )
        self.assertEqual(session.choose(1, 5), (12218, struct.pack(">i", 2)))
        self.assertIsNone(session.choose(2, -1))
        self.assertIsNone(session.node_id)

    def test_rejects_spoofed_speaker_stale_and_unknown_choices(self):
        session = DialogueSession(self.nodes, {(1, 5): 2})
        with self.assertRaises(ValueError):
            session.open(1, 100, lambda *_: False)
        session.open(1, 100, lambda *_: True)
        for node, choice in [(2, 5), (1, 99), (1, -1)]:
            with self.assertRaises(ValueError):
                session.choose(node, choice)
        self.assertEqual(session.node_id, 1)

    def test_never_infers_native_graph_or_ignores_criteria(self):
        session = DialogueSession(self.nodes)
        session.open(1, 100, lambda *_: True)
        with self.assertRaises(ValueError):
            session.choose(1, 5)
        self.nodes[2]["criteria"] = "SERVER_QUEST_FLAG"
        session.graph[(1, 5)] = 2
        with self.assertRaises(ValueError):
            session.choose(1, 5)
        self.assertEqual(session.node_id, 1)

    def test_rejects_malformed_requests(self):
        for opcode, body in [(12535, b""), (12058, bytes(9)), (0, bytes(8))]:
            with self.assertRaises(ValueError):
                decode_request(opcode, body)
