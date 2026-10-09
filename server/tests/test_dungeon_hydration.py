"""Worker hydration preparation fails before publication on stale authority."""

import struct
import unittest
from unittest.mock import Mock, patch

from wakfu_server.maps.dungeon_hydration import prepare_transition


class DungeonHydrationTests(unittest.TestCase):
    def setUp(self):
        self.character = dict(
            id=7,
            account_id=9,
            map_id=1086,
            instance_id=144115188075855873,
            x=1,
            y=2,
            z=0,
        )
        self.event = dict(character_id=7, session_generation="generation")
        self.event.update(
            {
                "destination_" + key: self.character[key]
                for key in ("map_id", "instance_id", "x", "y", "z")
            }
        )
        self.store = Mock()
        self.store.current_session.return_value = True
        self.store.character.return_value = self.character

    @patch("wakfu_server.maps.dungeon_hydration.dungeon_context.for_instance")
    def test_pinned_context_and_native_asset_are_prepared(self, context):
        context.return_value = dict(difficulty_level=2)
        plan = prepare_transition(self.store, 9, "generation", 7, self.event)
        context.assert_called_once_with(
            self.store, self.character["instance_id"], fight_in_progress=False
        )
        self.assertEqual(
            [opcode for opcode, body in plan.packets], [13256, 13974, 12318]
        )
        self.assertEqual(struct.unpack_from(">q", plan.packets[1][1], 30)[0], 1086)
        self.assertIsNot(plan.character, self.character)

    def test_stale_generation_is_rejected_before_reading_character(self):
        self.store.current_session.return_value = False
        with self.assertRaisesRegex(ValueError, "Stale"):
            prepare_transition(self.store, 9, "generation", 7, self.event)
        self.store.character.assert_not_called()

    @patch("wakfu_server.maps.dungeon_hydration.dungeon_context.for_instance")
    def test_superseded_destination_is_rejected_before_context(self, context):
        self.event["destination_x"] = 99
        with self.assertRaisesRegex(ValueError, "destination changed"):
            prepare_transition(self.store, 9, "generation", 7, self.event)
        context.assert_not_called()

    @patch("wakfu_server.maps.dungeon_hydration.dungeon_context.for_instance")
    def test_missing_policy_does_not_produce_partial_plan(self, context):
        context.side_effect = ValueError("Policy not configured")
        with self.assertRaisesRegex(ValueError, "Policy"):
            prepare_transition(self.store, 9, "generation", 7, self.event)
