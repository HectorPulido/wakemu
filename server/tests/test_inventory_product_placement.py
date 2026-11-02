"""Focused inventory placement regressions for harvest and recycling outputs."""
from copy import deepcopy
import struct
import unittest
import uuid
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.inventory_bag_rules import RULES
from wakfu_server.inventory_move import STACKS
from wakfu_server.inventory_product_placement import plan, plain_stack


CHARACTER_ID = 76
BASE_UID = 1099511651260
BAG_UIDS = (1099511651328, 1099511651415, 1099511651414)


def inventory_fixture(occupancy=(30, 20, 4, 0)):
    bags = [
        dict(
            uid=BASE_UID,
            character_id=CHARACTER_ID,
            reference=2175,
            kind=0,
            capacity=30,
            flags=0,
        ),
        *[
            dict(
                uid=uid,
                character_id=CHARACTER_ID,
                reference=12492,
                kind=kind,
                capacity=20,
                flags=0,
            )
            for uid, kind in zip(BAG_UIDS, (1, 2, 3))
        ],
    ]
    items = []
    uid = BASE_UID + 100
    for bag, count in zip(bags, occupancy):
        for slot in range(count):
            items.append(
                dict(
                    uid=uid,
                    character_id=CHARACTER_ID,
                    reference=12,
                    quantity=1,
                    container=bag["uid"],
                    slot=slot,
                )
            )
            uid += 1
    return dict(
        id=CHARACTER_ID, inventory_containers=bags, inventory_items=items, builds={}
    )


