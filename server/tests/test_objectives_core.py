"""Pure contracts for declarative objectives and timezone recurrence."""
import copy
from datetime import datetime, timezone
import unittest

from wakfu_server.objectives import catalog, engine, schedules


def definition():
    return {
        "key": "daily-hunt",
        "title": "Daily hunt",
        "description": "Defeat two gobballs and plant a seed.",
        "kind": "daily",
        "enabled": True,
        "objectives": [
            {
                "key": "kills",
                "event": "original_monster_killed",
                "filters": {"references": [1, 4086]},
                "target": 2,
            },
            {
                "key": "plant",
                "event": "monster_seed_planted",
                "filters": {
                    "family_id": 68,
                    "seed_reference": 7361,
                    "resource_reference": 192,
                },
                "target": 1,
            },
        ],
        "schedule": {"type": "daily", "timezone": "America/Bogota"},
        "rewards": [{"kind": "kamas", "amount": 100}],
    }


class ObjectivesCoreTests(unittest.TestCase):
    def test_independent_objective_counts_and_authoritative_event_filtering(self):
        rules = catalog.validate_definition(definition())["objectives"]
        kill_event = {
            "kind": "original_monster_killed",
            "fight_id": 8,
            "actors": [
                {"actor_id": -1, "reference": 1},
                {"actor_id": -2, "reference": 4086},
                {"actor_id": -3, "reference": 999},
            ],
        }
        self.assertEqual(engine.increment(rules[0], kill_event), 2)
        self.assertEqual(engine.increment(rules[1], kill_event), 0)
        plant_event = {
            "kind": "monster_seed_planted",
            "family_ids": [68, 69],
            "seed_reference": 7361,
            "resource_reference": 192,
        }
        self.assertEqual(engine.increment(rules[1], plant_event), 1)
        self.assertEqual(
            engine.increment(rules[1], dict(plant_event, family_ids=[69])), 0
        )
        self.assertEqual(
            engine.increment(rules[1], dict(plant_event, resource_reference=193)), 0
        )

    def test_schedule_periods_use_local_calendar_boundaries_and_dst(self):
        daily = {"type": "daily", "timezone": "America/New_York"}
        before = datetime(2026, 3, 8, 6, 59, tzinfo=timezone.utc)
        after = datetime(2026, 3, 8, 7, 1, tzinfo=timezone.utc)
        self.assertEqual(schedules.period_key(daily, before), "2026-03-08")
        self.assertEqual(
            schedules.period_key(daily, before), schedules.period_key(daily, after)
        )
        next_local_day = datetime(2026, 3, 9, 4, 1, tzinfo=timezone.utc)
        self.assertNotEqual(
            schedules.period_key(daily, after),
            schedules.period_key(daily, next_local_day),
        )

    def test_weekly_boundary_and_calendar_date_or_annual_match(self):
        weekly = {"type": "weekly", "timezone": "UTC"}
        self.assertNotEqual(
            schedules.period_key(
                weekly, datetime(2026, 10, 18, 23, 59, tzinfo=timezone.utc)
            ),
            schedules.period_key(
                weekly, datetime(2026, 10, 19, 0, 0, tzinfo=timezone.utc)
            ),
        )
        calendar = {
            "type": "calendar",
            "timezone": "UTC",
            "dates": ["2026-10-15"],
            "month_days": ["10-16"],
        }
        self.assertIsNone(
            schedules.period_key(
                calendar, datetime(2026, 10, 14, 23, 59, tzinfo=timezone.utc)
            )
        )
        self.assertEqual(
            schedules.period_key(calendar, datetime(2026, 10, 15, tzinfo=timezone.utc)),
            "2026-10-15",
        )
        self.assertEqual(
            schedules.period_key(calendar, datetime(2027, 10, 16, tzinfo=timezone.utc)),
            "2027-10-16",
        )

    def test_interval_anchor_and_once_are_deterministic(self):
        interval = {
            "type": "interval",
            "timezone": "UTC",
            "anchor": "2026-01-01T00:00:00+00:00",
            "seconds": 3600,
        }
        self.assertIsNone(
            schedules.period_key(
                interval, datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)
            )
        )
        self.assertEqual(
            schedules.period_key(
                interval, datetime(2026, 1, 1, 1, 59, 59, tzinfo=timezone.utc)
            ),
            "1",
        )
        self.assertEqual(
            schedules.period_key(
                interval, datetime(2026, 1, 1, 2, tzinfo=timezone.utc)
            ),
            "2",
        )
        self.assertEqual(
            schedules.period_key(
                {"type": "once", "timezone": "UTC"},
                datetime(2040, 1, 1, tzinfo=timezone.utc),
            ),
            "once",
        )
        with self.assertRaisesRegex(ValueError, "timezone"):
            schedules.period_key(interval, datetime(2026, 1, 1))

    def test_semantic_revision_changes_only_for_behavior(self):
        original = catalog.validate_definition(definition())
        signature = catalog.semantic_signature(original)
        for field, value in (
            ("title", "Renamed"),
            ("description", "New copy"),
            ("enabled", False),
        ):
            changed = copy.deepcopy(original)
            changed[field] = value
            self.assertEqual(catalog.semantic_signature(changed), signature)
        changed = copy.deepcopy(original)
        changed["objectives"][0]["target"] += 1
        self.assertNotEqual(catalog.semantic_signature(changed), signature)

    def test_native_title_emote_item_xp_and_random_rewards_validate_from_admin_shapes(
        self,
    ):
        value = definition()
        value["rewards"] = [
            {"aeV": 2, "ckl": [17]},
            {"aeV": 3, "ckl": [761]},
            {"aeV": 5, "ckl": [2021, 2]},
            {"aeV": 6, "ckl": [123456]},
            {"kind": "random_item", "references": [2021, 2025], "quantity": 1},
        ]
        normalized = catalog.validate_definition(value)
        self.assertEqual(normalized["rewards"][3], {"aeV": 6, "ckl": [123456]})
        for invalid in (
            {"aeV": 2, "ckl": [65536]},
            {"aeV": 3, "ckl": [0]},
            {"aeV": 5, "ckl": [2021, 32768]},
            {"aeV": 6, "ckl": [True]},
        ):
            changed = definition()
            changed["rewards"] = [invalid]
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                catalog.validate_definition(changed)

    def test_definition_rejects_duplicate_keys_unsafe_expressions_and_bad_schedules(
        self,
    ):
        invalid = []
        item = definition()
        item["objectives"].append(copy.deepcopy(item["objectives"][0]))
        invalid.append(item)
        item = definition()
        item["objectives"][0]["filters"] = {"__import__": "os"}
        invalid.append(item)
        item = definition()
        item["schedule"] = {"type": "daily", "timezone": "No/Such_Zone"}
        invalid.append(item)
        item = definition()
        item["rewards"] = [{"kind": "kamas", "amount": True}]
        invalid.append(item)
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(
                (ValueError, TypeError, KeyError)
            ):
                catalog.validate_definition(item)


if __name__ == "__main__":
    unittest.main()
