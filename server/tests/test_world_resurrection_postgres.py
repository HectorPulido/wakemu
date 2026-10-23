"""Atomic native BenKO interaction against trusted live company positions."""

import struct
import unittest
import uuid

from postgres_case import PostgresCase
from wakfu_server.heroes import add as add_hero
from wakfu_server.inventory_items import grant
from wakfu_server.world_resurrection import resurrect, snapshot


class WorldResurrectionPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "benko-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        self.main = self.store.create_character(self.account, "BenKO Main")
        self.hero = self.store.create_character(self.account, "BenKO Target")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.main["id"])
        add_hero(
            self.store, self.account, self.generation, self.main["id"], self.hero["id"]
        )
        self.container = next(
            row["uid"]
            for row in self.store.character(self.account, self.main["id"])[
                "inventory_containers"
            ]
            if row["kind"] == 0
        )

    def kill_hero(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=0,max_hp=100,hp_damage=250,health_dead=TRUE "
                "WHERE id=%s",
                (self.hero["id"],),
            )
        return self.store.character(self.account, self.hero["id"])

    def locations(self, *, distance=1, target_generation=None):
        return {
            self.main["id"]: {
                "generation": self.generation,
                "map_id": 1134,
                "instance_id": 900,
                "x": 10,
                "y": 10,
                "z": -1,
            },
            self.hero["id"]: {
                "generation": target_generation or self.generation,
                "map_id": 1134,
                "instance_id": 900,
                "x": 10 + distance,
                "y": 10,
                "z": 2,
            },
        }

    def grant_benkos(self, quantity=2):
        return grant(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            reference=9247,
            quantity=quantity,
            container=self.container,
            slot=0,
            allowed_references={9247},
        )

    def quantity(self):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE character_id=%s AND reference=9247",
                (self.main["id"],),
            ).fetchone()
        return 0 if row is None else row["quantity"]

    def test_company_resurrection_checks_live_range_then_consumes_once(self):
        self.grant_benkos()
        dead = self.kill_hero()
        self.assertEqual([12088], [opcode for opcode, _ in snapshot(self.store, dead)])

        with self.assertRaisesRegex(ValueError, "next to"):
            resurrect(
                self.store,
                self.account,
                self.generation,
                self.main["id"],
                struct.pack(">q", self.hero["id"]),
                target_generation=self.generation,
                live_locations=self.locations(distance=2),
            )
        self.assertEqual(2, self.quantity())

        result = resurrect(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            struct.pack(">q", self.hero["id"]),
            target_generation=self.generation,
            live_locations=self.locations(distance=1),
        )
        self.assertEqual(
            (1, 99, False),
            tuple(result["target"][key] for key in ("hp", "hp_damage", "health_dead")),
        )
        self.assertEqual(1, self.quantity())
        self.assertEqual([12088], [opcode for opcode, _ in result["world_packets"]])
        self.assertEqual(
            (2, 4, self.hero["id"], 0),
            struct.unpack(">BhqI", result["world_packets"][0][1]),
        )
        self.assertEqual([], snapshot(self.store, result["target"]))
        with self.assertRaisesRegex(ValueError, "already alive"):
            resurrect(
                self.store,
                self.account,
                self.generation,
                self.main["id"],
                struct.pack(">q", self.hero["id"]),
                target_generation=self.generation,
                live_locations=self.locations(distance=1),
            )
        self.assertEqual(1, self.quantity())

    def test_wrong_target_generation_and_foreign_live_identity_do_not_consume(self):
        self.grant_benkos()
        self.kill_hero()
        with self.assertRaisesRegex(ValueError, "position fence"):
            resurrect(
                self.store,
                self.account,
                self.generation,
                self.main["id"],
                struct.pack(">q", self.hero["id"]),
                target_generation="stale",
                live_locations=self.locations(),
            )
        foreign_account = self.store.register(
            "foreign-benk-" + uuid.uuid4().hex[:8], "local-password"
        )["id"]
        foreign = self.store.create_character(foreign_account, "Foreign Death")
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=0,max_hp=100,hp_damage=250,health_dead=TRUE "
                "WHERE id=%s",
                (foreign["id"],),
            )
        locations = self.locations()
        locations[foreign["id"]] = dict(locations[self.hero["id"]])
        with self.assertRaisesRegex(ValueError, "left its loaded company"):
            resurrect(
                self.store,
                self.account,
                self.generation,
                self.main["id"],
                struct.pack(">q", foreign["id"]),
                target_generation=self.generation,
                live_locations=locations,
            )
        self.assertEqual(2, self.quantity())

    def test_self_resurrection_is_allowed_for_dead_selected_main(self):
        self.grant_benkos(quantity=1)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=0,max_hp=100,hp_damage=250,health_dead=TRUE "
                "WHERE id=%s",
                (self.main["id"],),
            )
        dead = self.store.character(self.account, self.main["id"])
        self.assertEqual([12088], [opcode for opcode, _ in snapshot(self.store, dead)])
        location = {
            self.main["id"]: {
                "generation": self.generation,
                "map_id": 1134,
                "instance_id": 900,
                "x": 10,
                "y": 10,
                "z": -1,
            },
        }
        result = resurrect(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            struct.pack(">q", self.main["id"]),
            target_generation=self.generation,
            live_locations=location,
        )
        self.assertEqual(
            (1, 99, False),
            tuple(result["target"][key] for key in ("hp", "hp_damage", "health_dead")),
        )
        self.assertEqual(0, self.quantity())
        self.assertEqual(
            (2, 4, self.main["id"], 0),
            struct.unpack(">BhqI", result["world_packets"][0][1]),
        )


if __name__ == "__main__":
    unittest.main()
