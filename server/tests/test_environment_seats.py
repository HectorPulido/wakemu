import struct
import unittest
from postgres_case import PostgresCase
from wakfu_server import environment_seats as seats, world_static


class SeatWireTests(unittest.TestCase):
    def test_native_occupation_and_occupancy(self):
        self.assertEqual(seats.request(struct.pack(">qHH", 123, 6, 0)), (123, 6))
        self.assertEqual(
            seats.occupancy(123, 456),
            (
                12344,
                struct.pack(">qH", 123, 15)
                + bytes.fromhex("01030000000603")
                + struct.pack(">q", 456),
            ),
        )
        self.assertEqual(seats.stop(456), (12088, struct.pack(">Bhqi", 3, 16, 456, 0)))
        for body in (
            b"",
            struct.pack(">qHH", 123, 0, 0),
            struct.pack(">qHH", 123, 6, 1),
        ):
            with self.assertRaises(ValueError):
                seats.request(body)


class SeatAuthorityTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("seat-owner", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Seat Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        with self.store.connection() as db:
            allowed = {
                r["object_id"]
                for r in db.execute(
                    "SELECT object_id FROM environment_seat_definitions WHERE map_id=1134"
                ).fetchall()
            }
        self.rule = next(r for r in world_static.objects(1134) if r["id"] in allowed)
        self.character.update(map_id=1134, instance_id=0)
        self.body = struct.pack(">qHH", self.rule["id"], 6, 0)

    def claim(self, **kwargs):
        return seats.sit(
            self.store,
            self.account,
            self.generation,
            self.character,
            self.body,
            in_range=True,
            animation_verified=True,
            **kwargs
        )

    def test_claim_replay_release_and_stale_generation(self):
        result = self.claim()
        self.assertEqual(
            result["packets"][0],
            (13579, struct.pack(">Bhqq", 1, 16, self.rule["id"], self.character["id"])),
        )
        self.assertTrue(self.claim()["replay"])
        self.assertIn(
            seats.occupancy(self.rule["id"], self.character["id"]),
            seats.snapshots(self.store, 1134),
        )
        self.assertEqual(
            seats.release(self.store, self.account, "wrong", self.character["id"])[
                "packets"
            ],
            [],
        )
        self.assertIn(
            seats.occupancy(self.rule["id"], self.character["id"]),
            seats.snapshots(self.store, 1134),
        )
        release = seats.release(
            self.store, self.account, self.generation, self.character["id"]
        )
        self.assertEqual(
            release["scene_packets"], [seats.occupancy(self.rule["id"], 0)]
        )
        self.assertIn(
            seats.occupancy(self.rule["id"], 0), seats.snapshots(self.store, 1134)
        )
        self.claim()
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.assertFalse(self.claim()["replay"])

    def test_same_generation_actor_selection_clears_previous_seat(self):
        self.claim()
        other = self.store.create_character(self.account, "Seat Sibling")
        self.store.select_character(self.account, self.generation, other["id"])
        self.assertIn(
            seats.occupancy(self.rule["id"], 0), seats.snapshots(self.store, 1134)
        )

    def test_reject_range_occupation_and_foreign_claim(self):
        with self.assertRaises(ValueError):
            seats.sit(
                self.store,
                self.account,
                self.generation,
                self.character,
                self.body,
                in_range=False,
            )
        with self.assertRaises(ValueError):
            self.claim(blocked=True)
        self.claim()
        account = self.store.register("seat-other", "local-password")["id"]
        character = self.store.create_character(account, "Seat Other")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        character.update(map_id=1134, instance_id=0)
        with self.assertRaisesRegex(ValueError, "occupied"):
            seats.sit(
                self.store,
                account,
                generation,
                character,
                self.body,
                in_range=True,
                animation_verified=True,
            )

    def test_native_criteria_and_animation_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "animation"):
            seats.sit(
                self.store,
                self.account,
                self.generation,
                self.character,
                self.body,
                in_range=True,
            )
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM environment_seat_definitions WHERE map_id=%s AND object_id=%s",
                (1134, self.rule["id"]),
            )
        with self.assertRaisesRegex(ValueError, "criteria"):
            self.claim()
        self.assertEqual(
            seats.release(
                self.store, self.account, self.generation, self.character["id"]
            )["packets"],
            [],
        )


class SeatAnimationTests(unittest.TestCase):
    def test_certified_ordinary_class_models_and_fail_closed_appearance(self):
        from wakfu_server.environment_seat_animations import supported
        from wakfu_server.combat_character_copy_models import _models

        combinations = 0
        for breed in _models():
            for sex in (0, 1):
                for cloth in range(-128, 128):
                    actor = {
                        "breed": int(breed),
                        "appearance": {"sex": sex, "clothIndex": cloth},
                    }
                    self.assertTrue(
                        supported(actor, ordinary_actor=True), (breed, sex, cloth)
                    )
                    combinations += 1
        self.assertEqual(combinations, 9216)
        actor = {"breed": 1, "appearance": {"sex": 0, "clothIndex": 0}}
        self.assertFalse(supported(actor))
        self.assertFalse(supported(dict(actor, breed=999), ordinary_actor=True))
        self.assertFalse(
            supported(dict(actor, appearance={"sex": 2}), ordinary_actor=True)
        )
        self.assertFalse(supported(dict(actor, appearance=None), ordinary_actor=True))

    def test_equipment_appearance_override_is_not_qualified(self):
        from unittest.mock import patch
        from wakfu_server.environment_seat_animations import supported

        actor = {"breed": 1, "appearance": {"sex": 0, "clothIndex": 0}}
        with patch(
            "wakfu_server.environment_seat_animations.ENTITY_DEFAULTS",
            {"EQUIPMENT_APPEARANCE": b"\x01"},
        ):
            self.assertFalse(supported(actor, ordinary_actor=True))
        self.assertFalse(
            supported(
                dict(actor, appearance={"sex": 0, "modelOverride": 10}),
                ordinary_actor=True,
            )
        )
