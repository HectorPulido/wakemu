import unittest
from copy import deepcopy

from wakfu_server.achievements import counter_missions


def objective(identity, variable, source, count, prerequisite=""):
    return {
        "d": identity,
        "ckc": prerequisite,
        "cke": "",
        "ckf": [
            {
                "d": variable,
                "ckm": f'GetAchievementVariable("counter_{variable}") >= {count}',
                "ckn": [source],
            }
        ],
    }


def definition(identity, objectives):
    return {
        "d": identity,
        "native_class": "aJM",
        "aqb": False,
        "cjI": "",
        "cjJ": objectives,
        "cjK": [],
    }


def state():
    return {
        "variables": {},
        "objectives": [],
        "running": [5145],
        "completed": [],
        "tracking": [5145],
        "recent": [],
        "completion_dates": {},
    }


class CounterMissionsTest(unittest.TestCase):
    def test_native_thresholds_increment_once_and_require_active_quest(self):
        quests = [
            definition(
                5145, [objective(10597, 773, 756, 3), objective(10578, 774, 757, 2)]
            )
        ]
        current = state()
        original = deepcopy(current)
        for count in range(1, 4):
            current, _, new, _ = counter_missions.advance(
                current, quests, 756, character={}, store=None, now_ms=100
            )
            self.assertEqual(current["variables"]["756"], count)
            self.assertEqual(new, [10597] if count == 3 else [])
        self.assertEqual(original, state())
        current, _, new, _ = counter_missions.advance(
            current, quests, 756, character={}, store=None, now_ms=100
        )
        self.assertEqual(current["variables"]["756"], 3)
        self.assertEqual(new, [])
        for count in range(2):
            current, _, _, completed = counter_missions.advance(
                current, quests, 757, character={}, store=None, now_ms=100
            )
        self.assertEqual(completed, [5145])
        self.assertEqual(current["objectives"], [10578, 10597])
        self.assertEqual(
            counter_missions.advance(
                current, quests, 757, character={}, store=None, now_ms=100
            )[0],
            current,
        )

    def test_unsupported_counter_conditions_do_not_advance(self):
        target = objective(1, 10, 20, 3)
        target["ckf"][0]["ckm"] = 'GetAchievementVariable("counter_10") == 3'
        self.assertEqual(counter_missions.bindings([definition(5145, [target])]), {})
        target["ckf"][0]["ckm"] = 'GetAchievementVariable("counter_10") >= 3'
        target["ckf"].append(deepcopy(target["ckf"][0]))
        self.assertEqual(counter_missions.bindings([definition(5145, [target])]), {})

    def test_unknown_prerequisite_keeps_counter_without_false_completion(self):
        target = objective(1, 10, 20, 1, "UnknownNativeCriterion()")
        current, _, objectives, _ = counter_missions.advance(
            state(),
            [definition(5145, [target])],
            20,
            character={},
            store=None,
            now_ms=100,
        )
        self.assertEqual(current["variables"], {"20": 1})
        self.assertEqual(objectives, [])


class WodentHarvestSettlementTest(unittest.TestCase):
    def test_committed_harvest_updates_counter_and_only_after_threshold_objective(self):
        from datetime import datetime, timezone
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from wakfu_server.achievements import service, storage

        mission = definition(
            5145, [objective(10597, 773, 756, 3), objective(10578, 774, 757, 2)]
        )
        current = state()
        character = {"id": 3, "account_id": 4, "map_id": 1385}
        db = Mock()
        db.execute.return_value.fetchone.return_value = {"data": {"native": mission}}
        store = SimpleNamespace(now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))

        def save(_db, _char, after):
            nonlocal current
            current = after

        with patch.object(service, "_owner"), patch.object(
            storage, "load_locked", side_effect=lambda *_: current
        ), patch.object(
            storage, "record_event", return_value=True
        ) as receipt, patch.object(
            storage, "store", side_effect=save
        ):
            for count in range(1, 4):
                packets = counter_missions.settle_wodent_harvest(
                    db, store, character, token=str(count), item_reference=30927
                )
                self.assertEqual(current["variables"]["756"], count)
                self.assertEqual(
                    [packet[0] for packet in packets],
                    [13295, 13832, 13371, 13371]
                    if count == 3
                    else [13295, 13371, 13371],
                )
            self.assertEqual(receipt.call_count, 3)
            self.assertEqual(
                counter_missions.settle_wodent_harvest(
                    db, store, character, token="4", item_reference=30927
                ),
                [],
            )
            self.assertEqual(receipt.call_count, 3)

    def test_other_item_or_map_do_not_touch_transaction(self):
        from unittest.mock import Mock

        db = Mock()
        self.assertEqual(
            counter_missions.settle_wodent_harvest(
                db, None, {"map_id": 527}, token="t", item_reference=30927
            ),
            [],
        )
        self.assertEqual(
            counter_missions.settle_wodent_harvest(
                db, None, {"map_id": 1385}, token="t", item_reference=4
            ),
            [],
        )
        db.execute.assert_not_called()


class RiiEcosystemSettlementTest(unittest.TestCase):
    def test_each_reviewed_event_advances_only_matching_counter(self):
        from datetime import datetime, timezone
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from wakfu_server.achievements import service, storage

        cases = [
            ("monster_harvest", 30927, 5145, 10597, 756, 3),
            ("resource_harvest", 31007, 5155, 10598, 759, 3),
            ("resource_harvest", 31006, 5155, 10599, 758, 3),
            ("planting", 30927, 5145, 10578, 757, 2),
            ("planting", 31007, 5155, 10600, 760, 3),
        ]
        character = {"id": 3, "account_id": 4, "map_id": 1385}
        store = SimpleNamespace(now=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))
        for kind, item, quest, objective_id, variable, threshold in cases:
            with self.subTest(kind=kind, item=item):
                current = state()
                current["running"] = [quest]
                current["tracking"] = [quest]
                mission = definition(
                    quest,
                    [
                        objective(objective_id, 999, variable, threshold),
                        objective(99999, 9999, 9998, 1),
                    ],
                )
                db = Mock()
                db.execute.return_value.fetchone.return_value = {
                    "data": {"native": mission}
                }

                def save(_db, _char, after):
                    nonlocal current
                    current = after

                with patch.object(service, "_owner"), patch.object(
                    storage, "load_locked", side_effect=lambda *_: current
                ), patch.object(
                    storage, "record_event", return_value=True
                ), patch.object(
                    storage, "store", side_effect=save
                ):
                    for count in range(1, threshold + 1):
                        packets = counter_missions.settle_rii_event(
                            db,
                            store,
                            character,
                            token=str(count),
                            kind=kind,
                            item_reference=item,
                        )
                        self.assertEqual(current["variables"], {str(variable): count})
                        self.assertEqual(
                            [p[0] for p in packets],
                            [13295, 13832, 13371, 13371]
                            if count == threshold
                            else [13295, 13371, 13371],
                        )
