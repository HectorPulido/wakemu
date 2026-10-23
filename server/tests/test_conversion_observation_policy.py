"""Exact nullable recycling observations on native-equivalent bHF main units."""
import struct
import unittest
from itertools import product

from postgres_case import PostgresCase
from wakfu_server import conversion_item_actions as actions
from wakfu_server.conversion_observation_policy import validate_pair, validate_target


class ConversionObservationPolicyTests(unittest.TestCase):
    def test_all116_native_main_domains_and_nullable_row_shapes(self):
        plans = [
            plan
            for plan in actions.descriptors()["items"]
            if plan["main_reference"] > 0
        ]
        self.assertEqual(len(plans), 116)
        for plan in plans:
            for unidentified, socketed in product((None, False, True), repeat=2):
                if unidentified is None and socketed is None:
                    continue
                observation = dict(unidentified=unidentified, socketed=socketed)
                self.assertEqual(
                    validate_pair(
                        plan["item_ref"], plan["main_reference"], observation
                    ),
                    observation,
                )
        for observation in (
            dict(unidentified=None, socketed=None),
            dict(unidentified=1, socketed=False),
            dict(unidentified=False, socketed="false"),
            dict(unidentified=False),
            dict(unidentified=False, socketed=False, extra=True),
        ):
            with self.subTest(observation=observation), self.assertRaises(ValueError):
                validate_target(20720, observation)
        with self.assertRaises(ValueError):
            validate_pair(24110, 16367, dict(unidentified=True, socketed=None))


