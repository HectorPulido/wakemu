"""AST projections for entrance-only native mission override resources."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.build_dungeon_entry_overrides import build, projected_criterion


ROOT = Path(__file__).resolve().parents[2]
NATIVE_TRUE = "(IsNeoServer() or not IsNeoServer())"


def inventory(*routes):
    return {"records": [{"native_entry_routes": list(routes)}]}


def route(destination, criterion):
    return {"destination_id": destination, "criterion": criterion}


class DungeonEntryOverrideProjectionTests(unittest.TestCase):
    def test_positive_and_negated_mission_only_expressions_become_true(self):
        for expression in (
            "IsAchievementComplete(100)",
            "not IsAchievementRunning(100)",
            "not (IsAchievementRunning(100) and "
            "IsAchievementObjectiveComplete(101) and "
            "not IsAchievementObjectiveComplete(102))",
            "HasState(103)",
        ):
            with self.subTest(expression=expression):
                self.assertEqual(projected_criterion(expression), NATIVE_TRUE)

    def test_nonmission_requirements_survive_and_or_projections(self):
        self.assertIn(
            "GetRealLevel() >= 50",
            projected_criterion("IsAchievementComplete(100) and GetRealLevel() >= 50"),
        )
        self.assertIn(
            "IsNeoServer()",
            projected_criterion("IsNeoServer() and not IsAchievementComplete(100)"),
        )
        self.assertIn(
            'GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 8',
            projected_criterion(
                'IsNeoServer() and GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 8 '
                "and not IsAchievementComplete(100)"
            ),
        )
        self.assertEqual(
            projected_criterion("IsAchievementComplete(100) or GetRealLevel() >= 50"),
            NATIVE_TRUE,
        )

    def test_only_mission_state_predicates_are_projected(self):
        with self.assertRaisesRegex(ValueError, "Malformed mission prerequisite"):
            projected_criterion("IsAchievementComplete(0)")
        with self.assertRaisesRegex(ValueError, "Malformed mission prerequisite"):
            projected_criterion("HasState(true)")

    def test_build_uses_native_entry_routes_and_rejects_conflicting_destinations(self):
        result = build(
            inventory(
                route(4689, "IsAchievementComplete(100)"),
                route(200, "GetRealLevel() >= 50"),
            )
        )
        self.assertEqual(result, {4689: NATIVE_TRUE})
        with self.assertRaisesRegex(ValueError, "Conflicting native destination"):
            build(
                inventory(
                    route(4689, "IsAchievementComplete(100)"),
                    route(4689, "IsAchievementComplete(101) and GetRealLevel() >= 50"),
                )
            )


class DungeonEntryDatabaseExportTests(unittest.TestCase):
    def setUp(self):
        from tools.build_dungeon_entry_overrides import (
            validate_setting,
            load_database_rows,
            render_properties,
            read_local_database_rows,
        )

        self.validate = validate_setting
        self.load = load_database_rows
        self.render = render_properties
        self.local = read_local_database_rows
        sql = (
            ROOT / "server/migrations/149_dungeon_entry_client_overrides.sql"
        ).read_text()
        self.value = json.loads(sql.split("$reviewed$")[1])
        self.digest = self.value["native_client_sha256"]

    def test_reviewed_db_seed_exports_exact_five_entries_and_client_identity(self):
        rows = self.validate(self.value, self.digest)
        self.assertEqual(set(rows), {720, 4578, 4689, 4714, 4751})
        self.assertNotIn(26873, rows)
        expected = (
            "native_sha256="
            + self.digest
            + "\n# Generated from native entrance routes; never internal doors.\n"
            "720=(not IsNeoServer())\n4578=(not IsNeoServer())\n4689=(IsNeoServer() or not IsNeoServer())\n"
            "4714=(IsNeoServer() or not IsNeoServer())\n"
            '4751=(not ((not IsNeoServer()) or (not (GetGlobalVariable("NEO_BOSS_UNLOCKED") >= 8))))\n'
        )
        self.assertEqual(self.render(rows, self.digest), expected)

    def test_missing_malformed_hash_version_duplicate_identity_fail_closed(self):
        import copy

        bad = [
            None,
            {},
            {**self.value, "version": True},
            {**self.value, "version": 2},
            {**self.value, "native_client_sha256": "x"},
            {**self.value, "source_catalog_revision": "x"},
            {**self.value, "projection_sha256": "0" * 64},
        ]
        for identity in (True, 0, -1, 2**31):
            value = copy.deepcopy(self.value)
            value["entrances"][0]["destination_id"] = identity
            bad.append(value)
        value = copy.deepcopy(self.value)
        value["entrances"].append(value["entrances"][0])
        bad.append(value)
        value = copy.deepcopy(self.value)
        value["entrances"][0]["criterion"] = "True\n720=False"
        bad.append(value)
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.validate(value, self.digest)
        with self.assertRaisesRegex(ValueError, "version mismatch"):
            self.validate(self.value, "0" * 64)

    def test_database_missing_or_incomplete_source_rejected(self):
        class Result:
            def __init__(self, value):
                self.value = value

            def fetchone(self):
                return self.value

        class DB:
            def __init__(self, values):
                self.values = iter(values)

            def execute(self, *args):
                return Result(next(self.values))

        with self.assertRaises(ValueError):
            self.load(DB([None]), self.digest)
        for source in (None, {"complete": False}):
            with self.assertRaises(ValueError):
                self.load(DB([{"value": self.value}, source]), self.digest)
        self.assertEqual(
            len(
                self.load(DB([{"value": self.value}, {"complete": True}]), self.digest)
            ),
            5,
        )

    def test_host_without_driver_queries_only_postgresql_and_fails_closed(self):
        from types import SimpleNamespace

        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            return SimpleNamespace(
                returncode=0, stdout=json.dumps({"value": self.value, "complete": True})
            )

        self.assertEqual(len(self.local(self.digest, run=run)), 5)
        self.assertEqual(
            calls[0][:6], ["docker", "compose", "exec", "-T", "postgres", "psql"]
        )
        self.assertNotIn("inventory.json", " ".join(calls[0]))
        for result in (
            SimpleNamespace(returncode=1, stdout=""),
            SimpleNamespace(returncode=0, stdout=""),
            SimpleNamespace(returncode=0, stdout="{}"),
        ):
            with self.assertRaises(ValueError):
                self.local(self.digest, run=lambda *a, **k: result)


if __name__ == "__main__":
    unittest.main()
