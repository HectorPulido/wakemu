"""Reward delivery must keep items with random-use history as distinct UIDs."""
import struct
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.combat_drop_delivery import _container_can_hold, _identified_uids
from wakfu_server.inventory_items import grant
from wakfu_server.item_action_delivery import grant_outputs
from wakfu_server.random_item_actions import use


class RewardNonceMergePostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("reward-nonce-owner", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Reward Nonce Owner")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.bag = next(
            row for row in self.character["inventory_containers"] if row["kind"] == 0
        )

    def box(self, quantity=2):
        return grant(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            reference=12408,
            quantity=quantity,
            container=self.bag["uid"],
            slot=0,
            allowed_references={12408},
        )

    @staticmethod
    def use_body(uid):
        from wakfu_server.haven_bag_furniture_knowledge import _rules

        return struct.pack(">iq", _rules()[12408]["use_action_id"], uid)

    def test_item_action_reward_does_not_merge_into_nonce_bearing_stack(self):
        source = self.box()
        # 12408 is a visible single-outcome box. Use one real qualified
        # outcome so its native 13817 presentation packet remains valid.
        with patch(
            "wakfu_server.random_item_actions.draw_products", return_value={12127: 1}
        ):
            use(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                self.use_body(source["uid"]),
                in_fight=False,
            )

        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT next_use FROM random_item_use_counters WHERE source_uid=%s",
                    (source["uid"],),
                ).fetchone()["next_use"],
            )
            character = self.store.character(self.account, self.character["id"], db)
            outcome = grant_outputs(
                self.store, db, self.account, self.generation, character, {12408: 1}
            )
            # 12408 is not a qualified achievement descriptor in the reviewed
            # catalog; exercise only the shared native item-reward grant path.
            from wakfu_server.achievements.rewards import _item

            reward_packets = _item(db, self.store, outcome["character"], 12408, 1)

        rows = [
            row
            for row in self.store.character(self.account, self.character["id"])[
                "inventory_items"
            ]
            if row["reference"] == 12408
        ]
        self.assertEqual(2, len(rows))
        by_uid = {row["uid"]: row["quantity"] for row in rows}
        self.assertEqual(1, by_uid[source["uid"]])
        new_uid = next(uid for uid in by_uid if uid != source["uid"])
        self.assertEqual(2, by_uid[new_uid])
        self.assertTrue(any(opcode == 12471 for opcode, _ in outcome["packets"]))
        self.assertFalse(any(opcode == 12470 for opcode, _ in outcome["packets"]))
        self.assertTrue(any(opcode == 12470 for opcode, _ in reward_packets))
        with self.store.connection() as db:
            self.assertEqual(
                1,
                db.execute(
                    "SELECT next_use FROM random_item_use_counters WHERE source_uid=%s",
                    (source["uid"],),
                ).fetchone()["next_use"],
            )
            self.assertIsNone(
                db.execute(
                    "SELECT next_use FROM random_item_use_counters WHERE source_uid=%s",
                    (new_uid,),
                ).fetchone()
            )

    def test_full_bags_roll_back_consumption_and_nonce_when_output_cannot_place(self):
        from wakfu_server.achievements.rewards import RewardCapacity

        source = self.box()
        for container in self.character["inventory_containers"]:
            if not _container_can_hold(container, self.character["id"]):
                continue
            start = 1 if container["uid"] == self.bag["uid"] else 0
            for slot in range(start, container["capacity"]):
                with self.store.connection() as db:
                    db.execute(
                        "INSERT INTO inventory_items(character_id,reference,quantity,container,slot) "
                        "VALUES(%s,9724,1,%s,%s)",
                        (self.character["id"], container["uid"], slot),
                    )
        before = self.store.character(self.account, self.character["id"])[
            "inventory_items"
        ]
        with patch(
            "wakfu_server.random_item_actions.draw_products", return_value={12408: 1}
        ):
            with self.assertRaises(RewardCapacity):
                use(
                    self.store,
                    self.account,
                    self.generation,
                    self.character["id"],
                    self.use_body(source["uid"]),
                    in_fight=False,
                )
        self.assertEqual(
            before,
            self.store.character(self.account, self.character["id"])["inventory_items"],
        )
        with self.store.connection() as db:
            self.assertEqual(
                2,
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (source["uid"],),
                ).fetchone()["quantity"],
            )
            self.assertIsNone(
                db.execute(
                    "SELECT next_use FROM random_item_use_counters WHERE source_uid=%s",
                    (source["uid"],),
                ).fetchone()
            )

    def test_combat_drop_identifies_nonce_bearing_stack_as_nonmergeable(self):
        source = self.box(quantity=1)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO random_item_use_counters(source_uid,next_use) VALUES(%s,3)",
                (source["uid"],),
            )
            owned = db.execute(
                "SELECT uid,reference,quantity,container,slot FROM inventory_items WHERE uid=%s",
                (source["uid"],),
            ).fetchone()
            self.assertIn(source["uid"], _identified_uids(db, [dict(owned)]))
