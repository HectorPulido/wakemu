import copy
import struct
import unittest
from unittest.mock import patch

from wakfu_server.achievements import item_activation, mission_progress, service, wire


def state():
    return {
        "variables": {},
        "objectives": [],
        "running": [],
        "completed": [],
        "tracking": [7],
        "recent": [],
        "completion_dates": {},
    }


class MissionTrackingTests(unittest.TestCase):
    def test_reusing_starter_reports_active_or_completed_without_changing_progress(
        self,
    ):
        plan = dict(
            definition_id=1197,
            native_use_criterion="",
            native_use_has_criteria=False,
            native_definition_availability="",
            native_action_criterion="!IsAchievementActive(1197)",
            native_definition_criterion="GetRealLevel() >= 105",
            minimum_real_level=105,
            scope="initial_activation_only",
            repeatable=False,
            duration=0,
            period=0,
        )
        for field, text in (
            ("running", "ya está activa"),
            ("completed", "ya está completada"),
        ):
            with self.subTest(field=field):
                before = state()
                before[field] = [1197]
                with patch.object(item_activation, "_owner"), patch.object(
                    item_activation.storage, "load_locked", return_value=before
                ), patch.object(
                    item_activation.storage, "store"
                ) as saved, patch.object(
                    item_activation.storage, "record_event"
                ) as event:
                    result = item_activation.activate(
                        None, None, {"id": 4, "level": 105}, plan, source_uid=12
                    )
                self.assertFalse(result["applied"])
                self.assertEqual(result["packets"], [])
                self.assertIn(text, result["feedback"])
                saved.assert_not_called()
                event.assert_not_called()

    def test_item_activation_tracks_and_sends_native_notification(self):
        before = state()
        plan = dict(
            definition_id=1197,
            native_use_criterion="",
            native_use_has_criteria=False,
            native_definition_availability="",
            native_action_criterion="!IsAchievementActive(1197)",
            native_definition_criterion="GetRealLevel() >= 105",
            minimum_real_level=105,
            scope="initial_activation_only",
            repeatable=False,
            duration=0,
            period=0,
            action_id=3773,
            item_ref=16471,
        )
        with patch.object(item_activation, "_owner"), patch.object(
            item_activation.storage, "load_locked", return_value=before
        ), patch.object(
            item_activation.storage, "record_event", return_value=True
        ), patch.object(
            item_activation.storage, "store"
        ) as saved, patch.object(
            item_activation.wire, "changes", wraps=wire.changes
        ), patch.object(
            item_activation, "deepcopy", wraps=copy.deepcopy
        ):
            from datetime import datetime, timezone

            store = unittest.mock.Mock()
            store.now.return_value = datetime.now(timezone.utc)
            result = item_activation.activate(
                object(), store, {"id": 4, "level": 105}, plan, source_uid=12
            )
        self.assertEqual(saved.call_args.args[2]["tracking"], [7, 1197])
        self.assertEqual(
            result["packets"],
            [
                (13312, struct.pack(">qi", 4, 1197)),
                (13371, struct.pack(">qiB", 4, 1197, 1)),
            ],
        )
        self.assertEqual(before["tracking"], [7])

    def test_track_active_mission_and_untrack(self):
        current = state()
        current["running"] = [1197]
        with patch.object(service, "_owner"), patch.object(
            service.storage, "load_locked", return_value=current
        ), patch.object(service.storage, "store"), patch.object(
            service.catalog, "load"
        ) as catalog:
            self.assertEqual(
                service.track(None, {"id": 4}, 1197, True),
                [(13371, struct.pack(">qiB", 4, 1197, 1))],
            )
            self.assertEqual(current["tracking"], [7, 1197])
            self.assertEqual(
                service.track(None, {"id": 4}, 1197, False),
                [(13371, struct.pack(">qiB", 4, 1197, 0))],
            )
            self.assertEqual(current["tracking"], [7])
            catalog.assert_not_called()

    def test_full_tracking_preserves_existing(self):
        current = state()
        current["running"] = [1197]
        current["tracking"] = list(range(1, 256))
        mission_progress.auto_track(current, 1197)
        self.assertEqual(current["tracking"], list(range(1, 256)))

    def test_unrecognized_inactive_cannot_be_tracked(self):
        with patch.object(service, "_owner"), patch.object(
            service.storage, "load_locked", return_value=state()
        ), patch.object(
            service.catalog, "load", return_value={"definitions": {}}
        ), patch.object(
            service, "_guild_daily_trackable", return_value=False
        ):
            with self.assertRaises(ValueError):
                service.track(None, {"id": 4}, 1197, True)
