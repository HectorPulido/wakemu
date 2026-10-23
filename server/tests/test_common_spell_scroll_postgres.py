"""The common spell scroll grants ownership without consuming its source."""
import unittest
import uuid

from postgres_case import PostgresCase
from wakfu_server import spells
from wakfu_server.inventory_items import grant
from wakfu_server.combat_inventory_date_conditions import complete_owned_item_quantity


class CommonSpellScrollPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "common-spell-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        self.character = self.store.create_character(self.account, "Scroll Reader")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.container = next(
            row["uid"]
            for row in self.character["inventory_containers"]
            if row["kind"] == 0
        )

    def grant_scroll(self, character_id=None, *, slot=0):
        return grant(
            self.store,
            self.account,
            self.generation,
            character_id or self.character["id"],
            reference=26347,
            quantity=1,
            container=self.container,
            slot=slot,
            allowed_references={26347},
        )

    def test_account_quest_scroll_survives_reconnect_and_unlocks_common_spell(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=130 WHERE id=%s", (self.character["id"],)
            )
        source = self.grant_scroll()
        self.assertTrue(source["account_quest_item"])
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT quantity FROM account_quest_items WHERE account_id=%s AND reference=26347",
                    (self.account,),
                ).fetchone()["quantity"],
            )
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM inventory_items WHERE reference=26347"
                ).fetchone()["n"],
            )
        character = self.store.character(self.account, self.character["id"])
        self.assertEqual(1, complete_owned_item_quantity(character, (26347,)))
        self.assertEqual(2, complete_owned_item_quantity(character, (26347, 26347)))
        self.assertIn(
            (character["id"] << 32 | 5623, 5623, 130),
            spells.owned_spell_records(character),
        )
        spells.validate_deck(
            spells.encode_deck((5623,), ()),
            character["breed"],
            130,
            character=character,
        )
        self.assertEqual(12503, spells.common_spell_packet(character)[0])
        self.assertIn(
            5623,
            {
                row["id"]
                for row in spells.available_spells(
                    character["breed"], 130, character=character
                )
            },
        )
        self.assertNotIn(
            5623,
            {
                row["id"]
                for row in spells.available_spells(
                    character["breed"], 129, character=character
                )
            },
        )
        second = self.store.create_character(self.account, "Second Class Reader")
        with self.store.connection() as db:
            db.execute("UPDATE characters SET level=130 WHERE id=%s", (second["id"],))
        second = self.store.character(self.account, second["id"])
        self.assertIn(
            5623,
            {
                row["id"]
                for row in spells.available_spells(
                    second["breed"], second["level"], character=second
                )
            },
        )
        saved = dict(
            character,
            builds={
                "0": {"deck": spells.encode_deck((5623,), (), level_cap=130).hex()}
            },
        )
        without_source = dict(saved, account_quest_items=())
        projected = spells.reconcile_item_spell_decks(without_source)
        self.assertNotIn(
            5623,
            spells.validate_deck(
                bytes.fromhex(projected["builds"]["0"]["deck"]),
                character["breed"],
                130,
                character=without_source,
            )["active"],
        )
        self.assertIn(
            5623,
            spells.validate_deck(
                bytes.fromhex(saved["builds"]["0"]["deck"]),
                character["breed"],
                130,
                character=saved,
            )["active"],
        )
        self.assertIn(
            5623,
            spells.validate_deck(
                bytes.fromhex(saved["builds"]["0"]["deck"]),
                character["breed"],
                130,
                character=character,
            )["active"],
        )
        reopened = self.reopen().character(self.account, self.character["id"])
        self.assertIn(
            5623,
            {
                row["id"]
                for row in spells.available_spells(
                    reopened["breed"], reopened["level"], character=reopened
                )
            },
        )

    def test_level_gate_and_foreign_scroll_reject_without_consumption(self):
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=129 WHERE id=%s", (self.character["id"],)
            )
        self.grant_scroll()
        character = self.store.character(self.account, self.character["id"])
        self.assertNotIn(
            5623,
            {
                row["id"]
                for row in spells.available_spells(
                    character["breed"], character["level"], character=character
                )
            },
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=130 WHERE id=%s", (self.character["id"],)
            )
        character = self.store.character(self.account, self.character["id"])
        self.assertIn(
            5623,
            {
                row["id"]
                for row in spells.available_spells(
                    character["breed"], character["level"], character=character
                )
            },
        )
        foreign_account = self.store.register(
            "foreign-scroll-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        other = self.store.create_character(foreign_account, "Other Scroll Reader")
        other_generation = self.store.begin_session(foreign_account)
        self.store.select_character(foreign_account, other_generation, other["id"])
        other_container = next(
            row["uid"] for row in other["inventory_containers"] if row["kind"] == 0
        )
        grant(
            self.store,
            foreign_account,
            other_generation,
            other["id"],
            reference=26347,
            quantity=1,
            container=other_container,
            slot=0,
            allowed_references={26347},
        )
        other = self.store.character(foreign_account, other["id"])
        self.assertEqual(1, complete_owned_item_quantity(other, (26347,)))
        self.assertNotIn(
            5623,
            {
                row["id"]
                for row in spells.available_spells(
                    other["breed"], other["level"], character=other
                )
            },
        )
        with self.assertRaises(ValueError):
            complete_owned_item_quantity(
                dict(
                    character,
                    account_quest_items=(
                        *character["account_quest_items"],
                        {
                            "account_id": foreign_account,
                            "reference": 26347,
                            "quantity": 1,
                        },
                    ),
                ),
                (26347,),
            )
        with self.store.connection() as db:
            quantities = db.execute(
                "SELECT account_id,quantity FROM account_quest_items "
                "WHERE reference=26347 ORDER BY account_id"
            ).fetchall()
        self.assertEqual(
            [(self.account, 1), (foreign_account, 1)],
            [(row["account_id"], row["quantity"]) for row in quantities],
        )

    def test_publication_reads_only_selected_main_and_active_heroes(self):
        from wakfu_server.heroes import add as add_hero
        from wakfu_server.item_spell_publication import account_inventory_packets

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=130 WHERE id=%s", (self.character["id"],)
            )
        self.grant_scroll()
        hero = self.store.create_character(self.account, "Scroll Hero")
        inactive = self.store.create_character(self.account, "Inactive Scroll Alt")
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=130 WHERE id=ANY(%s)",
                ([hero["id"], inactive["id"]],),
            )
        add_hero(
            self.store, self.account, self.generation, self.character["id"], hero["id"]
        )

        packets = account_inventory_packets(
            self.store, self.account, self.generation, self.character["id"]
        )
        self.assertEqual(2, len(packets))
        self.assertTrue(all(opcode == 12503 for opcode, _ in packets))
        self.assertEqual(
            1,
            complete_owned_item_quantity(
                self.store.character(self.account, self.character["id"]), (26347,)
            ),
        )
        with self.assertRaises(ValueError):
            account_inventory_packets(
                self.store, self.account, "stale-generation", self.character["id"]
            )
        with self.assertRaises(ValueError):
            account_inventory_packets(
                self.store, self.account, self.generation, hero["id"]
            )


if __name__ == "__main__":
    unittest.main()
