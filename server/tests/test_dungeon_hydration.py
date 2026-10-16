"""Worker hydration preparation fails before publication on stale authority."""

import struct
import unittest
from contextlib import nullcontext
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

    def test_ordinary_entry_and_room_keep_zone_profile_publication(self):
        self.character["dungeon_modulation"] = None
        self.store.connection.return_value = nullcontext(Mock())
        with patch(
            "wakfu_server.maps.dungeon_hydration.dungeon_context.for_instance",
            return_value={"difficulty_level": 1},
        ), patch(
            "wakfu_server.maps.dungeon_hydration.native_transports.bootstrap",
            return_value=((13256, b"context"), (13974, b"map"), (12318, b"actor")),
        ), patch(
            "wakfu_server.characters.dungeon_modulation_publication.owned_hero_role",
            return_value=False,
        ), patch(
            "wakfu_server.characters.dungeon_modulation_publication.packets",
            return_value=((13811, b"selection"),),
        ) as publish:
            for transition_kind in ("enter", "room"):
                self.event["transition_kind"] = transition_kind
                plan = prepare_transition(
                    self.store,
                    9,
                    "generation",
                    7,
                    self.event,
                    fixture_provider=lambda _opcode: b"fixture",
                )
                self.assertEqual(
                    [opcode for opcode, _ in plan.packets],
                    [13256, 13811, 13974, 12318],
                )
        self.assertEqual(publish.call_count, 2)

    def test_ordinary_authorized_exit_keeps_zone_profile_publication(self):
        self.character.update(map_id=527, instance_id=0, x=-2, y=3, z=0)
        self.event.update(transition_kind="exit", event_id="ordinary-exit")
        self.event.update(
            {
                "destination_" + key: self.character[key]
                for key in ("map_id", "instance_id", "x", "y", "z")
            }
        )
        db = Mock()
        db.execute.return_value.fetchone.side_effect = [
            {"competitive": False},
            None,
        ]
        self.store.connection.return_value = nullcontext(db)
        with patch(
            "wakfu_server.characters.dungeon_modulation_publication.owned_hero_role",
            return_value=False,
        ), patch(
            "wakfu_server.characters.dungeon_modulation_publication.packets",
            return_value=((13811, b"selection"),),
        ) as publish, patch(
            "wakfu_server.maps.dungeon_hydration.native_transports.bootstrap",
            return_value=((13256, b"context"), (13974, b"map"), (12318, b"actor")),
        ):
            plan = prepare_transition(
                self.store,
                9,
                "generation",
                7,
                self.event,
                fixture_provider=lambda _opcode: b"fixture",
            )
        self.assertIn(13811, [opcode for opcode, _ in plan.packets])
        publish.assert_called_once()

    def test_competitive_entry_and_authorized_exit_restore_profile(self):
        self.character["dungeon_modulation"] = {"effective_level": 50}
        bootstrap = ((13256, b"context"), (13974, b"map"), (12318, b"actor"))
        self.store.connection.return_value = nullcontext(Mock())
        with patch(
            "wakfu_server.maps.dungeon_hydration.dungeon_context.for_instance",
            return_value={"difficulty_level": 2},
        ), patch(
            "wakfu_server.maps.dungeon_hydration.native_transports.bootstrap",
            return_value=bootstrap,
        ), patch(
            "wakfu_server.characters.dungeon_modulation_publication.owned_hero_role",
            return_value=False,
        ), patch(
            "wakfu_server.characters.dungeon_modulation_publication.packets",
            return_value=((13811, b"selection"), (12436, b"health")),
        ) as publish:
            entry = prepare_transition(
                self.store,
                9,
                "generation",
                7,
                self.event,
                fixture_provider=lambda _opcode: b"fixture",
            )
            self.assertIn(13811, [opcode for opcode, _ in entry.packets])

            self.character.update(map_id=527, instance_id=0, x=-2, y=3, z=0)
            self.event.update(transition_kind="exit", event_id="exit-event")
            self.event.update(
                {
                    "destination_" + key: self.character[key]
                    for key in ("map_id", "instance_id", "x", "y", "z")
                }
            )
            db = Mock()
            db.execute.return_value.fetchone.side_effect = [
                {"competitive": True},
                None,
            ]
            self.store.connection.return_value = nullcontext(db)
            exit_plan = prepare_transition(
                self.store,
                9,
                "generation",
                7,
                self.event,
                fixture_provider=lambda _opcode: b"fixture",
            )
            self.assertIn(13811, [opcode for opcode, _ in exit_plan.packets])
            self.assertEqual(publish.call_count, 2)

    def test_exit_without_current_return_authorization_is_rejected(self):
        self.character.update(map_id=527, instance_id=0, x=-2, y=3, z=0)
        self.event.update(transition_kind="exit", event_id="stale-exit")
        self.event.update(
            {
                "destination_" + key: self.character[key]
                for key in ("map_id", "instance_id", "x", "y", "z")
            }
        )
        db = Mock()
        db.execute.return_value.fetchone.side_effect = [None, None]
        self.store.connection.return_value = nullcontext(db)
        with patch(
            "wakfu_server.characters.dungeon_modulation_publication.packets"
        ) as publish:
            with self.assertRaisesRegex(ValueError, "not authorized"):
                prepare_transition(
                    self.store,
                    9,
                    "generation",
                    7,
                    self.event,
                    fixture_provider=lambda _opcode: b"fixture",
                )
        publish.assert_not_called()
