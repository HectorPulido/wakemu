"""Published release identity and complete source inventory regression."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.import_native_catalogs import (
    release_identity,
    release_revision,
    source_manifest,
    validate_release_inventory,
)


class NativeCatalogIdentityTests(unittest.TestCase):
    def test_published_algorithms_preserve_identity_and_reject_incomplete_sources(self):
        original = json.loads(
            (
                Path(__file__).parent
                / "fixtures"
                / "native_fishing_release_identity.json"
            ).read_text()
        )
        original_rows = [
            (row["path"], row["sha256"], row["source_bytes"])
            for row in original["documents"]
        ]
        verified = validate_release_inventory(original_rows, original)
        self.assertEqual(
            verified["revision"],
            "20f2731c921701c025af2d8416696e5b01c7346fc9393408b47533c092cab5fa",
        )
        self.assertEqual(len(original_rows), 41)
        self.assertEqual(sum(row[2] for row in original_rows), 514480)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a").mkdir()
            (root / "a" / "b.json").write_bytes(b'{"x":1}')
            (root / "a.json").write_bytes(b'{"x":2}')
            rows = source_manifest(root)
            self.assertEqual([row[0] for row in rows], ["a.json", "a/b.json"])
            expected = hashlib.sha256(
                b"".join(
                    path.encode() + b"\0" + digest.encode() + b"\n"
                    for path, digest, _ in rows
                )
            ).hexdigest()
            self.assertEqual(release_revision(list(reversed(rows))), expected)
            self.assertEqual(release_identity(rows)["revision"], expected)
            legacy_rows = sorted(rows, key=lambda row: Path(row[0]).parts)
            legacy_id = hashlib.sha256(
                b"".join(
                    path.encode() + b"\0" + digest.encode() + b"\n"
                    for path, digest, _ in legacy_rows
                )
            ).hexdigest()
            self.assertNotEqual(legacy_id, expected)
            historical = release_identity(rows, expected_revision=legacy_id)
            self.assertEqual(historical["identity_scheme"], "legacy-path-sha256-v1")
            self.assertEqual(historical["manifest_sha256"], expected)

        fishing = [
            ("fishing-navigation/10.json", hashlib.sha256(b"{}").hexdigest(), 2),
            ("fishing-navigation/2.json", hashlib.sha256(b"[]").hexdigest(), 2),
        ]
        fishing_id = hashlib.sha256(
            json.dumps(fishing, separators=(",", ":")).encode()
        ).hexdigest()
        inventory = dict(
            revision=fishing_id,
            complete=True,
            document_count=2,
            source_bytes=4,
            identity_scheme="fishing-json-manifest-v1",
            record_policy="raw-only",
            documents=[
                dict(path=p, sha256=h, source_bytes=n, record_count=0)
                for p, h, n in fishing
            ],
        )
        result = validate_release_inventory(list(reversed(fishing)), inventory)
        self.assertEqual(result["revision"], fishing_id)
        self.assertNotEqual(result["manifest_sha256"], fishing_id)
        self.assertEqual(result["record_policy"], "raw-only")
        self.assertEqual(
            release_identity(fishing, expected_revision=fishing_id), result
        )
        for changed in (
            dict(inventory, complete=False),
            dict(inventory, document_count=1),
            dict(inventory, source_bytes=5),
            dict(inventory, documents=inventory["documents"][:1]),
            dict(inventory, documents=inventory["documents"] * 2),
            dict(inventory, revision="0" * 64),
            dict(inventory, manifest_sha256="0" * 64),
            dict(inventory, record_policy="catalog-records-v1"),
            dict(inventory, identity_scheme="posix-path-sha256-v1"),
            dict(
                inventory,
                documents=[
                    dict(inventory["documents"][0], record_count=1),
                    inventory["documents"][1],
                ],
            ),
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    validate_release_inventory(fishing, changed)
        for changed_rows in (
            fishing[:1],
            fishing + [("fishing-navigation/3.json", "0" * 64, 0)],
            [(fishing[0][0], "0" * 64, 2), fishing[1]],
            [(fishing[0][0], fishing[0][1], 3), fishing[1]],
        ):
            with self.subTest(changed_rows=changed_rows):
                with self.assertRaises(ValueError):
                    validate_release_inventory(changed_rows, inventory)
        with self.assertRaises(ValueError):
            release_identity(fishing, expected_revision="f" * 64)
        with self.assertRaises(ValueError):
            release_revision([("../outside.json", "0" * 64, 0)])
