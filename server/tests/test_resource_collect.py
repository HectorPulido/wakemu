import copy
import struct
import unittest

from wakfu_server import planting
from postgres_case import PostgresCase
from wakfu_server.resource_collect import (
    action,
    authorize,
    decode_request,
    decode_result,
    prepare,
    start_packet,
)
from wakfu_server.profession_store import ensure_learned
from wakfu_server.wire import proto_field


def request(action_id=100, x=12, y=-8, ten_byte_y=False):
    def signed32(value, *, ten_byte=False):
        if value >= 0:
            return value
        return (1 << 64) + value if ten_byte else value + (1 << 32)

    return b"".join(
        (
            proto_field(8, action_id),
            proto_field(16, signed32(x, ten_byte=True)),
            proto_field(24, signed32(y, ten_byte=ten_byte_y)),
        )
    )


class ResourceCollectDecodeTests(unittest.TestCase):
    def test_native_positive_request_and_signed_int32_encodings(self):
        self.assertEqual(decode_request(request()), dict(action_id=100, x=12, y=-8))
        self.assertEqual(
            decode_request(request(x=-(1 << 31), y=(1 << 31) - 1)),
            dict(action_id=100, x=-(1 << 31), y=(1 << 31) - 1),
        )
        self.assertEqual(
            decode_request(request(x=-1, y=-1)),
            dict(action_id=100, x=-1, y=-1),
        )

    def test_rejects_invalid_action_and_coordinate_ranges(self):
        for body in (
            request(action_id=0),
            request(action_id=1 << 31),
            request(x=1 << 32),
            request(y=-(1 << 31) - 1, ten_byte_y=True),
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                decode_request(body)


class ResourceCollectPacketTests(unittest.TestCase):
    def test_start_packet_matches_native_captured_cyJ_field_layout(self):
        character = {"id": 10434830}
        resource = {"x": 12, "y": 20}
        rule = dict(
            profession_id=72,
            duration_ms=3000,
            action_id=2269,
        )
        opcode, body = start_packet(character, resource, rule)
        self.assertEqual(opcode, 12230)
        self.assertEqual(len(body), struct.calcsize(">BhqqBiiBiBdi"))
        self.assertEqual(
            struct.unpack(">BhqqBiiBiBdi", body),
            (1, 3, 10434830, 3000, 2, 12, 20, 72, 2269, 1, 0.0, 0),
        )

    def test_start_packet_encodes_negative_coordinates_and_accepts_zero_duration(self):
        opcode, body = start_packet(
            {"id": 1},
            {"x": -(1 << 31), "y": -1},
            {"profession_id": 127, "duration_ms": 0, "action_id": (1 << 31) - 1},
        )
        self.assertEqual(opcode, 12230)
        fields = struct.unpack(">BhqqBiiBiBdi", body)
        self.assertEqual(fields[3:9], (0, 2, -(1 << 31), -1, 127, (1 << 31) - 1))

    def test_start_packet_rejects_invalid_ranges_and_boolean_integers(self):
        valid_character = {"id": 1}
        valid_resource = {"x": 0, "y": 0}
        valid_rule = {"profession_id": 72, "duration_ms": 1, "action_id": 1}
        invalid = (
            ({"id": True}, valid_resource, valid_rule),
            ({"id": 0}, valid_resource, valid_rule),
            (valid_character, {"x": False, "y": 0}, valid_rule),
            (valid_character, valid_resource, {**valid_rule, "profession_id": True}),
            (valid_character, valid_resource, {**valid_rule, "profession_id": -1}),
            (valid_character, valid_resource, {**valid_rule, "profession_id": 128}),
            (valid_character, valid_resource, {**valid_rule, "duration_ms": False}),
            (valid_character, valid_resource, {**valid_rule, "duration_ms": -1}),
            (valid_character, valid_resource, {**valid_rule, "duration_ms": 1 << 63}),
            (valid_character, valid_resource, {**valid_rule, "action_id": True}),
            (valid_character, valid_resource, {**valid_rule, "action_id": 0}),
            (valid_character, valid_resource, {**valid_rule, "action_id": 1 << 31}),
            (valid_character, {"x": 1 << 31, "y": 0}, valid_rule),
            (valid_character, {"x": -(1 << 31) - 1, "y": 0}, valid_rule),
            ({"id": 1 << 63}, valid_resource, valid_rule),
        )
        for character, resource, rule in invalid:
            with self.subTest(character=character, resource=resource, rule=rule):
                with self.assertRaises(ValueError):
                    start_packet(character, resource, rule)

    def test_result_ack_accepts_only_native_codes_and_kind(self):
        self.assertEqual(decode_result(struct.pack(">Bh", 2, 3)), 2)
        self.assertEqual(decode_result(struct.pack(">Bh", 3, 3)), 3)
        for body in (
            struct.pack(">Bh", 1, 3),
            struct.pack(">Bh", 2, 2),
            struct.pack(">Bh", 2, 4),
            b"\x02\x00",
            b"\x02\x00\x03\x00",
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                decode_result(body)

    def test_rejects_truncation_and_malformed_varint(self):
        valid = request()
        for body in (valid[:-1], b"\x80", b"\x80" * 10 + b"\x00"):
            with self.subTest(body=body), self.assertRaises(ValueError):
                decode_request(body)

    def test_rejects_missing_duplicate_unknown_and_wrong_wire_fields(self):
        base = request()
        cases = (
            proto_field(8, 100) + proto_field(16, 12),
            base + proto_field(8, 100),
            base + proto_field(32, 1),
            proto_field(10, b"x") + proto_field(16, 12) + proto_field(24, 8),
            proto_field(8, 100) + proto_field(17, b"12345678") + proto_field(24, 8),
        )
        for body in cases:
            with self.subTest(body=body), self.assertRaises(ValueError):
                decode_request(body)


class ResourceCollectAuthorizationTests(unittest.TestCase):
    def test_cardo_action_is_bound_to_stage(self):
        rule = action(60, 3, 100)
        self.assertEqual(rule["item_reference"], 4275)
        with self.assertRaises(ValueError):
            action(60, 2, 100)

    def test_fresno_native_actions_and_nonharvestable_stage(self):
        self.assertEqual(action(139, 2, 310)["item_reference"], 8063)
        self.assertEqual(action(139, 3, 99)["item_reference"], 1723)
        with self.assertRaises(ValueError):
            action(139, 16, 99)

    def test_unknown_and_monster_resources_are_rejected(self):
        with self.assertRaises(ValueError):
            action(987654321, 1, 1)
        monster_ref = next(
            ref
            for ref, definition in planting.RESOURCES.items()
            if definition["monster_resource"]
        )
        with self.assertRaises(ValueError):
            action(monster_ref, 1, 1)

    def test_profession_and_level_are_strict_and_criteria_fail_closed(self):
        rule = action(60, 3, 100)
        authorize(rule, profession_id=72, profession_level=0)
        for kwargs in (
            dict(profession_id=True, profession_level=0),
            dict(profession_id=71, profession_level=0),
            dict(profession_id=72, profession_level=False),
            dict(profession_id=72, profession_level=-1),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                authorize(rule, **kwargs)

        criteria_resource = next(
            (ref, stage["stage_id"], native["action_id"])
            for ref, definition in planting.RESOURCES.items()
            for stage in definition["stage_definitions"]
            for native in stage["actions"]
            if native["criteria"].strip()
        )
        criteria_rule = action(*criteria_resource)
        self.assertTrue(criteria_rule["criteria"].strip())
        with self.assertRaises(ValueError):
            authorize(
                criteria_rule,
                profession_id=criteria_rule["profession_id"],
                profession_level=criteria_rule["minimum_level"],
            )

    def test_action_result_is_a_deep_copy_of_native_catalog(self):
        before = copy.deepcopy(planting.RESOURCES[60])
        rule = action(60, 3, 100)
        rule["raw_getters"]["cvF"] = -99
        rule["product_references"].append(-1)
        self.assertEqual(planting.RESOURCES[60], before)


class ResourceCollectPrepareTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register("collect-preparer", "local-password")["id"]
        self.char = self.store.create_character(self.account, "Collect Preparer")
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.char["id"])

    def plant(
        self,
        *,
        ref=60,
        stage=3,
        x=None,
        y=None,
        map_id=None,
        instance_id=None,
        resource_uid=None,
    ):
        resource = dict(
            resource_uid=9001 + ref if resource_uid is None else resource_uid,
            map_id=self.char["map_id"] if map_id is None else map_id,
            instance_id=self.char["instance_id"]
            if instance_id is None
            else instance_id,
            x=self.char["x"] if x is None else x,
            y=self.char["y"] if y is None else y,
            z=0,
            resource_reference=ref,
            stage=stage,
            creation_time=123,
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO planted_resources(resource_uid,map_id,instance_id,x,y,z,"
                "resource_reference,stage,creation_time) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                tuple(resource.values()),
            )
        return resource

    def learn(self, profession_id, level=0):
        ensure_learned(
            self.store,
            self.account,
            self.generation,
            self.char["id"],
            [profession_id],
        )
        if level:
            xp = 75 * level * level
            with self.store.connection() as db:
                db.execute(
                    "UPDATE account_professions SET xp=%s WHERE account_id=%s AND profession_id=%s",
                    (xp, self.account, profession_id),
                )

    def prepare(self, body, *, reachable=lambda character, resource: True, **identity):
        return prepare(
            self.store,
            identity.get("account_id", self.account),
            identity.get("generation", self.generation),
            identity.get("character_id", self.char["id"]),
            body,
            reachable=reachable,
        )

    def body(self, action_id, *, x=None, y=None):
        return request(
            action_id,
            self.char["x"] if x is None else x,
            self.char["y"] if y is None else y,
        )

    def test_rejects_stale_lease_and_foreign_character(self):
        self.plant()
        self.learn(72)
        stale_generation = self.generation
        fresh_generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, fresh_generation, self.char["id"])
        with self.assertRaises(ValueError):
            self.prepare(self.body(100), generation=stale_generation)

        other_account = self.store.register("other-collector", "local-password")["id"]
        other_char = self.store.create_character(other_account, "Other Collector")
        other_generation = self.store.begin_session(other_account)
        self.store.select_character(other_account, other_generation, other_char["id"])
        with self.assertRaises(ValueError):
            self.prepare(
                self.body(100),
                account_id=other_account,
                generation=other_generation,
                character_id=self.char["id"],
            )

    def test_target_lookup_uses_character_map_and_instance_scope(self):
        self.plant(map_id=self.char["map_id"] + 1, instance_id=77)
        self.learn(72)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            self.prepare(self.body(100))
        local = self.plant(resource_uid=99999)
        prepared = self.prepare(self.body(100))
        self.assertEqual(prepared["resource"], local)

    def test_unlearned_profession_and_wrong_stage_action_are_rejected(self):
        planted = self.plant(ref=60, stage=3)
        with self.assertRaisesRegex(ValueError, "unlearned"):
            self.prepare(self.body(100))
        self.learn(72)
        with self.store.connection() as db:
            db.execute(
                "UPDATE planted_resources SET stage=2 WHERE resource_uid=%s",
                (planted["resource_uid"],),
            )
        with self.assertRaisesRegex(ValueError, "does not belong"):
            self.prepare(self.body(100), reachable=lambda *_: True)

    def test_reachability_requires_exact_true(self):
        self.plant(ref=60, stage=3)
        self.learn(72)
        seen = []
        with self.assertRaisesRegex(ValueError, "unreachable"):
            self.prepare(
                self.body(100),
                reachable=lambda char, res: seen.append((char, res)) or 1,
            )
        self.assertEqual(seen[0][1]["resource_reference"], 60)
        self.assertEqual(self.prepare(self.body(100))["rule"]["action_id"], 100)

    def test_cardo_and_fresno_return_authoritative_snapshot_without_mutation(self):
        cardo = self.plant(ref=60, stage=3)
        self.learn(72)
        before_items = self.store.character(self.account, self.char["id"])[
            "inventory_items"
        ]
        result = self.prepare(self.body(100))
        self.assertEqual(result["resource"], cardo)
        self.assertEqual(result["rule"]["item_reference"], 4275)
        with self.store.connection() as db:
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM planted_resources WHERE resource_uid=%s",
                        (cardo["resource_uid"],),
                    ).fetchone()
                ),
                cardo,
            )
            self.assertEqual(
                db.execute("SELECT count(*) FROM planting_receipts").fetchone()[
                    "count"
                ],
                0,
            )
        self.assertEqual(
            self.store.character(self.account, self.char["id"])["inventory_items"],
            before_items,
        )

        fresno = self.plant(ref=139, stage=2, x=self.char["x"] + 1)
        self.learn(71)
        result = self.prepare(
            self.body(310, x=fresno["x"]),
            reachable=lambda char, resource: True,
        )
        self.assertEqual(result["resource"], fresno)
        self.assertEqual(result["rule"]["item_reference"], 8063)


if __name__ == "__main__":
    unittest.main()
