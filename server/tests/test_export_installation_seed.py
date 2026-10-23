"""Small offline installation export contract; no catalog heap or real database."""
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
from io import StringIO
import json
from pathlib import Path
import re
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from psycopg.conninfo import conninfo_to_dict
from psycopg.pq import TransactionStatus
from wakfu_server.storage import bootstrap_capture


def tool(name):
    path = Path(__file__).parents[1] / "tools" / (name + ".py")
    spec = importlib.util.spec_from_file_location("installation_test_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class InstallationSeedExportTests(unittest.TestCase):
    def test_reviewed_public_dungeon_sql_preserves_versions_and_rejects_private_or_changed_authority(
        self,
    ):
        exporter = tool("export_installation_seed")
        context = dict(
            zip(
                exporter.CONTEXT_COLUMNS,
                (
                    "fixture'route",
                    1,
                    10,
                    20,
                    0,
                    0,
                    2,
                    False,
                    False,
                    False,
                    [],
                    "fixture provenance $installation_seed$ 'quoted'",
                ),
            )
        )
        route = dict(
            key=context["route_key"],
            template_id=10,
            definition_id=20,
            entry_map_id=1134,
            entry_object_id=700,
            destination_id=1,
            start_map_id=1135,
            criterion="fixture's public criterion",
        )
        config = dict(
            compiled_plan={"definition_id": 20},
            context_policy=context,
            evidence_hashes={},
            level_policy={"mode": "native_minimum"},
            provenance=context["provenance"],
            route=route,
            schema_version=1,
            slug="fixture",
            topology={},
            version=1,
        )
        for key, value in (
            ("plan", config["compiled_plan"]),
            ("topology", {}),
            ("route", config["route"]),
        ):
            config["evidence_hashes"][key] = hashlib.sha256(
                json.dumps(
                    value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode()
            ).hexdigest()
        registry = dict(schema_version=1, routes=[deepcopy(route)])
        rows = [
            [
                dict(
                    route_key=context["route_key"],
                    policy_version=1,
                    configuration=config,
                )
            ],
            [context],
            [dict(route_key=context["route_key"], policy_version=1)],
            [dict(route_key=context["route_key"], policy_version=1)],
            [dict(value=registry)],
        ]

        class Database:
            def __init__(self, results):
                self.results = iter(results)
                self.queries = []

            def execute(self, sql):
                if not sql.startswith("SELECT "):
                    raise AssertionError("Only SELECT is permitted")
                self.queries.append(sql)
                result = next(self.results)
                return SimpleNamespace(
                    fetchall=lambda: result,
                    fetchone=lambda: result[0] if result else None,
                )

        source = Database(rows)
        tables = exporter.reviewed_dungeon_rows(source)
        self.assertEqual(
            source.queries[-1],
            "SELECT value FROM settings WHERE name='dungeon_runtime_routes'",
        )
        self.assertEqual(len(source.queries), 5)
        self.assertEqual(
            tables["settings"], [dict(name="dungeon_runtime_routes", value=registry)]
        )
        sql = exporter.reviewed_dungeon_sql(tables).decode()
        self.assertTrue(
            sql.startswith(
                "-- Explicit public reviewed dungeon authority; no player data.\nBEGIN;"
            )
        )
        self.assertTrue(sql.endswith("COMMIT;\n"))
        self.assertEqual(sql.count("INSERT INTO public."), 5)
        self.assertEqual(sql.count("ON CONFLICT DO NOTHING"), 4)
        self.assertEqual(
            sql.count("Conflicting reviewed dungeon installation authority"), 5
        )
        self.assertEqual(
            sql.count("ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value"), 1
        )
        self.assertIn("fixture''route", sql)
        self.assertIn("'{}'::bigint[]", sql)
        self.assertNotIn("DO $installation_seed$", sql)
        # Independently round-trip the generated SQL literal through a file;
        # startup must receive the same active route, not catalog defaults.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviewed-dungeons.sql"
            path.write_text(sql)
            imported = path.read_text()
            settings = re.findall(
                r"INSERT INTO public\.settings \(name,\s*value\) VALUES \('([^']*)','((?:[^']|'')*)'::jsonb\)",
                imported,
            )
            self.assertEqual(len(settings), 1)
            name, encoded = settings[0]
            self.assertEqual(name, "dungeon_runtime_routes")
            recovered = json.loads(encoded.replace("''", "'"))
            self.assertEqual(recovered, registry)
            self.assertEqual(recovered["routes"][0], config["route"])
            self.assertEqual(set(recovered), {"schema_version", "routes"})
            self.assertNotIn("private-character-marker", imported)
        for replacement in (
            [dict(name="private_account_setting", value=registry)],
            [
                dict(name="dungeon_runtime_routes", value=registry),
                dict(name="private_account_setting", value={"character_id": 999}),
            ],
        ):
            changed_tables = deepcopy(tables)
            changed_tables["settings"] = replacement
            with self.subTest(settings=replacement), self.assertRaises(ValueError):
                exporter.reviewed_dungeon_sql(changed_tables)
        for changes in (
            "whitelist",
            "missing_context",
            "changed_plan",
            "different_pin",
            "missing_setting",
            "mismatched_setting",
            "duplicate_route",
            "private_setting",
            "private_route",
        ):
            changed = deepcopy(rows)
            if changes == "whitelist":
                changed[1][0]["allowed_ids"] = [999]
            elif changes == "missing_context":
                changed[1] = []
            elif changes == "changed_plan":
                changed[0][0]["configuration"]["compiled_plan"]["definition_id"] = 21
            elif changes == "different_pin":
                changed[3][0]["policy_version"] = 2
            elif changes == "missing_setting":
                changed[4] = []
            elif changes == "mismatched_setting":
                changed[4][0]["value"]["routes"][0]["start_map_id"] += 1
            elif changes == "duplicate_route":
                changed[4][0]["value"]["routes"].append(deepcopy(route))
            elif changes == "private_setting":
                changed[4][0]["value"]["character_id"] = "private-character-marker"
            else:
                private = changed[0][0]["configuration"]
                private["route"]["allowed_character_ids"] = [999]
                private["evidence_hashes"]["route"] = hashlib.sha256(
                    json.dumps(
                        private["route"],
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    ).encode()
                ).hexdigest()
                changed[4][0]["value"]["routes"][0] = deepcopy(private["route"])
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                exporter.reviewed_dungeon_rows(Database(changed))

    def test_readonly_private_tempdir_roundtrip_and_rejection(self):
        exporter = tool("export_installation_seed")
        importer = tool("import_bootstrap_capture")
        for value in (
            "../x.json",
            "/x.json",
            "a/../x.json",
            "a\\x.json",
            "a//x.json",
            "x.txt",
        ):
            with self.subTest(path=value), self.assertRaises(ValueError):
                exporter.safe_document_path(value)
        self.assertEqual(
            exporter.safe_document_path("native/a.json").as_posix(), "native/a.json"
        )

        document = b'{"native_fixture":true}\n'
        checksum = hashlib.sha256(document).hexdigest()
        revision = hashlib.sha256(
            b"native/a.json\0" + checksum.encode() + b"\n"
        ).hexdigest()
        source_row = dict(
            path="native/a.json",
            raw=document,
            sha256=checksum,
            source_bytes=len(document),
            record_count=1,
        )
        self.assertEqual(exporter.release_digest([source_row]), revision)
        second = dict(path="b.json", sha256="a" * 64)
        self.assertEqual(
            exporter.release_digest([source_row, second]),
            exporter.release_digest([second, source_row]),
        )

        frames = [
            dict(
                direction="in",
                opcode=630,
                body_base64="aGVsbG8=",
                frame_index=index,
                remote="synthetic-private-marker",
            )
            for index in range(45)
        ]
        frames[44].update(direction="out", opcode=23664)
        content_sha, hashes = bootstrap_capture.describe(frames)
        # A different source-file identity is deliberately retained as provenance.
        capture_manifest = dict(
            capture_key="native-bootstrap-v1",
            source_sha256="b" * 64,
            content_sha256=content_sha,
            frame_count=len(frames),
        )
        queries = []

        class Result:
            def __init__(self, rows):
                self.rows = rows

            def fetchone(self):
                return self.rows[0] if self.rows else None

            def fetchall(self):
                return self.rows

        class Cursor:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def execute(self, sql, parameters):
                if not sql.startswith(
                    "SELECT path,raw,sha256,source_bytes,record_count FROM native_catalog_documents "
                ):
                    raise AssertionError("Unexpected export query")
                queries.append(sql)

            def __iter__(self):
                return iter([source_row])

        class ReadonlyDatabase:
            info = SimpleNamespace(transaction_status=TransactionStatus.INTRANS)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def cursor(self, **kwargs):
                return Cursor()

            def execute(self, sql, parameters=()):
                queries.append(sql)
                if sql == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY":
                    return Result([])
                if sql == "SELECT revision FROM native_catalog_active WHERE id=1":
                    return Result([dict(revision=revision)])
                if sql.startswith(
                    "SELECT revision,document_count,source_bytes,complete "
                ):
                    return Result(
                        [
                            dict(
                                revision=revision,
                                document_count=1,
                                source_bytes=len(document),
                                complete=True,
                            )
                        ]
                    )
                if "FROM bootstrap_capture_manifests WHERE capture_key=%s" in sql:
                    return Result([capture_manifest])
                if sql.startswith(
                    "SELECT ordinal,payload,payload_sha256 FROM bootstrap_capture_records "
                ):
                    return Result(
                        [
                            dict(ordinal=i, payload=frame, payload_sha256=hashes[i])
                            for i, frame in enumerate(frames)
                        ]
                    )
                raise AssertionError(
                    "Unexpected query outside immutable source allowlist"
                )

        def connect(conninfo, **kwargs):
            self.assertEqual(
                conninfo_to_dict(conninfo)["options"],
                "-c default_transaction_read_only=on",
            )
            return ReadonlyDatabase()

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "seed"
            stdout = StringIO()
            with patch.dict(
                "os.environ",
                {"WAKFU_DATABASE_URL": "postgresql://fixture/fixture"},
                clear=True,
            ), patch("psycopg.connect", side_effect=connect), redirect_stdout(stdout):
                with patch("sys.argv", ["export_installation_seed.py", "--plan"]):
                    exporter.main()
                self.assertEqual(list(Path(directory).iterdir()), [])
                with patch(
                    "sys.argv",
                    [
                        "export_installation_seed.py",
                        "--output",
                        str(output),
                        "--private-bootstrap-from-database",
                    ],
                ):
                    exporter.main()
            self.assertNotIn("synthetic-private-marker", stdout.getvalue())
            manifest = json.loads((output / "manifest.json").read_text())
            self.assertNotIn("synthetic-private-marker", json.dumps(manifest))
            self.assertEqual(manifest["player_tables_exported"], [])
            self.assertEqual(
                (output / "catalogs" / revision / "native/a.json").read_bytes(),
                document,
            )
            self.assertFalse((output / "INCOMPLETE").exists())
            private = output / "bootstrap.private.jsonl"
            recovered_sha, recovered_frames = importer.parse_source(
                private, content_sha
            )
            self.assertEqual(recovered_frames, frames)
            self.assertEqual(
                recovered_sha, manifest["bootstrap_export"]["import_expected_sha256"]
            )
            self.assertEqual(
                manifest["bootstrap_export"]["original_source_sha256"], "b" * 64
            )
            self.assertNotEqual(recovered_sha, capture_manifest["source_sha256"])
            self.assertTrue(manifest["contains_private_capture"])
            for path in output.rglob("*"):
                if path.is_file():
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            before = private.read_bytes()
            with self.assertRaises(FileExistsError):
                exporter.write_private(private, b"replacement")
            self.assertEqual(private.read_bytes(), before)
            source_row["sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                exporter.export_catalogs(
                    ReadonlyDatabase(), Path(directory) / "corrupt", manifest
                )
        self.assertTrue(
            all(sql.startswith(("SELECT ", "SET TRANSACTION ")) for sql in queries)
        )


if __name__ == "__main__":
    unittest.main()
