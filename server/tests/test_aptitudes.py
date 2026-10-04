import tempfile
import unittest
from pathlib import Path
from wakfu_server.aptitudes import validate, budgets
from wakfu_server.wire import proto_field
from wakfu_server.store import Store
from wakfu_server import builds


def sheet(entries):
    return proto_field(24, (1 << 64) - 1) + b"".join(
        proto_field(34, proto_field(8, bonus) + proto_field(16, points))
        for bonus, points in entries
    )


class AptitudeTests(unittest.TestCase):
    def test_native_java_two_hp_points_codec_and_partial_categories(self):
        blob = bytes.fromhex("18ffffffffffffffffff01220408011002")
        result = validate({"level": 6}, blob)
        self.assertEqual(result["allocations"], {1: 2})
        self.assertEqual(result["available"], {4: 1, 5: 1, 3: 1, 2: 2, 6: 0})
        self.assertEqual(result["spent"][2], 2)
        with self.assertRaises(ValueError):
            validate({"level": 6}, sheet([(1, 3)]))
        with self.assertRaises(ValueError):
            validate({"level": 6}, sheet([(1, 2), (16, 1)]))

    def test_level200_each_category_budget_and_per_bonus_caps(self):
        self.assertEqual(budgets(200), {4: 50, 5: 49, 3: 50, 2: 50, 6: 4})
        self.assertEqual(
            validate(
                {"level": 200},
                sheet(
                    [
                        (1, 50),
                        (23, 50),
                        (18, 50),
                        (11, 49),
                        (2, 1),
                        (3, 1),
                        (4, 1),
                        (5, 1),
                    ]
                ),
            )["spent"],
            budgets(200),
        )
        for entries in ([(16, 11)], [(2, 2)], [(1, 51)], [(1, 1), (1, 1)], [(9999, 1)]):
            with self.assertRaises(ValueError):
                validate({"level": 200}, sheet(entries))

    def test_save_reconnect_and_invalid_allocation_atomicity(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "world.db")
            account = store.register("aptitudes", "password")["id"]
            char = store.create_character(account, "Aptitude Player", breed=8)
            generation = store.begin_session(account)
            store.select_character(account, generation, char["id"])
            with store.connection() as db:
                db.execute("UPDATE characters SET level=6 WHERE id=?", (char["id"],))
            metadata = b"".join(
                proto_field(t, v)
                for t, v in (
                    (8, 0),
                    (18, b"Default"),
                    (24, (1 << 64) - 1),
                    (56, 1),
                    (64, 1),
                )
            )
            blobs = dict(
                sheet=metadata,
                equipment=builds.EMPTY_EQUIPMENT,
                deck=b"",
                aptitudes=sheet([(1, 2)]),
            )
            saved = store.save_build(account, generation, char["id"], 0, blobs)
            self.assertEqual(
                bytes.fromhex(saved["builds"][0]["aptitudes"]), blobs["aptitudes"]
            )
            with self.assertRaises(ValueError):
                store.save_build(
                    account,
                    generation,
                    char["id"],
                    0,
                    dict(blobs, aptitudes=sheet([(1, 3)])),
                )
            self.assertEqual(
                Store(store.path).character(account, char["id"])["builds"],
                saved["builds"],
            )

    def test_two_hp_points_native_percent_combined_with_amulet_and_major_ap(self):
        from wakfu_server.equipment_stats import effective_character, combat_resources
        from wakfu_server.aptitudes import bonuses

        char = {
            "id": 1,
            "breed": 8,
            "level": 6,
            "hp": 110,
            "inventory_items": [],
            "builds": {
                0: {
                    "aptitudes": sheet([(1, 2)]).hex(),
                    "equipment": builds.EMPTY_EQUIPMENT.hex(),
                }
            },
        }
        self.assertEqual(effective_character(char)["max_hp"], 118)
        char["inventory_items"] = [
            dict(uid=1000, character_id=1, reference=2021, quantity=1)
        ]
        char["builds"][0]["equipment"] = proto_field(
            10, proto_field(8, 1000) + proto_field(16, 4)
        ).hex()
        self.assertEqual(effective_character(char)["max_hp"], 125)
        self.assertEqual(combat_resources(char, wp=6)["ap"], 7)
        char["level"] = 200
        char["builds"][0]["aptitudes"] = sheet([(2, 1)]).hex()
        self.assertEqual(combat_resources(char, wp=6)["ap"], 8)
        char["builds"][0]["aptitudes"] = sheet([(3, 1)]).hex()
        self.assertEqual(bonuses(char)["unsupported"][0]["bonus"], 3)
