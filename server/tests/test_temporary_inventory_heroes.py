"""Temporary loot uses the selected main's lease for its actual loaded owner."""
import struct

from postgres_case import PostgresCase
import test_temporary_recycling as recycling_fixture
from wakfu_server import (
    combat_drop_delivery,
    temporary_recycling,
    recycling,
    recycling_wire,
)
from wakfu_server.characters import heroes


class TemporaryInventoryHeroTests(PostgresCase):
    _player = recycling_fixture.TemporaryRecyclingTests._player
    _temporary_item = recycling_fixture.TemporaryRecyclingTests._temporary_item

    def setUp(self):
        super().setUp()
        self.main = self._player("temp-hero-main")
        character = self.store.create_character(self.main["account"], "Temporary Hero")
        heroes.add(
            self.store,
            self.main["account"],
            self.main["generation"],
            self.main["character"]["id"],
            character["id"],
        )
        self.hero = dict(self.main, character=character)

    def call(self, operation, body, **kwargs):
        return operation(
            self.store,
            self.main["account"],
            self.main["generation"],
            self.main["character"]["id"],
            body,
            **kwargs,
        )

    def bag(self, owner):
        return next(
            row
            for row in owner["character"]["inventory_containers"]
            if row["kind"] == 0
        )

    def bulk_body(self, owner, uid, destination=None):
        identity = owner["character"]["id"]
        return struct.pack(">qqhq", identity, destination or identity, 1, uid)

    def claim_body(self, owner, uid):
        return struct.pack(">qhbqh", uid, 1, -1, self.bag(owner)["uid"], -1)

    def test_active_hero_claim_get_all_recycle_and_replay_preserve_main(self):
        hero_id = self.hero["character"]["id"]
        uid = self._temporary_item(self.hero)
        body = self.claim_body(self.hero, uid)
        claimed = self.call(combat_drop_delivery.claim, body)
        self.assertEqual(claimed["character"]["id"], hero_id)
        self.assertTrue(claimed["applied"])
        self.assertFalse(self.call(combat_drop_delivery.claim, body)["applied"])
        uid = self._temporary_item(self.hero)
        body = self.bulk_body(self.hero, uid)
        transferred = self.call(combat_drop_delivery.bulk_transfer, body)
        self.assertEqual(transferred["source"]["id"], hero_id)
        self.assertEqual(transferred["destination"]["id"], hero_id)
        self.assertFalse(self.call(combat_drop_delivery.bulk_transfer, body)["applied"])
        uid = self._temporary_item(self.hero, quantity=50)
        _, body = temporary_recycling.request(hero_id, [uid])
        recycled = self.call(temporary_recycling.recycle, body, rng=lambda: 0.0)
        self.assertEqual(recycled["character"]["id"], hero_id)
        self.assertTrue(recycled["applied"])
        self.assertFalse(self.call(temporary_recycling.recycle, body)["applied"])
        for result in (claimed, transferred, recycled):
            updates = [body for opcode, body in result["packets"] if opcode == 12691]
            self.assertTrue(updates)
            self.assertTrue(
                all(struct.unpack_from(">q", body)[0] == hero_id for body in updates)
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT character_id FROM sessions WHERE account_id=%s",
                    (self.main["account"],),
                ).fetchone()["character_id"],
                self.main["character"]["id"],
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE character_id=%s",
                    (self.main["character"]["id"],),
                ).fetchone()["n"],
                0,
            )

    def test_inactive_foreign_and_wrong_bag_requests_keep_temporary_sources(self):
        inactive = dict(
            self.main,
            character=self.store.create_character(
                self.main["account"], "Temporary Inactive"
            ),
        )
        foreign = self._player("temp-hero-foreign")
        for owner in (inactive, foreign):
            uid = self._temporary_item(owner)
            bodies = (
                (combat_drop_delivery.claim, self.claim_body(owner, uid)),
                (combat_drop_delivery.bulk_transfer, self.bulk_body(owner, uid)),
                (
                    temporary_recycling.recycle,
                    temporary_recycling.request(owner["character"]["id"], [uid])[1],
                ),
            )
            for action, body in bodies:
                with self.subTest(
                    owner=owner["character"]["id"], action=action.__name__
                ):
                    with self.assertRaises(ValueError):
                        self.call(action, body)
            with self.store.connection() as db:
                self.assertIsNotNone(
                    db.execute(
                        "SELECT uid FROM temporary_combat_items WHERE uid=%s", (uid,)
                    ).fetchone()
                )
        uid = self._temporary_item(self.hero)
        for target in (self.main, foreign):
            with self.assertRaises(ValueError):
                self.call(combat_drop_delivery.claim, self.claim_body(target, uid))
        with self.assertRaises(ValueError):
            self.call(
                combat_drop_delivery.bulk_transfer,
                self.bulk_body(self.hero, uid, foreign["character"]["id"]),
            )
        with self.store.connection() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT uid FROM temporary_combat_items WHERE uid=%s", (uid,)
                ).fetchone()
            )

    def test_withdrawn_hero_can_recycle_while_other_fighters_remain_active(self):
        hero_id = self.hero["character"]["id"]
        uid = self._temporary_item(self.hero, quantity=50)
        body = temporary_recycling.request(hero_id, [uid])[1]
        inventory_uid = self._temporary_item(self.hero, quantity=50)
        self.call(combat_drop_delivery.claim, self.claim_body(self.hero, inventory_uid))
        with self.store.connection() as db:
            item_uid = db.execute(
                "SELECT uid FROM inventory_items WHERE character_id=%s AND reference=2021",
                (hero_id,),
            ).fetchone()["uid"]
        inventory_body = recycling_wire.request([item_uid])[1]
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                (fight_id, hero_id, self.main["account"], self.main["generation"]),
            )
        for action, request_body in (
            (temporary_recycling.recycle, body),
            (recycling.recycle, inventory_body),
        ):
            with self.assertRaisesRegex(ValueError, "during combat"):
                self.call(action, request_body)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_pve_withdrawals(fight_id,character_id,account_id,session_generation,created_at) VALUES(%s,%s,%s,%s,%s)",
                (
                    fight_id,
                    hero_id,
                    self.main["account"],
                    self.main["generation"],
                    self.store.now(),
                ),
            )
        self.assertTrue(
            self.call(temporary_recycling.recycle, body, rng=lambda: 0.0)["applied"]
        )
        self.assertTrue(
            self.call(recycling.recycle, inventory_body, rng=lambda: 0.0)["applied"]
        )
