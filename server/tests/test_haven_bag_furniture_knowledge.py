"""Learning authorization, atomicity, replay and native account snapshots."""
import copy
import struct
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from wakfu_server import haven_bag_furniture_knowledge as knowledge


class Result:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)


class Store:
    def __init__(self):
        self.items = {
            80: {"uid": 80, "character_id": 42, "reference": 6293, "quantity": 2}
        }
        self.refs = set()
        self.receipts = {}
        self.fail_receipt = False

    @contextmanager
    def connection(self):
        before = copy.deepcopy((self.items, self.refs, self.receipts))
        try:
            yield self
        except Exception:
            self.items, self.refs, self.receipts = before
            raise

    def now(self):
        return 0

    def lock_character(self, db, account, generation, character):
        if (account, generation, character) != (7, 11, 42):
            raise ValueError("Invalid session")

    def character(self, account, character, db):
        return {
            "id": character,
            "builds": {},
            "inventory_items": copy.deepcopy(self.items),
        }

    def execute(self, sql, args=()):
        sql = " ".join(sql.split())
        if sql.startswith("SELECT character_id FROM sessions"):
            return Result([{"character_id": 42}] if args[:2] == (7, 11) else [])
        if sql.startswith("SELECT id FROM characters"):
            return Result([{"id": 42}] if args == (42, 7) else [])
        if sql.startswith("SELECT uid,character_id FROM inventory_items"):
            return Result(
                [
                    dict(uid=uid, character_id=self.items[uid]["character_id"])
                    for uid in args[0]
                    if uid in self.items
                ]
            )
        if sql.startswith("SELECT 1 FROM account_hero_slots"):
            return Result()
        if sql.startswith("SELECT id FROM accounts"):
            return Result([{"id": 7}])
        if sql.startswith("SELECT * FROM furniture_learning_receipts"):
            prior = self.receipts.get(args)
            return Result([prior] if prior else [])
        if sql.startswith("SELECT * FROM inventory_items"):
            row = self.items.get(args[0])
            return Result([row] if row and row["character_id"] == args[1] else [])
        if sql.startswith("SELECT 1 FROM inventory_"):
            return Result()
        if sql.startswith("SELECT 1 FROM account_furniture_knowledge"):
            return Result([{}] if args in self.refs else [])
        if sql.startswith("SELECT item_ref FROM account_furniture_knowledge"):
            return Result(
                [
                    {"item_ref": ref}
                    for account, ref in sorted(self.refs)
                    if account == args[0]
                ]
            )
        if sql.startswith("INSERT INTO account_furniture_knowledge"):
            self.refs.add(args)
            return Result()
        if sql.startswith("UPDATE inventory_items"):
            self.items[args[0]]["quantity"] -= 1
            return Result()
        if sql.startswith("DELETE FROM inventory_items"):
            del self.items[args[0]]
            return Result()
        if sql.startswith("INSERT INTO furniture_learning_receipts"):
            if self.fail_receipt:
                raise RuntimeError("Receipt failure")
            account, uid, character, source_ref, action, refs = args
            self.receipts[account, uid] = {
                "character_id": character,
                "action_id": action,
                "learned_refs": refs,
            }
            return Result()
        raise AssertionError(sql)


class FurnitureKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.rules = {
            6293: {
                "use_action_class": "bIx",
                "use_action_id": 466,
                "use_has_criteria": False,
            }
        }
        reader = patch.object(knowledge, "_rules", return_value=self.rules)
        reader.start()
        self.addCleanup(reader.stop)
        sources = patch.object(knowledge, "_source_refs", return_value=[6293, 17419])
        sources.start()
        self.addCleanup(sources.stop)

    def learn(self, body=None):
        return knowledge.learn(
            self.store, 7, 11, 42, body or struct.pack(">iq", 466, 80)
        )

    def test_learns_bundle_consumes_one_and_encodes_native_packets(self):
        result = self.learn()
        self.assertTrue(result["applied"])
        self.assertEqual(self.store.items[80]["quantity"], 1)
        self.assertEqual(self.store.refs, {(7, 6293), (7, 17419)})
        packets = dict(result["packets"])
        self.assertEqual(packets[12470], struct.pack(">qh", 80, -1))
        self.assertEqual(packets[13247], struct.pack(">III?", 2, 6293, 17419, True))
        self.assertEqual(packets[13873][:12], struct.pack(">III", 1, 11, 11))
        self.assertEqual(packets[13873][12:], bytes.fromhex("0a030895310a04088b8801"))

    def test_receipt_replay_never_consumes_or_replays_inventory_delta(self):
        self.learn()
        replay = self.learn()
        self.assertFalse(replay["applied"])
        self.assertEqual(self.store.items[80]["quantity"], 1)
        self.assertEqual([opcode for opcode, _ in replay["packets"]], [13873])

    def test_failed_receipt_rolls_back_item_and_collection(self):
        self.store.fail_receipt = True
        with self.assertRaises(RuntimeError):
            self.learn()
        self.assertEqual(self.store.items[80]["quantity"], 2)
        self.assertFalse(self.store.refs)

    def test_forged_action_foreign_item_and_criteria_rejected(self):
        with self.assertRaises(ValueError):
            self.learn(struct.pack(">iq", 4543, 80))
        with self.assertRaises(ValueError):
            self.learn(struct.pack(">iq", 466, 81))
        self.rules[6293]["use_has_criteria"] = True
        with self.assertRaises(ValueError):
            self.learn()
        self.assertEqual(self.store.items[80]["quantity"], 2)

    def test_already_known_source_is_not_consumed(self):
        self.store.refs.update({(7, 6293), (7, 17419)})
        with self.assertRaisesRegex(ValueError, "already learned"):
            self.learn()
        self.assertEqual(self.store.items[80]["quantity"], 2)

    def test_malformed_packets_and_invalid_session_rejected(self):
        for body in (
            b"x",
            struct.pack(">iq", 466, -1),
            struct.pack(">iq", 466, 80) + b"x",
        ):
            with self.assertRaises(ValueError):
                self.learn(body)
        with self.assertRaises(ValueError):
            knowledge.learn(self.store, 8, 11, 42, struct.pack(">iq", 466, 80))

    def test_empty_account_component_and_account_scoped_knowledge(self):
        self.assertEqual(
            knowledge.packet(self.store, 7), (13873, struct.pack(">III", 1, 11, 0))
        )
        self.store.refs.add((8, 6293))
        self.assertFalse(knowledge.known(self.store, 7, 6293))
        self.assertTrue(knowledge.known(self.store, 8, 6293))


if __name__ == "__main__":
    unittest.main()
