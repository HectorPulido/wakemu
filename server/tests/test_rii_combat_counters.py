import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server.achievements import rii_combat_counters, service, storage


class RiiCombatCounterTests(unittest.TestCase):
    def test_victory_counts_only_target_originals_once_and_clamps_at_completion(self):
        objective = {
            "d": 10579,
            "ckc": "",
            "cke": "",
            "ckf": [
                {
                    "d": 772,
                    "ckm": 'GetAchievementVariable("INCARNAM_nbWapinKilled") >= 3',
                    "ckn": [755],
                }
            ],
        }
        definition = {
            "d": 5145,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjJ": [objective, {"d": 10620, "ckc": "", "cke": "", "ckf": []}],
            "cjK": [],
        }
        current = {
            "variables": {},
            "objectives": [],
            "running": [5145],
            "completed": [],
            "tracking": [5145],
            "recent": [],
            "completion_dates": {},
        }
        character = {"id": 3, "account_id": 4, "map_id": 1385, "instance_id": 0}
        store = SimpleNamespace(now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
        db = Mock()
        db.execute.return_value.fetchone.return_value = {"data": {"native": definition}}
        receipts = set()

        def save(_db, _character_id, after):
            nonlocal current
            current = after

        def receipt(_db, _character_id, key, _payload):
            if key in receipts:
                return False
            receipts.add(key)
            return True

        with patch.object(service, "_owner"), patch.object(
            storage, "load_locked", side_effect=lambda *_: current
        ), patch.object(storage, "record_event", side_effect=receipt), patch.object(
            storage, "store", side_effect=save
        ):
            event = {"fight_id": 1, "original_breeds": [5455, 5456, 1]}
            self.assertEqual(
                [p[0] for p in rii_combat_counters.settle(db, store, character, event)],
                [13295],
            )
            self.assertEqual(current["variables"]["755"], 2)
            self.assertEqual(
                rii_combat_counters.settle(db, store, character, event), []
            )
            self.assertEqual(current["variables"]["755"], 2)
            self.assertEqual(
                [
                    p[0]
                    for p in rii_combat_counters.settle(
                        db,
                        store,
                        character,
                        {"fight_id": 2, "original_breeds": [5455, 5525]},
                    )
                ],
                [13295, 13832],
            )
            self.assertEqual(current["variables"]["755"], 3)
            self.assertEqual(current["objectives"], [10579])

    def test_other_maps_and_unmatched_targets_are_inert(self):
        db = Mock()
        self.assertEqual(
            rii_combat_counters.settle(
                db,
                None,
                {"map_id": 527, "instance_id": 0},
                {"fight_id": 1, "original_breeds": [5455]},
            ),
            [],
        )
        self.assertEqual(
            rii_combat_counters.settle(
                db,
                None,
                {"map_id": 1385, "instance_id": 0},
                {"fight_id": 1, "original_breeds": [1, 2]},
            ),
            [],
        )
        db.execute.assert_not_called()
