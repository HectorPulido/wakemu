"""Captain-map set conservation and explicitly inferred one-book policy."""
import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import captain_map_item_actions as actions
from wakfu_server import book_item_actions
from wakfu_server.inventory_items import grant


class CaptainMapWireTests(unittest.TestCase):
    def test_all_sixteen_native_actions_have_exact_grammar_and_explicit_policy(self):
        document = actions.descriptors()
        self.assertEqual(
            document["policy"], "supported_inference_wakemu_one_encyclopedia_per_set"
        )
        self.assertEqual(document["input_references"], list(range(15368, 15384)))
        self.assertEqual(document["products"], {"26729": 1})
        for plan in document["items"]:
            body = struct.pack(">iq", plan["action_id"], 123)
            self.assertEqual(actions.action_class(body), "bIn")
            with self.assertRaises(ValueError):
                actions.action_class(body + b"\0")
        self.assertIsNone(actions.action_class(struct.pack(">iq", 10234, 123)))


class CaptainMapPostgresTests(PostgresCase):
    def fixture(self, other=False):
        account = self.store.register(
            "captain-other" if other else "captain-owner", "local-password"
        )["id"]
        character = self.store.create_character(
            account, "Other Captain" if other else "Captain Owner"
        )
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        return account, generation, character

    def give(self, account, generation, character, ref, slot, container=None):
        base = next(
            row for row in character["inventory_containers"] if row["kind"] == 0
        )
        return grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=ref,
            quantity=1,
            container=base["uid"] if container is None else container,
            slot=slot,
            allowed_references={ref},
        )

    def maps(self, account, generation, character):
        return [
            self.give(account, generation, character, ref, slot)
            for slot, ref in enumerate(range(15368, 15384))
        ]

    def body(self, item):
        plan = next(
            row
            for row in actions.descriptors()["items"]
            if row["item_ref"] == item["reference"]
        )
        return struct.pack(">iq", plan["action_id"], item["uid"])

    def test_every_native_trigger_consumes_exact_sixteen_maps_and_grants_readable_bound_book(
        self,
    ):
        account, generation, character = self.fixture()
        for selected in range(16):
            with self.subTest(selected_reference=15368 + selected):
                with self.store.connection() as db:
                    db.execute(
                        "DELETE FROM inventory_items WHERE character_id=%s",
                        (character["id"],),
                    )
                maps = self.maps(account, generation, character)
                outcome = actions.use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    self.body(maps[selected]),
                    in_fight=False,
                )
                self.assertEqual(
                    set(outcome["consumed_uids"]), {item["uid"] for item in maps}
                )
                self.assertEqual(
                    (outcome["consumed"], outcome["source_consumed"]), (16, 1)
                )
                inventory = outcome["character"]["inventory_items"]
                self.assertEqual(
                    [(item["reference"], item["quantity"]) for item in inventory],
                    [(26729, 1)],
                )
                with self.store.connection() as db:
                    binding = db.execute(
                        "SELECT bound FROM inventory_item_bindings WHERE uid=%s",
                        (inventory[0]["uid"],),
                    ).fetchone()
                self.assertIs(binding["bound"], True)
                read = book_item_actions.use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    struct.pack(">iq", 10916, inventory[0]["uid"]),
                    in_fight=False,
                )
                self.assertEqual(
                    (read["source_reference"], read["consumed"]), (26729, 0)
                )
                with self.assertRaises(ValueError):
                    actions.use(
                        self.store,
                        account,
                        generation,
                        character["id"],
                        self.body(maps[selected]),
                        in_fight=False,
                    )

    def test_selected_duplicate_uid_is_debited_full_bags_use_freed_space_and_binding_persists(
        self,
    ):
        account, generation, character = self.fixture()
        maps = self.maps(account, generation, character)
        selected = self.give(account, generation, character, 15368, 16)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,true,15369)",
                (maps[1]["uid"],),
            )
        from wakfu_server.combat_drop_delivery import _container_can_hold

        for container in character["inventory_containers"]:
            if not _container_can_hold(container, character["id"]):
                continue
            start = 17 if container["kind"] == 0 else 0
            for slot in range(start, container["capacity"]):
                self.give(
                    account,
                    generation,
                    character,
                    9724,
                    slot,
                    container=container["uid"],
                )
        result = actions.use(
            self.store,
            account,
            generation,
            character["id"],
            self.body(selected),
            in_fight=False,
        )
        self.assertIn(selected["uid"], result["consumed_uids"])
        self.assertNotIn(maps[0]["uid"], result["consumed_uids"])
        self.assertIs(result["binding_inherited"], True)
        restored = self.reopen().character(account, character["id"])
        self.assertTrue(
            any(row["uid"] == maps[0]["uid"] for row in restored["inventory_items"])
        )
        self.assertEqual(
            sum(
                row["quantity"]
                for row in restored["inventory_items"]
                if row["reference"] == 26729
            ),
            1,
        )

    def test_missing_foreign_stale_combat_enhanced_and_provider_failure_are_atomic(
        self,
    ):
        account, generation, character = self.fixture()
        maps = self.maps(account, generation, character)
        other, other_generation, other_character = self.fixture(other=True)
        body = self.body(maps[0])
        for owner, lease, actor, combat in (
            (other, other_generation, other_character["id"], False),
            (account, "stale", character["id"], False),
            (account, generation, character["id"], True),
        ):
            with self.assertRaises(ValueError):
                actions.use(self.store, owner, lease, actor, body, in_fight=combat)
        with self.store.connection() as db:
            before = list(
                db.execute(
                    "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                    (character["id"],),
                )
            )
        with patch(
            "wakfu_server.item_action_delivery.grant_outputs",
            side_effect=ValueError("Injected output capacity failure"),
        ), self.assertRaises(ValueError):
            actions.use(
                self.store, account, generation, character["id"], body, in_fight=False
            )
        with self.store.connection() as db:
            self.assertEqual(
                list(
                    db.execute(
                        "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                        (character["id"],),
                    )
                ),
                before,
            )
            db.execute(
                "INSERT INTO inventory_item_appearances(uid,appearance_ref) VALUES(%s,2024)",
                (maps[-1]["uid"],),
            )
        with self.assertRaises(ValueError):
            actions.use(
                self.store, account, generation, character["id"], body, in_fight=False
            )
        with self.store.connection() as db:
            self.assertEqual(
                list(
                    db.execute(
                        "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                        (character["id"],),
                    )
                ),
                before,
            )
            self.assertEqual(
                db.execute(
                    "SELECT appearance_ref FROM inventory_item_appearances WHERE uid=%s",
                    (maps[-1]["uid"],),
                ).fetchone()["appearance_ref"],
                2024,
            )
            db.execute(
                "DELETE FROM inventory_item_appearances WHERE uid=%s",
                (maps[-1]["uid"],),
            )
            db.execute("DELETE FROM inventory_items WHERE uid=%s", (maps[-1]["uid"],))
        with self.assertRaises(ValueError):
            actions.use(
                self.store, account, generation, character["id"], body, in_fight=False
            )
