"""Build a player-free installation database from verified public seed inputs.

Only native catalog authority is read from the source database. The target must
be a brand-new wakemu_clean_backup_* database on the same PostgreSQL cluster.
No World, ecology worker, login probe, archive export or production write occurs.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import gzip
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row

SERVER = Path(__file__).resolve().parents[1]
FORMAT = "wakemu-clean-database-v1"
COPY_TABLES = {
    "native_catalog_releases": (
        "revision",
        "document_count",
        "source_bytes",
        "complete",
        "created_at",
        "completed_at",
    ),
    "native_catalog_collections": ("collection_id", "name"),
    "native_catalog_bodies": ("body_id", "sha256", "raw", "source_bytes"),
    "native_catalog_index_sets": (
        "index_set_id",
        "record_count",
        "records_sha256",
        "sealed",
    ),
    "native_catalog_index_records": (
        "index_set_id",
        "collection_id",
        "record_key",
        "payload",
    ),
    "native_catalog_document_links": (
        "revision",
        "path",
        "body_id",
        "index_set_id",
        "record_count",
    ),
    "native_catalog_document_index_contracts": ("revision", "path", "contract_sha256"),
    "native_catalog_active": ("id", "revision", "activated_at"),
}
ECOLOGY_STATE_TABLES = (
    "territory_weather",
    "territory_weather_transitions",
    "territory_weather_outbox",
    "territory_weather_simulation",
    "combat_groups",
    "combat_group_members",
    "planted_resources",
    "monster_corpses",
    "monster_initial_population_publication",
    "monster_group_birth_homes",
    "monster_life_plans",
    "monster_maturation_timers",
    "monster_maturation_receipts",
    "monster_maturation_outbox",
    "monster_reproduction_timers",
    "monster_reproduction_receipts",
    "monster_reproduction_outbox",
    "monster_idle_distribution_runs",
    "monster_idle_distribution_moves",
    "ecology_dirty_scopes",
    "ecology_service_proposals",
    "ecology_planting_intents",
    "ecology_admin_operations",
    "environmental_event_instances",
    "environmental_participants",
    "environmental_event_memberships",
    "environmental_event_groups",
    "environmental_event_group_members",
    "environmental_event_rankings",
    "environmental_cleanup_outbox",
    "environmental_progress",
    "environmental_fact_receipts",
    "environmental_reward_entitlements",
    "environmental_reward_components",
    "environmental_entitlement_companions",
    "environmental_claim_receipts",
    "environmental_publication_outbox",
    "environmental_owned_resources",
    "environmental_resource_publications",
    "environmental_owned_groups",
    "environmental_owned_group_members",
    "environmental_group_publications",
    "environmental_regional_schedule_slots",
    "environmental_random_roster_draws",
    "environmental_random_roster_slots",
    "archmonster_spawn_births",
    "archmonster_spawn_publications",
)


def read_public_pack(pack):
    from tools.materialize_installation_data import verify, _file
    from tools.import_native_catalogs import validate_release_inventory

    pack = Path(pack)
    manifest = verify(pack)
    native = json.loads(
        _file(pack, manifest["artifacts"]["native-catalogs"]["path"]).read_text()
    )
    roles = manifest["catalogs"]
    revisions = {
        roles[key] for key in ("active_revision", "mining_revision", "fishing_revision")
    }
    if (
        any(
            not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None
            for value in revisions
        )
        or native.get("active_revision") != roles["active_revision"]
        or {release["revision"] for release in native["releases"]} != revisions
        or len(native["releases"]) != len(revisions)
    ):
        raise ValueError("Public native catalog roles disagree with their manifest")
    for release in native["releases"]:
        validate_release_inventory(
            [
                (row["path"], row["sha256"], row["source_bytes"])
                for row in release["documents"]
            ],
            release,
        )
    return manifest, native


def validate_source_inventory(source, manifest, native):
    """Match source bytes to the public, hash-verified document inventories."""
    active = source.execute(
        "SELECT revision FROM public.native_catalog_active WHERE id=1"
    ).fetchone()
    if active is None or active["revision"] != manifest["catalogs"]["active_revision"]:
        raise ValueError(
            "Source active catalog differs from the public installation pack"
        )
    for release in native["releases"]:
        revision = release["revision"]
        actual = source.execute(
            "SELECT revision,document_count,source_bytes,complete FROM public.native_catalog_releases WHERE revision=%s",
            (revision,),
        ).fetchone()
        if (
            actual is None
            or not actual["complete"]
            or any(
                actual[key] != release[key]
                for key in ("document_count", "source_bytes")
            )
        ):
            raise ValueError(
                "Source native release header differs from its public inventory"
            )
        rows = source.execute(
            'SELECT path,sha256,source_bytes FROM public.native_catalog_documents WHERE revision=%s ORDER BY path COLLATE "C"',
            (revision,),
        ).fetchall()
        expected = sorted(
            (
                {key: row[key] for key in ("path", "sha256", "source_bytes")}
                for row in release["documents"]
            ),
            key=lambda row: row["path"].encode("utf8"),
        )
        if rows != expected:
            raise ValueError(
                "Source native document bytes differ from their public inventory"
            )
    return [row["revision"] for row in native["releases"]]


def copy_native_catalogs(source, target, revisions):
    """Stream only explicitly selected normalized catalog data, retaining FKs."""
    sets = "SELECT DISTINCT index_set_id FROM public.native_catalog_document_links WHERE revision=ANY(%s)"
    queries = {
        "native_catalog_releases": ("revision=ANY(%s)", (revisions,)),
        "native_catalog_collections": (
            "collection_id IN (SELECT DISTINCT collection_id FROM public.native_catalog_index_records WHERE index_set_id IN ("
            + sets
            + "))",
            (revisions,),
        ),
        "native_catalog_bodies": (
            "body_id IN (SELECT body_id FROM public.native_catalog_document_links WHERE revision=ANY(%s))",
            (revisions,),
        ),
        "native_catalog_index_sets": ("index_set_id IN (" + sets + ")", (revisions,)),
        "native_catalog_index_records": (
            "index_set_id IN (" + sets + ")",
            (revisions,),
        ),
        "native_catalog_document_links": ("revision=ANY(%s)", (revisions,)),
        "native_catalog_document_index_contracts": ("revision=ANY(%s)", (revisions,)),
        "native_catalog_active": ("id=1", ()),
    }
    counts = {}
    with target.transaction():
        for table in COPY_TABLES:
            if target.execute(
                sql.SQL("SELECT 1 FROM public.{} LIMIT 1").format(sql.Identifier(table))
            ).fetchone():
                raise ValueError("Target native catalog tables must be empty")
            target.execute(
                sql.SQL("ALTER TABLE public.{} DISABLE TRIGGER USER").format(
                    sql.Identifier(table)
                )
            )
        for table, columns in COPY_TABLES.items():
            fields = sql.SQL(",").join(map(sql.Identifier, columns))
            predicate, parameters = queries[table]
            select = sql.SQL("SELECT {} FROM public.{} WHERE ").format(
                fields, sql.Identifier(table)
            ) + sql.SQL(predicate)
            with source.cursor().copy(
                sql.SQL("COPY ({}) TO STDOUT (FORMAT BINARY)").format(select),
                parameters,
            ) as outgoing:
                with target.cursor().copy(
                    sql.SQL("COPY public.{} ({}) FROM STDIN (FORMAT BINARY)").format(
                        sql.Identifier(table), fields
                    )
                ) as incoming:
                    for block in outgoing:
                        incoming.write(block)
            counts[table] = target.execute(
                sql.SQL("SELECT count(*) AS n FROM public.{}").format(
                    sql.Identifier(table)
                )
            ).fetchone()["n"]
            print(
                json.dumps(
                    {
                        "event": "clean_catalog_table_copied",
                        "table": table,
                        "rows": counts[table],
                    }
                ),
                flush=True,
            )
        for table in COPY_TABLES:
            target.execute(
                sql.SQL("ALTER TABLE public.{} ENABLE TRIGGER USER").format(
                    sql.Identifier(table)
                )
            )
        for table, field in (
            ("native_catalog_collections", "collection_id"),
            ("native_catalog_bodies", "body_id"),
            ("native_catalog_index_sets", "index_set_id"),
        ):
            target.execute(
                sql.SQL(
                    "SELECT setval(pg_get_serial_sequence(%s,%s),coalesce(max({}),1),count(*)>0) FROM public.{}"
                ).format(sql.Identifier(field), sql.Identifier(table)),
                ("public." + table, field),
            )
        invalid = target.execute(
            "SELECT 1 FROM public.native_catalog_document_links d JOIN public.native_catalog_index_sets s USING(index_set_id) "
            "WHERE NOT s.sealed OR s.records_sha256 IS NULL OR d.record_count<>s.record_count LIMIT 1"
        ).fetchone()
        if invalid:
            raise ValueError(
                "Copied native index sets are not complete authenticated publications"
            )
    return counts


def _artifact(pack, manifest, reference):
    from tools.materialize_installation_data import _file

    row = manifest["artifacts"][reference]
    raw = _file(Path(pack), row["path"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != row["sha256"] or len(raw) != row["size"]:
        raise ValueError("Public installation artifact changed during the build")
    return gzip.decompress(raw) if row.get("compression", "none") == "gzip" else raw


def merge_public_dungeon_pins(target, reviewed):
    """Promote paired public pins without downgrading canonical migration pins."""
    tables = (
        "dungeon_context_active_policies",
        "dungeon_runtime_active_configurations",
    )
    previous = {
        table: {
            row["route_key"]: row["policy_version"]
            for row in target.execute(
                sql.SQL("SELECT route_key,policy_version FROM public.{}").format(
                    sql.Identifier(table)
                )
            )
        }
        for table in tables
    }
    if previous[tables[0]] != previous[tables[1]]:
        raise ValueError("Canonical dungeon configuration/context pins disagree")
    text = reviewed.decode("utf8")
    pattern = re.compile(
        r"INSERT INTO public\.(dungeon_context_active_policies|dungeon_runtime_active_configurations) "
        r"\(route_key,policy_version\) VALUES \('((?:[^']|'')*)',([0-9]+)\) ON CONFLICT DO NOTHING;"
    )
    declared = {table: {} for table in tables}
    receipts = []
    for match in list(pattern.finditer(text)):
        table, escaped_route, version = match.groups()
        route, version = escaped_route.replace("''", "'"), int(version)
        if route in declared[table]:
            raise ValueError("Duplicate public dungeon pin")
        declared[table][route] = version
        selected = max(version, previous[table].get(route, version))
        replacement = match.group().replace(
            "ON CONFLICT DO NOTHING;",
            "ON CONFLICT(route_key) DO UPDATE SET policy_version=GREATEST("
            + table
            + ".policy_version,EXCLUDED.policy_version);",
        )
        text = text.replace(match.group(), replacement, 1)
        if selected != version:

            def guard(number):
                body = (
                    "BEGIN IF NOT EXISTS (SELECT 1 FROM public."
                    + table
                    + " WHERE route_key IS NOT DISTINCT FROM "
                    + sql.Literal(route).as_string(target)
                    + " AND policy_version IS NOT DISTINCT FROM "
                    + str(number)
                    + ") THEN RAISE EXCEPTION 'Conflicting reviewed dungeon installation authority'; END IF; END;"
                )
                return "DO " + sql.Literal(body).as_string(target) + ";"

            original = guard(version)
            if text.count(original) != 1:
                raise ValueError("Unrecognized public dungeon pin assertion")
            text = text.replace(original, guard(selected), 1)
        if previous[table].get(route, version) != version:
            receipts.append(
                dict(
                    table=table,
                    route_key=route,
                    previous=previous[table][route],
                    public=version,
                    selected=selected,
                )
            )
    if not declared[tables[0]] or declared[tables[0]] != declared[tables[1]]:
        raise ValueError("Public dungeon configuration/context pins disagree")
    return text, receipts


def apply_public_data(target, pack, manifest):
    from wakfu_server.bootstrap_capture import import_records

    bootstrap = _artifact(pack, manifest, manifest["bootstrap"]["artifact"])
    if hashlib.sha256(bootstrap).hexdigest() != manifest["bootstrap"]["sha256"]:
        raise ValueError("Synthetic bootstrap checksum mismatch")
    frames = [json.loads(line) for line in bootstrap.decode().splitlines()]
    if (
        not frames
        or frames[0].get("synthetic_template", {}).get("policy")
        != "wakemu-synthetic-bootstrap-v1"
        or any(
            set(frame) - {"direction", "opcode", "body_base64", "synthetic_template"}
            for frame in frames
        )
    ):
        raise ValueError(
            "Only the explicit synthetic public bootstrap may be installed"
        )
    with target.transaction():
        import_records(
            target,
            manifest["bootstrap"]["capture_key"],
            hashlib.sha256(bootstrap).hexdigest(),
            frames,
        )
    reviewed = _artifact(pack, manifest, manifest["reviewed_dungeons"]["artifact"])
    if hashlib.sha256(reviewed).hexdigest() != manifest["reviewed_dungeons"]["sha256"]:
        raise ValueError("Public dungeon seed checksum mismatch")
    # Existing public SQL retains every immutable-data conflict assertion.
    reviewed_sql, receipts = merge_public_dungeon_pins(target, reviewed)
    target.execute(reviewed_sql, prepare=False)
    from tools.export_installation_seed import reviewed_dungeon_rows

    reviewed_dungeon_rows(target)
    for reference in manifest.get("sql_seeds", []):
        target.execute(
            _artifact(pack, manifest, reference).decode("utf8"), prepare=False
        )
    return receipts


def add_admin(target):
    from wakfu_server.store import Store

    salt = secrets.token_bytes(16)
    with target.transaction():
        row = target.execute(
            "INSERT INTO public.accounts(username,username_key,salt,password_hash,is_admin) VALUES ('admin','admin',%s,%s,true) RETURNING id",
            (salt, Store.password_hash("admin", salt)),
        ).fetchone()
        target.execute(
            "INSERT INTO public.account_wallets(account_id,kamas) VALUES(%s,0)",
            (row["id"],),
        )
    return row["id"]


def prepare_clean_state(target):
    """Remove only migration-generated weather and wakeups in the scratch DB."""
    name = target.execute("SELECT current_database() AS name").fetchone()["name"]
    if re.fullmatch(r"wakemu_clean_backup_[a-z0-9_]+", name) is None:
        raise ValueError("Cleanup requires the dedicated clean-backup database")
    with target.transaction():
        target.execute("TRUNCATE public.territory_weather CASCADE")
        target.execute("TRUNCATE public.ecology_dirty_scopes")


def audit_clean_database(target, manifest):
    from wakfu_server.store import Store

    tables = [
        row["tablename"]
        for row in target.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        )
    ]
    counts = {
        table: target.execute(
            sql.SQL("SELECT count(*) AS n FROM public.{}").format(sql.Identifier(table))
        ).fetchone()["n"]
        for table in tables
    }
    private = {
        "characters",
        "sessions",
        "tokens",
        "inventory_items",
        "inventory_containers",
        *ECOLOGY_STATE_TABLES,
    }
    private.update(
        row["table_name"]
        for row in target.execute(
            "SELECT DISTINCT table_name FROM information_schema.columns WHERE table_schema='public' "
            "AND column_name ~ '(^|_)(account|character)_id$'"
        )
    )
    quests = target.execute(
        "SELECT account_id,reference,quantity FROM public.account_quest_items ORDER BY account_id,reference"
    ).fetchall()
    if quests != [{"account_id": 1, "reference": 32864, "quantity": 1}]:
        raise ValueError(
            "Only the new administrator's canonical starter entitlement may exist"
        )
    private -= {"accounts", "account_wallets", "account_quest_items"}
    if any(counts.get(table, 0) != 0 for table in private):
        raise ValueError("Clean installation contains player or ecology state")
    account = target.execute(
        "SELECT id,username,username_key,salt,password_hash,is_admin FROM public.accounts"
    ).fetchall()
    if counts["accounts"] != 1 or len(account) != 1:
        raise ValueError("Clean installation must have exactly one administrator")
    account = account[0]
    if (
        account["id"] != 1
        or account["username"] != "admin"
        or account["username_key"] != "admin"
        or not account["is_admin"]
        or not hmac.compare_digest(
            bytes(account["password_hash"]),
            Store.password_hash("admin", bytes(account["salt"])),
        )
    ):
        raise ValueError("Clean installation administrator differs from admin/admin")
    wallets = target.execute(
        "SELECT account_id,kamas FROM public.account_wallets"
    ).fetchall()
    if wallets != [{"account_id": 1, "kamas": 0}]:
        raise ValueError(
            "Clean installation administrator must have a fresh empty wallet"
        )
    for table, count in manifest["expected_counts"].items():
        if counts.get(table) != count:
            raise ValueError("Public installation table count differs: " + table)
    return {
        "table_counts": counts,
        "required_zero_tables": sorted(table for table in tables if counts[table] == 0),
    }


@contextmanager
def _target_environment(url, revision, password_file=None):
    changes = {
        "WAKFU_DATABASE_URL": url,
        "WAKFU_CATALOG_REVISION": revision,
        "WAKFU_REDIS_URL": "redis://127.0.0.1:1/14",
    }
    if password_file is not None:
        changes["WAKFU_DATABASE_PASSWORD_FILE"] = str(Path(password_file).resolve())
    original = {key: os.environ.get(key) for key in changes}
    os.environ.update(changes)
    try:
        yield
    finally:
        from wakfu_server import native_catalog

        if native_catalog._database.cache_info().currsize:
            native_catalog._database().close()
            native_catalog._database.cache_clear()
        native_catalog.release.cache_clear()
        native_catalog._redis.cache_clear()
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def describe_manifest(target, manifest, native, pack, database_name, *, pin_merges=()):
    """Describe a completed scratch seed without copying or modifying it."""
    pack = Path(pack)
    audit = audit_clean_database(target, manifest)
    schema = target.execute(
        "SELECT version,checksum FROM public.schema_migrations ORDER BY version"
    ).fetchall()
    copied = {table: audit["table_counts"][table] for table in COPY_TABLES}
    return dict(
        format=FORMAT,
        created_at=datetime.now(timezone.utc).isoformat(),
        database=database_name,
        contains_production_player_data=False,
        contains_production_ecology_state=False,
        source_tables_read=list(COPY_TABLES),
        copied_table_counts=copied,
        compiled_cache_included=False,
        public_seed_pin_merges=list(pin_merges),
        bootstrap_policy="wakemu-synthetic-bootstrap-v1",
        public_pack_manifest_sha256=hashlib.sha256(
            (pack / "manifest.json").read_bytes()
        ).hexdigest(),
        schema_versions=schema,
        native_catalog=dict(
            **{
                key: manifest["catalogs"][key]
                for key in ("active_revision", "mining_revision", "fishing_revision")
            },
            releases=[
                {
                    key: row[key]
                    for key in ("revision", "document_count", "source_bytes")
                }
                for row in native["releases"]
            ],
        ),
        admin=dict(username="admin", password="admin", is_admin=True, kamas=0),
        **audit,
    )


def build(source_url, database_name, *, password_file=None, pack=None, migrations=None):
    from wakfu_server.postgres import migrate
    from tools.install_environmental_profiles import install

    if (
        re.fullmatch(r"wakemu_clean_backup_[a-z0-9_]+", database_name) is None
        or len(database_name.encode()) > 63
    ):
        raise ValueError(
            "Target must be a new dedicated wakemu_clean_backup_* database"
        )
    pack = Path(pack) if pack is not None else SERVER / "data" / "installation"
    manifest, native = read_public_pack(pack)
    password = (
        {}
        if password_file is None
        else {"password": Path(password_file).read_text().strip()}
    )
    if password_file is not None and not password["password"]:
        raise ValueError("Empty PostgreSQL password file")
    target_url = make_conninfo(
        **dict(conninfo_to_dict(source_url), dbname=database_name)
    )
    # Guard and create before copying anything. Existing databases are never reused.
    with psycopg.connect(
        source_url, **password, autocommit=True, row_factory=dict_row
    ) as admin:
        if admin.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s", (database_name,)
        ).fetchone():
            raise ValueError(
                "Target database already exists; refusing to reuse or overwrite it"
            )
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(
                sql.Identifier(database_name)
            )
        )
    with psycopg.connect(
        source_url, **password, autocommit=True, row_factory=dict_row
    ) as source, psycopg.connect(
        target_url, **password, autocommit=True, row_factory=dict_row
    ) as target:
        migrate(target, migrations or SERVER / "migrations")
        with source.transaction():
            source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            revisions = validate_source_inventory(source, manifest, native)
            copied = copy_native_catalogs(source, target, revisions)
        pin_merges = apply_public_data(target, pack, manifest)
        with _target_environment(
            target_url, manifest["catalogs"]["active_revision"], password_file
        ):
            with target.transaction():
                install(
                    target,
                    expected_revision=manifest["catalogs"]["active_revision"],
                    activate=True,
                )
        add_admin(target)
        prepare_clean_state(target)
        return describe_manifest(
            target, manifest, native, pack, database_name, pin_merges=pin_merges
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-url", default=os.environ.get("WAKFU_DATABASE_URL"))
    parser.add_argument("--database", required=True)
    parser.add_argument(
        "--password-file",
        type=Path,
        default=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    parser.add_argument("--pack", type=Path, default=SERVER / "data" / "installation")
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if not args.source_url:
        parser.error("--source-url or WAKFU_DATABASE_URL is required")
    if args.manifest.exists():
        parser.error("Manifest destination already exists")
    result = build(
        args.source_url, args.database, password_file=args.password_file, pack=args.pack
    )
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(
        json.dumps(
            {
                "event": "clean_database_ready",
                "database": args.database,
                "manifest": str(args.manifest),
                "tables": len(result["table_counts"]),
            }
        )
    )


if __name__ == "__main__":
    main()
