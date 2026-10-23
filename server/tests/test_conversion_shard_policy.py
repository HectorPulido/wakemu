"""Lossless Wakemu conversion policy, using original destination constraints."""
import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import conversion_item_actions as actions
from wakfu_server.conversion_shard_policy import validate_target
from wakfu_server.wire import proto_field


def socket_state(*, reference=0, amount=0, color=1, charges=0):
    row = (
        proto_field(80, 0)
        + proto_field(88, reference)
        + proto_field(96, color)
        + proto_field(112, amount)
    )
    return proto_field(10, row) + proto_field(72, charges)


class ConversionShardPolicyTests(unittest.TestCase):
    def test_native_contracts_and_complete_state_are_validated_without_rewriting(self):
        from wakfu_server.shard_identification import _catalog
        from wakfu_server.socket_enchantment import _bonus_catalog

        sockets = _catalog()
        compatible = []
        for plan in actions.descriptors()["items"]:
            try:
                target = actions.identified_contract(plan)
            except ValueError:
                continue
            source = sockets.get(plan["item_ref"])
            if source is None:
                continue
            compatible.append(plan["item_ref"])
            self.assertEqual(
                {
                    key: source[key]
                    for key in ("item_level", "min_sockets", "max_sockets")
                },
                {
                    key: sockets[target][key]
                    for key in ("item_level", "min_sockets", "max_sockets")
                },
            )
            state = socket_state(charges=12)
            self.assertIs(validate_target(None, target, state), state)
        self.assertEqual(len(compatible), 99)
        bonus = next(row for row in _bonus_catalog().values() if row["selectable"])
        state = socket_state(
            reference=bonus["reference"], amount=bonus["costs"][0], color=bonus["color"]
        )
        self.assertEqual(validate_target(None, 21150, state), state)
        with patch(
            "wakfu_server.sublimation_eligibility.pattern",
            return_value=dict(tag=24, kind="BASIC", colors=(1,)),
        ):
            attached = socket_state() + proto_field(24, 123)
            self.assertEqual(validate_target(None, 21150, attached), attached)
        for state in (
            socket_state(color=0),
            socket_state(charges=256),
            socket_state(reference=123, amount=1),
            socket_state(reference=bonus["reference"], amount=2147483647),
            socket_state() + proto_field(18, b""),
            socket_state() + proto_field(800, 1),
            socket_state() + proto_field(72, 1),
        ):
            with self.subTest(state=state), self.assertRaises(ValueError):
                validate_target(None, 21150, state)
        with patch(
            "wakfu_server.sublimation_eligibility.pattern",
            return_value=dict(tag=32, kind="RELIC", colors=()),
        ), patch(
            "wakfu_server.sublimation_eligibility.special_target",
            side_effect=ValueError("wrong rarity"),
        ):
            with self.assertRaises(ValueError):
                validate_target(None, 21150, socket_state() + proto_field(32, 123))


class ConversionShardPostgresTests(PostgresCase):
    def fixture(self):
        from test_conversion_item_actions import ConversionItemPostgresTests

        return ConversionItemPostgresTests.fixture(self)

    def give(self, *args, **kwargs):
        from test_conversion_item_actions import ConversionItemPostgresTests

        return ConversionItemPostgresTests.give(self, *args, **kwargs)

    def body(self, item):
        from test_conversion_item_actions import ConversionItemPostgresTests

        return ConversionItemPostgresTests.body(self, item)

    def test_real_12487_preserves_exact_generated_state_on_fresh_main_only(self):
        from wakfu_server.element_selection import select, _required_counts

        account, generation, character = self.fixture()
        source = self.give(account, generation, character, 24040)
        counts = _required_counts(24040)
        damage = sum(1 << (i + 1) for i in range(counts["damage_elements"]))
        resistance = sum(1 << (i + 1) for i in range(counts["resistance_elements"]))
        select(
            self.store,
            account,
            generation,
            character["id"],
            struct.pack(">qBB", source["uid"], damage, resistance),
        )
        with self.store.connection() as db:
            original = bytes(
                db.execute(
                    "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                    (source["uid"],),
                ).fetchone()["shard_state"]
            )
        resident = self.give(account, generation, character, 21150, slot=1)
        result = actions.use(
            self.store,
            account,
            generation,
            character["id"],
            self.body(source),
            in_fight=False,
        )
        main = next(
            row
            for row in result["character"]["inventory_items"]
            if row["reference"] == 21150 and row["uid"] != resident["uid"]
        )
        self.assertNotEqual(main["uid"], source["uid"])
        self.assertEqual(main["shard_state"], original)
        self.assertEqual(
            (main["damage_elements"], main["resistance_elements"]), (damage, resistance)
        )
        for item in result["character"]["inventory_items"]:
            if item["uid"] != main["uid"]:
                self.assertNotIn("shard_state", item)
        self.assertEqual(
            main,
            next(
                row
                for row in self.reopen().character(account, character["id"])[
                    "inventory_items"
                ]
                if row["uid"] == main["uid"]
            ),
        )

    def test_installed_bonus_preserved_and_invalid_extension_rolls_back(self):
        from wakfu_server.socket_enchantment import _bonus_catalog

        account, generation, character = self.fixture()
        bonus = next(row for row in _bonus_catalog().values() if row["selectable"])
        source = self.give(account, generation, character, 24040)
        state = socket_state(
            reference=bonus["reference"],
            amount=bonus["costs"][0],
            color=bonus["color"],
            charges=7,
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_shards(uid,shard_state) VALUES(%s,%s)",
                (source["uid"], state),
            )
        result = actions.use(
            self.store,
            account,
            generation,
            character["id"],
            self.body(source),
            in_fight=False,
        )
        main = next(
            row
            for row in result["character"]["inventory_items"]
            if row["reference"] == 21150
        )
        self.assertEqual(main["shard_state"], state)
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM inventory_items WHERE character_id=%s", (character["id"],)
            )
        source = self.give(account, generation, character, 24040)
        invalid = state + proto_field(800, 1)
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_shards(uid,shard_state) VALUES(%s,%s)",
                (source["uid"], invalid),
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
                bytes(
                    db.execute(
                        "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                        (source["uid"],),
                    ).fetchone()["shard_state"]
                ),
                invalid,
            )
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE uid=%s",
                    (source["uid"],),
                ).fetchone()["quantity"],
                1,
            )

    def test_shard_capacity_failure_restores_source_and_every_refund(self):
        from wakfu_server.combat_drop_delivery import _container_can_hold

        account, generation, character = self.fixture()
        source = self.give(account, generation, character, 24040)
        state = socket_state(charges=12)
        for bag in character["inventory_containers"]:
            if _container_can_hold(bag, character["id"]):
                for slot in range(1 if bag["kind"] == 0 else 0, bag["capacity"]):
                    self.give(
                        account,
                        generation,
                        character,
                        9724,
                        slot=slot,
                        container=bag["uid"],
                    )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_shards(uid,shard_state) VALUES(%s,%s)",
                (source["uid"], state),
            )
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
            self.assertEqual(
                before,
                list(
                    db.execute(
                        "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                        (character["id"],),
                    )
                ),
            )
            self.assertEqual(
                bytes(
                    db.execute(
                        "SELECT shard_state FROM inventory_item_shards WHERE uid=%s",
                        (source["uid"],),
                    ).fetchone()["shard_state"]
                ),
                state,
            )
