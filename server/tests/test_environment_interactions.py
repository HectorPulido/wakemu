import struct
import unittest

from postgres_case import PostgresCase
from wakfu_server import environment_interactions as interactions


class EnvironmentRequestTests(unittest.TestCase):
    def test_native_action_and_state_preserve_flags(self):
        self.assertEqual(interactions.request(struct.pack(">qHH", 25457, 0, 0)), 25457)
        for body in (
            b"",
            struct.pack(">qHH", 25457, 82, 0),
            struct.pack(">qHH", 25457, 0, 1),
        ):
            with self.assertRaises(ValueError):
                interactions.request(body)
        original = bytes.fromhex("0102000000060200001234567890")
        opcode, payload = interactions._packet(
            {"object_id": 9, "state_payload_hex": original.hex()}, 1
        )
        self.assertEqual(opcode, 12344)
        self.assertEqual(payload[10:], original[:7] + b"\x00\x01" + original[9:])


class EnvironmentAuthorityTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.clock = [1000.0]
        self.store.clock = lambda: self.clock[0]
        self.account = self.store.register("environment-owner", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Environment Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.place(25457, 1134)

    def place(self, object_id, map_id):
        self.rule = interactions.definition(self.store, map_id, object_id)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                (
                    map_id,
                    self.rule["x"],
                    self.rule["y"],
                    self.rule["z"],
                    self.character["id"],
                ),
            )
        self.character = self.store.character(self.account, self.character["id"])
        self.body = struct.pack(">qHH", object_id, 0, 0)

    def test_well_timer_replay_and_stationary_exactly_once_reward(self):
        ticket = interactions.begin(
            self.store, self.account, self.generation, self.character, self.body
        )
        replay = interactions.begin(
            self.store, self.account, self.generation, self.character, self.body
        )
        self.assertEqual(ticket["token"], replay["token"])
        with self.assertRaises(ValueError):
            interactions.complete(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                ticket["token"],
                location=self.character,
            )
        self.clock[0] += 2
        moved = dict(self.character, x=self.character["x"] + 1)
        with self.assertRaises(ValueError):
            interactions.complete(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                ticket["token"],
                location=moved,
            )
        result = interactions.complete(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            ticket["token"],
            location=self.character,
        )
        self.assertEqual(len(result["packets"]), 1)
        water = [
            item
            for item in result["character"]["inventory_items"]
            if item["reference"] == 2340
        ]
        self.assertEqual(sum(item["quantity"] for item in water), 100)
        again = interactions.complete(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            ticket["token"],
            location=self.character,
        )
        self.assertTrue(again["replay"])
        self.assertEqual(again["packets"], [])
        with self.store.connection() as db:
            row = db.execute(
                "SELECT state FROM environment_interaction_tickets WHERE token=%s",
                (ticket["token"],),
            ).fetchone()
        self.assertEqual(row["state"], "completed")

    def test_cancel_and_authoritative_hero_guard(self):
        ticket = interactions.begin(
            self.store, self.account, self.generation, self.character, self.body
        )
        interactions.cancel(
            self.store, self.account, self.generation, self.character["id"]
        )
        self.clock[0] += 3
        with self.assertRaises(ValueError):
            interactions.complete(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                ticket["token"],
                location=self.character,
            )
        self.place(31111, 1135)
        for hero in (None, True, 0):
            with self.assertRaises(ValueError):
                interactions.begin(
                    self.store,
                    self.account,
                    self.generation,
                    self.character,
                    self.body,
                    is_hero=hero,
                )
        ticket = interactions.begin(
            self.store,
            self.account,
            self.generation,
            self.character,
            self.body,
            is_hero=False,
        )
        self.clock[0] += 3
        with self.assertRaises(ValueError):
            interactions.complete(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                ticket["token"],
                location=self.character,
                is_hero=True,
            )
        self.assertFalse(
            interactions.complete(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                ticket["token"],
                location=self.character,
                is_hero=False,
            )["replay"]
        )

    def test_new_session_replaces_stale_ticket_and_invalidates_old_completion(self):
        old = interactions.begin(
            self.store, self.account, self.generation, self.character, self.body
        )
        previous = self.generation
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        fresh = interactions.begin(
            self.store, self.account, self.generation, self.character, self.body
        )
        self.assertNotEqual(old["token"], fresh["token"])
        self.clock[0] += 2
        with self.assertRaises(ValueError):
            interactions.complete(
                self.store,
                self.account,
                previous,
                self.character["id"],
                old["token"],
                location=self.character,
            )
        self.assertFalse(
            interactions.complete(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                fresh["token"],
                location=self.character,
            )["replay"]
        )

    def test_light_persistent_overlay_and_native_timeout(self):
        with self.store.connection() as db:
            light = db.execute(
                "SELECT * FROM environment_interaction_definitions WHERE kind='light' AND on_timeout_ms>0 LIMIT 1"
            ).fetchone()
        self.place(light["object_id"], light["map_id"])
        first = interactions.toggle(
            self.store, self.account, self.generation, self.character, self.body
        )
        second = interactions.toggle(
            self.store, self.account, self.generation, self.character, self.body
        )
        self.assertEqual(first["state"], 0)
        self.assertEqual(second["state"], 1)
        self.assertIn(
            second["packets"][0], interactions.snapshots(self.store, light["map_id"])
        )
        self.clock[0] += 180
        packets = interactions.snapshots(self.store, light["map_id"])
        self.assertIn(interactions._packet(light, 0), packets)
        self.assertEqual(packets, interactions.snapshots(self.store, light["map_id"]))
