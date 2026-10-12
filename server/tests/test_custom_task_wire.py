"""Original passive task-detail packet has strict UTF-8 byte boundaries."""
import unittest
from wakfu_server.achievements.custom_wire import task_detail


class CustomTaskWireTests(unittest.TestCase):
    def test_multilingual_text_has_exact_byte_length_and_passive_flags(self):
        message = "Misión: Árbol — 森林 🌱\nObjectif: 3/10"
        opcode, body = task_detail(message)
        encoded = message.encode("utf-8")
        self.assertEqual(opcode, 12963)
        self.assertEqual(body, b"\x00" + bytes([len(encoded)]) + encoded + b"\x01\x01")
        self.assertEqual(body[2:-2].decode("utf-8"), message)

    def test_ascii_255_bytes_accepted_256_rejected(self):
        self.assertEqual(task_detail("x" * 255)[1][1], 255)
        with self.assertRaises(ValueError):
            task_detail("x" * 256)

    def test_multibyte_limit_counts_bytes_instead_of_characters(self):
        self.assertEqual(task_detail("é" * 127 + "x")[1][1], 255)
        with self.assertRaises(ValueError):
            task_detail("é" * 128)
        self.assertEqual(task_detail("🌱" * 63 + "abc")[1][1], 255)
        with self.assertRaises(ValueError):
            task_detail("🌱" * 64)

    def test_empty_nul_and_nontext_are_rejected(self):
        for message in ("", "\x00", "before\x00after", None, b"text", 1, True, [], {}):
            with self.subTest(message=message), self.assertRaises(ValueError):
                task_detail(message)
