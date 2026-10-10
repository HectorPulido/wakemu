"""Malformed private exit requests fail before any database or catalog reads."""
import struct
import unittest
from unittest.mock import Mock
from wakfu_server.rift_exit import _exit


class RiftExitWireTests(unittest.TestCase):
    def test_malformed_body_and_mode_reject_before_store_use(self):
        store = Mock()
        for body in (
            b"",
            b"\0" * 16,
            "not bytes",
            struct.pack(">qiBi", 1, 2, 1, 2),
            struct.pack(">qiBi", 1, 2, 0, 1),
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                _exit(
                    store,
                    1,
                    "gen",
                    2,
                    body,
                    allowed_accounts={1},
                    source_allowed=lambda *a: True,
                    fighting=lambda *a: False,
                )
        store.connection.assert_not_called()
