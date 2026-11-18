"""A genuine challenge victory may restore its actual accepted entry pose."""

import unittest
from unittest.mock import Mock, patch

from wakfu_server import owned_story_terminal_returns as returns


class RecordedVictoryReturnTests(unittest.TestCase):
    def test_genuine_victory_restores_the_original_recorded_entry(self):
        selected = dict(
            terminal_returns=dict(
                schema=returns.SCHEMA,
                room_order=1,
                victory=dict(kind="recorded_entry"),
                defeat=dict(kind="recorded_entry"),
                evidence="Native accepted source-bound challenge visit",
            )
        )
        self.assertEqual(returns.policy(selected), selected["terminal_returns"])
        db = Mock()
        db.execute.return_value.fetchone.side_effect = [
            dict(
                payload=dict(
                    kind=returns.SCHEMA,
                    instance_id=77,
                    profile_sha256="pinned",
                    victory=True,
                )
            ),
            dict(
                instance_id=77,
                entry_map_id=1018,
                entry_object_id=3916,
                entry_destination_id=8198,
            ),
        ]
        source = dict(map_id=1018, instance_id=0, x=25, y=-35, z=0)
        with patch(
            "wakfu_server.owned_story_controller.recognizes_instance", return_value=True
        ), patch(
            "wakfu_server.owned_story_controller._scope", return_value=(selected, set())
        ), patch(
            "wakfu_server.owned_story_controller._digest", return_value="pinned"
        ), patch(
            "wakfu_server.dungeon_recovery._recorded_exterior", return_value=source
        ) as exterior:
            self.assertEqual(
                returns.pending(db, Mock(), dict(id=5, account_id=2, instance_id=77)),
                source,
            )
        exterior.assert_called_once()
        db.execute.return_value.fetchone.side_effect = [None]
        with patch(
            "wakfu_server.owned_story_controller.recognizes_instance", return_value=True
        ), patch(
            "wakfu_server.owned_story_controller._scope", return_value=(selected, set())
        ):
            self.assertIsNone(
                returns.pending(db, Mock(), dict(id=5, account_id=2, instance_id=77))
            )
