"""Verifier discovers official schema and refuses ambiguous manifest authority."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "tools/verify_clean_install.py"
SPEC = importlib.util.spec_from_file_location("clean_install_verifier", PATH)
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class VerificationManifestTests(unittest.TestCase):
    def test_schema_discovery_extends_without_fixed_version_and_rejects_untrusted_names(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            expected = {}
            for version in (1, 2):
                body = f"SELECT {version};\n".encode()
                (root / f"{version:03}_source.sql").write_bytes(body)
                expected[version] = hashlib.sha256(body).hexdigest()
            self.assertEqual(verifier.official_migrations(root), expected)
            manifest = [
                {"version": f"{version:03}", "sha256": digest}
                for version, digest in expected.items()
            ]
            self.assertEqual(verifier.migration_manifest(manifest), expected)
            body = b"SELECT 3;\n"
            (root / "003_future.sql").write_bytes(body)
            current = verifier.official_migrations(root)
            self.assertEqual(max(current), 3)
            self.assertNotEqual(current, verifier.migration_manifest(manifest))
            for rows in (
                manifest + [manifest[0]],
                [{"version": True, "sha256": "0" * 64}],
                [{"version": "002", "sha256": "not-a-digest"}],
            ):
                with self.subTest(rows=rows), self.assertRaises(ValueError):
                    verifier.migration_manifest(rows)
            (root / "003_future.sql").unlink()
            (root / "004_gap.sql").write_bytes(body)
            with self.assertRaisesRegex(ValueError, "contiguous"):
                verifier.official_migrations(root)
        for name in (
            "accounts; DROP TABLE characters",
            "public.accounts",
            "../accounts",
            "accounts--",
            "Accounts",
            True,
        ):
            with self.subTest(identifier=name), self.assertRaises(ValueError):
                verifier.table_identifier(name)
        self.assertIsNotNone(
            verifier.table_identifier("environmental_runtime_profiles")
        )
