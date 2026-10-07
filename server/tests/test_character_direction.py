from postgres_case import PostgresCase
from psycopg.errors import CheckViolation
from wakfu_server.native_transports import bootstrap


class CharacterDirectionTests(PostgresCase):
    def setUp(self):
        super().setUp()
        from unittest.mock import patch

        self.account_id = self.store.register("direction-owner", "test-password")["id"]
        with patch("wakfu_server.breed_resources.playable_breeds", return_value={15}):
            self.character = self.store.create_character(
                self.account_id, "Direction Owner"
            )

    def test_direction_defaults_and_survives_store_reopen_for_all_eight_values(self):
        self.assertEqual(3, self.character["direction"])
        for direction in range(8):
            with self.subTest(direction=direction):
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE characters SET direction=%s WHERE id=%s AND account_id=%s",
                        (direction, self.character["id"], self.account_id),
                    )
                reopened = self.reopen()
                loaded = reopened.character(self.account_id, self.character["id"])
                self.assertEqual(direction, loaded["direction"])
                packets = bootstrap(loaded)
                entity_len = int.from_bytes(packets[1][1][:2], "big")
                entity = packets[1][1][2 : 2 + entity_len]
                self.assertEqual(direction, entity[36])

    def test_database_rejects_direction_outside_native_unsigned_byte(self):
        for direction in (-1, 8):
            with self.subTest(direction=direction), self.assertRaises(CheckViolation):
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE characters SET direction=%s WHERE id=%s",
                        (direction, self.character["id"]),
                    )

    def test_character_selection_attaches_persisted_direction_to_position_buffer(self):
        from unittest.mock import patch
        from wakfu_server.position_buffer import Positions

        account = self.store.register("direction-selection", "test-password")["id"]
        # The runtime image under test may omit the optional presentation catalog;
        # keep this regression focused on persisted selection and position attach.
        with patch("wakfu_server.breed_resources.playable_breeds", return_value={15}):
            character = self.store.create_character(account, "Selected Direction")
        generation = self.store.begin_session(account)
        selected = self.store.select_character(account, generation, character["id"])
        self.assertEqual(selected["direction"], 3)
        key = (account, generation, character["id"])
        positions = Positions(self.store, lease_active=lambda *lease: lease == key)
        attached = positions.attach(account, generation, selected)
        self.assertEqual(attached["direction"], 3)


class WorldOrientationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account_id = self.store.register("orientation-owner", "test-password")[
            "id"
        ]
        self.character = self.store.create_character(
            self.account_id, "Orientation Owner"
        )
        self.generation = self.store.begin_session(self.account_id)
        self.store.select_character(
            self.account_id, self.generation, self.character["id"]
        )

    def test_native_packet_all_directions_and_strict_integer_domain(self):
        from wakfu_server.world_orientation import packet

        for direction in range(8):
            with self.subTest(direction=direction):
                self.assertEqual(
                    (
                        12401,
                        self.character["id"].to_bytes(8, "big") + bytes([direction]),
                    ),
                    packet(self.character["id"], direction),
                )
        for direction in (True, -1, 8):
            with self.subTest(direction=direction), self.assertRaises(ValueError):
                packet(self.character["id"], direction)

    def test_save_uses_selected_lease_and_persists_direction_for_bootstrap(self):
        from wakfu_server.world_orientation import packet, save

        for direction in range(8):
            saved = save(
                self.store,
                self.account_id,
                self.generation,
                self.character["id"],
                direction,
            )
            self.assertEqual(packet(self.character["id"], direction), saved["packet"])
            loaded = self.store.character(self.account_id, self.character["id"])
            self.assertEqual(direction, loaded["direction"])
            packets = bootstrap(loaded)
            entity_len = int.from_bytes(packets[1][1][:2], "big")
            entity = packets[1][1][2 : 2 + entity_len]
            self.assertEqual(direction, entity[36])
        with self.assertRaises(ValueError):
            save(
                self.store, self.account_id, self.generation, self.character["id"], True
            )

    def test_stale_and_foreign_account_leases_cannot_change_direction(self):
        from wakfu_server.world_orientation import save

        foreign = self.store.register("orientation-foreign", "test-password")["id"]
        with self.assertRaises(ValueError):
            save(self.store, foreign, self.generation, self.character["id"], 6)
        with self.assertRaises(ValueError):
            save(
                self.store, self.account_id, "stale-generation", self.character["id"], 6
            )
        self.assertEqual(
            3, self.store.character(self.account_id, self.character["id"])["direction"]
        )

    def test_outside_guard_rejects_placement_or_active_fight_without_mutation(self):
        from wakfu_server.world_orientation import save

        for status in ("placement", "active"):
            with self.subTest(status=status):
                with self.store.connection() as db:
                    fight_id = db.execute(
                        "INSERT INTO combat_fights(status) VALUES(%s) RETURNING id",
                        (status,),
                    ).fetchone()["id"]
                    db.execute(
                        "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                        "VALUES(%s,%s,%s,0)",
                        (fight_id, self.character["id"], self.account_id),
                    )
                with self.assertRaisesRegex(ValueError, "outside actor"):
                    save(
                        self.store,
                        self.account_id,
                        self.generation,
                        self.character["id"],
                        7,
                        outside=True,
                    )
                self.assertEqual(
                    3,
                    self.store.character(self.account_id, self.character["id"])[
                        "direction"
                    ],
                )
                with self.store.connection() as db:
                    db.execute(
                        "UPDATE combat_fights SET status='finished' WHERE id=%s",
                        (fight_id,),
                    )
