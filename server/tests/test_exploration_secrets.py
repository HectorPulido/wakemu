import struct
import hashlib
import unittest
import uuid
from unittest.mock import patch

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.characters import exploration_secrets as secrets


class PolicyDatabase:
    def __init__(self, value):
        self.value = value

    def execute(self, query, params):
        assert params == (secrets.SETTING,)
        return self

    def fetchone(self):
        return None if self.value is None else {"value": self.value}


class ExplorationSecretTests(unittest.TestCase):
    def test_all_native_artifacts_and_movement_powers_are_projected(self):
        result = secrets.load(PolicyDatabase({"version": 1, "unlock_all": True}))
        self.assertEqual(len(set(result["account_item_refs"])), 11)
        self.assertEqual(result["world_properties"], (85, 105, 117, 118))
        component = secrets.world_properties({"exploration_secrets": result})
        self.assertEqual(component, bytes.fromhex("0100045501690175017601"))

    def test_disabled_policy_projects_no_grants(self):
        db = PolicyDatabase({"version": 1, "unlock_all": False})
        result = secrets.load(db)
        self.assertEqual(result, {"account_item_refs": (), "world_properties": ()})
        self.assertEqual(
            secrets.world_properties({"exploration_secrets": result}), b"\x00"
        )
        self.assertEqual(
            secrets.account_packet(db), (13873, struct.pack(">III", 1, 4, 0))
        )

    def test_missing_and_malformed_policy_fail_closed(self):
        for value in (
            None,
            {},
            {"version": True, "unlock_all": True},
            {"version": 1, "unlock_all": 1},
            {"version": 2, "unlock_all": True},
            {"version": 1, "unlock_all": True, "extra": True},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                secrets.load(PolicyDatabase(value))

    def test_only_exact_exploration_powers_can_be_serialized(self):
        for value in ((85, 85), (True,), (19,), (85, 127), None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                secrets.world_properties(
                    {"exploration_secrets": {"world_properties": value}}
                )
        self.assertIsNone(secrets.world_properties({}))

    def test_account_snapshot_is_absolute_and_repeatable(self):
        db = PolicyDatabase({"version": 1, "unlock_all": True})
        opcode, body = secrets.account_packet(db)
        self.assertEqual(opcode, 13873)
        count, section, size = struct.unpack_from(">III", body)
        self.assertEqual((count, section, size), (1, 4, len(body) - 12))
        self.assertEqual(secrets.account_packet(db), (opcode, body))
        self.assertEqual(body[12:].count(b"\x10\x01"), 11)


class ExplorationSecretPostgresTests(PostgresCase):
    def test_migration_policy_and_operator_change_survive_reopen(self):
        with self.store.connection() as db:
            self.assertEqual(secrets.load(db)["account_item_refs"], secrets.ITEM_REFS)
            db.execute(
                "UPDATE settings SET value=%s WHERE name=%s",
                (Jsonb({"version": 1, "unlock_all": False}), secrets.SETTING),
            )
        with self.reopen().connection() as db:
            self.assertFalse(secrets.load(db)["account_item_refs"])

    def test_policy_reaches_existing_and_new_character_entity_world_properties(self):
        account = self.store.register(
            "explore" + uuid.uuid4().hex[:8], "test-password"
        )["id"]
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name=%s",
                (Jsonb({"version": 1, "unlock_all": False}), secrets.SETTING),
            )
        existing = self.store.create_character(account, "Old Explorer")
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name=%s",
                (Jsonb({"version": 1, "unlock_all": True}), secrets.SETTING),
            )
        created_after_unlock = self.store.create_character(account, "New Explorer")
        from wakfu_server import wire

        expected_component = bytes.fromhex("0100045501690175017601")
        for character_id in (existing["id"], created_after_unlock["id"]):
            with self.subTest(character_id=character_id):
                character = self.store.character(account, character_id)
                self.assertEqual(
                    character["exploration_secrets"]["world_properties"],
                    secrets.MOVEMENT_PROPERTIES,
                )
                for entity_format in (10, 11):
                    header = (
                        struct.pack(
                            ">BqBqH",
                            entity_format,
                            wire.TEMPLATE_CHARACTER,
                            1,
                            wire.TEMPLATE_ACCOUNT,
                            6,
                        )
                        + b"Pekebu"
                    )
                    position = wire.INITIAL_POSITION + struct.pack(">qBB", 1134, 3, 1)
                    body = header + position + b"old-props" + struct.pack(">i", 30)
                    property_start = len(header) + len(position)
                    property_end = property_start + len(b"old-props")
                    nation_start = property_end
                    sections = [
                        {
                            "name": "WORLD_PROPERTIES",
                            "start": property_start,
                            "end": property_end,
                        },
                        {
                            "name": "NATION_ID",
                            "start": nation_start,
                            "end": nation_start + 4,
                        },
                    ]
                    layout = {
                        "template_sha256": hashlib.sha256(body).hexdigest(),
                        "sections": sections,
                    }
                    with patch.dict(wire.ENTITY_LAYOUTS, {entity_format: layout}):
                        serialized = wire.spawn_player(body, character)
                    self.assertIn(expected_component, serialized)
                    self.assertNotIn(b"old-props", serialized)


class ExplorationSecretCriterionTests(unittest.TestCase):
    def character(self, enabled=True):
        return {
            "inventory_items": [{"uid": 1, "reference": 18722, "quantity": 2}],
            "exploration_secrets": secrets.load(
                PolicyDatabase({"version": 1, "unlock_all": enabled})
            ),
        }

    def test_dungeon_artifact_criteria_add_account_and_bag_quantities(self):
        from wakfu_server.maps import dungeon_criteria

        character = self.character()
        self.assertTrue(
            dungeon_criteria.evaluate(
                None, "GetItemQuantity(18722) == 3", character=character
            )
        )
        self.assertTrue(
            dungeon_criteria.evaluate(
                None, "GetItemQuantity(18722,18722,20784) == 7", character=character
            )
        )
        self.assertTrue(
            dungeon_criteria.evaluate(
                None, "GetItemQuantity(22087) == 1", character=character
            )
        )

    def test_disabled_grants_preserve_bag_quantities(self):
        from wakfu_server.maps import dungeon_criteria

        self.assertTrue(
            dungeon_criteria.evaluate(
                None, "GetItemQuantity(18722) == 2", character=self.character(False)
            )
        )
        self.assertFalse(
            dungeon_criteria.evaluate(
                None, "GetItemQuantity(20784) > 0", character=self.character(False)
            )
        )

    def test_native_narrowing_and_invalid_account_authority(self):
        character = self.character()
        self.assertEqual(secrets.account_quantity(character, [18722 + 2**32]), 1)
        for refs in ((18722, 18722), (19,), (True,), None):
            with self.subTest(refs=refs), self.assertRaises(ValueError):
                secrets.account_quantity(
                    {"exploration_secrets": {"account_item_refs": refs}}, [18722]
                )
