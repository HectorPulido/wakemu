"""Public build saves use owned achievement and live map/clock authority."""
import uuid
from unittest.mock import patch

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import builds, wire
from wakfu_server.character_levels import XP_BY_LEVEL
from wakfu_server.equipment import RULES
from wakfu_server.inventory_items import grant


class EquipmentAchievementMapTimePostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.account = self.store.register(
            "equip-context-" + uuid.uuid4().hex[:10], "local-password"
        )["id"]
        self.character = self.store.create_character(
            self.account, "Equipment Context", breed=8
        )
        self.character_id = self.character["id"]
        self.generation = self.store.begin_session(self.account)
        self.store.select_character(self.account, self.generation, self.character_id)
        self.character = self.store.character(self.account, self.character_id)
        self.container = next(
            row["uid"]
            for row in self.character["inventory_containers"]
            if row["kind"] == 0
        )

    def _grant(self, reference):
        return grant(
            self.store,
            self.account,
            self.generation,
            self.character_id,
            reference=reference,
            quantity=1,
            container=self.container,
            slot=0,
            allowed_references={reference},
        )

    @staticmethod
    def _blobs(index, level, entries):
        equipment = b"".join(
            wire.proto_field(
                10,
                wire.proto_field(8, uid) + wire.proto_field(16, slot),
            )
            for slot, uid in sorted(entries.items())
        )
        return {
            "sheet": b"".join(
                wire.proto_field(tag, value)
                for tag, value in (
                    (8, index),
                    (18, f"Context {index}".encode()),
                    (24, level),
                    (56, 0),
                )
            ),
            "equipment": equipment or builds.EMPTY_EQUIPMENT,
            "deck": b"",
            "aptitudes": b"",
        }

    def _save(self, index, level, entries):
        return self.store.save_build(
            self.account,
            self.generation,
            self.character_id,
            index,
            self._blobs(index, level, entries),
        )

    def test_owned_completion_controls_mount_equip_and_reconnect_preserves_uid(self):
        reference = 14422
        slot = 24
        self.assertIn(slot, RULES[reference]["slots"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=35 WHERE id=%s", (self.character_id,)
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[35], self.character_id),
            )
        item = self._grant(reference)
        entry = {slot: item["uid"]}

        # Running the achievement is not equivalent to completing it. A new
        # selection remains strict and leaves the owned physical mount intact.
        with self.store.connection() as db:
            db.execute(
                "UPDATE character_achievement_authority SET snapshot=%s "
                "WHERE character_id=%s",
                (
                    Jsonb({"running": [1509], "completed": [], "objectives": []}),
                    self.character_id,
                ),
            )
        with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
            self._save(0, 35, entry)
        self.assertTrue(
            any(
                row["uid"] == item["uid"]
                for row in self.store.character(self.account, self.character_id)[
                    "inventory_items"
                ]
            )
        )

        with self.store.connection() as db:
            db.execute(
                "UPDATE character_achievement_authority SET snapshot=%s "
                "WHERE character_id=%s",
                (
                    Jsonb({"running": [], "completed": [1509], "objectives": []}),
                    self.character_id,
                ),
            )
        saved = self._save(0, 35, entry)
        reopened = self.reopen().character(self.account, self.character_id)
        durable_entry = wire.proto_fields(
            bytes.fromhex(reopened["builds"][0]["equipment"])
        )
        self.assertEqual(
            item["uid"],
            next(
                fields[8]
                for tag, raw in durable_entry
                if tag == 10
                for fields in [dict(wire.proto_fields(raw))]
                if fields.get(16) == slot
            ),
        )
        self.assertEqual(
            item["uid"],
            next(
                row["uid"]
                for row in reopened["inventory_items"]
                if row["reference"] == reference
            ),
        )
        self.assertEqual(
            reference,
            next(
                row["reference"]
                for row in saved["inventory_items"]
                if row["uid"] == item["uid"]
            ),
        )

    def test_light_item_uses_live_map_and_native_day_cycle_for_new_builds(self):
        reference, slot = 8089, 17
        self.assertIn(slot, RULES[reference]["slots"])
        item = self._grant(reference)
        entry = {slot: item["uid"]}
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET level=1,map_id=527,instance_id=0 WHERE id=%s",
                (self.character_id,),
            )
            db.execute(
                "UPDATE character_progression SET xp=%s WHERE character_id=%s",
                (XP_BY_LEVEL[1], self.character_id),
            )

        with patch("wakfu_server.world_clock.current_time_ms", return_value=0):
            self._save(0, 1, entry)
        with patch("wakfu_server.world_clock.current_time_ms", return_value=1800000):
            with self.assertRaisesRegex(ValueError, "EQUIP criteria"):
                self._save(1, 1, entry)

        # Map506 is one of the original location exceptions; daytime remains
        # valid there. Persisting the world map verifies this uses Store context.
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=506,instance_id=0 WHERE id=%s",
                (self.character_id,),
            )
        with patch("wakfu_server.world_clock.current_time_ms", return_value=1800000):
            saved = self._save(1, 1, entry)
        self.assertTrue(
            any(row["uid"] == item["uid"] for row in saved["inventory_items"])
        )
        reopened = self.reopen().character(self.account, self.character_id)
        self.assertTrue(
            any(row["uid"] == item["uid"] for row in reopened["inventory_items"])
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
