"""Activation must preserve installed native flow and reject stale evidence."""
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from activate_prepared_dungeon_configurations import activate


class DungeonCandidateActivationTests(unittest.TestCase):
    def test_missing_lifecycle_evidence_prevents_database_access(self):
        store = Mock()
        with self.assertRaises(ValueError):
            activate(
                store,
                dict(
                    records=[dict(route="one", status="offline_configuration_prepared")]
                ),
                dict(records=[], source_sha256={}),
                Path("/unused"),
            )
        store.connection.assert_not_called()

    def test_stale_source_evidence_prevents_database_access(self):
        store = Mock()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.py"
            source.write_text("changed")
            with self.assertRaises(ValueError):
                activate(
                    store,
                    dict(records=[]),
                    dict(records=[], source_sha256={str(source): "old-hash"}),
                    Path(directory) / "backup.json",
                )
        store.connection.assert_not_called()

    def test_existing_native_physical_and_teleport_configurations_are_preserved(self):
        from wakfu_server.maps import dungeon_runtime_config

        with tempfile.TemporaryDirectory() as directory:
            route = dict(key="one")
            candidate = Path(directory) / "candidate.json"
            candidate.write_text(json.dumps(dict(route=route)))
            row = dict(
                route="one",
                name="Accepted dungeon",
                path=str(candidate),
                status="offline_configuration_prepared",
            )
            evidence = dict(
                records=[
                    dict(
                        route="one",
                        status="isolated_postgres_lifecycle_and_economy_passed",
                    )
                ],
                source_sha256={},
            )
            for policy in (
                "native_physical_door_victory_policy",
                "native_teleport_victory_policy",
            ):
                with self.subTest(policy=policy):
                    db = Mock()
                    db.execute.return_value.fetchone.return_value = dict(
                        value=dict(routes=[route])
                    )
                    db.execute.return_value.fetchall.return_value = []

                    @contextmanager
                    def connection():
                        yield db

                    store = Mock()
                    store.connection = connection
                    current = dict(version=3, topology=dict(policy=policy))
                    with patch.object(
                        dungeon_runtime_config,
                        "active_configuration",
                        return_value=current,
                    ), patch.object(
                        dungeon_runtime_config, "install_configuration"
                    ) as install:
                        result = activate(
                            store,
                            dict(records=[row]),
                            evidence,
                            Path(directory) / (policy + ".backup.json"),
                            apply=True,
                        )
                    install.assert_not_called()
                    self.assertEqual(
                        result["actions"][0]["status"],
                        "preserved_existing_native_physical_configuration",
                    )
                    self.assertEqual(result["actions"][0]["version"], 3)
                    self.assertTrue(
                        (Path(directory) / (policy + ".backup.json")).exists()
                    )
                    backup = json.loads(
                        (Path(directory) / (policy + ".backup.json")).read_text()
                    )
                    self.assertIn("runtime_configurations", backup)
                    self.assertIn("runtime_active_configurations", backup)
                    self.assertNotIn("settings", backup)
                    queries = [call.args[0] for call in db.execute.call_args_list]
                    self.assertTrue(
                        any(
                            "FROM dungeon_runtime_configurations WHERE route_key=%s"
                            in query
                            for query in queries
                        )
                    )
                    self.assertTrue(
                        any(
                            "FROM dungeon_runtime_active_configurations WHERE route_key=%s"
                            in query
                            for query in queries
                        )
                    )
                    self.assertFalse(
                        any(
                            "dungeon_runtime_active:" in query
                            or "dungeon_runtime_config:" in query
                            for query in queries
                        )
                    )
