"""Level-band policy and player objectives section projection contracts."""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
import json
from pathlib import Path
import unittest

from wakfu_server.custom_tasks import sections
from wakfu_server.objectives import catalog
from wakfu_server.objectives.reward_policies import validate_policy


def band_policy():
    return {
        "bands": [
            {
                "minimum": 1,
                "maximum": 99,
                "rewards": [{"kind": "kamas", "amount": 100}],
            },
            {
                "minimum": 100,
                "maximum": MAX_CHARACTER_LEVEL,
                "rewards": [{"aeV": 5, "ckl": [2021, 1]}],
            },
        ]
    }


def definition(key, kind="task", schedule="once"):
    return {
        "key": key,
        "definition": {"kind": kind, "schedule": {"type": schedule, "timezone": "UTC"}},
    }


class ObjectivesContentTests(unittest.TestCase):
    def test_shipped_content_manifest_is_native_referenced_and_identity_scoped(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "objectives-service"
            / "content-catalog.json"
        )
        content = json.loads(path.read_text())
        inventory = content["inventory"]
        counts = inventory["counts"]
        definitions = content["definitions"]
        policies = {
            row["key"]: validate_policy(row["policy"]) for row in content["policies"]
        }
        self.assertEqual(
            content["provenance"]["revision"],
            "08523b7b8f2dd2e7c5fcac816bfcc7e31f777beb61acb0d76913bfcd568007f8",
        )
        self.assertTrue(
            all(
                len(value) == 64
                for value in content["provenance"]["document_hashes"].values()
            )
        )

        self.assertEqual(
            counts,
            {
                "maps": 53,
                "special_zones": 109,
                "dungeons_admitted": 87,
                "dungeons_with_qualification_notes": 30,
                "definitions": 265,
            },
        )
        self.assertEqual(len(definitions), counts["definitions"])
        self.assertEqual(
            set(policies),
            {
                "content-v1.exploration",
                "content-v1.territory",
                "content-v1.daily",
                "content-v1.dungeon",
                "content-v1.weekly",
                "weekly-ranking-v1",
            },
        )
        keys = set()
        for definition_value in definitions:
            normalized = catalog.validate_definition(definition_value)
            self.assertTrue(normalized["key"].startswith("content-v1."))
            self.assertNotIn(normalized["key"], keys)
            keys.add(normalized["key"])
            for reward in normalized["rewards"]:
                if reward.get("kind") == "scaled":
                    self.assertIn(reward["policy_key"], policies)

        equipment = {row["reference"]: row for row in inventory["equipment"]}
        sublimations = set(inventory["basic_sublimation_references"])
        materials = set(inventory["material_references"])
        self.assertEqual(len(equipment), 36)
        self.assertEqual(len(sublimations), 388)
        self.assertEqual(materials, {27083, 27093})
        for policy_key, policy in policies.items():
            for band in policy["bands"]:
                for reward in band["rewards"]:
                    if reward.get("aeV") == 5:
                        self.assertIn(reward["ckl"][0], materials)
                    if reward.get("kind") == "random_item":
                        for reference in reward["references"]:
                            self.assertTrue(
                                reference in equipment or reference in sublimations,
                                (policy_key, band["minimum"], reference),
                            )
                            if reference in equipment:
                                self.assertLessEqual(
                                    equipment[reference]["minimum_level"],
                                    band["minimum"],
                                )

        maps = inventory["maps"]
        zones = inventory["special_zones"]
        dungeons = inventory["dungeons"]
        self.assertEqual(len({row["map_id"] for row in maps}), 53)
        self.assertEqual(len({(row["map_id"], row["region_id"]) for row in zones}), 109)
        self.assertEqual(len({row["definition_id"] for row in dungeons}), 87)
        map_definitions = [
            row for row in definitions if row["key"].startswith("content-v1.map.")
        ]
        region_definitions = [
            row for row in definitions if row["key"].startswith("content-v1.region.")
        ]
        dungeon_definitions = [
            row for row in definitions if row["key"].startswith("content-v1.dungeon.")
        ]
        self.assertEqual(
            {row["objectives"][0]["filters"]["map_id"] for row in map_definitions},
            {row["map_id"] for row in maps},
        )
        self.assertEqual(
            {
                (
                    row["objectives"][0]["filters"]["map_id"],
                    row["objectives"][0]["filters"]["region_id"],
                )
                for row in region_definitions
            },
            {(row["map_id"], row["region_id"]) for row in zones},
        )
        self.assertEqual(
            {
                row["objectives"][0]["filters"]["dungeon_id"]
                for row in dungeon_definitions
            },
            {row["definition_id"] for row in dungeons},
        )
        weekly_challenge = [
            row for row in definitions if row["key"] == "content-v1.weekly.challenge"
        ]
        self.assertEqual(len(weekly_challenge), 1)
        self.assertEqual(
            weekly_challenge[0]["level_range"],
            {"minimum": 1, "maximum": MAX_CHARACTER_LEVEL},
        )
        self.assertTrue(
            weekly_challenge[0]["objectives"][0]["filters"].get("ranked") is True
        )
        weekly_dungeon = [
            row for row in definitions if row["key"] == "content-v1.weekly.dungeons"
        ]
        self.assertEqual(len(weekly_dungeon), 1)
        pvp = [row for row in definitions if row["key"].startswith("content-v1.pvp.")]
        self.assertEqual(
            {row["key"] for row in pvp},
            {
                "content-v1.pvp.first_victory",
                "content-v1.pvp.weekly_victories",
            },
        )
        self.assertEqual(pvp[0]["objectives"][0]["filters"]["same_account"], False)
        self.assertIn("content-v1.daily.pve_victories", keys)
        self.assertTrue(
            all(
                row["objectives"][0]["filters"].get("ranked") is True
                for row in definitions
                if row["key"] == "content-v1.weekly.challenge"
            )
        )

    def test_level_policy_requires_gapless_bounded_levels_and_valid_rewards(self):
        valid = band_policy()
        self.assertEqual(validate_policy(valid), valid)
        malformed = (
            {"bands": valid["bands"][:1]},
            {
                "bands": [
                    {
                        "minimum": 1,
                        "maximum": 100,
                        "rewards": [{"kind": "kamas", "amount": 1}],
                    },
                    {
                        "minimum": 100,
                        "maximum": MAX_CHARACTER_LEVEL,
                        "rewards": [{"kind": "kamas", "amount": 1}],
                    },
                ]
            },
            {
                "bands": [
                    {
                        "minimum": 1,
                        "maximum": 99,
                        "rewards": [{"kind": "scaled", "policy_key": "nested"}],
                    },
                    valid["bands"][1],
                ]
            },
            {
                "bands": [
                    {"minimum": 1, "maximum": 99, "rewards": []},
                    valid["bands"][1],
                ]
            },
            {
                "bands": [
                    {
                        "minimum": 1,
                        "maximum": 99,
                        "rewards": [{"aeV": 5, "ckl": [2021, 0]}],
                    },
                    valid["bands"][1],
                ]
            },
        )
        for policy in malformed:
            with self.subTest(policy=policy), self.assertRaises(
                (ValueError, TypeError)
            ):
                validate_policy(policy)

    def test_tasks_argument_parser_validates_sections_and_one_based_pages(self):
        self.assertEqual(sections.parse([]), ("overview", 1))
        self.assertEqual(sections.parse(["PvP", "2"]), ("pvp", 2))
        for args in (
            ("unknown",),
            ("tasks", "0"),
            ("tasks", "1", "3"),
            ("tasks", "one"),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                sections.parse(list(args))

    def test_task_pages_are_stable_bounded_and_keep_overview_catalog_entry(self):
        snapshot = [
            {
                "key": f"task-{index:02d}",
                "title": f"Task {index:02d}",
                "description": "Progress only",
                "count": 0,
                "target": 1,
                "completed": False,
            }
            for index in range(41)
        ]
        definitions = [definition(row["key"]) for row in snapshot]
        definitions.append(definition("gobball-kills-20", "achievement", "once"))
        snapshot.append(
            {
                "key": "gobball-kills-20",
                "title": "Gobball kills",
                "description": "Native-preserving task",
                "count": 3,
                "target": 20,
                "completed": False,
            }
        )

        first = sections.project(snapshot, definitions, "tasks", 1)
        second = sections.project(snapshot, definitions, "tasks", 2)
        third = sections.project(snapshot, definitions, "tasks", 3)
        self.assertEqual((len(first), len(second), len(third)), (21, 21, 2))
        self.assertIn("page 1/3", first[0]["title"])
        self.assertIn("page 2/3", second[0]["title"])
        self.assertIn("page 3/3", third[0]["title"])
        keys = [row["key"] for page in (first, second, third) for row in page[1:]]
        ordered = [
            row["key"]
            for row in sorted(
                snapshot[:41], key=lambda row: (row["completed"], row["key"])
            )
        ]
        self.assertEqual(keys, ordered)

        overview = sections.project(snapshot, definitions, "overview", 1)
        self.assertIn("gobball-kills-20", {row["key"] for row in overview})
        self.assertIn("!tasks achievements", overview[0]["description"])
        self.assertIn(
            "page 3/3", sections.project(snapshot, definitions, "tasks", 4)[0]["title"]
        )

    def test_categories_keep_weekly_daily_pvp_and_native_achievement_separate(self):
        definitions = [
            definition("week", "recurring", "weekly"),
            definition("day", "daily", "daily"),
            definition("duel", "pvp", "weekly"),
            definition("old", "achievement", "once"),
        ]
        self.assertEqual(
            [sections.category(row["definition"]) for row in definitions],
            ["weekly", "daily", "pvp", "achievements"],
        )
        snapshot = [
            {
                "key": key,
                "title": key,
                "description": "",
                "count": 0,
                "target": 1,
                "completed": False,
            }
            for key in ("week", "day", "duel", "old")
        ]
        self.assertEqual(
            [
                row["key"]
                for row in sections.project(snapshot, definitions, "weekly", 1)[1:]
            ],
            ["week"],
        )
        self.assertEqual(
            [
                row["key"]
                for row in sections.project(snapshot, definitions, "pvp", 1)[1:]
            ],
            ["duel"],
        )


if __name__ == "__main__":
    unittest.main()
