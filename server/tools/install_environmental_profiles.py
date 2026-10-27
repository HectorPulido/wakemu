"""Install the complete disabled environmental bundle atomically on an empty DB.

Use --activate to enable the installed bundle in the same transaction, or
--verify-only to inspect an existing complete installation without writes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

import psycopg
from psycopg.rows import dict_row
from psycopg.pq import TransactionStatus


SEEDS = (
    "environmental_resource_profiles.sql",
    "environmental_resource_races.sql",
    "environmental_resource_competitions.sql",
    "environmental_resource_results.sql",
    "environmental_resource_level_criteria.sql",
    "environmental_group_profiles.sql",
    "environmental_group_criteria_profiles.sql",
    "environmental_destroy_profiles.sql",
    "environmental_named_destroy_profiles.sql",
    "environmental_resource_stage_profiles.sql",
)
GENESIS = "wakemu.environmental-exact-species-genesis-v1"
# Original physical resource actions, creature definitions and regional birth
# authority consumed by the installed profile families. Metadata-only catalog
# additions do not rewrite the frozen revision stored on sealed profiles.
PROFILE_SOURCE_DOCUMENTS = (
    "plant-resources.json",
    "seed-actions.json",
    "monsters.json",
    "monster-encyclopedia.json",
    "territory-map-cells.json",
    "territory-protector-bonuses.json",
)


def seed_body(sql):
    """Remove only complete top-level BEGIN/COMMIT statements, preserving bodies."""
    chunks, code, start, index = [], [], 0, 0
    while index < len(sql):
        if sql.startswith("--", index):
            end = sql.find("\n", index)
            index = len(sql) if end < 0 else end + 1
            code.append(" ")
            continue
        if sql.startswith("/*", index):
            depth, end = 1, index + 2
            while depth and end < len(sql):
                if sql.startswith("/*", end):
                    depth += 1
                    end += 2
                elif sql.startswith("*/", end):
                    depth -= 1
                    end += 2
                else:
                    end += 1
            if depth:
                raise ValueError("Unterminated seed comment")
            index = end
            code.append(" ")
            continue
        char = sql[index]
        if char in ("'", '"'):
            end = index + 1
            while end < len(sql):
                if char == "'" and sql[end] == "\\":
                    end += 2
                elif sql[end] == char:
                    if end + 1 < len(sql) and sql[end + 1] == char:
                        end += 2
                    else:
                        end += 1
                        break
                else:
                    end += 1
            else:
                raise ValueError("Unterminated seed string")
            code.append(sql[index:end])
            index = end
            continue
        if char == "$":
            tag = re.match(r"\$(?:[A-Za-z_][A-Za-z_0-9]*)?\$", sql[index:])
            if tag is not None:
                marker = tag.group()
                end = sql.find(marker, index + len(marker))
                if end < 0:
                    raise ValueError("Unterminated seed dollar body")
                end += len(marker)
                code.append(sql[index:end])
                index = end
                continue
        if char == ";":
            statement = "".join(code).strip().upper()
            if statement not in ("BEGIN", "COMMIT"):
                if re.match(
                    r"^(?:BEGIN|COMMIT|ROLLBACK|START\s+TRANSACTION)\b", statement
                ):
                    raise ValueError("Unsupported seed transaction control")
                chunks.append(sql[start : index + 1])
            start, code = index + 1, []
        else:
            code.append(char)
        index += 1
    if "".join(code).strip():
        raise ValueError("Seed must end with a complete SQL statement")
    chunks.append(sql[start:])
    return "".join(chunks)


def _count(db, sql, parameters=()):
    return db.execute(sql, parameters).fetchone()["n"]


def _catalog(db, expected_revision):
    if (
        type(expected_revision) is not str
        or re.fullmatch("[0-9a-f]{64}", expected_revision) is None
    ):
        raise ValueError(
            "WAKFU_CATALOG_REVISION must identify the expected complete catalog"
        )
    active = db.execute(
        "SELECT a.revision FROM native_catalog_active a "
        "JOIN native_catalog_releases r USING(revision) WHERE a.id=1 AND r.complete"
    ).fetchone()
    if active is None or active["revision"] != expected_revision:
        raise ValueError(
            "Environmental installation catalog differs from expected release"
        )


def verify(db, expected_revision):
    _catalog(db, expected_revision)
    row = db.execute(
        "SELECT count(*) AS n,count(*) FILTER(WHERE sealed) AS sealed,"
        "count(DISTINCT native_scenario_id) AS scenarios,count(*) FILTER(WHERE enabled) AS enabled "
        "FROM environmental_runtime_profiles",
    ).fetchone()
    if (row["n"], row["sealed"], row["scenarios"]) != (1270, 1270, 1057):
        raise ValueError(
            "Environmental installation requires 1270 sealed profiles and 1057 source scenarios"
        )
    source_revisions = tuple(
        source["catalog_revision"]
        for source in db.execute(
            "SELECT DISTINCT catalog_revision FROM environmental_runtime_profiles "
            "ORDER BY catalog_revision"
        ).fetchall()
    )
    from wakfu_server.native_catalog_compatibility import require_source_revision

    for revision in source_revisions:
        if revision != expected_revision:
            require_source_revision(revision, PROFILE_SOURCE_DOCUMENTS)
    policies = db.execute(
        "SELECT count(*) AS n,count(*) FILTER(WHERE sealed) AS sealed,"
        "count(*) FILTER(WHERE enabled) AS enabled FROM environmental_regional_schedule_policies "
        "WHERE version=9"
    ).fetchone()
    candidates = _count(
        db,
        "SELECT count(*) AS n FROM environmental_regional_schedule_candidates WHERE version=9",
    )
    if (policies["n"], policies["sealed"], candidates) != (90, 90, 1270):
        raise ValueError(
            "Environmental installation lacks the complete version 9 schedule"
        )
    other_enabled = _count(
        db,
        "SELECT count(*) AS n FROM environmental_regional_schedule_policies "
        "WHERE enabled AND version<>9",
    )
    arch = db.execute(
        "SELECT count(*) FILTER(WHERE NOT blocked_by_membership) AS eligible,"
        "count(*) FILTER(WHERE blocked_by_membership) AS blocked FROM archmonster_spawn_sources"
    ).fetchone()
    if (arch["eligible"], arch["blocked"]) != (61, 2):
        raise ValueError(
            "Archmonster source inventory differs from 61 eligible and 2 blocked"
        )
    genesis = db.execute(
        "SELECT policy_version,enabled FROM environmental_random_roster_active "
        "WHERE singleton"
    ).fetchone()
    spawn = db.execute(
        "SELECT a.policy_version,a.enabled,v.cooldown_ms FROM archmonster_spawn_active a "
        "JOIN archmonster_spawn_policy_versions v USING(policy_version) WHERE a.singleton"
    ).fetchone()
    if (
        genesis is None
        or genesis["policy_version"] != GENESIS
        or spawn is None
        or spawn["cooldown_ms"] is None
    ):
        raise ValueError(
            "Missing qualified environmental population activation pointers"
        )
    return dict(
        profiles=row["n"],
        sealed_profiles=row["sealed"],
        native_scenarios=row["scenarios"],
        catalog_revision=expected_revision,
        source_catalog_revisions=list(source_revisions),
        schedule_version=9,
        schedule_policies=policies["n"],
        schedule_candidates=candidates,
        enabled_profiles=row["enabled"],
        enabled_schedules=policies["enabled"],
        other_enabled_schedules=other_enabled,
        random_roster_enabled=genesis["enabled"],
        archmonster_enabled=spawn["enabled"],
        archmonster_policy=spawn["policy_version"],
        archmonster_eligible=arch["eligible"],
        archmonster_blocked=arch["blocked"],
    )


def install(
    db, *, expected_revision, activate=False, verify_only=False, seed_directory=None
):
    """Caller owns one transaction. Existing installations are verification-only."""
    if activate and verify_only:
        raise ValueError("--activate and --verify-only are mutually exclusive")
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended('install_environmental_profiles',0))"
    )
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Environmental installer requires one owned transaction")
    if verify_only:
        return dict(verify(db, expected_revision), verified_only=True, installed=False)
    _catalog(db, expected_revision)
    if _count(db, "SELECT count(*) AS n FROM environmental_runtime_profiles") != 0:
        raise ValueError(
            "Environmental profiles already exist; use --verify-only, never reimport"
        )
    seed_directory = (
        Path(seed_directory)
        if seed_directory is not None
        else Path(__file__).resolve().parents[1] / "seeds"
    )
    hashes = {}
    for index, name in enumerate(SEEDS):
        if index == 5:
            if (
                _count(db, "SELECT count(*) AS n FROM environmental_runtime_profiles")
                != 352
            ):
                raise ValueError(
                    "Resource bundle must contain exactly 352 profiles before sealing"
                )
            db.execute("UPDATE environmental_runtime_profiles SET sealed=true")
            db.execute(
                "UPDATE environmental_regional_schedule_policies SET sealed=true"
            )
            db.execute("SET CONSTRAINTS ALL IMMEDIATE")
        raw = (seed_directory / name).read_bytes()
        hashes[name] = hashlib.sha256(raw).hexdigest()
        db.execute("SET CONSTRAINTS ALL DEFERRED")
        db.execute(seed_body(raw.decode()), prepare=False)
    db.execute("SET CONSTRAINTS ALL IMMEDIATE")
    result = verify(db, expected_revision)
    if activate:
        db.execute("UPDATE environmental_runtime_profiles SET enabled=true")
        db.execute(
            "UPDATE environmental_regional_schedule_policies SET enabled=false WHERE enabled"
        )
        db.execute(
            "UPDATE environmental_regional_schedule_policies SET enabled=true WHERE version=9"
        )
        row = db.execute(
            "UPDATE environmental_random_roster_active SET enabled=true "
            "WHERE singleton AND policy_version=%s RETURNING policy_version",
            (GENESIS,),
        ).fetchone()
        if row is None:
            raise ValueError("Exact random roster policy activation failed")
        db.execute("UPDATE archmonster_spawn_active SET enabled=true WHERE singleton")
        db.execute("SET CONSTRAINTS ALL IMMEDIATE")
        result = verify(db, expected_revision)
        if (
            result["enabled_profiles"],
            result["enabled_schedules"],
            result["other_enabled_schedules"],
            result["random_roster_enabled"],
            result["archmonster_enabled"],
        ) != (1270, 90, 0, True, True):
            raise ValueError(
                "Environmental activation did not enable the complete declared bundle"
            )
    return dict(
        result, installed=True, activated=activate, verified_only=False, seeds=hashes
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--activate", action="store_true")
    mode.add_argument("--verify-only", action="store_true")
    parser.add_argument(
        "--catalog-revision", default=os.environ.get("WAKFU_CATALOG_REVISION")
    )
    args = parser.parse_args()
    options = dict(row_factory=dict_row, autocommit=True)
    password_file = os.environ.get("WAKFU_DATABASE_PASSWORD_FILE")
    if password_file:
        options["password"] = Path(password_file).read_text().strip()
    elif os.environ.get("WAKFU_DATABASE_PASSWORD") is not None:
        options["password"] = os.environ["WAKFU_DATABASE_PASSWORD"]
    with psycopg.connect(os.environ["WAKFU_DATABASE_URL"], **options) as db:
        with db.transaction():
            if args.verify_only:
                db.execute("SET TRANSACTION READ ONLY")
            result = install(
                db,
                expected_revision=args.catalog_revision,
                activate=args.activate,
                verify_only=args.verify_only,
            )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
