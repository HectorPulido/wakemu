"""Native optimistic hero moves persist both owner and owned container."""
import struct
from copy import deepcopy
from unittest.mock import patch
from postgres_case import PostgresCase
from wakfu_server.characters import heroes
from wakfu_server.inventory_items import grant
from wakfu_server.inventory_move import EquippedTransferError, transfer


class HeroInventoryTransferTests(PostgresCase):
    def setup_roster(self):
        account = self.store.register("transfer-heroes", "local-password")["id"]
        main = self.store.create_character(account, "Transfer Main")
        first = self.store.create_character(account, "Transfer First")
        second = self.store.create_character(account, "Transfer Second")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        for hero in (first, second):
            heroes.add(self.store, account, generation, main["id"], hero["id"])
        source = main["inventory_containers"][0]["uid"]
        unit = grant(
            self.store,
            account,
            generation,
            main["id"],
            reference=2021,
            quantity=10,
            container=source,
            slot=0,
            allowed_references={2021},
        )
        return account, generation, main, first, second, unit

    def test_hero_to_hero_whole_transfer_survives_reopen(self):
        account, generation, main, first, second, unit = self.setup_roster()
        source = main["inventory_containers"][0]["uid"]
        first_bag = first["inventory_containers"][0]["uid"]
        second_bag = second["inventory_containers"][0]["uid"]
        transfer(
            self.store,
            account,
            generation,
            main["id"],
            struct.pack(">qqqhB", unit["uid"], first_bag, source, 0, 0),
        )
        result = transfer(
            self.store,
            account,
            generation,
            main["id"],
            struct.pack(">qqqhB", unit["uid"], second_bag, first_bag, 0, 0),
        )
        self.assertEqual(result["packets"], [])
        self.assertEqual(
            self.reopen().character(account, first["id"])["inventory_items"], []
        )
        received = self.reopen().character(account, second["id"])["inventory_items"]
        self.assertEqual(
            [
                (row["uid"], row["character_id"], row["container"], row["quantity"])
                for row in received
            ],
            [(unit["uid"], second["id"], second_bag, 10)],
        )

    def test_owned_character_outside_active_roster_is_rejected(self):
        account, generation, main, first, second, unit = self.setup_roster()
        inactive = self.store.create_character(account, "Inactive Transfer")
        source = main["inventory_containers"][0]["uid"]
        with self.assertRaisesRegex(ValueError, "active owned hero roster"):
            transfer(
                self.store,
                account,
                generation,
                main["id"],
                struct.pack(
                    ">qqqhB",
                    unit["uid"],
                    inactive["inventory_containers"][0]["uid"],
                    source,
                    0,
                    0,
                ),
            )
        self.assertEqual(
            self.reopen().character(account, main["id"])["inventory_items"][0][
                "quantity"
            ],
            10,
        )

    def test_equipped_cross_owner_transfer_rejects_without_mutation_or_switch(self):
        from wakfu_server.wire import proto_field

        account, generation, main, first, _, unit = self.setup_roster()
        source = main["inventory_containers"][0]["uid"]
        destination = first["inventory_containers"][0]["uid"]
        body = struct.pack(">qqqhB", unit["uid"], destination, source, 0, 0)
        original_character = self.store.character

        def character_with_equipped_build(account_id, character_id, db=None):
            current = original_character(account_id, character_id, db)
            if character_id == main["id"]:
                equipment = proto_field(
                    10, proto_field(8, unit["uid"]) + proto_field(16, 3)
                )
                current["builds"][0] = {"equipment": equipment.hex()}
            return current

        with patch.object(
            self.store, "character", side_effect=character_with_equipped_build
        ), self.assertRaises(EquippedTransferError):
            transfer(self.store, account, generation, main["id"], body)

        reopened = self.reopen()
        self.assertEqual(
            [
                (row["uid"], row["quantity"])
                for row in reopened.character(account, main["id"])["inventory_items"]
            ],
            [(unit["uid"], 10)],
        )
        self.assertEqual(
            reopened.character(account, first["id"])["inventory_items"], []
        )
        self.assertTrue(
            reopened.current_character_session(account, generation, main["id"])
        )
        self.assertFalse(
            reopened.current_character_session(account, generation, first["id"])
        )

    def test_partial_transfer_preserves_binding_and_recycling_metadata(self):
        from wakfu_server.inventory_uids import reserve

        account, generation, main, first, _, unit = self.setup_roster()
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,false,2021)",
                (unit["uid"],),
            )
            db.execute(
                "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) VALUES(%s,true,false)",
                (unit["uid"],),
            )
        clone = reserve(self.store, account, generation, main["id"], count=1)["uids"][0]
        body = struct.pack(
            ">qqqhBqh",
            unit["uid"],
            first["inventory_containers"][0]["uid"],
            main["inventory_containers"][0]["uid"],
            0,
            1,
            clone,
            3,
        )
        transfer(self.store, account, generation, main["id"], body)
        self.assertEqual(
            self.reopen().character(account, first["id"])["inventory_items"][0][
                "quantity"
            ],
            3,
        )
        with self.store.connection() as db:
            binding = db.execute(
                "SELECT bound,template_reference FROM inventory_item_bindings WHERE uid=%s",
                (clone,),
            ).fetchone()
            recycling = db.execute(
                "SELECT unidentified,socketed FROM inventory_item_recycling_state WHERE uid=%s",
                (clone,),
            ).fetchone()
        self.assertEqual(dict(binding), dict(bound=False, template_reference=2021))
        self.assertEqual(dict(recycling), dict(unidentified=True, socketed=False))

    def test_instance_bound_without_account_scope_cannot_change_hero_owner(self):
        account, generation, main, first, _, unit = self.setup_roster()
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,true,2021)",
                (unit["uid"],),
            )
        with self.assertRaisesRegex(ValueError, "Character-bound"):
            transfer(
                self.store,
                account,
                generation,
                main["id"],
                struct.pack(
                    ">qqqhB",
                    unit["uid"],
                    first["inventory_containers"][0]["uid"],
                    main["inventory_containers"][0]["uid"],
                    0,
                    0,
                ),
            )

    def binding_scope_case(self, scope, bound, allowed):
        from wakfu_server.exchange_rules import ITEMS

        account, generation, main, first, _, unit = self.setup_roster()
        reference = unit["reference"]
        # This catalog has no BOE item rows. Exercise the supported native
        # binding policies explicitly without changing catalog persistence.
        definition = deepcopy(ITEMS[str(reference)])
        definition["binding_template"].update(enum=scope, default_eKo=False)
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET reference=%s,quantity=1 WHERE uid=%s",
                (reference, unit["uid"]),
            )
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,%s,%s)",
                (unit["uid"], bound, reference),
            )
        body = struct.pack(
            ">qqqhB",
            unit["uid"],
            first["inventory_containers"][0]["uid"],
            main["inventory_containers"][0]["uid"],
            0,
            0,
        )
        with patch.dict(ITEMS, {str(reference): definition}):
            if allowed:
                transfer(self.store, account, generation, main["id"], body)
                self.assertEqual(
                    self.reopen().character(account, first["id"])["inventory_items"][0][
                        "uid"
                    ],
                    unit["uid"],
                )
            else:
                with self.assertRaisesRegex(ValueError, "Character-bound"):
                    transfer(self.store, account, generation, main["id"], body)
                self.assertEqual(
                    self.reopen().character(account, main["id"])["inventory_items"][0][
                        "uid"
                    ],
                    unit["uid"],
                )

    def test_unbound_equip_character_template_transfers_before_binding(self):
        self.binding_scope_case("BOUND_ON_EQUIP_TO_CHARACTER", False, True)

    def test_bound_equip_character_template_cannot_change_owner(self):
        self.binding_scope_case("BOUND_ON_EQUIP_TO_CHARACTER", True, False)

    def test_bound_equip_account_template_transfers_within_account(self):
        self.binding_scope_case("BOUND_ON_EQUIP_TO_ACCOUNT", True, True)
