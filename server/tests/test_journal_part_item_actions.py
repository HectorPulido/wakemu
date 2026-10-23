"""Native journal-set conservation, quest storage and deferred objective provenance."""
import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import journal_part_item_actions as actions
from wakfu_server.inventory_items import grant
from wakfu_server.achievements import storage


class JournalPartWireTests(unittest.TestCase):
    def test_shared_assembly_metadata_keeps_binding_and_rejects_lost_enhancements(self):
        from wakfu_server.item_set_assembly import validate_input_metadata

        plain = {
            "inventory_item_bindings": {"bound": True},
            "inventory_item_elements": {"damage_elements": 0, "resistance_elements": 0},
            "inventory_item_recycling_state": {
                "unidentified": False,
                "socketed": False,
            },
        }
        validate_input_metadata({})
        validate_input_metadata(plain)
        for table, row in (
            (
                "inventory_item_elements",
                {"damage_elements": 2, "resistance_elements": 0},
            ),
            (
                "inventory_item_recycling_state",
                {"unidentified": None, "socketed": False},
            ),
            ("inventory_item_shards", {"shard_state": b"state"}),
            ("inventory_item_appearances", {"appearance_ref": 2024}),
            ("inventory_pets", {"xp": 50}),
            ("random_item_use_counters", {"next_use": 1}),
        ):
            with self.subTest(table=table), self.assertRaises(ValueError):
                validate_input_metadata({**plain, table: row})

    def test_fifteen_actions_have_exact_grammar_and_three_native_sets(self):
        groups = actions.descriptors()["groups"]
        self.assertEqual([len(group["items"]) for group in groups], [6, 4, 5])
        self.assertEqual(
            [group["products"] for group in groups],
            [{"20443": 1}, {"20444": 1}, {"20445": 1}],
        )
        for group in groups:
            for row in group["items"]:
                body = struct.pack(">iq", row["action_id"], 123)
                self.assertEqual(actions.action_class(body), "bIn")
                with self.assertRaises(ValueError):
                    actions.action_class(body + b"\0")
        self.assertIsNone(actions.action_class(struct.pack(">iq", 3090, 123)))


