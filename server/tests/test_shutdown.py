import socket
import unittest
from wakfu_server.shutdown import Connections, SERVER_SHUTDOWN


class ShutdownTests(unittest.TestCase):
    def test_notice_precedes_eof_and_registry_seals(self):
        registry = Connections()
        sender, receiver = socket.socketpair()
        try:
            self.assertTrue(
                registry.register(
                    sender, lambda opcode, body: sender.sendall(bytes([opcode]) + body)
                )
            )
            self.assertEqual(len(registry.drain()), 1)
            self.assertEqual(receiver.recv(2), b"\x12\x10")
            self.assertEqual(receiver.recv(1), b"")
            self.assertFalse(registry.register(sender, lambda *args: None))
            self.assertEqual(registry.drain(), ())
        finally:
            sender.close()
            receiver.close()

    def test_failed_peer_does_not_skip_other_notices(self):
        class Peer:
            def shutdown(self, mode):
                events.append(("close", mode))

        events = []
        registry = Connections()
        first = Peer()
        second = Peer()

        def failed(*args):
            raise OSError("closed")

        registry.register(first, failed)
        registry.register(second, lambda *args: events.append(("notice", args)))
        result = registry.drain()
        self.assertEqual(result[0]["notice_error"], "OSError")
        self.assertEqual(events[0], ("notice", SERVER_SHUTDOWN))
        self.assertEqual(len(events), 3)
