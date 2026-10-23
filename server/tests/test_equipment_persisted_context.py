"""Owned profession context and original signed gauge wire parity."""
import hashlib
import struct
import unittest
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server import (
    equipment_conditions,
    equipment_persisted_context,
    personal_ecology,
    wire,
)


class EquipmentGaugeParityTests(unittest.TestCase):
    def test_original_jvm_gauges_and_both_publication_paths(self):
        # Original fzY/eLQ oracle: score500=50%,1000=75%,3322=99%.
        for basis, score, percent in (
            (0, 0, 0),
            (5000, 500, 50),
            (7500, 1000, 75),
            (9900, 3322, 99),
            (-5000, -500, -50),
            (-7500, -1000, -75),
            (-9900, -3322, -99),
        ):
            with self.subTest(basis=basis):
                self.assertEqual(
                    (percent, -percent),
                    equipment_persisted_context.native_gauges(basis),
                )
                body = bytes([10]) + struct.pack(">i", 123)
                layout = dict(
                    template_sha256=hashlib.sha256(body).hexdigest(),
                    sections=[dict(name="XP_CHARACTERISTICS", start=1, end=5)],
                )
                with patch.dict(wire.ENTITY_LAYOUTS, {10: layout}):
                    snapshot = wire.minimal_entity(
                        body, dict(level=1, ecology_value=basis)
                    )
                self.assertEqual(struct.pack(">i", score), snapshot[1:])
                self.assertEqual(
                    (13574, struct.pack(">qi", 77, score)),
                    personal_ecology.packet(77, basis),
                )

    def test_predicates_use_owned_context_and_reject_missing_authority(self):
        context = dict(
            actor_kind="player",
            level=50,
            profession_levels={64: 10, 73: 0},
            guild_level=7,
            wakfu_gauge=-50,
            stasis_gauge=50,
        )

        def check(text, selected_context=context):
            return equipment_conditions.evaluate(
                text,
                item=dict(uid=1, reference=2292),
                selected=(),
                owned={},
                criterion_context=selected_context,
            )

        for text in (
            "GetCraftLevel(64)>=10",
            "HasCraft(73)",
            "HasCraft(0)",
            "GetCraftLevel(999)==0",
            "not HasCraft(999)",
            "GetGuildLevel()==7",
            "GetStasisGauge()>=50",
            'GetWakfuGauge("target")==-50',
        ):
            self.assertTrue(check(text), text)
        self.assertFalse(check("GetCraftLevel(73)>0"))
        for text in ("GetCraftLevel(64)>0", "GetWakfuGauge()>0", "GetGuildLevel()>0"):
            with self.assertRaises(ValueError):
                check(text, dict(actor_kind="player", level=50))


class EquipmentPersistedContextPostgresTests(PostgresCase):
    def test_account_crafts_are_shared_without_foreign_or_unlearned_defaults(self):
        account = self.store.register("equipment-context", "local-password")["id"]
        main = self.store.create_character(account, "Context Main")
        hero = self.store.create_character(account, "Context Hero")
        foreign = self.store.register("equipment-other", "local-password")["id"]
        other = self.store.create_character(foreign, "Other Context")
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO account_professions(account_id,profession_id,xp) VALUES(%s,64,7500),(%s,73,0),(%s,76,30000)",
                (account, account, foreign),
            )
            db.execute(
                "UPDATE characters SET ecology_value=-5000 WHERE id=%s", (main["id"],)
            )
        with self.store.connection() as db:
            first = equipment_persisted_context.load(
                db, self.store.character(account, main["id"], db)
            )
            second = equipment_persisted_context.load(
                db, self.store.character(account, hero["id"], db)
            )
            third = equipment_persisted_context.load(
                db, self.store.character(foreign, other["id"], db)
            )
        self.assertEqual({64: 10, 73: 0}, first["profession_levels"])
        self.assertEqual(first["profession_levels"], second["profession_levels"])
        self.assertEqual({76: 20}, third["profession_levels"])
        self.assertEqual((-50, 50), (first["wakfu_gauge"], first["stasis_gauge"]))
        self.assertEqual(0, first["guild_level"])
        self.assertEqual(0, first["nation_id"])
        self.assertNotIn(76, first["profession_levels"])
        with self.assertRaises(ValueError):
            equipment_persisted_context.load(
                None, dict(main, native_social_context=third)
            )
