"""Completed Rift interior: hero loot through the selected main's session."""
import struct

from test_temporary_inventory_heroes import TemporaryInventoryHeroTests
from wakfu_server import combat_drop_delivery, temporary_recycling, rift_runtime


class RiftInteriorHeroLootTests(TemporaryInventoryHeroTests):
    def test_main_session_claim_bulk_recycle_inside_completed_rift_with_free_bag(self):
        main_id = self.main["character"]["id"]
        hero_id = self.hero["character"]["id"]
        self.assertNotEqual(main_id, hero_id)
        # Same real Rift entry and completed-interior setup as the existing
        # selected-hero HTTP shop regression; do not switch the session owner.
        with self.store.connection() as db:
            run = rift_runtime.enter(
                db,
                3,
                main_id,
                [main_id, hero_id],
                seed="hero-interior-loot",
                authorize=lambda *_: True,
            )
            db.execute(
                "UPDATE rift_instances SET status='lost',ended_at=CURRENT_TIMESTAMP "
                "WHERE instance_id=%s",
                (run["instance_id"],),
            )
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s WHERE id=ANY(%s)",
                (run["catalog"]["map_id"], run["instance_id"], [main_id, hero_id]),
            )
            initial_run = db.execute(
                "SELECT * FROM rift_instances WHERE instance_id=%s",
                (run["instance_id"],),
            ).fetchone()
            initial_main = db.execute(
                "SELECT uid,reference,quantity,container,slot FROM inventory_items "
                "WHERE character_id=%s ORDER BY uid",
                (main_id,),
            ).fetchall()
            bag = db.execute(
                "SELECT uid,capacity FROM inventory_containers "
                "WHERE character_id=%s AND kind=0",
                (hero_id,),
            ).fetchone()
            occupied = db.execute(
                "SELECT count(*) AS n FROM inventory_items "
                "WHERE character_id=%s AND container=%s",
                (hero_id, bag["uid"]),
            ).fetchone()["n"]
            self.assertGreaterEqual(bag["capacity"] - occupied, 3)

        def assert_interior_and_owner():
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT character_id FROM sessions WHERE account_id=%s",
                        (self.main["account"],),
                    ).fetchone()["character_id"],
                    main_id,
                )
                positions = db.execute(
                    "SELECT id,map_id,instance_id FROM characters "
                    "WHERE id=ANY(%s) ORDER BY id",
                    ([main_id, hero_id],),
                ).fetchall()
                self.assertEqual(len(positions), 2)
                self.assertTrue(
                    all(
                        row["map_id"] == run["catalog"]["map_id"]
                        and row["instance_id"] == run["instance_id"]
                        for row in positions
                    )
                )
                self.assertEqual(
                    db.execute(
                        "SELECT * FROM rift_instances WHERE instance_id=%s",
                        (run["instance_id"],),
                    ).fetchone(),
                    initial_run,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT uid,reference,quantity,container,slot FROM inventory_items "
                        "WHERE character_id=%s ORDER BY uid",
                        (main_id,),
                    ).fetchall(),
                    initial_main,
                )

        assert_interior_and_owner()
        # Existing native drop fixture supplies real finished-award provenance;
        # all three inventory actions execute while both owners stay inside.
        claimed_uid = self._temporary_item(self.hero)
        bulk_uid = self._temporary_item(self.hero)
        recycled_uid = self._temporary_item(self.hero, quantity=50)
        cases = (
            (
                combat_drop_delivery.claim,
                self.claim_body(self.hero, claimed_uid),
                {},
                claimed_uid,
            ),
            (
                combat_drop_delivery.bulk_transfer,
                self.bulk_body(self.hero, bulk_uid),
                {},
                bulk_uid,
            ),
            (
                temporary_recycling.recycle,
                temporary_recycling.request(hero_id, [recycled_uid])[1],
                {"rng": lambda: 0.0},
                recycled_uid,
            ),
        )
        for operation, body, options, uid in cases:
            with self.subTest(operation=operation.__name__):
                result = self.call(operation, body, **options)
                self.assertTrue(result["applied"])
                if operation is combat_drop_delivery.bulk_transfer:
                    self.assertEqual(result["source"]["id"], hero_id)
                    self.assertEqual(result["destination"]["id"], hero_id)
                else:
                    self.assertEqual(result["character"]["id"], hero_id)
                updates = [
                    payload for opcode, payload in result["packets"] if opcode == 12691
                ]
                self.assertTrue(updates)
                self.assertTrue(
                    all(
                        struct.unpack_from(">q", payload)[0] == hero_id
                        for payload in updates
                    )
                )
                with self.store.connection() as db:
                    self.assertIsNone(
                        db.execute(
                            "SELECT uid FROM temporary_combat_items WHERE uid=%s",
                            (uid,),
                        ).fetchone()
                    )
                    first_inventory = db.execute(
                        "SELECT uid,reference,quantity,container,slot FROM inventory_items "
                        "WHERE character_id=%s ORDER BY uid",
                        (hero_id,),
                    ).fetchall()
                self.assertFalse(self.call(operation, body, **options)["applied"])
                with self.store.connection() as db:
                    self.assertEqual(
                        db.execute(
                            "SELECT uid,reference,quantity,container,slot FROM inventory_items "
                            "WHERE character_id=%s ORDER BY uid",
                            (hero_id,),
                        ).fetchall(),
                        first_inventory,
                    )
                assert_interior_and_owner()
