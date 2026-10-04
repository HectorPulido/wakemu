import struct
import tempfile
import unittest
from pathlib import Path
from wakfu_server.store import Store
from wakfu_server.creation import create
from wakfu_server.wire import appearance_section


class CreationTests(unittest.TestCase):
    def test_protocol_creation_persistence_errors_and_session_ownership(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "world.db")
            account = store.register("creator", "creation-password")["id"]
            generation = store.begin_session(account)

            def request(name, character_id=-1):
                encoded = name.encode()
                return (
                    struct.pack(">qhB", character_id, 2, len(encoded))
                    + encoded
                    + b"\x01"
                    + appearance_section(
                        {"skinColor": -1, "sex": 0, "faceIndex": 3, "clothIndex": 0}
                    )
                )

            status, char = create(store, account, generation, request("Fresh"))
            self.assertEqual(status, 0)
            self.assertEqual(char["appearance"]["skinColor"], -1)
            self.assertEqual(
                create(store, account, generation, request("Fresh")), (102, None)
            )
            self.assertEqual(
                create(store, account, generation, request("12")), (103, None)
            )
            self.assertEqual(
                create(store, account, generation, request("Modify", char["id"])),
                (101, None),
            )
            for name in ("Second", "Third", "Fourth", "Fifth"):
                self.assertEqual(
                    create(store, account, generation, request(name))[0], 0
                )
            self.assertEqual(
                create(store, account, generation, request("Sixth")), (104, None)
            )
            store.begin_session(account)
            with self.assertRaises(ValueError):
                create(store, account, generation, request("Stale"))