class InventoryProductPlacementTests(unittest.TestCase):
    def setUp(self):
        self.stack_rules = STACKS

    def make_plan(self, character, products, *, whole_quantity=False):
        return plan(
            character,
            products,
            stack_rules=self.stack_rules,
            mergeable=plain_stack,
            whole_quantity=whole_quantity,
        )

    def test_full_base_and_first_bag_places_harvest_into_next_native_slot(self):
        character = inventory_fixture()
        before = deepcopy(character)
        supported = sum(bag["capacity"] for bag in character["inventory_containers"])
        occupied = len(character["inventory_items"])
        self.assertEqual((supported, occupied, supported - occupied), (90, 54, 36))

        placement = self.make_plan(character, {30349: 1}, whole_quantity=True)

        self.assertEqual(
            placement,
            [
                dict(
                    uid=None,
                    reference=30349,
                    container=BAG_UIDS[1],
                    slot=4,
                    quantity=1,
                    added=1,
                )
            ],
        )
        self.assertEqual(character, before)

    def test_full_base_merges_into_a_plain_stack_in_an_ordinary_bag(self):
        character = inventory_fixture()
        rule = STACKS[30349]
        self.assertTrue(rule["minimal_mergeable"])
        resident = next(
            item
            for item in character["inventory_items"]
            if item["container"] == BAG_UIDS[0] and item["slot"] == 0
        )
        resident.update(reference=30349, quantity=rule["maximum"] - 1)

        placement = self.make_plan(character, {30349: 1}, whole_quantity=True)

        self.assertEqual(
            placement,
            [
                dict(
                    uid=resident["uid"],
                    reference=30349,
                    container=BAG_UIDS[0],
                    slot=0,
                    quantity=rule["maximum"],
                    added=1,
                )
            ],
        )

    def test_all_full_bags_split_a_yield_across_two_partial_native_stacks(self):
        character = inventory_fixture((30, 20, 20, 20))
        maximum = STACKS[30349]["maximum"]
        partials = [
            item
            for item in character["inventory_items"]
            if item["container"] in (BAG_UIDS[0], BAG_UIDS[1]) and item["slot"] == 0
        ]
        for item in partials:
            item.update(reference=30349, quantity=maximum - 1)

        placements = self.make_plan(character, {30349: 2})

        self.assertEqual(len(placements), 2)
        self.assertEqual(
            [row["uid"] for row in placements], [row["uid"] for row in partials]
        )
        self.assertEqual([row["quantity"] for row in placements], [maximum, maximum])
        self.assertEqual([row["added"] for row in placements], [1, 1])
        self.assertEqual(
            [row["container"] for row in placements], [BAG_UIDS[0], BAG_UIDS[1]]
        )

    def test_specialized_wrong_capacity_and_foreign_bags_cannot_receive_products(self):
        specialized = next(
            row
            for row in RULES.values()
            if row["reference"] != 2175
            and (row["accepted_types"] or row["has_equip_criteria"])
        )
        base_only = inventory_fixture((30, 0, 0, 0))
        base_only["inventory_containers"] = base_only["inventory_containers"][:1]
        base_only["inventory_containers"].append(
            dict(
                uid=7001,
                character_id=CHARACTER_ID,
                reference=specialized["reference"],
                kind=1,
                capacity=specialized["capacity"],
                flags=0,
            )
        )
        with self.assertRaisesRegex(ValueError, "no supported ordinary bag space"):
            self.make_plan(base_only, {30349: 1})

        wrong_capacity = inventory_fixture((30, 0, 0, 0))
        wrong_capacity["inventory_containers"] = wrong_capacity["inventory_containers"][
            :1
        ]
        wrong_capacity["inventory_containers"].append(
            dict(
                uid=7002,
                character_id=CHARACTER_ID,
                reference=12492,
                kind=1,
                capacity=19,
                flags=0,
            )
        )
        with self.assertRaisesRegex(ValueError, "no supported ordinary bag space"):
            self.make_plan(wrong_capacity, {30349: 1})

        foreign = inventory_fixture((30, 0, 0, 0))
        foreign["inventory_containers"] = foreign["inventory_containers"][:1]
        foreign["inventory_containers"].append(
            dict(
                uid=7003,
                character_id=999,
                reference=12492,
                kind=1,
                capacity=20,
                flags=0,
            )
        )
        with self.assertRaisesRegex(ValueError, "Foreign inventory container"):
            self.make_plan(foreign, {30349: 1})

    def test_multiple_products_fail_atomically_when_only_one_slot_remains(self):
        character = inventory_fixture((30, 20, 19, 20))
        before = deepcopy(character)

        with self.assertRaisesRegex(ValueError, "no supported ordinary bag space"):
            self.make_plan(character, {30349: 1, 27093: 1})

        self.assertEqual(character, before)

    def test_harvest_grant_plans_before_any_sql_or_uid_allocation(self):
        from wakfu_server.harvest_inventory import grant

        class NoSql:
            def __init__(self):
                self.calls = []

            def execute(self, *args, **kwargs):
                self.calls.append((args, kwargs))
                raise AssertionError("A rejected product must not reach SQL")

        db = NoSql()
        character = inventory_fixture((30, 20, 20, 20))
        before = deepcopy(character)
        with patch(
            "wakfu_server.inventory_uids.allocate",
            side_effect=AssertionError("UID allocated before placement"),
        ):
            with self.assertRaisesRegex(ValueError, "no supported ordinary bag space"):
                grant(db, character, 30349, 1)
        self.assertEqual(db.calls, [])
        self.assertEqual(character, before)

    def test_recycling_commit_uses_the_preflight_product_destinations(self):
        from wakfu_server import recycling

        character = inventory_fixture((30, 20, 4, 0))
        character["inventory_items"][50].update(reference=27083, quantity=3)
        character["inventory_items"][51].update(reference=16163, quantity=2)
        source_uids = {
            character["inventory_items"][50]["uid"],
            character["inventory_items"][51]["uid"],
        }
        destination = dict(
            character,
            inventory_items=[
                item
                for item in character["inventory_items"]
                if item["uid"] not in source_uids
            ],
        )
        # The incident fixture's two source items occupy two of the four used
        # slots in bag 12492; the preview destination frees those same slots.
        products = {27083: 4, 27093: 3}

        class RecordingDb:
            def __init__(self):
                self.calls = []

            def execute(self, *args, **kwargs):
                self.calls.append((args, kwargs))

        db = RecordingDb()
        placements = recycling._product_plan(
            db,
            destination,
            products,
            offered_uids=set(),
            equipped_uids=set(),
        )
        allocated = iter((99001, 99002))
        with patch(
            "wakfu_server.inventory_uids.allocate",
            side_effect=lambda _db: next(allocated),
        ):
            _, grants = recycling._grant_products(
                db,
                destination,
                products,
                offered_uids=set(),
                equipped_uids=set(),
                placements=placements,
            )
        expected = [
            (row["reference"], row["container"], row["slot"], row["quantity"])
            for row in placements
        ]
        actual = [
            (row["reference"], row["container"], row["slot"], row["quantity"])
            for row in grants
        ]
        self.assertEqual(actual, expected)
        self.assertEqual(
            [(row["container"], row["slot"]) for row in placements],
            [(BAG_UIDS[1], 0), (BAG_UIDS[1], 1)],
        )
        self.assertEqual(len(db.calls), 2)


class InventoryProductPlacementPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.now = [2_000_000_000.0]
        self.store.clock = lambda: self.now[0]
        account_name = "placement-" + uuid.uuid4().hex[:12]
        self.account = self.store.register(account_name, "temporary-test-password")[
            "id"
        ]
        self.character = self.store.create_character(self.account, "Placement Test")
        self.generation = self.store.begin_session(self.account, ttl=10_000)
        self.store.select_character(self.account, self.generation, self.character["id"])
        self.character_id = self.character["id"]

    def _layout(self, occupancy):
        from wakfu_server.inventory_uids import allocate

        with self.store.connection() as db:
            db.execute(
                "DELETE FROM inventory_items WHERE character_id=%s",
                (self.character_id,),
            )
            db.execute(
                "DELETE FROM inventory_containers WHERE character_id=%s AND kind IN (2,3)",
                (self.character_id,),
            )
            db.execute(
                "UPDATE inventory_containers SET reference=12492,capacity=20,flags=0 "
                "WHERE character_id=%s AND kind=1",
                (self.character_id,),
            )
            for kind in (2, 3):
                db.execute(
                    "INSERT INTO inventory_containers(character_id,reference,kind,capacity,flags) "
                    "VALUES(%s,12492,%s,20,0)",
                    (self.character_id, kind),
                )
            containers = {
                row["kind"]: row["uid"]
                for row in db.execute(
                    "SELECT kind,uid FROM inventory_containers WHERE character_id=%s",
                    (self.character_id,),
                )
            }
            for kind, count in enumerate(occupancy):
                for slot in range(count):
                    uid = allocate(db)
                    db.execute(
                        "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
                        "VALUES(%s,%s,12,1,%s,%s)",
                        (uid, self.character_id, containers[kind], slot),
                    )
        return containers

    def _add_item(self, db, container, slot, reference, quantity):
        from wakfu_server.inventory_uids import allocate

        uid = allocate(db)
        db.execute(
            "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (uid, self.character_id, reference, quantity, container, slot),
        )
        return uid

    def _harvest(self, harvest, monster, rule):
        from wakfu_server.wire import proto_field

        body = proto_field(8, rule["action_id"]) + proto_field(
            16, monster["id"] % (2**64)
        )
        harvest.begin(
            self.account,
            self.generation,
            self.character_id,
            body,
            monster,
            profession_level=max(20, rule["required_level"]),
            reachable=True,
        )
        self.now[0] += max(1.0, rule["duration_ms"] / 1000)
        return harvest.complete(
            self.account,
            self.generation,
            self.character_id,
            b"\x02\x00\x06",
            monster=monster,
            profession_level=max(20, rule["required_level"]),
        )

    def test_harvest_item_grants_migration_checksum_and_replay_are_stable(self):
        from wakfu_server.postgres import migrate

        migration_dir = Path(__file__).resolve().parents[1] / "migrations"
        migration = migration_dir / "333_harvest_item_grants.sql"
        checksum = sha256(migration.read_bytes()).hexdigest()
        with self.store.connection() as db:
            row = db.execute(
                "SELECT checksum FROM schema_migrations WHERE version=333"
            ).fetchone()
            self.assertEqual(row["checksum"], checksum)
            self.assertEqual(migrate(db, migration_dir), 0)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM information_schema.columns "
                    "WHERE table_schema=current_schema() AND column_name='item_grants' "
                    "AND table_name IN ('monster_harvest_receipts','environment_interaction_tickets')"
                ).fetchone()["n"],
                2,
            )

    def test_harvest_success_full_base_and_first_bag_then_all_full_failure_is_atomic(
        self,
    ):
        from wakfu_server.monster_collect import Harvests, action
        from wakfu_server.profession_store import ensure_learned

        containers = self._layout((30, 20, 4, 0))
        rule = action(5379, 4967)
        self.assertEqual(rule["item_ref"], 30349)
        ensure_learned(
            self.store,
            self.account,
            self.generation,
            self.character_id,
            [rule["profession_id"]],
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=1134,instance_id=17,x=54,y=36,z=17 WHERE id=%s",
                (self.character_id,),
            )
        monster = dict(
            id=-8_881_234_567,
            ref=5379,
            hp=100,
            map_id=1134,
            instance_id=17,
            x=54,
            y=36,
            z=17,
        )
        harvest = Harvests(self.store)
        with patch("wakfu_server.territory_bonuses.current_region", return_value=None):
            success = self._harvest(harvest, monster, rule)
        self.assertTrue(success["applied"])
        with patch("wakfu_server.territory_bonuses.current_region", return_value=None):
            replay = harvest.complete(
                self.account,
                self.generation,
                self.character_id,
                b"\x02\x00\x06",
                monster=monster,
                profession_level=max(20, rule["required_level"]),
            )
        self.assertFalse(replay["applied"])
        self.assertEqual([], replay["packets"])
        current = self.store.character(self.account, self.character_id)
        product = next(
            item for item in current["inventory_items"] if item["reference"] == 30349
        )
        self.assertEqual((product["container"], product["slot"]), (containers[2], 4))
        self.assertEqual(product["quantity"], success["item"]["quantity"])
        with self.store.connection() as db:
            successful_receipts = db.execute(
                "SELECT count(*) AS n FROM monster_harvest_receipts WHERE character_id=%s",
                (self.character_id,),
            ).fetchone()["n"]
            receipt = db.execute(
                "SELECT item_uid,item_grants FROM monster_harvest_receipts "
                "WHERE character_id=%s ORDER BY completed_at DESC LIMIT 1",
                (self.character_id,),
            ).fetchone()
            xp_before = db.execute(
                "SELECT COALESCE(sum(applied_xp),0) AS xp FROM profession_xp_receipts "
                "WHERE character_id=%s",
                (self.character_id,),
            ).fetchone()["xp"]
        self.assertEqual(receipt["item_uid"], product["uid"])
        self.assertEqual(
            [grant["uid"] for grant in receipt["item_grants"]], [product["uid"]]
        )

        containers = self._layout((30, 20, 20, 20))
        before_failure = self.store.character(self.account, self.character_id)
        failed_monster = dict(monster, id=monster["id"] - 1)
        with patch("wakfu_server.territory_bonuses.current_region", return_value=None):
            with self.assertRaisesRegex(ValueError, "no supported ordinary bag space"):
                self._harvest(harvest, failed_monster, rule)
        after_failure = self.store.character(self.account, self.character_id)
        self.assertEqual(
            after_failure["inventory_items"], before_failure["inventory_items"]
        )
        self.assertIn(self.character_id, harvest.pending)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM monster_harvest_receipts WHERE character_id=%s",
                    (self.character_id,),
                ).fetchone()["n"],
                successful_receipts,
            )
            self.assertEqual(
                db.execute(
                    "SELECT COALESCE(sum(applied_xp),0) AS xp FROM profession_xp_receipts "
                    "WHERE character_id=%s",
                    (self.character_id,),
                ).fetchone()["xp"],
                xp_before,
            )
        self.assertFalse(
            any(item["reference"] == 30349 for item in after_failure["inventory_items"])
        )

        from wakfu_server.harvest_inventory import grant_products

        maximum = STACKS[30349]["maximum"]
        with self.store.connection() as db:
            first_partial = db.execute(
                "UPDATE inventory_items SET reference=30349,quantity=%s "
                "WHERE character_id=%s AND container=%s AND slot=0",
                (maximum - 1, self.character_id, containers[1]),
            )
            second_partial = db.execute(
                "UPDATE inventory_items SET reference=30349,quantity=%s "
                "WHERE character_id=%s AND container=%s AND slot=0",
                (maximum - 1, self.character_id, containers[2]),
            )
            self.assertEqual((first_partial.rowcount, second_partial.rowcount), (1, 1))
            stacked_character = self.store.character(
                self.account, self.character_id, db
            )
            from wakfu_server.inventory_product_placement import containers, plain_stack

            partials = [
                item
                for item in stacked_character["inventory_items"]
                if item["reference"] == 30349
            ]
            self.assertEqual(len(partials), 2)
            self.assertTrue(all(plain_stack(item) for item in partials), partials)
            self.assertEqual(len(containers(stacked_character)), 4)
            split = grant_products(db, stacked_character, {30349: 2})
        self.assertEqual(len(split["items"]), 2)
        self.assertEqual(len(split["packets"]), 2)
        self.assertTrue(all(packet[0] == 12470 for packet in split["packets"]))
        self.assertEqual(
            [row["quantity"] for row in split["items"]], [maximum, maximum]
        )
        self.assertEqual([row["added"] for row in split["grants"]], [1, 1])

    def test_recycling_commit_matches_the_all_products_preflight_plan(self):
        from wakfu_server import recycling

        containers = self._layout((30, 20, 0, 0))
        with self.store.connection() as db:
            source_a = self._add_item(db, containers[2], 0, 27083, 3)
            source_b = self._add_item(db, containers[2], 1, 16163, 2)
            for slot in (2, 3):
                self._add_item(db, containers[2], slot, 12, 1)
            character = self.store.character(self.account, self.character_id, db)
            selected = {source_a, source_b}
            destination_character = dict(
                character,
                inventory_items=[
                    item
                    for item in character["inventory_items"]
                    if item["uid"] not in selected
                ],
            )
            predicted_products = {27083: 4, 27093: 3}
            predicted = recycling._product_plan(
                db,
                destination_character,
                predicted_products,
                offered_uids=set(),
                equipped_uids=set(),
            )
        result = recycling.recycle(
            self.store,
            self.account,
            self.generation,
            self.character_id,
            recycling.recycling_wire.request([source_a, source_b])[1],
            rng=lambda: self.fail("Fixed native yields must not draw"),
        )
        self.assertTrue(result["applied"])
        self.assertEqual(
            result["receipt"]["products"],
            {str(key): value for key, value in predicted_products.items()},
        )
        actual = [
            (row["reference"], row["container"], row["slot"], row["quantity"])
            for row in result["product_grants"]
        ]
        expected = [
            (row["reference"], row["container"], row["slot"], row["quantity"])
            for row in predicted
        ]
        self.assertEqual(actual, expected)
        self.assertEqual(
            [(row["container"], row["slot"]) for row in predicted],
            [(containers[2], 0), (containers[2], 1)],
        )
        self.assertEqual(
            self.store.character(self.account, self.character_id)["inventory_items"],
            [row for row in result["character"]["inventory_items"]],
        )


if __name__ == "__main__":
    unittest.main()
