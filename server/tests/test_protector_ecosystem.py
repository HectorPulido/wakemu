"""Native protector tax bootstrap identity, merge and fail-closed boundaries."""
import struct
import unittest
from unittest.mock import patch
from wakfu_server.maps import protector_ecosystem as subject


class Database:
    def __init__(self, policy=None):
        self.policy = (
            policy
            if policy is not None
            else {"schema_version": 1, "contexts": {"1": 0.05}}
        )

    def execute(self, sql, params):
        assert "SELECT value FROM settings" in sql
        assert params == (subject.SETTING,)
        return self

    def fetchone(self):
        return {"value": self.policy}


class ProtectorEcosystemTests(unittest.TestCase):
    def setUp(self):
        self.wish_patch = patch.object(subject, "_wishes", return_value={})
        self.wish_patch.start()
        self.population_patch = patch.object(subject, "_satisfaction", return_value={})
        self.population_patch.start()
        self.addCleanup(self.population_patch.stop)
        self.addCleanup(self.wish_patch.stop)

    def tearDown(self):
        subject._map_ids.cache_clear()

    def test_map_join_uses_native_protector_identity_and_skips_unmapped(self):
        def load(path):
            if path.name == "territory-protector-bonuses.json":
                return {
                    "territories": {"76101": {"map_id": 527}, "2": {"map_id": None}}
                }
            return {
                "territories": [
                    {
                        "territory_id": 76101,
                        "raw_native": {"ctC": 303, "ctH": 76101, "Xt": 0},
                    },
                    {"territory_id": 2, "raw_native": {"ctC": 400, "ctH": 2, "Xt": 30}},
                ]
            }

        subject._map_ids.cache_clear()
        with patch.object(subject.native_catalog, "load", side_effect=load), patch(
            "builtins.open", side_effect=AssertionError("filesystem read")
        ):
            records = subject.bootstrap_records(Database(), 527)
        self.assertEqual(len(records), 1)
        expected = (
            struct.pack(">iBiii", 303, 1, 0, 0, 76101)
            + bytes(6)
            + b"\x01"
            + struct.pack(">HBf", 1, 1, 0.05)
            + bytes(5)
        )
        self.assertEqual(records[0], expected)
        self.assertEqual(len(records[0]), 36)

    def test_captured_full_record_is_enriched_once_and_fields_preserved(self):
        record = struct.pack(">iBiiiBiq", 424, 1, 0, 0, 0, 1, 5474, -12345) + bytes(11)
        with patch.object(
            subject,
            "_map_ids",
            return_value={1385: ((303, 0, 0, 76101), (424, 0, 0, 93601))},
        ):
            result = subject.bootstrap_records(Database(), 1385, (record,))
            self.assertEqual(len(result), 2)
            full = result[1]
            self.assertEqual(full[:35], record[:35])
            self.assertEqual(full[43:], record[36:])
            self.assertEqual(len(full), 48)
            self.assertEqual(
                subject.bootstrap_records(Database(), 1385, (full,))[1], full
            )
            with self.assertRaises(ValueError):
                subject.bootstrap_records(Database(), 1385, (record, record))

    def test_invalid_policy_or_record_fails_closed(self):
        for policy in (
            {},
            {"schema_version": 1, "contexts": {"0": 0.05}},
            {"schema_version": 1, "contexts": {"1": True}},
            {"schema_version": 1, "contexts": {"1": 0.01}},
            {"schema_version": 1, "contexts": {"1": float("nan")}},
        ):
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                subject.bootstrap_records(Database(policy), 527)
        with patch.object(subject, "_map_ids", return_value={}):
            with self.assertRaises(ValueError):
                subject.bootstrap_records(Database(), 527, (b"\x00\x00\x01\x2f",))
            self.assertEqual(subject.bootstrap_records(Database(), 9999), ())

    def test_all_astrub_protectors_have_native_territory_and_nation_sections(self):
        bindings = [
            (203, 66701),
            (292, 75701),
            (293, 76001),
            (299, 75601),
            (300, 75801),
            (301, 75901),
            (302, 76201),
            (303, 76101),
        ]

        def load(path):
            if path.name == "territory-protector-bonuses.json":
                return {
                    "territories": {
                        str(territory): {"map_id": 527} for _, territory in bindings
                    }
                }
            return {
                "territories": [
                    {
                        "territory_id": territory,
                        "raw_native": {"ctC": identity, "ctH": territory, "Xt": 0},
                    }
                    for identity, territory in bindings
                ]
            }

        with patch.object(subject.native_catalog, "load", side_effect=load):
            records = subject.bootstrap_records(Database(), 527)
        self.assertEqual(len(records), 8)
        for record, (identity, territory) in zip(records, bindings):
            self.assertEqual(
                struct.unpack_from(">iBiii", record), (identity, 1, 0, 0, territory)
            )
            self.assertEqual(record[17:23], bytes(6))
            self.assertEqual(record[23], 1)
            self.assertEqual(struct.unpack_from(">HBf", record, 24)[:2], (1, 1))
            self.assertEqual(record[31:], bytes(5))

    def test_invalid_native_nation_rejects(self):
        def load(path):
            if path.name == "territory-protector-bonuses.json":
                return {"territories": {"76101": {"map_id": 527}}}
            return {
                "territories": [
                    {
                        "territory_id": 76101,
                        "raw_native": {"ctC": 303, "ctH": 76101, "Xt": True},
                    }
                ]
            }

        with patch.object(
            subject.native_catalog, "load", side_effect=load
        ), self.assertRaises(ValueError):
            subject.bootstrap_records(Database(), 527)

    def test_ermi_native_monster_and_plant_threshold_sections(self):
        wishes = (
            b"\x01"
            + struct.pack(">Hiii", 1, 68, 200, 300)
            + b"\x01"
            + struct.pack(">Hiii", 1, 10, 200, 300)
            + b"\x00"
        )
        with patch.object(
            subject, "_map_ids", return_value={527: ((300, 0, 0, 75801),)}
        ), patch.object(subject, "_wishes", return_value={300: wishes}):
            (record,) = subject.bootstrap_records(Database(), 527)
        self.assertEqual(
            record[:33],
            struct.pack(">iBiii", 300, 1, 0, 0, 75801)
            + bytes(6)
            + b"\x01"
            + struct.pack(">HBf", 1, 1, 0.05)
            + bytes(2),
        )
        self.assertEqual(record[33:], wishes)
        self.assertEqual(len(record), 64)

    def test_native_wish_catalog_encodes_exact_targets_and_empty_sections(self):
        self.wish_patch.stop()
        subject._wishes.cache_clear()
        self.addCleanup(subject._wishes.cache_clear)
        document = {
            "territories": [
                {
                    "raw_native": {
                        "ctC": 300,
                        "ctN": [{"aIc": 68, "ctP": 200, "ctQ": 300}],
                        "ctO": [],
                    }
                }
            ]
        }
        with patch.object(subject.native_catalog, "load", return_value=document):
            self.assertEqual(
                subject._wishes()[300],
                b"\x01" + struct.pack(">Hiii", 1, 68, 200, 300) + b"\x01\x00\x00\x00",
            )
        subject._wishes.cache_clear()
        document["territories"][0]["raw_native"]["ctN"][0]["ctP"] = True
        with patch.object(
            subject.native_catalog, "load", return_value=document
        ), self.assertRaises(ValueError):
            subject._wishes()

    def test_explicit_zero_satisfaction_with_native_wishes(self):
        wishes = b"\x01" + struct.pack(">Hiii", 1, 68, 200, 300) + b"\x01\x00\x00\x00"
        with patch.object(
            subject, "_map_ids", return_value={527: ((300, 0, 0, 75801),)}
        ), patch.object(subject, "_wishes", return_value={300: wishes}), patch.object(
            subject, "_satisfaction", return_value={300: 1}
        ):
            (record,) = subject.bootstrap_records(Database(), 527, instance_id=77)
        self.assertEqual(record[32:34], b"\x01\x01")
        self.assertEqual(record[34:], wishes)

    def test_complete_instance_snapshot_is_shared_and_incomplete_suppressed(self):
        self.population_patch.stop()
        from wakfu_server import ecology_population
        from wakfu_server.characters import territory_bonuses

        bindings = {527: ((300, 0, 0, 75801), (303, 0, 0, 76101))}
        population = {
            "complete": True,
            "regions": {75801: {"monster": {68: 58}, "plant": {10: 77}}},
        }
        with patch.object(subject, "_map_ids", return_value=bindings), patch.object(
            ecology_population, "snapshot", return_value=population
        ) as snapshot, patch.object(
            territory_bonuses,
            "evaluate_population",
            side_effect=[{"state_id": 1917}, {"state_id": 1916}],
        ) as evaluate:
            self.assertEqual(
                subject._satisfaction(Database(), 527, 77), {300: 1, 303: 3}
            )
            snapshot.assert_called_once()
            self.assertEqual(snapshot.call_args.args[1:], (527, 77))
            self.assertTrue(snapshot.call_args.kwargs["exclude_unassigned"])
            self.assertEqual(
                evaluate.call_args_list[0].args, (75801, {68: 58}, {10: 77})
            )
            population["complete"] = False
            evaluate.reset_mock()
            self.assertEqual(subject._satisfaction(Database(), 527, 77), {})
            evaluate.assert_not_called()
