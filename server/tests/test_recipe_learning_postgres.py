"""PostgreSQL tests for native bIB/bIz recipe-learning books."""
import json
from pathlib import Path
import struct

from postgres_case import PostgresCase
from wakfu_server import recipe_learning
from wakfu_server.profession_store import account_packet


class RecipeLearningPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("recipe_learning", "password-test")["id"]
        self.character = self.store.create_character(self.account, "Recipe Learner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])

    def add_item(self, reference, *, quantity=1, character_id=None):
        character_id = character_id or self.character["id"]
        with self.store.connection() as db:
            bag = db.execute(
                "SELECT uid FROM inventory_containers WHERE character_id=%s AND kind=0",
                (character_id,),
            ).fetchone()["uid"]
            slot = db.execute(
                "SELECT COALESCE(MAX(slot)+1,0) AS slot FROM inventory_items WHERE container=%s",
                (bag,),
            ).fetchone()["slot"]
            return db.execute(
                "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,%s,%s,%s) RETURNING uid",
                (character_id, reference, quantity, bag, slot),
            ).fetchone()["uid"]

    def learn(self, uid, action, *, account=None, generation=None, character_id=None):
        return recipe_learning.learn(
            self.store,
            self.account if account is None else account,
            self.generation if generation is None else generation,
            self.character["id"] if character_id is None else character_id,
            struct.pack(">iq", action, uid),
        )

    def quantity(self, uid):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT quantity FROM inventory_items WHERE uid=%s", (uid,)
            ).fetchone()
        return None if row is None else row["quantity"]

    def set_profession(self, profession_id, *, actions=(), xp=0, counters=(0, 0, 0, 0)):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO account_professions(account_id,profession_id,xp,counters,actions) "
                "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(account_id,profession_id) DO UPDATE "
                "SET xp=EXCLUDED.xp,counters=EXCLUDED.counters,actions=EXCLUDED.actions",
                (self.account, profession_id, xp, list(counters), list(actions)),
            )

    def profession(self, profession_id):
        with self.store.connection() as db:
            return db.execute(
                "SELECT xp,counters,actions FROM account_professions "
                "WHERE account_id=%s AND profession_id=%s",
                (self.account, profession_id),
            ).fetchone()

    def test_seed_matches_all_native_recipe_action_descriptors(self):
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT item_ref,action_id,native_class,profession_id,recipe_ids,has_criteria "
                "FROM native_recipe_learning_actions ORDER BY native_class,item_ref"
            ).fetchall()
        self.assertEqual(len(rows), 132)
        self.assertEqual(
            {
                kind: sum(row["native_class"] == kind for row in rows)
                for kind in ("bIB", "bIz")
            },
            {"bIB": 54, "bIz": 78},
        )
        self.assertTrue(all(row["has_criteria"] is False for row in rows))
        self.assertTrue(
            all(row["profession_id"] > 0 and row["recipe_ids"] for row in rows)
        )

        # Cross-check every persisted action against the server's authoritative
        # item-action index, not merely the two examples used by transaction tests.
        from wakfu_server.haven_bag_furniture_knowledge import _rules

        native = _rules()
        for row in rows:
            descriptor = native.get(row["item_ref"])
            self.assertIsNotNone(descriptor, row["item_ref"])
            self.assertEqual(descriptor.get("use_action_class"), row["native_class"])
            self.assertEqual(descriptor.get("use_action_id"), row["action_id"])
            self.assertIs(descriptor.get("use_has_criteria"), False)

        # The checked-in native export is useful as a compact independent oracle
        # for the two action classes, while the production test remains DB-isolated.
        export = (
            Path(__file__).resolve().parents[2]
            / ".runtime/recipe-learning-audit-20261018/native-recipe-actions.json"
        )
        if export.exists():
            expected = json.loads(export.read_text())
            self.assertEqual(len(expected), 132)
            self.assertEqual(
                {
                    (
                        row["item_ref"],
                        row["action_id"],
                        row["native_class"],
                        row["profession_id"],
                        tuple(row["recipe_ids"]),
                    )
                    for row in rows
                },
                {
                    (
                        row["item_ref"],
                        row["action_id"],
                        row["native_class"],
                        row["profession_id"],
                        tuple(row["recipe_ids"]),
                    )
                    for row in expected
                },
            )

    def test_bib_book_consumes_once_and_replays_after_source_is_gone(self):
        self.set_profession(79, xp=900, counters=(1, 2, 3, 4))
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO account_craft_state(account_id,configuration,additional) "
                "VALUES(%s,%s,%s) ON CONFLICT(account_id) DO UPDATE "
                "SET configuration=EXCLUDED.configuration,additional=EXCLUDED.additional",
                (self.account, b"\x08\x07", b"\x18\x09"),
            )
        uid = self.add_item(15992, quantity=1)
        first = self.learn(uid, 7950)
        self.assertTrue(first["applied"])
        self.assertEqual(first["packets"][0], (12470, struct.pack(">qh", uid, -1)))
        self.assertIn(13186, [packet[0] for packet in first["packets"]])
        self.assertEqual(first["packets"][-1][0], 13873)
        self.assertIsNone(self.quantity(uid))
        state = self.profession(79)
        self.assertEqual(
            (state["xp"], state["counters"], state["actions"]),
            (900, [1, 2, 3, 4], [3796]),
        )

        replay = self.learn(uid, 7950)
        self.assertFalse(replay["applied"])
        self.assertEqual([packet[0] for packet in replay["packets"]], [13873])
        self.assertIsNone(self.quantity(uid))
        with self.reopen().connection() as db:
            row = db.execute(
                "SELECT profession_id,recipe_ids FROM recipe_learning_receipts "
                "WHERE account_id=%s AND source_uid=%s",
                (self.account, uid),
            ).fetchone()
            reopened_packet = account_packet(db, self.account)
        self.assertEqual((row["profession_id"], row["recipe_ids"]), (79, [3796]))
        self.assertEqual(reopened_packet, first["packets"][-1])

    def test_biz_book_unions_partially_known_recipes_and_rejects_fully_known_book(self):
        self.set_profession(80, actions=(3759,), xp=75)
        uid = self.add_item(19804, quantity=2)
        learned = self.learn(uid, 7622)
        self.assertTrue(learned["applied"])
        self.assertEqual(self.profession(80)["actions"], [3759, 4806, 4814])
        self.assertEqual(learned["packets"][0], (12470, struct.pack(">qh", uid, -1)))
        incremental = [
            struct.unpack(">ii", packet[1])[1]
            for packet in learned["packets"]
            if packet[0] == 13186
        ]
        self.assertEqual(incremental, [4806, 4814])
        self.assertEqual(learned["packets"][-1][0], 13873)

        another_uid = self.add_item(19804)
        with self.assertRaisesRegex(ValueError, "already learned"):
            self.learn(another_uid, 7622)
        self.assertEqual(self.quantity(another_uid), 1)
        self.assertEqual(self.profession(80)["actions"], [3759, 4806, 4814])

    def test_retired_native_book_output_is_learnable_without_craft_catalog_entry(self):
        # Native eTe.fM stores the action's recipe ID directly; some historical
        # books reference recipes no longer present in the server craft catalog.
        self.set_profession(76, xp=400, counters=(4, 3, 2, 1))
        uid = self.add_item(19456)
        result = self.learn(uid, 7378)
        self.assertTrue(result["applied"])
        self.assertEqual(self.profession(76)["actions"], [3659])
        self.assertEqual([packet[0] for packet in result["packets"]], [12470, 13873])
        with self.reopen().connection() as db:
            receipt = db.execute(
                "SELECT source_ref,action_id,profession_id,recipe_ids "
                "FROM recipe_learning_receipts WHERE account_id=%s AND source_uid=%s",
                (self.account, uid),
            ).fetchone()
        self.assertEqual(
            (
                receipt["source_ref"],
                receipt["action_id"],
                receipt["profession_id"],
                receipt["recipe_ids"],
            ),
            (19456, 7378, 76, [3659]),
        )

    def test_missing_native_profession_rejects_without_learning_or_consuming(self):
        uid = self.add_item(15992)
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM account_professions WHERE account_id=%s AND profession_id=79",
                (self.account,),
            )
        with self.assertRaisesRegex(ValueError, "requires its native profession"):
            self.learn(uid, 7950)
        self.assertEqual(self.quantity(uid), 1)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM recipe_learning_receipts WHERE account_id=%s AND source_uid=%s",
                    (self.account, uid),
                ).fetchone()
            )
        self.assertEqual(self.quantity(uid), 1)

    def test_bib_known_recipe_wrong_action_foreign_item_and_stale_lease_do_not_mutate(
        self,
    ):
        self.set_profession(79, actions=(3796,))
        uid = self.add_item(15992)
        with self.assertRaisesRegex(ValueError, "already learned"):
            self.learn(uid, 7950)
        self.assertEqual(self.quantity(uid), 1)
        with self.assertRaises(ValueError):
            self.learn(uid, 7951)
        self.assertEqual(self.quantity(uid), 1)

        foreign = self.store.register("recipe_foreign", "password-test")["id"]
        other = self.store.create_character(foreign, "Foreign Recipe Owner")
        other_generation = self.store.begin_session(foreign)
        self.store.select_character(foreign, other_generation, other["id"])
        foreign_uid = self.add_item(15992, character_id=other["id"])
        with self.assertRaises(ValueError):
            self.learn(foreign_uid, 7950)
        self.assertEqual(self.quantity(foreign_uid), 1)

        self.store.end_session(self.account, self.generation)
        with self.assertRaises(ValueError):
            self.learn(uid, 7950)
        self.assertEqual(self.quantity(uid), 1)
        self.assertEqual(self.profession(79)["actions"], [3796])
