"""Read-only native catalog export; never export player tables or runtime state.

Use --plan for metadata only. Bootstrap export is private and opt-in: either
exact original JSONL or explicit canonical recovery with a new file identity.
No destination import, schema migration, service startup or activation occurs.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re

CONTEXT_COLUMNS = (
    "route_key",
    "policy_version",
    "template_id",
    "definition_id",
    "max_level",
    "min_level",
    "difficulty_level",
    "is_difficulty_available",
    "can_increase_difficulty",
    "is_competitive_cancelled",
    "allowed_ids",
    "provenance",
)
CONFIGURATION_KEYS = frozenset(
    (
        "compiled_plan",
        "context_policy",
        "evidence_hashes",
        "level_policy",
        "provenance",
        "route",
        "schema_version",
        "slug",
        "topology",
        "version",
    )
)
ROUTE_SETTING = "dungeon_runtime_routes"
ROUTE_FIELDS = frozenset(
    (
        "key",
        "template_id",
        "definition_id",
        "entry_map_id",
        "entry_object_id",
        "destination_id",
        "start_map_id",
        "criterion",
    )
)
LEGACY_ROUTE_FIELDS = frozenset(
    (
        "registration_policy",
        "native_definition_id",
        "native_template_id",
        "native_localization_key",
    )
)


def public_route(route):
    """Keep the native entry contract; never export extended player constraints."""
    if not isinstance(route, dict):
        raise ValueError("Invalid public dungeon route")
    legacy = route.get("registration_policy") == "local_legacy_map_registry"
    if (
        set(route) != (ROUTE_FIELDS | LEGACY_ROUTE_FIELDS if legacy else ROUTE_FIELDS)
        or not isinstance(route["key"], str)
        or not route["key"]
        or not isinstance(route["criterion"], str)
    ):
        raise ValueError("Dungeon route contains unsupported or private fields")
    for key in ROUTE_FIELDS - {"key", "criterion"}:
        if type(route[key]) is not int or route[key] <= 0:
            raise ValueError("Invalid public dungeon route identity")
    return route


def reviewed_dungeon_rows(db):
    """Only public immutable versions of currently selected reviewed routes.

    No instance, member, difficulty selection, whitelist or progress row is read.
    Restricted policies reject rather than being silently scrubbed or published.
    """
    configurations = db.execute(
        "SELECT c.route_key,c.policy_version,c.configuration FROM dungeon_runtime_configurations c "
        "JOIN dungeon_runtime_active_configurations a ON a.route_key=c.route_key "
        "ORDER BY c.route_key,c.policy_version"
    ).fetchall()
    contexts = db.execute(
        "SELECT "
        + ",".join("c." + key for key in CONTEXT_COLUMNS)
        + " FROM dungeon_context_policy_versions c JOIN dungeon_runtime_active_configurations a "
        "ON a.route_key=c.route_key ORDER BY c.route_key,c.policy_version"
    ).fetchall()
    runtime_pins = db.execute(
        "SELECT route_key,policy_version FROM dungeon_runtime_active_configurations ORDER BY route_key"
    ).fetchall()
    context_pins = db.execute(
        "SELECT c.route_key,c.policy_version FROM dungeon_context_active_policies c "
        "JOIN dungeon_runtime_active_configurations a ON a.route_key=c.route_key ORDER BY c.route_key"
    ).fetchall()
    by_context = {(row["route_key"], row["policy_version"]): row for row in contexts}
    if len(by_context) != len(contexts) or not runtime_pins:
        raise ValueError("Missing or duplicate reviewed dungeon authority")
    configuration_ids = set()
    for row in configurations:
        key = (row["route_key"], row["policy_version"])
        config = row["configuration"]
        context = by_context.get(key)
        if (
            set(config) != CONFIGURATION_KEYS
            or context is None
            or context["allowed_ids"] != []
            or config["context_policy"] != context
            or config["route"]["key"] != key[0]
            or config["version"] != key[1]
        ):
            raise ValueError(
                "Dungeon seed requires unchanged public reviewed configurations"
            )
        for name, value in (
            ("plan", config["compiled_plan"]),
            ("topology", config["topology"]),
            ("route", config["route"]),
        ):
            digest = hashlib.sha256(
                json.dumps(
                    value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                ).encode()
            ).hexdigest()
            if config["evidence_hashes"].get(name) != digest:
                raise ValueError("Reviewed dungeon evidence hash mismatch")
        configuration_ids.add(key)
    runtime_ids = {(row["route_key"], row["policy_version"]) for row in runtime_pins}
    context_ids = {(row["route_key"], row["policy_version"]) for row in context_pins}
    if (
        configuration_ids != set(by_context)
        or not runtime_ids <= configuration_ids
        or runtime_ids != context_ids
    ):
        raise ValueError("Reviewed dungeon configuration/context pins disagree")
    active_routes = sorted(
        (
            public_route(row["configuration"]["route"])
            for row in configurations
            if (row["route_key"], row["policy_version"]) in runtime_ids
        ),
        key=lambda route: route["key"],
    )
    setting = db.execute(
        "SELECT value FROM settings WHERE name='dungeon_runtime_routes'"
    ).fetchone()
    registry = None if setting is None else setting["value"]
    if (
        not isinstance(registry, dict)
        or set(registry) != {"schema_version", "routes"}
        or type(registry["schema_version"]) is not int
        or registry["schema_version"] != 1
        or not isinstance(registry["routes"], list)
    ):
        raise ValueError("Missing or invalid installed dungeon route registry")
    actual_routes = sorted(
        (public_route(route) for route in registry["routes"]),
        key=lambda route: route["key"],
    )
    if (
        len({route["key"] for route in actual_routes}) != len(actual_routes)
        or actual_routes != active_routes
    ):
        raise ValueError(
            "Installed dungeon route registry differs from active reviewed configurations"
        )
    return {
        "dungeon_runtime_configurations": configurations,
        "dungeon_context_policy_versions": contexts,
        "dungeon_context_active_policies": context_pins,
        "dungeon_runtime_active_configurations": runtime_pins,
        "settings": [
            {
                "name": ROUTE_SETTING,
                "value": {"schema_version": 1, "routes": active_routes},
            }
        ],
    }


def reviewed_dungeon_sql(tables):
    """Explicit SQL for the existing normalized authority tables, not JSON rules.

    Existing conflicting versions or pins abort the whole target transaction.
    Only the known public route-registry setting is upserted. No progress,
    identity sequence or permission grant is copied or changed.
    """
    from psycopg.sql import Literal

    columns = {
        "dungeon_runtime_configurations": (
            "route_key",
            "policy_version",
            "configuration",
        ),
        "dungeon_context_policy_versions": CONTEXT_COLUMNS,
        "dungeon_context_active_policies": ("route_key", "policy_version"),
        "dungeon_runtime_active_configurations": ("route_key", "policy_version"),
        "settings": ("name", "value"),
    }
    if (
        len(tables.get("settings", ())) != 1
        or tables["settings"][0]["name"] != ROUTE_SETTING
    ):
        raise ValueError("Only the known public dungeon route setting can be exported")
    lines = ["-- Explicit public reviewed dungeon authority; no player data.", "BEGIN;"]
    for table, fields in columns.items():
        for row in tables[table]:
            values = []
            for field in fields:
                value = row[field]
                if field in ("configuration", "value"):
                    value = (
                        Literal(
                            json.dumps(value, sort_keys=True, ensure_ascii=False)
                        ).as_string()
                        + "::jsonb"
                    )
                elif field == "allowed_ids":
                    if value != []:
                        raise ValueError("Character whitelists cannot be exported")
                    value = "'{}'::bigint[]"
                else:
                    value = Literal(value).as_string()
                values.append(value)
            qualified = "public." + table
            conflict = (
                " ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value;"
                if table == "settings"
                else " ON CONFLICT DO NOTHING;"
            )
            lines.append(
                "INSERT INTO "
                + qualified
                + " ("
                + ",".join(fields)
                + ") VALUES ("
                + ",".join(values)
                + ")"
                + conflict
            )
            condition = " AND ".join(
                field + " IS NOT DISTINCT FROM " + value
                for field, value in zip(fields, values)
            )
            body = (
                "BEGIN IF NOT EXISTS (SELECT 1 FROM "
                + qualified
                + " WHERE "
                + condition
                + ") THEN RAISE EXCEPTION 'Conflicting reviewed dungeon installation authority'; "
                "END IF; END;"
            )
            # Quoting the whole DO body also protects captured dollar delimiters
            # inside public provenance strings or the original configuration.
            lines.append("DO " + Literal(body).as_string() + ";")
    lines.append("COMMIT;")
    return ("\n".join(lines) + "\n").encode("utf-8")


def safe_document_path(value):
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or "\\" in value
        or any(part in ("", ".", "..") for part in value.split("/"))
        or path.suffix != ".json"
    ):
        raise ValueError("Unsafe native catalog document path")
    return path


def release_digest(documents):
    digest = hashlib.sha256()
    for item in sorted(documents, key=lambda row: row["path"]):
        digest.update(item["path"].encode("utf-8") + b"\0")
        digest.update(item["sha256"].encode("ascii") + b"\n")
    return digest.hexdigest()


def plan(db, extra_revisions, capture_key):
    active = db.execute(
        "SELECT revision FROM native_catalog_active WHERE id=1"
    ).fetchone()
    if active is None:
        raise ValueError("No active native catalog release")
    revisions = list(dict.fromkeys([active["revision"], *extra_revisions]))
    releases = []
    for revision in revisions:
        if re.fullmatch(r"[0-9a-f]{64}", revision) is None:
            raise ValueError("Invalid explicit catalog revision")
        row = db.execute(
            "SELECT revision,document_count,source_bytes,complete "
            "FROM native_catalog_releases WHERE revision=%s",
            (revision,),
        ).fetchone()
        if row is None or not row["complete"]:
            raise ValueError("Required native catalog release is incomplete or absent")
        releases.append(dict(row))
    bootstrap = db.execute(
        "SELECT capture_key,source_sha256,content_sha256,frame_count "
        "FROM bootstrap_capture_manifests WHERE capture_key=%s",
        (capture_key,),
    ).fetchone()
    return {
        "format": "wakemu-installation-seed-v1",
        "player_tables_exported": [],
        "catalog_privacy": "Native source documents only; embedded captured templates have not been privacy-certified",
        "active_revision": active["revision"],
        "releases": releases,
        "bootstrap": None if bootstrap is None else dict(bootstrap),
        "bootstrap_exported": False,
        "bootstrap_privacy": "Captured protocol bodies are not certified player-free",
    }


def write_private(path, raw):
    with path.open("xb") as output:
        os.chmod(path, 0o600)
        output.write(raw)


def export_catalogs(db, destination, manifest):
    from tools.import_native_catalogs import release_identity

    for release in manifest["releases"]:
        revision = release["revision"]
        root = destination / "catalogs" / revision
        root.mkdir(parents=True, mode=0o700)
        documents = []
        # A server-side cursor bounds memory to one original document. Indexed
        # records are rebuilt by import_native_catalogs, not copied from runtime.
        with db.cursor(name="installation_catalog_documents") as cursor:
            cursor.itersize = 1
            cursor.execute(
                "SELECT path,raw,sha256,source_bytes,record_count FROM native_catalog_documents "
                'WHERE revision=%s ORDER BY path COLLATE "C"',
                (revision,),
            )
            for row in cursor:
                relative = safe_document_path(row["path"])
                raw = bytes(row["raw"])
                if (
                    len(raw) != row["source_bytes"]
                    or hashlib.sha256(raw).hexdigest() != row["sha256"]
                ):
                    raise ValueError("Native catalog document checksum mismatch")
                target = root.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                write_private(target, raw)
                documents.append(
                    {
                        key: row[key]
                        for key in ("path", "sha256", "source_bytes", "record_count")
                    }
                )
        if (
            len(documents) != release["document_count"]
            or sum(row["source_bytes"] for row in documents) != release["source_bytes"]
        ):
            raise ValueError("Exported release differs from its immutable manifest")
        release.update(
            release_identity(
                [
                    (row["path"], row["sha256"], row["source_bytes"])
                    for row in documents
                ],
                expected_revision=revision,
            )
        )
        release["documents"] = documents


def export_private_bootstrap(db, destination, manifest, source):
    from wakfu_server.storage.bootstrap_capture import canonical_frame, describe, load

    expected = manifest["bootstrap"]
    if expected is None:
        raise ValueError("Bootstrap capture manifest is absent")
    verified = load(
        db, expected["capture_key"], expected_source_sha256=expected["source_sha256"]
    )
    if source is None:
        # Exact ordered records, including private fields; new serialization,
        # explicitly NOT the unrecovered original source-file byte identity.
        records = verified
        raw = b"".join(canonical_frame(record) + b"\n" for record in records)
        serialization = "canonical-jsonl-recovered-from-verified-database"
    else:
        raw = Path(source).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected["source_sha256"]:
            raise ValueError("Bootstrap source is not the original captured file")
        records = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
        serialization = "original-source-bytes"
    content_sha, _ = describe(records)
    if (
        len(records) != expected["frame_count"]
        or content_sha != expected["content_sha256"]
        or records != verified
    ):
        raise ValueError(
            "Original bootstrap bytes do not match the verified database capture"
        )
    write_private(destination / "bootstrap.private.jsonl", raw)
    manifest["bootstrap_exported"] = True
    manifest["contains_private_capture"] = True
    manifest["bootstrap_export"] = {
        "path": "bootstrap.private.jsonl",
        "serialization": serialization,
        "import_expected_sha256": hashlib.sha256(raw).hexdigest(),
        "original_source_sha256": expected["source_sha256"],
        "content_sha256": content_sha,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--plan", action="store_true", help="Read only small release/manifest metadata"
    )
    parser.add_argument(
        "--output", type=Path, help="New private directory; must not already exist"
    )
    parser.add_argument(
        "--revision",
        action="append",
        default=[],
        help="Additional pinned release; repeatable",
    )
    parser.add_argument("--capture-key", default="native-bootstrap-v1")
    parser.add_argument(
        "--reviewed-dungeons",
        action="store_true",
        help="Opt in to public immutable dungeon versions and their active pins as SQL",
    )
    private = parser.add_mutually_exclusive_group()
    private.add_argument(
        "--private-bootstrap-source",
        type=Path,
        help="Explicit opt-in: exact original private JSONL; never claimed player-free",
    )
    private.add_argument(
        "--private-bootstrap-from-database",
        action="store_true",
        help="Explicit opt-in: private canonical JSONL, with a NEW source-file SHA",
    )
    args = parser.parse_args()
    if not args.plan and args.output is None:
        parser.error("--output is required unless --plan")
    if args.plan and (
        args.output is not None
        or args.private_bootstrap_source is not None
        or args.private_bootstrap_from_database
    ):
        parser.error("--plan does not write files")

    from psycopg import connect
    from psycopg.conninfo import conninfo_to_dict, make_conninfo
    from psycopg.rows import dict_row

    config = conninfo_to_dict(os.environ["WAKFU_DATABASE_URL"])
    # Override caller options: this tool must never gain a writable transaction.
    config["options"] = "-c default_transaction_read_only=on"
    password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
    kwargs = (
        {}
        if password_file is None
        else {"password": Path(password_file).read_text().strip()}
    )
    with connect(make_conninfo(**config), row_factory=dict_row, **kwargs) as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        manifest = plan(db, args.revision, args.capture_key)
        dungeons = None
        if args.reviewed_dungeons:
            dungeons = reviewed_dungeon_rows(db)
            manifest["reviewed_dungeons"] = {
                "tables": {key: len(rows) for key, rows in dungeons.items()},
                "character_whitelists_exported": False,
                "progress_exported": False,
            }
        if args.plan:
            print(json.dumps(manifest, sort_keys=True, indent=2))
            return
        args.output.mkdir(mode=0o700, parents=False, exist_ok=False)
        write_private(
            args.output / "INCOMPLETE", b"Export incomplete; do not import.\n"
        )
        export_catalogs(db, args.output, manifest)
        if dungeons is not None:
            raw = reviewed_dungeon_sql(dungeons)
            write_private(args.output / "reviewed-dungeons.sql", raw)
            manifest["reviewed_dungeons"].update(
                path="reviewed-dungeons.sql",
                sha256=hashlib.sha256(raw).hexdigest(),
                source_bytes=len(raw),
            )
        if (
            args.private_bootstrap_source is not None
            or args.private_bootstrap_from_database
        ):
            export_private_bootstrap(
                db, args.output, manifest, args.private_bootstrap_source
            )
        encoded = (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode(
            "utf-8"
        )
        write_private(args.output / "manifest.json", encoded)
        write_private(
            args.output / "manifest.sha256",
            (hashlib.sha256(encoded).hexdigest() + "  manifest.json\n").encode("ascii"),
        )
        (args.output / "INCOMPLETE").unlink()
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "manifest_sha256": hashlib.sha256(encoded).hexdigest(),
                    "bootstrap_exported": manifest["bootstrap_exported"],
                },
                sort_keys=True,
            )
        )


if __name__ == "__main__":
    main()
