"""Native constructor arM authority without inventing a published map."""
from dataclasses import replace
from types import SimpleNamespace
import unittest

from wakfu_server.combat_npc_initialization import (
    native_fresh_ordinary_instance_authority,
)
from wakfu_server.combat_summon_creation import native_fresh_summon_authority


class OrdinaryConstructorInstanceTests(unittest.TestCase):
    def authority(self):
        return native_fresh_summon_authority(
            SimpleNamespace(id=-200, effective_level=53, native_controlled_by_ai=False),
            5386,
        )

    def test_only_fresh_ordinary_wrapper_has_native_constructor_zero(self):
        original = self.authority()
        actual = native_fresh_ordinary_instance_authority(original)
        self.assertEqual(actual.native_instance_id, 0)
        self.assertIsNone(original.native_instance_id)
        self.assertFalse(actual.native_in_play)
        self.assertEqual(actual.targeting, original.targeting)

    def test_cannot_replace_a_published_position_or_registered_actor(self):
        for authority in (
            replace(self.authority(), native_instance_id=1376),
            replace(self.authority(), native_in_play=True),
            replace(self.authority(), is_player=True),
            replace(self.authority(), targeting={"bcN": 0}),
            None,
        ):
            with self.subTest(authority=authority):
                with self.assertRaisesRegex(ValueError, "constructor authority"):
                    native_fresh_ordinary_instance_authority(authority)
