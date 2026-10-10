"""Native account EMOTES and occupation packet layouts."""
import struct
import time
import unittest
from unittest.mock import Mock
from wakfu_server.characters import emotes


class EmoteWireTests(unittest.TestCase):
    def test_ordinary_occupation_contains_exact_native_emote(self):
        opcode, body = emotes.occupation(7, 20001)
        self.assertEqual(12088, opcode)
        self.assertEqual(struct.pack('>BhqIiB', 1, 20, 7, 5, 20001, 0), body)

    def test_targeted_occupation_has_native_parameter_name_and_long(self):
        _, body = emotes.occupation(7, 20060, [('targetId', 8)])
        self.assertEqual((1, 20, 7, 25), struct.unpack('>BhqI', body[:15]))
        self.assertEqual(struct.pack('>iBI', 20060, 1, 8) + b'targetId' + struct.pack('>q', 8), body[15:])

    def test_malformed_play_never_queries_knowledge(self):
        for body in (b'', b'\0' * 11, b'\0' * 13, 'invalid'):
            db = Mock()
            with self.assertRaises(ValueError):
                emotes.authorize(db, 1, body)
            db.execute.assert_not_called()

    def test_retained_animation_expires_and_native_stop_has_no_payload(self):
        packet = emotes.occupation(7, 20001)
        self.assertEqual((packet,), emotes.retained({'_emote_until': time.monotonic()+10,
                                                   '_emote_packet': packet}))
        self.assertEqual((), emotes.retained({'_emote_until': 0, '_emote_packet': packet}))
        self.assertEqual((12088, struct.pack('>BhqI', 2, 20, 7, 0)), emotes.stopped(7))

    def test_default_snapshot_is_view_without_knowledge_insert(self):
        db = Mock()
        db.execute.side_effect = [Mock(fetchone=lambda: {'value': {'unlock_all': True}}),
                                  [{'emote_id': 20001}, {'emote_id': 20060}]]
        opcode, payload = emotes.snapshot(db, 1)
        self.assertEqual(13873, opcode)
        self.assertEqual((1, 10, len(payload)-12), struct.unpack('>III', payload[:12]))
        self.assertTrue(all(not call.args[0].startswith('INSERT') for call in db.execute.call_args_list))
