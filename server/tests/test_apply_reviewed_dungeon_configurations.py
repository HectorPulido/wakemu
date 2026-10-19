"""Fail-closed guards for reviewed future-run dungeon configuration bundles."""
import hashlib
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[2]
_TOOLS = _ROOT / "server" / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from apply_reviewed_dungeon_configurations import apply, bundle_file
from wakfu_server.maps.dungeon_runtime_config import canonical_hash


class Cursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class FakeDatabase:
    def __init__(
        self, source, monsters_sha, *, context_version=1, revision=9, collision=None
    ):
        self.source = source
        self.monsters_sha = monsters_sha
        self.context_version = context_version
        self.revision = revision
        self.collision = collision
        self.statements = []

    def execute(self, statement, params=None):
        self.statements.append((statement, params))
        if "native_catalog_active" in statement:
            return Cursor(dict(revision=self.revision, sha256=self.monsters_sha))
        if "pg_advisory_xact_lock" in statement:
            return Cursor(None)
        if "dungeon_runtime_active_configurations" in statement:
            return Cursor(
                dict(policy_version=self.source["version"], configuration=self.source)
            )
        if "dungeon_context_active_policies" in statement:
            return Cursor(dict(policy_version=self.context_version))
        if statement.startswith(
            "SELECT configuration FROM dungeon_runtime_configurations"
        ):
            return Cursor(
                None if self.collision is None else dict(configuration=self.collision)
            )
        raise AssertionError("Unexpected SQL: " + statement)


class ReviewedDungeonInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.native_raw = b'{"monsters": []}'
        self.geometry = dict(map_id=100, cells=[[0, 0, 0]], edges=[])
        self.teleporters = [
            dict(
                map_id=100,
                id=11,
                destinations=[dict(destination_id=21, map_id=100, x=0, y=0, z=0)],
            )
        ]
        self.source = dict(
            version=1,
            route=dict(
                key="route:test",
                start_map_id=100,
                entry_map_id=100,
                entry_object_id=11,
                destination_id=21,
            ),
            topology=dict(doors=[], rooms=[dict(order=1, cells=[[0, 0, 0]])]),
            compiled_plan={},
            context_policy=dict(policy_version=1),
            level_policy=dict(minimum=1, maximum=200),
            provenance={},
        )
        self.proposal = dict(
            route_key="route:test",
            room_scope="native_entry_component",
            native_entry=[0, 0, 0],
            rooms=[dict(order=1, monsters=[])],
            native_names_fr={},
        )
        self.candidate = dict(
            version=2, route=dict(key="route:test"), payload="reviewed"
        )
        self.manifest = dict(
            repair_kind="reviewed-dungeon-guide-data-v1",
            future_runs_only=True,
            installed=False,
            native_monsters_path="monsters.json",
            native_monsters_sha256=hashlib.sha256(self.native_raw).hexdigest(),
            catalog_revision=9,
            candidates=[],
        )
        self._write("monsters.json", self.native_raw)
        self._write("geometry.json", json.dumps(self.geometry).encode())
        self._write("proposal.json", json.dumps(self.proposal).encode())
        self._write("candidate.json", json.dumps(self.candidate).encode())
        self.manifest["candidates"].append(
            dict(
                route_key="route:test",
                path="candidate.json",
                candidate_version=2,
                candidate_sha256=canonical_hash(self.candidate),
                proposal_path="proposal.json",
                proposal_sha256=hashlib.sha256(
                    (self.root / "proposal.json").read_bytes()
                ).hexdigest(),
                geometry_path="geometry.json",
                geometry_canonical_sha256=canonical_hash(self.geometry),
                allowed_sources=[dict(version=1, sha256=canonical_hash(self.source))],
            )
        )
        self.db = FakeDatabase(self.source, self.manifest["native_monsters_sha256"])

    def _write(self, name, raw):
        (self.root / name).write_bytes(raw)

    def native_load(self, path):
        name = Path(path).name
        if name == "100.json":
            return deepcopy(self.geometry)
        if name == "native-generic-teleporters.json":
            return deepcopy(self.teleporters)
        raise AssertionError("Unexpected native catalog load: " + str(path))

    def patch_native(self):
        return patch("wakfu_server.native_catalog.load", side_effect=self.native_load)

    def patch_prepare(self, *, result=None, side_effect=None):
        if side_effect is not None:
            return patch(
                "apply_reviewed_dungeon_configurations.prepare", side_effect=side_effect
            )
        return patch(
            "apply_reviewed_dungeon_configurations.prepare",
            return_value=self.candidate if result is None else result,
        )

    def test_bundle_paths_cannot_escape_root(self):
        with self.assertRaisesRegex(ValueError, "escapes its bundle"):
            bundle_file(self.root, "../outside.json")
        manifest = deepcopy(self.manifest)
        manifest["native_monsters_path"] = "../outside.json"
        with self.assertRaisesRegex(ValueError, "escapes its bundle"):
            apply(
                self.db,
                manifest,
                self.root,
                install=True,
                backup=self.root / "backup.json",
            )
        self.assertEqual(self.db.statements, [])

    def test_malformed_native_candidate_proposal_and_geometry_hashes_reject(self):
        cases = []
        native = deepcopy(self.manifest)
        native["native_monsters_sha256"] = "0" * 64
        cases.append((native, "native monster evidence changed"))
        for field in (
            "candidate_sha256",
            "proposal_sha256",
            "geometry_canonical_sha256",
        ):
            candidate = deepcopy(self.manifest)
            candidate["candidates"][0][field] = "f" * 64
            cases.append((candidate, "candidate or evidence changed"))
        for manifest, message in cases:
            with self.subTest(
                message=message, field=manifest["candidates"][0].get("candidate_sha256")
            ):
                with self.patch_native(), self.patch_prepare() as prepare, patch(
                    "apply_reviewed_dungeon_configurations.install_configuration"
                ) as install:
                    with self.assertRaisesRegex(ValueError, message):
                        apply(
                            self.db,
                            manifest,
                            self.root,
                            install=True,
                            backup=self.root / "backup.json",
                        )
                install.assert_not_called()
                self.assertFalse((self.root / "backup.json").exists())

    def test_candidate_version_source_context_and_native_entry_are_pinned(self):
        bad_version = deepcopy(self.manifest)
        bad_version["candidates"][0]["candidate_version"] = 3
        wrong_source = deepcopy(self.manifest)
        wrong_source["candidates"][0]["allowed_sources"] = [
            dict(version=1, sha256="a" * 64)
        ]
        changed_context = FakeDatabase(
            self.source, self.manifest["native_monsters_sha256"], context_version=4
        )
        self.teleporters[0]["destinations"][0]["x"] = 1
        with self.patch_native(), self.patch_prepare(), patch(
            "apply_reviewed_dungeon_configurations.install_configuration"
        ) as install:
            with self.assertRaisesRegex(ValueError, "candidate or evidence changed"):
                apply(
                    self.db,
                    bad_version,
                    self.root,
                    install=True,
                    backup=self.root / "backup.json",
                )
            with self.assertRaisesRegex(ValueError, "approved frozen policy"):
                apply(
                    self.db,
                    wrong_source,
                    self.root,
                    install=True,
                    backup=self.root / "backup.json",
                )
            with self.assertRaisesRegex(ValueError, "approved frozen policy"):
                apply(
                    changed_context,
                    self.manifest,
                    self.root,
                    install=True,
                    backup=self.root / "backup.json",
                )
            with self.assertRaisesRegex(ValueError, "actual native entry"):
                apply(
                    self.db,
                    self.manifest,
                    self.root,
                    install=True,
                    backup=self.root / "backup.json",
                )
        install.assert_not_called()
        self.assertFalse((self.root / "backup.json").exists())

    def test_all_candidates_validate_before_backup_or_installer_mutation(self):
        second_source = deepcopy(self.source)
        second_source["route"]["key"] = "route:second"
        second_proposal = deepcopy(self.proposal)
        second_proposal["route_key"] = "route:second"
        second_candidate = dict(
            version=2, route=dict(key="route:second"), payload="bad"
        )
        self._write("proposal2.json", json.dumps(second_proposal).encode())
        self._write("candidate2.json", json.dumps(second_candidate).encode())
        manifest = deepcopy(self.manifest)
        manifest["candidates"].append(
            dict(
                route_key="route:second",
                path="candidate2.json",
                candidate_version=2,
                candidate_sha256="0" * 64,
                proposal_path="proposal2.json",
                proposal_sha256=hashlib.sha256(
                    (self.root / "proposal2.json").read_bytes()
                ).hexdigest(),
                geometry_path="geometry.json",
                geometry_canonical_sha256=canonical_hash(self.geometry),
                allowed_sources=[dict(version=1, sha256=canonical_hash(second_source))],
            )
        )
        backup = self.root / "backup.json"
        with self.patch_native(), self.patch_prepare(), patch(
            "apply_reviewed_dungeon_configurations.install_configuration"
        ) as install:
            with self.assertRaisesRegex(ValueError, "candidate or evidence changed"):
                apply(self.db, manifest, self.root, install=True, backup=backup)
        install.assert_not_called()
        self.assertFalse(backup.exists())

    def test_existing_backup_path_prevents_any_install(self):
        backup = self.root / "backup.json"
        backup.write_text("existing evidence")
        with self.patch_native(), self.patch_prepare(), patch(
            "apply_reviewed_dungeon_configurations.install_configuration"
        ) as install:
            with self.assertRaises(FileExistsError):
                apply(self.db, self.manifest, self.root, install=True, backup=backup)
        install.assert_not_called()
        self.assertEqual(backup.read_text(), "existing evidence")

    def test_immutable_target_conflict_rejects_before_backup_or_install(self):
        db = FakeDatabase(
            self.source,
            self.manifest["native_monsters_sha256"],
            collision=dict(
                version=2, route=dict(key="route:test"), payload="different"
            ),
        )
        backup = self.root / "backup.json"
        with self.patch_native(), self.patch_prepare(), patch(
            "apply_reviewed_dungeon_configurations.install_configuration"
        ) as install:
            with self.assertRaisesRegex(ValueError, "immutable target version"):
                apply(db, self.manifest, self.root, install=True, backup=backup)
        install.assert_not_called()
        self.assertFalse(backup.exists())

    def test_matching_bundle_is_read_only_by_default_and_installs_only_after_backup(
        self,
    ):
        self.teleporters[0]["destinations"][0].update(map_id=100, x=0, y=0, z=0)
        with self.patch_native(), self.patch_prepare() as prepare, patch(
            "apply_reviewed_dungeon_configurations.install_configuration"
        ) as install:
            review = apply(self.db, self.manifest, self.root)
            self.assertTrue(review["qualified"])
            self.assertFalse(review["installed"])
            self.assertEqual(review["candidates"], 1)
            install.assert_not_called()
            prepare.assert_called_once_with(
                self.source,
                self.proposal,
                [],
                self.geometry,
                version=self.candidate["version"],
            )

            prepare.reset_mock()
            backup = self.root / "install-backup.json"

            def assert_backup_precedes_install(db, candidate):
                self.assertTrue(backup.is_file())
                saved = json.loads(backup.read_text())
                self.assertEqual(saved["originals"][0]["configuration"], self.source)
                self.assertEqual(candidate, self.candidate)

            install.side_effect = assert_backup_precedes_install
            applied = apply(
                self.db, self.manifest, self.root, install=True, backup=backup
            )

        self.assertTrue(applied["installed"])
        self.assertEqual(applied["backup"], str(backup))
        install.assert_called_once()


if __name__ == "__main__":
    unittest.main()
