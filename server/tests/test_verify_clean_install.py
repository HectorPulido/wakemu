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

    def test_first_selection_uses_canonical_territory_cap_and_recheck_preserves_only_probe_fixtures(
        self,
    ):
        from copy import deepcopy
        import json
        from wakfu_server.health import maximum

        cap = maximum(8, 1)
        before = dict(
            id=1,
            account_id=2,
            breed=8,
            level=1,
            map_id=527,
            instance_id=0,
            x=0,
            y=32,
            z=0,
            hp=cap,
            max_hp=cap,
            hp_damage=0,
            health_dead=False,
            hp_zero_valid=False,
            territory_health_projection=None,
            inventory_items=[],
            builds={},
        )
        projection = dict(
            applied_flat=-1,
            state_id=1917,
            map_id=527,
            instance_id=0,
            region_id=66701,
            revision=1,
        )
        first = dict(
            before, hp=cap - 1, max_hp=cap - 1, territory_health_projection=projection
        )
        verifier.compare_selected_character(before, first)
        verifier.compare_selected_character(first, deepcopy(first))
        # The existing canonical reducer owns positive caps too. Raising the
        # territory cap preserves current HP and rebases wounds, never heals.
        positive = dict(
            before,
            max_hp=cap + 2,
            hp_damage=2,
            territory_health_projection=dict(projection, applied_flat=2, state_id=1916),
        )
        verifier.compare_selected_character(before, positive)
        for key in verifier.IDENTITY_KEYS:
            bad = dict(first, **{key: first[key] + 1})
            with self.subTest(identity=key), self.assertRaises(ValueError):
                verifier.compare_selected_character(before, bad)
        for changes in (
            dict(max_hp=cap),
            dict(hp=cap),
            dict(hp=cap - 2, hp_damage=1),
            dict(health_dead=True),
            dict(hp_zero_valid=True),
        ):
            with self.subTest(health=changes), self.assertRaises(ValueError):
                verifier.compare_selected_character(before, dict(first, **changes))
        tables = [
            "accounts",
            "characters",
            "sessions",
            "inventory_items",
            "inventory_containers",
        ]
        witness = dict(
            database="fresh_test",
            zero_player_state=True,
            counts=dict.fromkeys(tables, 0),
        )
        verifier.validate_zero_witness(witness, "fresh_test", tables)
        for changes in (
            dict(database="other"),
            dict(zero_player_state=False),
            dict(counts=dict(accounts=0)),
            dict(counts=dict(witness["counts"], accounts=1)),
            dict(counts=dict(witness["counts"], accounts=False)),
        ):
            with self.subTest(witness=changes), self.assertRaises(ValueError):
                verifier.validate_zero_witness(
                    dict(witness, **changes), "fresh_test", tables
                )

        class Rows:
            def __init__(self, rows):
                self.rows = rows

            def fetchall(self):
                return self.rows

        class ProbeDatabase:
            def __init__(self, accounts, characters):
                self.accounts, self.characters = accounts, characters

            def execute(self, query):
                return Rows(
                    self.accounts if "FROM accounts" in query else self.characters
                )

        existing = ProbeDatabase(
            [(1, "clean19_0123456789")], [(1, "Cleanabcdefgh", 8, None)]
        )
        self.assertEqual(
            verifier.existing_probe_fixtures(existing), dict(accounts=1, characters=1)
        )
        invalid = [
            ProbeDatabase([(1, "real_player")], existing.characters),
            ProbeDatabase(existing.accounts, [(1, "Original Hero", 8, None)]),
            ProbeDatabase(existing.accounts, [(1, "Cleanabcdefgh", 15, None)]),
            ProbeDatabase(existing.accounts, [(1, "Cleanabcdefgh", 8, "deleted")]),
            ProbeDatabase(existing.accounts, existing.characters * 2),
            ProbeDatabase([], []),
        ]
        for database in invalid:
            with self.subTest(accounts=database.accounts), self.assertRaises(
                ValueError
            ):
                verifier.existing_probe_fixtures(database)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "failure.json"
            observations = {
                name: verifier.character_observation(value)
                for name, value in [("before", before), ("first", first)]
            }
            verifier.access_diagnostic(
                path,
                "first-selection",
                observations,
                ValueError("secret-token-must-not-leak"),
            )
            raw = path.read_text()
            self.assertNotIn("secret-token-must-not-leak", raw)
            result = json.loads(raw)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(
                result["differences"]["before_to_first"]["max_hp"], [cap, cap - 1]
            )
            self.assertEqual(result["observations"]["first"]["hp_damage"], 0)
