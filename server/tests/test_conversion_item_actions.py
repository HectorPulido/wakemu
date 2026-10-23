"""Exact native conversion products, conservation, binding and atomic failures."""
import struct
import unittest
from collections import Counter

from postgres_case import PostgresCase
from wakfu_server import conversion_item_actions as actions
from wakfu_server.inventory_items import grant


class ConversionItemWireTests(unittest.TestCase):
    def test_129_qualified_conversions_have_exact_native_request_and_output_maps(self):
        plans = actions.descriptors()["items"]
        self.assertEqual(len(plans), 129)
        self.assertEqual(sum(row["main_reference"] > 0 for row in plans), 116)
        for row in plans:
            body = struct.pack(">iq", row["action_id"], 123)
            self.assertEqual(actions.action_class(body), "bHF")
            self.assertTrue(
                all(
                    int(ref) > 0 and type(qty) is int and qty > 0
                    for ref, qty in row["products"].items()
                )
            )
            with self.assertRaises(ValueError):
                actions.action_class(body + b"\0")
        self.assertIsNone(actions.action_class(struct.pack(">iq", 904, 123)))


class ConversionItemPostgresTests(PostgresCase):
    def fixture(self, other=False):
        account = self.store.register(
            "other-converter" if other else "converter", "local-password"
        )["id"]
        character = self.store.create_character(
            account, "Other Converter" if other else "Converter"
        )
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        return account, generation, character

    def give(
        self,
        account,
        generation,
        character,
        reference,
        slot=0,
        quantity=1,
        container=None,
    ):
        bag = next(row for row in character["inventory_containers"] if row["kind"] == 0)
        return grant(
            self.store,
            account,
            generation,
            character["id"],
            reference=reference,
            quantity=quantity,
            container=bag["uid"] if container is None else container,
            slot=slot,
            allowed_references={reference},
        )

    def body(self, item):
        plan = next(
            row
            for row in actions.descriptors()["items"]
            if row["item_ref"] == item["reference"]
        )
        return struct.pack(">iq", plan["action_id"], item["uid"])

    def test_every_129_conversion_grants_its_exact_native_product_multiset(self):
        account, generation, character = self.fixture()
        for plan in actions.descriptors()["items"]:
            with self.subTest(reference=plan["item_ref"]):
                with self.store.connection() as db:
                    db.execute(
                        "DELETE FROM inventory_items WHERE character_id=%s",
                        (character["id"],),
                    )
                item = self.give(account, generation, character, plan["item_ref"])
                result = actions.use(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    self.body(item),
                    in_fight=False,
                )
                actual = Counter()
                for row in result["character"]["inventory_items"]:
                    actual[row["reference"]] += row["quantity"]
                self.assertEqual(
                    dict(actual),
                    {int(ref): qty for ref, qty in plan["products"].items()},
                )
                self.assertEqual(
                    (result["native_class"], result["consumed"], result["source_uid"]),
                    ("bHF", 1, item["uid"]),
                )
                self.assertFalse(
                    any(
                        row["uid"] == item["uid"]
                        for row in result["character"]["inventory_items"]
                    )
                )

    def test_bound_outputs_stay_bound_and_enhanced_source_is_preserved(self):
        account, generation, character = self.fixture()
        item = self.give(account, generation, character, 11080)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,true,11080)",
                (item["uid"],),
            )
        result = actions.use(
            self.store,
            account,
            generation,
            character["id"],
            self.body(item),
            in_fight=False,
        )
        with self.store.connection() as db:
            items = list(
                db.execute(
                    "SELECT i.uid,b.bound FROM inventory_items i LEFT JOIN inventory_item_bindings b ON b.uid=i.uid WHERE i.character_id=%s",
                    (character["id"],),
                )
            )
        self.assertTrue(items)
        self.assertTrue(all(row["bound"] is True for row in items))
        # Every newly granted source below is independently protected, rather
        # than copying opaque sockets/appearance into an unrelated product.
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM inventory_items WHERE character_id=%s", (character["id"],)
            )
        enhanced = self.give(account, generation, character, 11080)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_appearances(uid,appearance_ref) VALUES(%s,2024)",
                (enhanced["uid"],),
            )
        with self.assertRaises(ValueError):
            actions.use(
                self.store,
                account,
                generation,
                character["id"],
                self.body(enhanced),
                in_fight=False,
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (enhanced["uid"],),
                ).fetchone()["quantity"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT appearance_ref FROM inventory_item_appearances WHERE uid=%s",
                    (enhanced["uid"],),
                ).fetchone()["appearance_ref"],
                2024,
            )
        restored = self.reopen().character(account, character["id"])
        self.assertEqual(
            next(
                row
                for row in restored["inventory_items"]
                if row["uid"] == enhanced["uid"]
            )["appearance_ref"],
            2024,
        )

    def test_explicit_plain_recycling_observation_is_allowed_but_partial_or_enhanced_is_preserved(
        self,
    ):
        account, generation, character = self.fixture()
        plan = next(
            row for row in actions.descriptors()["items"] if row["item_ref"] == 11080
        )

        # The explicit native observation that both checks were clear is
        # compatible with conversion and produces the exact native output.
        plain = self.give(account, generation, character, 11080)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) VALUES(%s,FALSE,FALSE)",
                (plain["uid"],),
            )
        result = actions.use(
            self.store,
            account,
            generation,
            character["id"],
            self.body(plain),
            in_fight=False,
        )
        self.assertEqual(result["products"], plan["products"])
        self.assertEqual(result["consumed"], 1)
        actual = Counter()
        for row in result["character"]["inventory_items"]:
            actual[row["reference"]] += row["quantity"]
        self.assertEqual(
            dict(actual), {int(ref): qty for ref, qty in plan["products"].items()}
        )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM inventory_item_recycling_state WHERE uid=%s",
                    (plain["uid"],),
                ).fetchone()
            )
            db.execute(
                "DELETE FROM inventory_items WHERE character_id=%s", (character["id"],)
            )

        # A partial observation or either positive flag is still unqualified.
        for unidentified, socketed in (
            (None, False),
            (False, None),
            (True, False),
            (False, True),
        ):
            with self.subTest(unidentified=unidentified, socketed=socketed):
                source = self.give(account, generation, character, 11080)
                with self.store.connection() as db:
                    db.execute(
                        "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) VALUES(%s,%s,%s)",
                        (source["uid"], unidentified, socketed),
                    )
                with self.assertRaises(ValueError):
                    actions.use(
                        self.store,
                        account,
                        generation,
                        character["id"],
                        self.body(source),
                        in_fight=False,
                    )
                with self.store.connection() as db:
                    self.assertEqual(
                        db.execute(
                            "SELECT quantity FROM inventory_items WHERE uid=%s",
                            (source["uid"],),
                        ).fetchone()["quantity"],
                        1,
                    )
                    observation = db.execute(
                        "SELECT unidentified,socketed FROM inventory_item_recycling_state WHERE uid=%s",
                        (source["uid"],),
                    ).fetchone()
                    self.assertEqual(
                        (observation["unidentified"], observation["socketed"]),
                        (unidentified, socketed),
                    )
                    db.execute(
                        "DELETE FROM inventory_items WHERE character_id=%s",
                        (character["id"],),
                    )

        # Clear recycling flags do not authorize discarding other real item
        # state, including a visual and a nonzero element mask.
        for enhancement in ("appearance", "elements"):
            with self.subTest(enhancement=enhancement):
                source = self.give(account, generation, character, 11080)
                with self.store.connection() as db:
                    db.execute(
                        "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) VALUES(%s,FALSE,FALSE)",
                        (source["uid"],),
                    )
                    if enhancement == "appearance":
                        db.execute(
                            "INSERT INTO inventory_item_appearances(uid,appearance_ref) VALUES(%s,2024)",
                            (source["uid"],),
                        )
                    else:
                        db.execute(
                            "INSERT INTO inventory_item_elements(uid,damage_elements,resistance_elements) VALUES(%s,2,0)",
                            (source["uid"],),
                        )
                with self.assertRaises(ValueError):
                    actions.use(
                        self.store,
                        account,
                        generation,
                        character["id"],
                        self.body(source),
                        in_fight=False,
                    )
                with self.store.connection() as db:
                    self.assertEqual(
                        db.execute(
                            "SELECT quantity FROM inventory_items WHERE uid=%s",
                            (source["uid"],),
                        ).fetchone()["quantity"],
                        1,
                    )
                    self.assertEqual(
                        db.execute(
                            "SELECT unidentified,socketed FROM inventory_item_recycling_state WHERE uid=%s",
                            (source["uid"],),
                        ).fetchone(),
                        {"unidentified": False, "socketed": False},
                    )
                    if enhancement == "appearance":
                        self.assertEqual(
                            db.execute(
                                "SELECT appearance_ref FROM inventory_item_appearances WHERE uid=%s",
                                (source["uid"],),
                            ).fetchone()["appearance_ref"],
                            2024,
                        )
                    else:
                        self.assertEqual(
                            db.execute(
                                "SELECT damage_elements,resistance_elements FROM inventory_item_elements WHERE uid=%s",
                                (source["uid"],),
                            ).fetchone(),
                            {"damage_elements": 2, "resistance_elements": 0},
                        )
                    db.execute(
                        "DELETE FROM inventory_items WHERE character_id=%s",
                        (character["id"],),
                    )

    def test_foreign_stale_combat_and_capacity_fail_without_losing_source(self):
        account, generation, character = self.fixture()
        source = self.give(account, generation, character, 11080)
        other, other_generation, other_character = self.fixture(other=True)
        for owner, lease, actor, fight in (
            (other, other_generation, other_character["id"], False),
            (account, "stale", character["id"], False),
            (account, generation, character["id"], True),
        ):
            with self.assertRaises(ValueError):
                actions.use(
                    self.store, owner, lease, actor, self.body(source), in_fight=fight
                )
        bag = next(row for row in character["inventory_containers"] if row["kind"] == 0)
        from wakfu_server.combat_drop_delivery import _container_can_hold

        for container in character["inventory_containers"]:
            if not _container_can_hold(container, character["id"]):
                continue
            for slot in range(
                1 if container["uid"] == bag["uid"] else 0, container["capacity"]
            ):
                self.give(
                    account,
                    generation,
                    character,
                    9724,
                    slot,
                    container=container["uid"],
                )
        with self.store.connection() as db:
            before = list(
                db.execute(
                    "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                    (character["id"],),
                )
            )
        with self.assertRaises(ValueError):
            actions.use(
                self.store,
                account,
                generation,
                character["id"],
                self.body(source),
                in_fight=False,
            )
        with self.store.connection() as db:
            after = list(
                db.execute(
                    "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                    (character["id"],),
                )
            )
        self.assertEqual(after, before)
