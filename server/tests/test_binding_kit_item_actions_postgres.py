"""Native binding-assembly transaction, mission settlement and rollback."""
import struct
import unittest

from postgres_case import PostgresCase


class BindingKitItemActionsPostgresTests(PostgresCase):
    def _character(self, account_name, character_name):
        account = self.store.register(account_name, "local-password")["id"]
        character = self.store.create_character(account, character_name)
        generation = self.store.begin_session(account)
        character = self.store.select_character(account, generation, character["id"])
        return account, generation, character

    def _seed_mission_fixture(self, account, character_id):
        from wakfu_server.achievements import storage
        from wakfu_server.character_levels import XP_BY_LEVEL

        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=178 WHERE id=%s AND account_id=%s",
                (character_id, account),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[178], character_id),
            )
            state = storage.load_locked(db, character_id)
            state["running"] = sorted(set(state["running"]) | {2909})
            state["objectives"] = sorted(
                set(state["objectives"]) | {5914, 5915, 5916, 5917, 5918}
            )
            storage.store(db, character_id, state)

    def _grant(self, account, generation, character, reference, quantity, slot):
        from wakfu_server.inventory_items import grant

        bag = next(row for row in character["inventory_containers"] if row["kind"] == 0)
        return grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=reference,
            quantity=quantity,
            container=bag["uid"],
            slot=slot,
            allowed_references={reference},
        )

    def _inventory_quantities(self, character_id):
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT reference,sum(quantity) AS quantity FROM inventory_items "
                "WHERE character_id=%s GROUP BY reference ORDER BY reference",
                (character_id,),
            ).fetchall()
        return {row["reference"]: row["quantity"] for row in rows}

    def test_native_kit_debits_mixed_stacks_once_and_completes_only_prepared_mission(
        self,
    ):
        from wakfu_server import binding_kit_item_actions as actions
        from wakfu_server.achievements import storage
        from wakfu_server.items import quest_inventory

        account, generation, character = self._character(
            "binding-kit-owner", "Kit Owner"
        )
        self._seed_mission_fixture(account, character["id"])
        kit = self._grant(account, generation, character, 20440, 1, 0)
        source_stacks = []
        slot = 1
        for reference, quantities in (
            (19147, (3, 2)),
            (19791, (1, 1)),
            (20148, (1, 1)),
            (19798, (1, 1)),
            (20196, (1, 1)),
        ):
            for quantity in quantities:
                source_stacks.append(
                    self._grant(
                        account, generation, character, reference, quantity, slot
                    )
                )
                slot += 1
        before = self._inventory_quantities(character["id"])
        with self.store.connection() as db:
            quest_inventory.grant(db, character["id"], 20441, 99)

        body = struct.pack(">iq", 8071, kit["uid"])
        with self.store.connection() as db:
            before_xp = db.execute(
                "SELECT xp FROM character_progression WHERE character_id=%s",
                (character["id"],),
            ).fetchone()["xp"]

        with self.assertRaisesRegex(ValueError, "quest quantity capacity is full"):
            actions.use(
                self.store, account, generation, character["id"], body, in_fight=False
            )
        self.assertEqual(self._inventory_quantities(character["id"]), before)
        with self.store.connection() as db:
            self.assertEqual(
                quest_inventory.load(db, character["id"]),
                [{"character_id": character["id"], "reference": 20441, "quantity": 99}],
            )
            state = storage.load_locked(db, character["id"])
            self.assertIn(2909, state["running"])
            self.assertNotIn(5919, state["objectives"])
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM scenario_assembly_receipts WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["n"],
                0,
            )

        with self.assertRaises(ValueError):
            actions.use(
                self.store,
                account,
                "stale-generation",
                character["id"],
                body,
                in_fight=False,
            )
        foreign_account, foreign_generation, foreign = self._character(
            "binding-kit-foreign", "Foreign Owner"
        )
        with self.assertRaises(ValueError):
            actions.use(
                self.store,
                foreign_account,
                foreign_generation,
                foreign["id"],
                body,
                in_fight=False,
            )
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM character_quest_items WHERE character_id=%s AND reference=20441",
                (character["id"],),
            )
            db.execute(
                "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
                (source_stacks[0]["uid"],),
            )
        with self.assertRaisesRegex(
            ValueError, "Collect every native binding material"
        ):
            actions.use(
                self.store, account, generation, character["id"], body, in_fight=False
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity+1 WHERE uid=%s",
                (source_stacks[0]["uid"],),
            )

        result = actions.use(
            self.store, account, generation, character["id"], body, in_fight=False
        )
        self.assertTrue(result["applied"])
        self.assertEqual(result["consumed"], 13)
        self.assertEqual(result["source_consumed"], 0)
        self.assertEqual(result["source_uid"], kit["uid"])
        self.assertEqual(result["products"], {20441: 1})
        self.assertEqual(result["mission_result"]["completed"], [2909])
        self.assertTrue(result["xp_changed"])
        after_inventory = self._inventory_quantities(character["id"])
        self.assertEqual(after_inventory, {20440: 1})
        with self.store.connection() as db:
            quest = quest_inventory.load(db, character["id"])
            state = storage.load_locked(db, character["id"])
            progression = db.execute(
                "SELECT xp FROM character_progression WHERE character_id=%s",
                (character["id"],),
            ).fetchone()
            receipts = list(
                db.execute(
                    "SELECT * FROM scenario_assembly_receipts WHERE character_id=%s",
                    (character["id"],),
                )
            )
            events = list(
                db.execute(
                    "SELECT * FROM character_achievement_events WHERE character_id=%s",
                    (character["id"],),
                )
            )
        self.assertEqual(
            quest,
            [{"character_id": character["id"], "reference": 20441, "quantity": 1}],
        )
        self.assertEqual(progression["xp"], before_xp + 200000000)
        self.assertIn(5919, state["objectives"])
        self.assertIn(2909, state["completed"])
        self.assertNotIn(2909, state["running"])
        self.assertEqual(len(receipts), 1)
        self.assertEqual(len(events), 1)

        replay = actions.use(
            self.store, account, generation, character["id"], body, in_fight=False
        )
        self.assertFalse(replay["applied"])
        self.assertEqual(replay["consumed"], 0)
        self.assertEqual(replay["character"]["quest_items"], quest)
        self.assertEqual(self._inventory_quantities(character["id"]), after_inventory)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT xp FROM character_progression WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["xp"],
                before_xp + 200000000,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM scenario_assembly_receipts WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["n"],
                1,
            )
