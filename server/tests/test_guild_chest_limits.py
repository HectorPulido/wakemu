"""Oversized native storage snapshots must roll back before publication."""
import unittest
from unittest.mock import Mock, patch

from wakfu_server.characters import guild_chest, guild_chest_wire


class GuildChestLimitsTests(unittest.TestCase):
    def test_oversized_compartment_is_rejected_before_any_write(self):
        chest = dict(
            id=0,
            guild_id=7,
            capacity=40,
            revision=2,
            items=[dict(slot=0, item=dict(uid=5, reference=2504, quantity=1))],
        )
        db = Mock()
        with patch.object(guild_chest_wire, "item_proto", return_value=b"a" * 327664):
            with self.assertRaisesRegex(ValueError, "frame budget"):
                guild_chest._save(db, chest)
        db.execute.assert_not_called()
        self.assertEqual(2, chest["revision"])

    def test_non_native_capacity_cannot_create_a_compartment(self):
        definition = dict(name="Guild chest", capacity=41, requires_unlock=False)
        policy = {"compartments": {"0": definition}}
        with self.assertRaisesRegex(ValueError, "capacity"):
            guild_chest._definition(policy, {"unlocked_compartments": []}, 0)
