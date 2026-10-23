"""Shared native criterion bonus routes, without item-specific templates."""
import copy
import unittest

from wakfu_server.guild_bonus_authority import active_identity, native_descriptor
from wakfu_server.guild_progression import catalog


class GuildBonusAuthorityTests(unittest.TestCase):
    def test_all_original_criterion_definitions_have_identity_only_effect(self):
        rows = [
            row
            for row in catalog()["bonuses"]
            if row["effect_type"] == "CRITERION_BONUS"
        ]
        self.assertEqual(8, len(rows))
        for row in rows:
            self.assertEqual(
                dict(kind="criterion_bonus", value=row["id"], duration_ms=-1),
                native_descriptor(row),
            )

    def test_unrelated_bonus_has_no_criterion_route(self):
        self.assertIsNone(native_descriptor(dict(effect_type="MEMBER_EFFECT")))

    def test_criterion_descriptor_rejects_unproven_duration_or_operands(self):
        native = next(
            row
            for row in catalog()["bonuses"]
            if row["effect_type"] == "CRITERION_BONUS"
        )
        for change in (
            dict(effect_parameters={"value": 10}),
            dict(has_effect_duration=True),
            dict(id=True),
            dict(effect_duration_ms=1000),
            dict(effect_class="other"),
        ):
            row = copy.deepcopy(native)
            row.update(change)
            with self.assertRaises(ValueError):
                native_descriptor(row)

    def test_active_date_boundary_and_malformed_authority(self):
        self.assertFalse(active_identity(None, 100))
        self.assertFalse(active_identity(dict(active=False), 100))
        self.assertFalse(active_identity(dict(active=True, activated_at_ms=101), 100))
        self.assertTrue(active_identity(dict(active=True, activated_at_ms=100), 100))
        self.assertTrue(active_identity(dict(active=True, activated_at_ms=99), 100))
        for row in (
            {},
            dict(active=True),
            dict(active=1),
            dict(active=True, activated_at_ms=True),
        ):
            with self.assertRaises(ValueError):
                active_identity(row, 100)