class JournalPartPostgresTests(PostgresCase):
    def fixture(self, other=False):
        account = self.store.register(
            "journal-other" if other else "journal-owner", "local-password"
        )["id"]
        character = self.store.create_character(
            account, "Other Journal" if other else "Journal Owner"
        )
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        return account, generation, character

    def pages(self, account, generation, character, group, quantity=1):
        bag = next(row for row in character["inventory_containers"] if row["kind"] == 0)
        return [
            grant(
                self.store,
                account,
                generation,
                character["id"],
                reference=ref,
                quantity=quantity,
                container=bag["uid"],
                slot=slot,
                allowed_references={ref},
            )
            for slot, ref in enumerate(group["input_references"])
        ]

    def body(self, item):
        row = next(
            row
            for group in actions.descriptors()["groups"]
            for row in group["items"]
            if row["item_ref"] == item["reference"]
        )
        return struct.pack(">iq", row["action_id"], item["uid"])

    def test_every_trigger_assembles_exact_native_personal_quest_part_and_durable_fact(
        self,
    ):
        account, generation, character = self.fixture()
        with self.store.connection() as db:
            before = storage.load_locked(db, character["id"])
        count = 0
        for group in actions.descriptors()["groups"]:
            for selected in range(len(group["items"])):
                pages = self.pages(account, generation, character, group)
                result = actions.use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    self.body(pages[selected]),
                    in_fight=False,
                )
                count += 1
                self.assertEqual(
                    set(result["consumed_uids"]), {item["uid"] for item in pages}
                )
                self.assertEqual(result["consumed"], len(pages))
                self.assertTrue(any(packet[0] == 13879 for packet in result["packets"]))
                output = int(next(iter(group["products"])))
                self.assertEqual(
                    next(
                        item["quantity"]
                        for item in result["character"]["quest_items"]
                        if item["reference"] == output
                    ),
                    selected + 1,
                )
                with self.assertRaises(ValueError):
                    actions.use(
                        self.store,
                        account,
                        generation,
                        character["id"],
                        self.body(pages[selected]),
                        in_fight=False,
                    )
        with self.store.connection() as db:
            self.assertEqual(storage.load_locked(db, character["id"]), before)
            receipts = list(
                db.execute(
                    "SELECT fact FROM item_set_assembly_receipts WHERE character_id=%s ORDER BY id",
                    (character["id"],),
                )
            )
            self.assertEqual(len(receipts), count)
            for row in receipts:
                self.assertEqual(
                    row["fact"]["native_objective_binding"]["definition_id"], 2907
                )
                self.assertEqual(
                    row["fact"]["mission_effect"],
                    "deferred_unqualified_completion_engine",
                )
        restored = self.reopen().character(account, character["id"])
        self.assertEqual(
            {row["reference"]: row["quantity"] for row in restored["quest_items"]},
            {20443: 6, 20444: 4, 20445: 5},
        )

    def test_all_groups_reject_missing_foreign_stale_combat_and_capacity_without_debits(
        self,
    ):
        account, generation, character = self.fixture()
        other, other_generation, other_character = self.fixture(other=True)
        for group in actions.descriptors()["groups"]:
            pages = self.pages(account, generation, character, group)
            body = self.body(pages[0])
            for owner, lease, actor, fight in (
                (other, other_generation, other_character["id"], False),
                (account, "stale", character["id"], False),
                (account, generation, character["id"], True),
            ):
                with self.assertRaises(ValueError):
                    actions.use(self.store, owner, lease, actor, body, in_fight=fight)
            with patch(
                "wakfu_server.item_action_delivery.grant_outputs",
                side_effect=ValueError("Output unavailable"),
            ), self.assertRaises(ValueError):
                actions.use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    body,
                    in_fight=False,
                )
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM item_set_assembly_receipts WHERE character_id=%s",
                        (character["id"],),
                    ).fetchone()["n"],
                    0,
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM inventory_items WHERE uid=ANY(%s)",
                        ([item["uid"] for item in pages],),
                    ).fetchone()["n"],
                    len(pages),
                )
                output = int(next(iter(group["products"])))
                db.execute(
                    "INSERT INTO character_quest_items(character_id,reference,quantity) VALUES(%s,%s,99)",
                    (character["id"], output),
                )
            with self.assertRaises(ValueError):
                actions.use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    body,
                    in_fight=False,
                )
            with self.store.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM inventory_items WHERE uid=ANY(%s)",
                        ([item["uid"] for item in pages],),
                    ).fetchone()["n"],
                    len(pages),
                )
                db.execute(
                    "DELETE FROM inventory_items WHERE uid=%s", (pages[-1]["uid"],)
                )
            with self.assertRaises(ValueError):
                actions.use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    body,
                    in_fight=False,
                )
            with self.store.connection() as db:
                db.execute(
                    "DELETE FROM inventory_items WHERE uid=ANY(%s)",
                    ([item["uid"] for item in pages],),
                )

    def test_assembly_accepts_empty_metadata_and_rejects_unqualified_appearance_or_shard(
        self,
    ):
        account, generation, character = self.fixture()
        group = actions.descriptors()["groups"][0]
        pages = self.pages(account, generation, character, group)
        selected = pages[0]
        body = self.body(selected)

        # Nonempty sidecars have no native set-to-product inheritance rule.
        # Each rejection must leave every input and the durable receipt untouched.
        for table, statement, values in (
            (
                "inventory_item_appearances",
                "INSERT INTO inventory_item_appearances(uid,appearance_ref) VALUES(%s,%s)",
                (selected["uid"], 2024),
            ),
            (
                "inventory_item_shards",
                "INSERT INTO inventory_item_shards(uid,shard_state) VALUES(%s,%s)",
                # Valid native lD protobuf (`field 3 = 1`); assembly rejects it
                # because it is real enhancement state, not because it is malformed.
                (selected["uid"], bytes.fromhex("1801")),
            ),
        ):
            with self.store.connection() as db:
                db.execute(statement, values)
            with self.assertRaisesRegex(
                ValueError, "no qualified inheritance contract"
            ):
                actions.use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    body,
                    in_fight=False,
                )
            with self.store.connection() as db:
                db.execute(f"DELETE FROM {table} WHERE uid=%s", (selected["uid"],))
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM inventory_items WHERE uid=ANY(%s)",
                        ([item["uid"] for item in pages],),
                    ).fetchone()["n"],
                    len(pages),
                )
                self.assertEqual(
                    db.execute(
                        "SELECT count(*) AS n FROM item_set_assembly_receipts WHERE character_id=%s",
                        (character["id"],),
                    ).fetchone()["n"],
                    0,
                )

        # Empty element selection and false/false recycling observations are
        # compatible facts, so they do not block the ordinary assembly path.
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_elements(uid,damage_elements,resistance_elements) "
                "VALUES(%s,0,0)",
                (selected["uid"],),
            )
            db.execute(
                "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) "
                "VALUES(%s,FALSE,FALSE)",
                (selected["uid"],),
            )
        result = actions.use(
            self.store, account, generation, character["id"], body, in_fight=False
        )
        self.assertEqual(set(result["consumed_uids"]), {item["uid"] for item in pages})
        self.assertEqual(result["consumed"], len(pages))
        self.assertEqual(result["products"], {int(next(iter(group["products"]))): 1})
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM item_set_assembly_receipts WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()["n"],
                1,
            )
