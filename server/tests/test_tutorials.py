import struct, unittest
from postgres_case import PostgresCase
from wakfu_server import tutorials


class TutorialTests(PostgresCase):
    def test_account_state_survives_reconnect_without_inherited_ids(self):
        s = self.store
        a = s.register("tutorial", "password")["id"]
        g = s.begin_session(a)
        self.assertEqual(tutorials.payload(s, a), bytes.fromhex("0000000308bd01"))
        tutorials.update(s, a, g, struct.pack(">BIi", 1, 1, 201))
        self.assertEqual(
            tutorials.payload(self.reopen(), a),
            bytes.fromhex("0000000908bd0108c90110c901"),
        )
        tutorials.update(s, a, g, struct.pack(">BIi", 0, 1, 201))
        self.assertEqual(tutorials.payload(s, a), bytes.fromhex("0000000608bd0108c901"))
        s.begin_session(a)
        with self.assertRaises(ValueError):
            tutorials.update(s, a, g, struct.pack(">BIi", 1, 1, 202))
        self.assertEqual(tutorials.payload(s, a), bytes.fromhex("0000000608bd0108c901"))

    def test_malformed_requests_rejected(self):
        for body in (
            b"",
            struct.pack(">BI", 2, 0),
            struct.pack(">BIi", 1, 1, -1),
            struct.pack(">BI", 1, 1025),
        ):
            with self.assertRaises((ValueError, struct.error)):
                tutorials.decode(body)
