"""Original unusable32701 grants only its actual ordinary-bag character scope."""
from uuid import uuid4
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant
from wakfu_server.neo_regeneration import eligible, restore_canonical
from wakfu_server.native_world_context import battleground_worlds


class NeoCharacterPossessionTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("neo-character", "local-password")["id"]
        self.main = self.store.create_character(self.account, "Neo Personal Main")
        self.other = self.store.create_character(self.account, "Neo Personal Other")
        self.foreign_account = self.store.register(
            "neo-character-foreign", "local-password"
        )["id"]
        self.foreign = self.store.create_character(
            self.foreign_account, "Neo Personal Foreign"
        )
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.main["id"])
        self.bags = {c["kind"]: c for c in self.main["inventory_containers"]}
        self.item = grant(
            self.store,
            self.account,
            self.generation,
            self.main["id"],
            reference=32701,
            quantity=1,
            container=self.bags[0]["uid"],
            slot=0,
            allowed_references={32701},
        )

    def active(self, db, identity=None, account=None):
        return eligible(
            db,
            self.account if account is None else account,
            character_id=self.main["id"] if identity is None else identity,
            native_map_id=1134,
            is_neo_server=True,
        )

    def test_only_actual_owned_character_and_supported_ordinary_bags_qualify(self):
        with self.store.connection() as db:
            for bag in (self.bags[0], self.bags[1]):
                db.execute(
                    "UPDATE inventory_items SET container=%s,slot=0 WHERE uid=%s",
                    (bag["uid"], self.item["uid"]),
                )
                self.assertTrue(self.active(db))
                self.assertFalse(self.active(db, self.other["id"]))
                self.assertFalse(
                    self.active(db, self.foreign["id"], self.foreign_account)
                )
                self.assertFalse(self.active(db, self.main["id"], self.foreign_account))
                self.assertFalse(
                    eligible(db, self.account, native_map_id=1134, is_neo_server=True)
                )
            other_bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (self.other["id"],),
            ).fetchone()["uid"]
            db.execute(
                "UPDATE inventory_items SET character_id=%s,container=%s WHERE uid=%s",
                (self.other["id"], other_bag, self.item["uid"]),
            )
            self.assertFalse(self.active(db))
            self.assertTrue(self.active(db, self.other["id"]))

    def test_chest_temporary_build_projection_and_unsupported_container_do_not_qualify(
        self,
    ):
        from test_temporary_recycling import TemporaryRecyclingTests
        from wakfu_server.wire import proto_field

        owner = {
            "account": self.account,
            "generation": self.generation,
            "character": self.main,
        }
        temporary_uid = TemporaryRecyclingTests._temporary_item(
            self, owner, reference=32701
        )
        with self.store.connection() as db:
            entry = {"item": dict(self.item), "metadata": {}}
            db.execute(
                "INSERT INTO account_haven_chests(account_id,compartment_id,items) VALUES(%s,%s,%s)",
                (self.account, uuid4(), Jsonb([entry])),
            )
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (self.item["uid"],))
            fake_equipment = proto_field(
                10, proto_field(8, self.item["uid"]) + proto_field(16, 22)
            )
            db.execute(
                "UPDATE character_builds SET equipment=%s WHERE character_id=%s",
                (fake_equipment, self.main["id"]),
            )
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM temporary_combat_items WHERE uid=%s",
                    (temporary_uid,),
                ).fetchone()
            )
            self.assertFalse(self.active(db))
            unusual = db.execute(
                "INSERT INTO inventory_containers(character_id,reference,kind,capacity,flags) VALUES(%s,2175,127,1,0) RETURNING uid",
                (self.main["id"],),
            ).fetchone()["uid"]
            db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) VALUES(%s,32701,1,%s,0)",
                (self.main["id"], unusual),
            )
            self.assertFalse(self.active(db))

    def test_restoration_is_non_consuming_survives_reopen_and_preserves_dead_entry_guard(
        self,
    ):
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=1,hp_damage=max_hp-1,health_dead=false WHERE id=%s",
                (self.main["id"],),
            )
            saved = dict(
                db.execute(
                    "SELECT * FROM characters WHERE id=%s", (self.main["id"],)
                ).fetchone()
            )
            result = restore_canonical(
                self.store,
                db,
                saved,
                native_map_id=1134,
                is_neo_server=True,
                boundary="entry",
            )
            self.assertTrue(result["applied"])
            self.assertEqual(
                (saved["max_hp"], 0, False),
                tuple(
                    result["character"][k] for k in ("hp", "hp_damage", "health_dead")
                ),
            )
            self.assertEqual(
                1,
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (self.item["uid"],),
                ).fetchone()["quantity"],
            )
            self.assertFalse(
                eligible(
                    db,
                    self.account,
                    character_id=self.main["id"],
                    native_map_id=1134,
                    is_neo_server=False,
                )
            )
            for world in battleground_worlds():
                self.assertFalse(
                    eligible(
                        db,
                        self.account,
                        character_id=self.main["id"],
                        native_map_id=world,
                        is_neo_server=True,
                    )
                )
            db.execute(
                "UPDATE characters SET hp=0,hp_damage=max_hp,health_dead=true WHERE id=%s",
                (self.main["id"],),
            )
            dead = dict(
                db.execute(
                    "SELECT * FROM characters WHERE id=%s", (self.main["id"],)
                ).fetchone()
            )
            with self.assertRaisesRegex(ValueError, "Dead characters"):
                restore_canonical(
                    self.store,
                    db,
                    dead,
                    native_map_id=1134,
                    is_neo_server=True,
                    boundary="entry",
                )
            self.assertEqual(
                0,
                db.execute(
                    "SELECT hp FROM characters WHERE id=%s", (self.main["id"],)
                ).fetchone()["hp"],
            )
        reopened = self.reopen()
        with reopened.connection() as db:
            self.assertTrue(self.active(db))
            self.assertEqual(
                1,
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (self.item["uid"],),
                ).fetchone()["quantity"],
            )
