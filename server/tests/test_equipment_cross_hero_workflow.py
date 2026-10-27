"""One physical equipment unit crosses saved builds and hero custody safely."""
import struct

from postgres_case import PostgresCase
from wakfu_server import builds, heroes, player_exchanges
from wakfu_server.equipment_stacks import EquipmentOwnershipError
from wakfu_server.inventory_items import grant
from wakfu_server.inventory_move import EquippedTransferError, transfer
from wakfu_server.wire import proto_field


class EquipmentCrossHeroWorkflowTests(PostgresCase):
    def test_all_builds_unequip_transfer_equip_and_custody_guards(self):
        account = self.store.register("gear-workflow", "local-password")["id"]
        main = self.store.create_character(account, "Gear Main")
        hero = self.store.create_character(account, "Gear Hero")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        heroes.add(self.store, account, generation, main["id"], hero["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=50 WHERE id=ANY(%s)",
                ([main["id"], hero["id"]],),
            )
        main_bag = main["inventory_containers"][0]["uid"]
        hero_bag = hero["inventory_containers"][0]["uid"]
        item = grant(
            self.store,
            account,
            generation,
            main["id"],
            reference=2021,
            quantity=1,
            container=main_bag,
            slot=0,
            allowed_references={2021},
        )
        uid = item["uid"]
        equipment = proto_field(10, proto_field(8, uid) + proto_field(16, 4))

        def save(owner, index, selected, *, owner_account=account, lease=generation):
            sheet = b"".join(
                proto_field(tag, value)
                for tag, value in (
                    (8, index),
                    (18, b"Physical equipment"),
                    (24, 50),
                    (56, 0),
                )
            )
            return self.store.save_build(
                owner_account,
                lease,
                owner,
                index,
                dict(
                    sheet=sheet,
                    equipment=selected,
                    deck=b"",
                    aptitudes=b"",
                ),
            )

        def move(source, destination):
            return transfer(
                self.store,
                account,
                generation,
                main["id"],
                struct.pack(">qqqhB", uid, destination, source, 0, 0),
            )

        def custody():
            with self.store.connection() as db:
                return dict(
                    db.execute(
                        "SELECT * FROM inventory_items WHERE uid=%s", (uid,)
                    ).fetchone()
                )

        move(main_bag, hero_bag)
        save(hero["id"], 0, equipment)
        save(hero["id"], 1, equipment)
        with self.assertRaises(EquipmentOwnershipError) as unavailable:
            save(main["id"], 0, equipment)
        self.assertEqual(unavailable.exception.owner_name, hero["name"])
        before = custody()
        for cleared in (None, 0):
            if cleared is not None:
                save(hero["id"], cleared, builds.EMPTY_EQUIPMENT)
            with self.assertRaises(EquippedTransferError):
                move(hero_bag, main_bag)
            self.assertEqual(custody(), before)
        save(hero["id"], 1, builds.EMPTY_EQUIPMENT)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,true,2021)",
                (uid,),
            )
        with self.assertRaisesRegex(ValueError, "Character-bound"):
            move(hero_bag, main_bag)
        self.assertEqual(custody(), before)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_item_bindings SET bound=false WHERE uid=%s", (uid,)
            )
        move(hero_bag, main_bag)
        saved = save(main["id"], 0, equipment)
        self.assertEqual(saved["builds"][0]["equipment"], equipment.hex())
        self.assertEqual(custody()["character_id"], main["id"])
        self.assertEqual(custody()["quantity"], 1)
        save(main["id"], 0, builds.EMPTY_EQUIPMENT)
        # A real bilateral offer reserves the unit against a hero transfer.
        foreign_account = self.store.register("gear-recipient", "local-password")["id"]
        foreign = self.store.create_character(foreign_account, "Gear Recipient")
        foreign_generation = self.store.begin_session(foreign_account)
        self.store.select_character(foreign_account, foreign_generation, foreign["id"])
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=50 WHERE id=%s", (foreign["id"],))
        invitation = player_exchanges.invite(
            self.store, account, generation, main["id"], foreign["id"]
        )
        exchange = player_exchanges.answer(
            self.store,
            foreign_account,
            foreign_generation,
            foreign["id"],
            invitation["id"],
            True,
        )
        offered = player_exchanges.offer_item(
            self.store, account, generation, main["id"], exchange["id"], uid, 1
        )
        before = custody()
        with self.assertRaisesRegex(ValueError, "Offered item"):
            move(main_bag, hero_bag)
        self.assertEqual(custody(), before)
        with self.assertRaises(ValueError):
            transfer(
                self.store,
                account,
                generation,
                main["id"],
                struct.pack(
                    ">qqqhB",
                    uid,
                    foreign["inventory_containers"][0]["uid"],
                    main_bag,
                    0,
                    0,
                ),
            )
        missing = proto_field(10, proto_field(8, 1 << 60) + proto_field(16, 4))
        with self.assertRaises(EquipmentOwnershipError) as absent:
            save(main["id"], 0, missing)
        self.assertIsNone(absent.exception.owner_name)
        self.assertEqual(custody(), before)
        for owner_account, lease, identity in (
            (account, generation, main["id"]),
            (foreign_account, foreign_generation, foreign["id"]),
        ):
            player_exchanges.published(
                self.store,
                owner_account,
                lease,
                identity,
                exchange["id"],
                offered["revision"],
            )
        self.assertFalse(
            player_exchanges.confirm(
                self.store, account, generation, main["id"], exchange["id"]
            )["applied"]
        )
        received = player_exchanges.confirm(
            self.store,
            foreign_account,
            foreign_generation,
            foreign["id"],
            exchange["id"],
        )
        self.assertTrue(received["applied"])
        self.assertEqual(custody()["character_id"], foreign["id"])
        self.assertEqual(custody()["quantity"], 1)
        # The real receiving owner can immediately equip/save the committed UID.
        save(
            foreign["id"],
            0,
            equipment,
            owner_account=foreign_account,
            lease=foreign_generation,
        )
        with self.assertRaises(EquipmentOwnershipError) as foreign_custody:
            save(main["id"], 0, equipment)
        self.assertIsNone(foreign_custody.exception.owner_name)
        self.assertNotIn(foreign["name"], foreign_custody.exception.player_message)
        before = custody()
        self.store.begin_session(account)
        with self.assertRaises(ValueError):
            move(main_bag, hero_bag)
        self.assertEqual(custody(), before)
