"""Bounded immutable public metadata release; no DB, client or full unpack."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class RiftCompleteMetadataPublicPackTests(unittest.TestCase):
    def test_additive_getters_original_inventory_roles_checksums_and_cli_replay(self):
        from tools.stage_rift_complete_metadata_catalog import (
            read_document,
            CASTING,
            SOURCE_MANIFESTS,
        )
        from tools.import_native_catalogs import release_identity

        root = Path(__file__).resolve().parents[1] / "data/installation"
        catalogs = root / "catalogs"
        proof_path = root.parent / "native-rift-casting-root-additions-v1.json"
        proof = json.loads(proof_path.read_bytes())
        original = json.loads((catalogs / "manifest.json").read_bytes())
        old = next(
            row
            for row in original["releases"]
            if row["revision"] == original["active_revision"]
        )
        parent = json.loads(
            (catalogs / "manifest-rift-cell-groups-v1.json").read_bytes()
        )
        parent_active = next(
            row
            for row in parent["releases"]
            if row["revision"] == parent["active_revision"]
        )
        parent_documents = {row["path"]: row for row in parent_active["documents"]}
        original_documents = {row["path"]: row for row in old["documents"]}
        self.assertEqual(len(old["documents"]), 7490)
        with tempfile.TemporaryDirectory(prefix="rift-public-complete-") as directory:
            target = Path(directory)
            (target / "catalogs").mkdir()
            for name in (
                "manifest.json",
                "manifest-rift-cell-groups-v1.json",
                "rift-cell-groups-v1-receipt.json",
            ):
                shutil.copyfile(catalogs / name, target / "catalogs" / name)
            shutil.copyfile(root / "manifest.json", target / "manifest.json")
            for pack, document in (
                (parent, parent_documents[CASTING]),
                (parent, parent_documents["native-class-cell-group-metadata.json"]),
                (original, original_documents["native-class-cell-group-metadata.json"]),
            ):
                for part in pack["blobs"][document["sha256"]]["parts"]:
                    dst = target / "catalogs" / part["path"]
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(catalogs / part["path"], dst)
            command = [
                sys.executable,
                "-S",
                "-m",
                "tools.stage_rift_complete_metadata_catalog",
                "--pack",
                str(target),
                "--casting-proof",
                str(proof_path),
            ]
            first = subprocess.run(command, check=True, capture_output=True, text=True)
            receipt = json.loads(first.stdout)
            self.assertFalse(receipt["activated"])
            self.assertFalse(receipt["database_staged"])
            self.assertFalse(receipt["live_environment_changed"])
            top_raw = (target / "manifest.json").read_bytes()
            self.assertEqual(top_raw, (root / "manifest.json").read_bytes())
            top = json.loads(top_raw)
            combined_raw = (target / receipt["candidate_manifest"]).read_bytes()
            self.assertEqual(
                hashlib.sha256(combined_raw).hexdigest(),
                receipt["candidate_manifest_sha256"],
            )
            self.assertEqual(
                combined_raw, (root / receipt["candidate_manifest"]).read_bytes()
            )
            combined = json.loads(combined_raw)
            active = next(
                row
                for row in combined["releases"]
                if row["revision"] == combined["active_revision"]
            )
            documents = {row["path"]: row for row in active["documents"]}
            self.assertEqual(set(documents) - set(parent_documents), {SOURCE_MANIFESTS})
            self.assertEqual(
                {
                    name
                    for name in parent_documents
                    if parent_documents[name] != documents[name]
                },
                {CASTING},
            )
            release_identity(
                [
                    (row["path"], row["sha256"], row["source_bytes"])
                    for row in active["documents"]
                ],
                expected_revision=active["revision"],
                identity_scheme=active["identity_scheme"],
            )
            for role in ("mining_revision", "fishing_revision"):
                revision = top["catalogs"][role]
                self.assertEqual(
                    next(
                        row
                        for row in combined["releases"]
                        if row["revision"] == revision
                    ),
                    next(
                        row
                        for row in original["releases"]
                        if row["revision"] == revision
                    ),
                )
            before = read_document(
                target / "catalogs", parent, parent_documents[CASTING]
            )
            after = read_document(target / "catalogs", combined, documents[CASTING])
            self.assertEqual(
                (len(before["roots"]), len(after["roots"])), (11405, 11455)
            )
            self.assertEqual(
                {key: after["roots"][key] for key in before["roots"]}, before["roots"]
            )
            self.assertEqual(
                set(after["roots"]) - set(before["roots"]),
                set(proof["original_export"]["roots"]),
            )
            for key, value in proof["original_export"]["roots"].items():
                self.assertEqual(after["roots"][key], value)
            for key in ("schema", "fight_properties", "normal_casting_overrides"):
                self.assertEqual(before[key], after[key])
            sources = read_document(
                target / "catalogs", combined, documents[SOURCE_MANIFESTS]
            )
            self.assertEqual(
                sources["policy"], "wakemu.native-catalog-source-manifests.v1"
            )
            self.assertEqual(sources["releases"], [old])
            release_identity(
                [
                    (row["path"], row["sha256"], row["source_bytes"])
                    for row in sources["releases"][0]["documents"]
                ],
                expected_revision=old["revision"],
                identity_scheme=old["identity_scheme"],
            )
            cell_name = "native-class-cell-group-metadata.json"
            cells_old = read_document(
                target / "catalogs", original, original_documents[cell_name]
            )
            cells_new = read_document(
                target / "catalogs", combined, documents[cell_name]
            )
            self.assertEqual(
                (len(cells_old["effects"]), len(cells_new["effects"])), (1029, 1033)
            )
            self.assertEqual(
                {key: cells_new["effects"][key] for key in cells_old["effects"]},
                cells_old["effects"],
            )
            self.assertEqual(
                set(cells_new["effects"]) - set(cells_old["effects"]),
                {"315439", "315771", "315773", "315775"},
            )
            second = subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(second.stdout), receipt)
            self.assertEqual((target / "manifest.json").read_bytes(), top_raw)
            self.assertEqual(
                (target / "catalogs/manifest.json").read_bytes(),
                (catalogs / "manifest.json").read_bytes(),
            )
            tampered = deepcopy(proof)
            tampered["original_export"]["fight_properties"] = {"forged": True}
            bad = target / "bad-proof.json"
            bad.write_text(json.dumps(tampered))
            rejected = subprocess.run(
                command[:-1] + [str(bad)], capture_output=True, text=True
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("Original casting globals differ", rejected.stderr)
            self.assertEqual((target / "manifest.json").read_bytes(), top_raw)
