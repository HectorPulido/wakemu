"""Original PT getters extend immutable public metadata without live activation."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class RiftPtMetadataPublicPackTests(unittest.TestCase):
    def test_preserved_roots_overlap_roles_identity_replay_and_corruption(self):
        from tools.import_native_catalogs import release_identity
        from tools.stage_rift_pt_metadata_catalog import CASTING
        from tools.stage_rift_complete_metadata_catalog import read_document

        root = Path(__file__).resolve().parents[1] / "data/installation"
        catalogs = root / "catalogs"
        proof_path = root.parent / "native-rift-pt-casting-additions-v1.json"
        proof = json.loads(proof_path.read_bytes())
        parent_name = "manifest-rift-complete-metadata-v1.json"
        parent_raw = (catalogs / parent_name).read_bytes()
        parent = json.loads(parent_raw)
        active = next(
            row
            for row in parent["releases"]
            if row["revision"] == parent["active_revision"]
        )
        documents = {row["path"]: row for row in active["documents"]}
        with tempfile.TemporaryDirectory(prefix="rift-public-pt-") as directory:
            target = Path(directory)
            output = target / "catalogs"
            output.mkdir()
            (output / parent_name).write_bytes(parent_raw)
            shutil.copyfile(root / "manifest.json", target / "manifest.json")
            top_before = (target / "manifest.json").read_bytes()
            for part in parent["blobs"][documents[CASTING]["sha256"]]["parts"]:
                path = output / part["path"]
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(catalogs / part["path"], path)
            command = [
                sys.executable,
                "-S",
                "-m",
                "tools.stage_rift_pt_metadata_catalog",
                "--pack",
                str(target),
                "--proof",
                str(proof_path),
            ]
            receipt = json.loads(
                subprocess.run(
                    command, check=True, capture_output=True, text=True
                ).stdout
            )
            self.assertFalse(receipt["database_staged"])
            self.assertFalse(receipt["activated"])
            self.assertFalse(receipt["public_selector_changed"])
            candidate_raw = (target / receipt["candidate_manifest"]).read_bytes()
            self.assertEqual(
                hashlib.sha256(candidate_raw).hexdigest(),
                receipt["candidate_manifest_sha256"],
            )
            self.assertEqual(
                candidate_raw, (root / receipt["candidate_manifest"]).read_bytes()
            )
            candidate = json.loads(candidate_raw)
            release = next(
                row
                for row in candidate["releases"]
                if row["revision"] == candidate["active_revision"]
            )
            changed = {row["path"]: row for row in release["documents"]}
            self.assertEqual(set(changed), set(documents))
            self.assertEqual(
                {name for name in documents if documents[name] != changed[name]},
                {CASTING},
            )
            release_identity(
                [
                    (row["path"], row["sha256"], row["source_bytes"])
                    for row in release["documents"]
                ],
                expected_revision=release["revision"],
                identity_scheme=release["identity_scheme"],
            )
            for row in parent["releases"]:
                if row["revision"] != parent["active_revision"]:
                    self.assertIn(row, candidate["releases"])
            before = read_document(output, parent, documents[CASTING])
            after = read_document(output, candidate, changed[CASTING])
            self.assertEqual(
                (len(before["roots"]), len(after["roots"])), (11455, 11466)
            )
            self.assertEqual(
                {key: after["roots"][key] for key in before["roots"]}, before["roots"]
            )
            recovered = proof["original_export"]["roots"]
            self.assertEqual(len(recovered), 19)
            self.assertEqual(len(set(recovered) & set(before["roots"])), 8)
            self.assertEqual(
                set(after["roots"]) - set(before["roots"]),
                set(recovered) - set(before["roots"]),
            )
            for key, value in recovered.items():
                self.assertEqual(after["roots"][key], value)
            for field in ("schema", "fight_properties", "normal_casting_overrides"):
                self.assertEqual(after[field], before[field])
            self.assertEqual(
                json.loads(
                    subprocess.run(
                        command, check=True, capture_output=True, text=True
                    ).stdout
                ),
                receipt,
            )
            self.assertEqual((output / parent_name).read_bytes(), parent_raw)
            self.assertEqual((target / "manifest.json").read_bytes(), top_before)
            # Start from the exact historical parent selector, then select only the
            # already qualified candidate for future installations.
            historical = json.loads(top_before)
            historical["catalogs"]["active_revision"] = parent["active_revision"]
            for row in historical["catalogs"]["releases"]:
                if row["revision"] == candidate["active_revision"]:
                    row.update(
                        revision=active["revision"],
                        document_count=active["document_count"],
                        source_bytes=active["source_bytes"],
                    )
            historical["artifacts"]["native-catalogs"].update(
                path="catalogs/" + parent_name,
                sha256=hashlib.sha256(parent_raw).hexdigest(),
                size=len(parent_raw),
            )
            from tools.stage_rift_complete_metadata_catalog import encode

            historical_raw = encode(historical)
            (target / "manifest.json").write_bytes(historical_raw)
            subprocess.run(command, check=True, capture_output=True, text=True)
            self.assertEqual((target / "manifest.json").read_bytes(), historical_raw)
            selected = json.loads(
                subprocess.run(
                    command + ["--select-public"],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout
            )
            self.assertTrue(selected["public_selector_changed"])
            self.assertFalse(selected["activated"])
            self.assertFalse(selected["database_staged"])
            selected_raw = (target / "manifest.json").read_bytes()
            self.assertEqual(selected_raw, top_before)
            self.assertEqual(
                (target / "manifest.sha256").read_text().split()[0],
                hashlib.sha256(selected_raw).hexdigest(),
            )
            self.assertEqual(
                json.loads(
                    subprocess.run(
                        command + ["--select-public"],
                        check=True,
                        capture_output=True,
                        text=True,
                    ).stdout
                ),
                selected,
            )
            self.assertEqual((target / "manifest.json").read_bytes(), selected_raw)
            revision = candidate["active_revision"]
            repository = root.parents[2]
            compose = (repository / "compose.yaml").read_text()
            defaults = (repository / ".env.example").read_text()
            self.assertGreaterEqual(
                compose.count("${WAKFU_CATALOG_REVISION:-" + revision + "}"), 4
            )
            self.assertIn("WAKFU_CATALOG_REVISION=" + revision, defaults)
            # Contradictory overlap and global metadata must fail before changing the candidate.
            for kind in ("overlap", "globals"):
                bad = deepcopy(proof)
                if kind == "overlap":
                    key = next(iter(set(recovered) & set(before["roots"])))
                    bad["original_export"]["roots"][key] = {"forged": True}
                else:
                    bad["original_export"]["fight_properties"] = {"forged": True}
                path = target / (kind + ".json")
                path.write_text(json.dumps(bad))
                result = subprocess.run(
                    command[:-1] + [str(path)], capture_output=True, text=True
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Original", result.stderr)
                self.assertEqual(
                    (target / receipt["candidate_manifest"]).read_bytes(), candidate_raw
                )
            part = candidate["blobs"][changed[CASTING]["sha256"]]["parts"][0]
            path = output / part["path"]
            path.write_bytes(path.read_bytes() + b"tamper")
            with self.assertRaises(ValueError):
                read_document(output, candidate, changed[CASTING])
