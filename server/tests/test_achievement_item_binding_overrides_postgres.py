"""Native three-parameter item rewards retain binding, pet state and retries."""

import struct
import unittest

from postgres_case import PostgresCase
from wakfu_server.achievements import rewards, service, storage
from wakfu_server import item_binding


class AchievementItemBindingOverridePostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("reward-binding", "local-password")["id"]
        self.character = self.store.create_character(self.account, "Bound Reward")

    def test_gemlin_reward_retains_native_binding_pet_state_wire_and_exactly_once(self):
        reward = dict(d=10398, aeV=5, ckk=False, ckl=[12237, 1, 4])
        self.assertEqual(rewards.validate(reward), (5, (12237, 1, 4)))
        with self.store.connection() as db:
            service._owner(db, self.character)
            storage.claim_reward(db, self.character["id"], 5593, "once", 10398, reward)
            packets = service.drain_rewards(db, self.store, self.character)
            self.assertEqual([opcode for opcode, _ in packets], [12471])
            from wakfu_server.wire import proto_fields

            packet = packets[0][1]
            size = struct.unpack_from(">I", packet, 10)[0]
            encoded = dict(proto_fields(packet[14 : 14 + size]))
            self.assertEqual(dict(proto_fields(encoded[442])), {8: 4, 16: 1})
            item = next(
                item
                for item in self.store.character(
                    self.account, self.character["id"], db
                )["inventory_items"]
                if item["reference"] == 12237
            )
            self.assertEqual((item["binding_type"], item["bound"]), (4, True))
            self.assertEqual(item_binding.binary_option(item), bytes((1, 4, 1)))
            self.assertEqual(item["pet"]["model_id"], 5)
            self.assertEqual(item["pet"]["health"], 20)
            self.assertEqual(service.drain_rewards(db, self.store, self.character), [])
            saved_uid = item["uid"]
        with self.store.connection() as db:
            item = next(
                item
                for item in self.store.character(
                    self.account, self.character["id"], db
                )["inventory_items"]
                if item["reference"] == 12237
            )
            self.assertEqual(item["uid"], saved_uid)
            self.assertEqual((item["binding_type"], item["bound"]), (4, True))
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM inventory_pets WHERE uid=%s",
                    (saved_uid,),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(service.drain_rewards(db, self.store, self.character), [])

    def test_rollbacks_preserve_pending_entitlement_and_override_stack_identity(self):
        legacy = dict(d=1, aeV=5, ckl=[2021, 1])
        bound = dict(d=2, aeV=5, ckl=[2021, 1, 4])
        with self.store.connection() as db:
            service._owner(db, self.character)
            rewards.grant(db, self.store, self.character, legacy)
            storage.claim_reward(db, self.character["id"], 5591, "once", 2, bound)
            with self.assertRaisesRegex(RuntimeError, "rollback reward"):
                with db.transaction():
                    service.drain_rewards(db, self.store, self.character)
                    raise RuntimeError("rollback reward")
            self.assertEqual(len(storage.pending_rewards(db, self.character["id"])), 1)
            service.drain_rewards(db, self.store, self.character)
            items = self.store.character(self.account, self.character["id"], db)[
                "inventory_items"
            ]
            self.assertEqual(len(items), 2)
            self.assertEqual(
                sorted(
                    (
                        item.get("binding_type", 0),
                        item.get("bound", False),
                        item["quantity"],
                    )
                    for item in items
                ),
                [(0, False, 1), (4, True, 1)],
            )
            # A further plain reward must not merge into the explicit override.
            rewards.grant(db, self.store, self.character, legacy)
            items = self.store.character(self.account, self.character["id"], db)[
                "inventory_items"
            ]
            self.assertEqual(
                sorted(
                    (item.get("binding_type", 0), item["quantity"]) for item in items
                ),
                [(0, 2), (4, 1)],
            )

    def test_binding_override_native_enum_validation_and_custody(self):
        for value in (True, -1, 9, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                rewards.validate(dict(aeV=5, ckl=[12237, 1, value]))
        self.assertEqual(
            rewards.validate(dict(aeV=5, ckl=[2021, 1, 0])), (5, (2021, 1, 0))
        )
        item = dict(uid=50, reference=12237)
        projected = item_binding.from_custody(
            item,
            {
                "inventory_item_bindings": dict(
                    uid=50, template_reference=12237, bound=True, binding_type=4
                )
            },
        )
        self.assertEqual(item_binding.binary_option(projected), bytes((1, 4, 1)))
        from wakfu_server.haven_chest import _snapshot

        unit = dict(item, character_id=self.character["id"])
        account_binding = {
            "inventory_item_bindings": dict(
                uid=50, template_reference=12237, bound=True, binding_type=4
            )
        }
        self.assertNotIn(
            "binding_owner_character_id",
            _snapshot(None, unit, metadata=account_binding),
        )
        account_binding["inventory_item_bindings"]["binding_type"] = 2
        self.assertEqual(
            _snapshot(None, unit, metadata=account_binding)[
                "binding_owner_character_id"
            ],
            self.character["id"],
        )

    def test_native_split_preserves_account_override_and_character_override_stays_owned(
        self,
    ):
        from wakfu_server.characters import heroes
        from wakfu_server.inventory_move import transfer
        from wakfu_server.inventory_uids import reserve

        hero = self.store.create_character(self.account, "Reward Hero")
        generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, generation, self.character["id"])
        heroes.add(
            self.store, self.account, generation, self.character["id"], hero["id"]
        )
        with self.store.connection() as db:
            service._owner(db, self.character)
            rewards.grant(
                db, self.store, self.character, dict(aeV=5, ckl=[2021, 10, 4])
            )
            unit = self.store.character(self.account, self.character["id"], db)[
                "inventory_items"
            ][0]
        clone = reserve(
            self.store, self.account, generation, self.character["id"], count=1
        )["uids"][0]
        destination = hero["inventory_containers"][0]["uid"]
        transfer(
            self.store,
            self.account,
            generation,
            self.character["id"],
            struct.pack(
                ">qqqhBqh", unit["uid"], destination, unit["container"], 0, 1, clone, 3
            ),
        )
        received = self.reopen().character(self.account, hero["id"])["inventory_items"][
            0
        ]
        self.assertEqual(
            (
                received["uid"],
                received["quantity"],
                received["binding_type"],
                received["bound"],
            ),
            (clone, 3, 4, True),
        )
        with self.store.connection() as db:
            item_binding.save_override(db, unit["uid"], 2021, 2)
        with self.assertRaisesRegex(ValueError, "Character-bound"):
            transfer(
                self.store,
                self.account,
                generation,
                self.character["id"],
                struct.pack(
                    ">qqqhB", unit["uid"], destination, unit["container"], 1, 0
                ),
            )


if __name__ == "__main__":
    unittest.main()
