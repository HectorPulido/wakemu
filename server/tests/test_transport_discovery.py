import unittest, struct
from postgres_case import PostgresCase
from wakfu_server.transport_discovery import (
    Discoveries,
    account_packet,
    discovery_packet,
)


class DiscoveryTests(PostgresCase):
    def test_account_scope_persistence_dedup_and_stale_session(self):
        store = self.store
        a = store.register("one", "local-pass")["id"]
        b = store.register("two", "local-pass")["id"]
        g = store.begin_session(a)
        d = Discoveries(store)
        self.assertTrue(d.discover(a, g, 1, 123))
        self.assertFalse(d.discover(a, g, 1, 123))
        self.assertTrue(d.discover(a, g, 2, 456))
        self.assertEqual(Discoveries(store).known(a), {1: (123,), 2: (456,)})
        self.assertEqual(d.known(b), {1: (), 2: ()})
        store.begin_session(a)
        with self.assertRaises(ValueError):
            d.discover(a, g, 1, 789)

    def test_exact_native_incremental_and_section_envelope(self):
        self.assertEqual(discovery_packet(1, 123), (12674, b"\0\0\0{\1"))
        opcode, raw = account_packet({1: [123], 2: [456]})
        self.assertEqual(opcode, 13873)
        self.assertEqual(struct.unpack(">iii", raw[:12]), (1, 12, len(raw) - 12))
        self.assertEqual(raw[12:], bytes.fromhex("0a05080210c8030a040801107b"))
        with self.assertRaises(ValueError):
            account_packet({1: [-1]})

    def test_local_drago_availability_is_sent_and_excludes_unroutable_entry(self):
        from wakfu_server.transport_discovery import local_policy, known_all

        saved = {1: (), 2: (31333,)}
        projected = local_policy(saved, all_zaaps=True, all_dragos=True)
        self.assertEqual(saved, {1: (), 2: (31333,)})
        self.assertEqual(len(projected[1]), 45)
        self.assertEqual(len(projected[2]), 120)
        self.assertIn(31334, projected[2])
        self.assertNotIn(4412, projected[2])
        self.assertNotEqual(account_packet(saved), account_packet(projected))
        self.assertEqual(local_policy(saved, all_zaaps=True)[2], (31333,))
        self.assertEqual(known_all(include_dragos=True), projected)
