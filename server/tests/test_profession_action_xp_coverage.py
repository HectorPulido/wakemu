"""Profession XP receipts across native planting and flora harvest actions."""
import json
import struct
from hashlib import sha256
import unittest

from postgres_case import PostgresCase
from wakfu_server.inventory_items import grant
from wakfu_server.monsters import REFERENCES, owned_instance
from wakfu_server.planting import (
    SEEDS,
    complete as complete_plant,
    prepare as prepare_plant,
)
from wakfu_server.profession_store import ensure_learned
from wakfu_server.resource_collect import (
    complete as complete_harvest,
    prepare as prepare_harvest,
    reserve as reserve_harvest,
)
from wakfu_server.paths import DATA_ROOT
from wakfu_server.wire import proto_field
from wakfu_server import native_catalog


SEED_COVERAGE = (
    # Native seed, profession, native minimum level.
    (1750, 64, 15),
    (8064, 71, 5),
    (4273, 72, 40),
    (6220, 74, 0),
    (7353, 82, 0),
)

# Native plant-resources.json rules with an unconditional primary product.
HARVEST_COVERAGE = (
    # profession, resource, stage, action, minimum level, primary product, duration
    (64, 23, 2, 94, 0, 4278, 3000),
    (71, 334, 2, 796, 25, 10008, 3000),
    (72, 351, 2, 854, 30, 11455, 3000),
    (73, 433, 1, 1119, 60, 13180, 6000),
    (75, 259, 2, 603, 25, 8113, 6000),
    (82, 163, 2, 247, 0, 22516, 3000),
)


def _level_xp(level):
    return 75 * level * level


def _harvest_request(action_id, x, y):
    def unsigned(value):
        return value if value >= 0 else value + (1 << 64)

    return (
        proto_field(8, action_id)
        + proto_field(16, unsigned(x))
        + proto_field(24, unsigned(y))
    )


class ProfessionActionXpCoverageTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.clock = [10_000.0]
        self.store.clock = lambda: self.clock[0]
        self.account = self.store.register("profession-xp-coverage", "local-password")[
            "id"
        ]
        self.character = self.store.create_character(
            self.account, "Profession Coverage"
        )
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character["id"])

    def learn_at(self, profession_id, level=0):
        ensure_learned(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            [profession_id],
        )
        with self.store.connection() as db:
            db.execute(
                "UPDATE account_professions SET xp=%s WHERE account_id=%s AND profession_id=%s",
                (_level_xp(level), self.account, profession_id),
            )

    def xp(self, profession_id):
        with self.store.connection() as db:
            row = db.execute(
                "SELECT xp FROM account_professions WHERE account_id=%s AND profession_id=%s",
                (self.account, profession_id),
            ).fetchone()
        return None if row is None else row["xp"]

    def counts(self, table, where, value):
        with self.store.connection() as db:
            return db.execute(
                f"SELECT count(*) AS count FROM {table} WHERE {where}=%s", (value,)
            ).fetchone()["count"]

    def test_native_planting_professions_award_once_and_failures_award_nothing(self):
        for index, (seed_ref, profession_id, required_level) in enumerate(
            SEED_COVERAGE
        ):
            with self.subTest(seed=seed_ref, profession=profession_id):
                seed_rule = SEEDS[seed_ref]
                self.assertEqual(seed_rule["profession_id"], profession_id)
                self.assertEqual(seed_rule["minimum_level"], required_level)
                self.assertFalse(seed_rule["has_item_criteria"])
                item = grant(
                    self.store,
                    self.account,
                    self.generation,
                    self.character["id"],
                    reference=seed_ref,
                    quantity=2,
                    container=self.character["inventory_containers"][0]["uid"],
                    slot=index,
                    allowed_references=SEEDS,
                )
                self.learn_at(profession_id)
                body = struct.pack(
                    ">iqii", seed_rule["action_id"], item["uid"], 20 + index * 2, 30
                )
                if required_level:
                    with self.assertRaisesRegex(ValueError, "below seed requirement"):
                        prepare_plant(
                            self.store,
                            self.account,
                            self.generation,
                            self.character,
                            body,
                            authorize_cell=lambda *_args: 0,
                        )
                    self.learn_at(profession_id, required_level)
                prepared = prepare_plant(
                    self.store,
                    self.account,
                    self.generation,
                    self.character,
                    body,
                    authorize_cell=lambda *_args: 0,
                )
                resource = prepared["definition"]
                members = None
                group_id = None
                if resource["monster_resource"]:
                    family = resource["monster_family_ids"][0]
                    monster = next(
                        m for m in REFERENCES.values() if m["family_id"] == family
                    )
                    member_id = -(8_000_000_000 + index)
                    members = [
                        owned_instance(
                            monster["ref"],
                            monster["min_level"],
                            member_id,
                            map_id=self.character["map_id"],
                            instance_id=self.character["instance_id"],
                            x=20 + index * 2,
                            y=30,
                            z=0,
                        )
                    ]
                    group_id = 8_000 + index
                operation = f"profession-plant-{profession_id}"
                outcome = complete_plant(
                    self.store,
                    self.account,
                    self.generation,
                    prepared,
                    operation_id=operation,
                    stage=resource["stages"][0],
                    creation_time=123_000 + index,
                    result_prefix=(0, 1),
                    success=True,
                    monster_members=members,
                    group_id=group_id,
                )
                rewards = [
                    body for opcode, body in outcome["packets"] if opcode == 12916
                ]
                self.assertEqual(len(rewards), 1)
                self.assertEqual(struct.unpack(">iq", rewards[0]), (profession_id, 10))
                self.assertEqual(self.xp(profession_id), _level_xp(required_level) + 10)
                xp_operation = "planting:" + sha256(operation.encode()).hexdigest()
                with self.store.connection() as db:
                    receipt_count = db.execute(
                        "SELECT count(*) AS count FROM profession_xp_receipts "
                        "WHERE account_id=%s AND operation=%s AND profession_id=%s",
                        (self.account, xp_operation, profession_id),
                    ).fetchone()["count"]
                self.assertEqual(receipt_count, 1)
                replay = complete_plant(
                    self.store,
                    self.account,
                    self.generation,
                    prepared,
                    operation_id=operation,
                    stage=resource["stages"][0],
                    creation_time=123_000 + index,
                    result_prefix=(0, 1),
                    success=True,
                    monster_members=members,
                    group_id=group_id,
                )
                self.assertTrue(replay["duplicate"])
                self.assertEqual(replay["packets"], [])
                self.assertEqual(self.xp(profession_id), _level_xp(required_level) + 10)

                failed_body = struct.pack(
                    ">iqii", seed_rule["action_id"], item["uid"], 21 + index * 2, 30
                )
                failed_prepared = prepare_plant(
                    self.store,
                    self.account,
                    self.generation,
                    self.character,
                    failed_body,
                    authorize_cell=lambda *_args: 0,
                )
                failed = complete_plant(
                    self.store,
                    self.account,
                    self.generation,
                    failed_prepared,
                    operation_id=f"profession-plant-failed-{profession_id}",
                    stage=resource["stages"][0],
                    creation_time=124_000 + index,
                    result_prefix=(0, 1),
                    success=False,
                )
                self.assertFalse(failed["success"])
                self.assertFalse(
                    any(opcode == 12916 for opcode, _ in failed["packets"])
                )
                self.assertEqual(self.xp(profession_id), _level_xp(required_level) + 10)
                self.assertEqual(
                    self.counts("profession_xp_receipts", "operation", xp_operation), 1
                )

    def _insert_resource(self, uid, reference, stage, x, y):
        resource = dict(
            resource_uid=uid,
            map_id=self.character["map_id"],
            instance_id=self.character["instance_id"],
            x=x,
            y=y,
            z=self.character["z"],
            resource_reference=reference,
            stage=stage,
            creation_time=777,
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,resource_reference,stage,creation_time) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                tuple(resource.values()),
            )
        return resource

    def _collect(self, resource, action_id):
        prepared = prepare_harvest(
            self.store,
            self.account,
            self.generation,
            self.character["id"],
            _harvest_request(action_id, resource["x"], resource["y"]),
            reachable=lambda _actor, _resource: True,
        )
        return reserve_harvest(self.store, self.account, self.generation, prepared)

    def test_product_bearing_flora_professions_award_once_and_cancel_awards_nothing(
        self,
    ):
        for index, (
            profession_id,
            reference,
            stage,
            action_id,
            required_level,
            product,
            duration,
        ) in enumerate(HARVEST_COVERAGE):
            with self.subTest(profession=profession_id, action=action_id):
                self.learn_at(profession_id)
                x, y = self.character["x"] + index + 1, self.character["y"] + index + 1
                resource = self._insert_resource(
                    91_000 + index * 2, reference, stage, x, y
                )
                if required_level:
                    with self.assertRaisesRegex(ValueError, "profession requirement"):
                        self._collect(resource, action_id)
                    self.learn_at(profession_id, required_level)
                ticket = self._collect(resource, action_id)
                self.clock[0] += duration / 1000 + 0.1
                result = complete_harvest(self.store, ticket, struct.pack(">Bh", 2, 3))
                self.assertTrue(result["applied"])
                self.assertEqual(result["outcome"]["item_reference"], product)
                self.assertEqual(result["outcome"]["quantity"], 1)
                self.assertEqual(result["outcome"]["xp"], 50)
                rewards = [
                    body for opcode, body in result["packets"] if opcode == 12916
                ]
                self.assertEqual(len(rewards), 1)
                self.assertEqual(struct.unpack(">iq", rewards[0]), (profession_id, 50))
                self.assertEqual(self.xp(profession_id), _level_xp(required_level) + 50)
                self.assertEqual(
                    self.counts("resource_harvest_receipts", "token", ticket["token"]),
                    1,
                )
                replay = complete_harvest(self.store, ticket, struct.pack(">Bh", 2, 3))
                self.assertEqual(
                    replay, {"applied": False, "packets": [], "world_packets": []}
                )
                self.assertEqual(self.xp(profession_id), _level_xp(required_level) + 50)

                # A second native target for this profession is explicitly cancelled.
                failed_resource = self._insert_resource(
                    91_001 + index * 2, reference, stage, x + 20, y + 20
                )
                failed_ticket = self._collect(failed_resource, action_id)
                failed = complete_harvest(
                    self.store, failed_ticket, struct.pack(">Bh", 3, 3)
                )
                self.assertFalse(failed["applied"])
                self.assertFalse(
                    any(opcode == 12916 for opcode, _ in failed["packets"])
                )
                self.assertIsNone(
                    self._receipt(
                        "resource_harvest_receipts", "token", failed_ticket["token"]
                    )
                )
                self.assertEqual(self.xp(profession_id), _level_xp(required_level) + 50)

    def _receipt(self, table, key, value):
        with self.store.connection() as db:
            return db.execute(
                f"SELECT * FROM {table} WHERE {key}=%s", (value,)
            ).fetchone()

    def test_profession_62_alternative_product_list_is_not_awarded_as_a_selected_product(
        self,
    ):
        native_professions = set(
            json.loads(native_catalog.read_text(DATA_ROOT / "profession-actions.json"))[
                "profession_ids"
            ]
        )
        self.assertNotIn(62, native_professions)
        rule = next(
            action
            for resource in json.loads(
                native_catalog.read_text(DATA_ROOT / "plant-resources.json")
            )
            if resource["resource_reference"] == 368
            for step in resource["stage_definitions"]
            if step["stage_id"] == 1
            for action in step["actions"]
            if action["action_id"] == 896
        )
        self.assertEqual(rule["profession_id"], 62)
        self.assertEqual(rule["item_reference"], 0)
        self.assertTrue(rule["product_references"])
        resource = self._insert_resource(
            92_001, 368, 1, self.character["x"] + 1, self.character["y"] + 1
        )
        with self.assertRaisesRegex(ValueError, "profession is unlearned"):
            prepare_harvest(
                self.store,
                self.account,
                self.generation,
                self.character["id"],
                _harvest_request(896, resource["x"], resource["y"]),
                reachable=lambda _actor, _resource: True,
            )
        self.assertEqual(
            self.counts(
                "resource_harvest_occupations", "character_id", self.character["id"]
            ),
            0,
        )
        self.assertEqual(
            self.counts(
                "resource_harvest_receipts", "character_id", self.character["id"]
            ),
            0,
        )

    def test_non_native_flora_profession_ids_68_and_70_cannot_be_learned_or_occupied(
        self,
    ):
        native_professions = set(
            json.loads(native_catalog.read_text(DATA_ROOT / "profession-actions.json"))[
                "profession_ids"
            ]
        )
        cases = ((68, 220, 3, 435), (70, 217, 1, 411))
        for index, (profession_id, reference, stage, action_id) in enumerate(cases):
            with self.subTest(profession=profession_id):
                self.assertNotIn(profession_id, native_professions)
                with self.assertRaisesRegex(ValueError, "Unknown native profession"):
                    self.learn_at(profession_id)
                resource = self._insert_resource(
                    93_000 + index,
                    reference,
                    stage,
                    self.character["x"] + 40 + index,
                    self.character["y"] + 40 + index,
                )
                with self.assertRaisesRegex(ValueError, "profession is unlearned"):
                    self._collect(resource, action_id)
                self.assertIsNone(self.xp(profession_id))
                self.assertEqual(
                    self.counts(
                        "resource_harvest_occupations",
                        "character_id",
                        self.character["id"],
                    ),
                    0,
                )
                self.assertEqual(
                    self.counts(
                        "resource_harvest_receipts",
                        "character_id",
                        self.character["id"],
                    ),
                    0,
                )


if __name__ == "__main__":
    unittest.main()