class ConversionObservationPostgresTests(PostgresCase):
    def fixture(self):
        from test_conversion_item_actions import ConversionItemPostgresTests

        return ConversionItemPostgresTests.fixture(self)

    def give(self, *args, **kwargs):
        from test_conversion_item_actions import ConversionItemPostgresTests

        return ConversionItemPostgresTests.give(self, *args, **kwargs)

    def body(self, item):
        from test_conversion_item_actions import ConversionItemPostgresTests

        return ConversionItemPostgresTests.body(self, item)

    def observation(self, uid, unidentified, socketed):
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) VALUES(%s,%s,%s)",
                (uid, unidentified, socketed),
            )

    def test_identified_main_retains_exact_observation_and_refunds_do_not_inherit_it(
        self,
    ):
        from wakfu_server.element_selection import select

        account, generation, character = self.fixture()
        for values in ((True, None), (None, False), (False, False)):
            with self.subTest(values=values):
                with self.store.connection() as db:
                    db.execute(
                        "DELETE FROM inventory_items WHERE character_id=%s",
                        (character["id"],),
                    )
                source = self.give(account, generation, character, 24110)
                select(
                    self.store,
                    account,
                    generation,
                    character["id"],
                    struct.pack(">qBB", source["uid"], 14, 0),
                )
                self.observation(source["uid"], *values)
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
                    if row["reference"] == 20720
                )
                self.assertNotEqual(main["uid"], source["uid"])
                self.assertEqual(
                    (main["damage_elements"], main["resistance_elements"]), (14, 0)
                )
                with self.reopen().connection() as db:
                    rows = list(
                        db.execute(
                            "SELECT s.* FROM inventory_item_recycling_state s JOIN inventory_items i USING(uid) WHERE i.character_id=%s",
                            (character["id"],),
                        )
                    )
                    self.assertEqual(len(rows), 1)
                    self.assertEqual(
                        (rows[0]["uid"], rows[0]["unidentified"], rows[0]["socketed"]),
                        (main["uid"], *values),
                    )
                before = self.store.character(account, character["id"])[
                    "inventory_items"
                ]
                with self.assertRaises(ValueError):
                    actions.use(
                        self.store,
                        account,
                        generation,
                        character["id"],
                        self.body(source),
                        in_fight=False,
                    )
                self.assertEqual(
                    before,
                    self.store.character(account, character["id"])["inventory_items"],
                )

    def test_installed_bonus_and_positive_socket_observation_survive_together(self):
        from wakfu_server.socket_enchantment import _bonus_catalog
        from wakfu_server.wire import proto_field

        account, generation, character = self.fixture()
        source = self.give(account, generation, character, 24040)
        bonus = next(row for row in _bonus_catalog().values() if row["selectable"])
        state = proto_field(
            10,
            proto_field(80, 0)
            + proto_field(88, bonus["reference"])
            + proto_field(96, bonus["color"])
            + proto_field(112, bonus["costs"][0]),
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO inventory_item_shards(uid,shard_state) VALUES(%s,%s)",
                (source["uid"], state),
            )
        self.observation(source["uid"], False, True)
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
            row = db.execute(
                "SELECT unidentified,socketed FROM inventory_item_recycling_state WHERE uid=%s",
                (main["uid"],),
            ).fetchone()
            self.assertEqual(dict(row), dict(unidentified=False, socketed=True))
        self.assertEqual(
            main["shard_state"],
            next(
                row
                for row in self.reopen().character(account, character["id"])[
                    "inventory_items"
                ]
                if row["uid"] == main["uid"]
            )["shard_state"],
        )

    def test_stack_observation_copies_one_unit_without_resetting_remaining_source(self):
        account, generation, character = self.fixture()
        source = self.give(account, generation, character, 24110, quantity=2)
        self.observation(source["uid"], True, None)
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
            if row["reference"] == 20720
        )
        remaining = next(
            row
            for row in result["character"]["inventory_items"]
            if row["uid"] == source["uid"]
        )
        self.assertEqual(remaining["quantity"], 1)
        with self.store.connection() as db:
            rows = list(
                db.execute(
                    "SELECT uid,unidentified,socketed FROM inventory_item_recycling_state WHERE uid=ANY(%s)",
                    ([source["uid"], main["uid"]],),
                )
            )
            self.assertEqual(len(rows), 2)
            self.assertTrue(
                all(
                    row["unidentified"] is True and row["socketed"] is None
                    for row in rows
                )
            )

    def test_refund_only_marker_and_capacity_failure_preserve_source_observations(self):
        from wakfu_server.combat_drop_delivery import _container_can_hold

        account, generation, character = self.fixture()
        refund_source = self.give(account, generation, character, 11080)
        self.observation(refund_source["uid"], None, False)
        with self.assertRaises(ValueError):
            actions.use(
                self.store,
                account,
                generation,
                character["id"],
                self.body(refund_source),
                in_fight=False,
            )
        with self.store.connection() as db:
            self.assertIsNotNone(
                db.execute(
                    "SELECT 1 FROM inventory_item_recycling_state WHERE uid=%s",
                    (refund_source["uid"],),
                ).fetchone()
            )
            db.execute(
                "DELETE FROM inventory_items WHERE character_id=%s", (character["id"],)
            )
        source = self.give(account, generation, character, 24110)
        self.observation(source["uid"], True, None)
        self.give(account, generation, character, 20720, slot=1)
        plan = next(
            row for row in actions.descriptors()["items"] if row["item_ref"] == 24110
        )
        next_slot = 2
        for reference in sorted(
            int(ref) for ref in plan["products"] if int(ref) not in (16367, 20720)
        ):
            self.give(account, generation, character, reference, slot=next_slot)
            next_slot += 1
        bag = character["inventory_containers"][0]["uid"]
        for container in character["inventory_containers"]:
            if _container_can_hold(container, character["id"]):
                for slot in range(
                    next_slot if container["uid"] == bag else 0, container["capacity"]
                ):
                    self.give(
                        account,
                        generation,
                        character,
                        9724,
                        slot=slot,
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
            self.assertEqual(
                before,
                list(
                    db.execute(
                        "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid",
                        (character["id"],),
                    )
                ),
            )
            row = db.execute(
                "SELECT unidentified,socketed FROM inventory_item_recycling_state WHERE uid=%s",
                (source["uid"],),
            ).fetchone()
            self.assertEqual(dict(row), dict(unidentified=True, socketed=None))
