"""Guarded future-run-only configuration promotion; defaults to read-only review.

Never updates dungeon_instances, dungeon_room_runs, spawn receipts or groups.
Use --apply only within an explicitly authorized environment and deployment.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from wakfu_server.dungeon_runtime_config import canonical_hash, install_configuration


def load_candidates(manifest):
    if (
        manifest.get("future_runs_only") is not True
        or manifest.get("installed") is not False
    ):
        raise ValueError("Explicit uninstalled future-run manifest required")
    rows, seen = [], set()
    for row in manifest["candidates"]:
        candidate = json.loads(Path(row["path"]).read_text())
        route = row["route_key"]
        if route in seen or candidate["route"]["key"] != route:
            raise ValueError("Duplicate or conflicting candidate route")
        seen.add(route)
        if (
            canonical_hash(candidate) != row["candidate_sha256"]
            or candidate["version"] != row["candidate_version"]
            or candidate["version"] <= row["source_version"]
        ):
            raise ValueError("Candidate content/version differs from manifest")
        rows.append((row, candidate))
    if not rows:
        raise ValueError("Repair manifest contains no candidates")
    return sorted(rows, key=lambda pair: pair[0]["route_key"])


def apply(db, manifest, candidates, *, install=False, backup=None):
    """Call inside one transaction; guard every source before writing any row."""
    raw = Path(manifest["native_monsters_path"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["native_monsters_sha256"]:
        raise ValueError("Native role evidence file changed")
    native_monsters = json.loads(raw)["monsters"]
    catalog = db.execute(
        "SELECT a.revision,d.sha256 FROM native_catalog_active a "
        "JOIN native_catalog_documents d USING(revision) "
        "WHERE a.id=1 AND d.path='monsters.json'"
        + (" FOR SHARE OF a" if install else "")
    ).fetchone()
    if catalog is None or (catalog["revision"], catalog["sha256"]) != (
        manifest["catalog_revision"],
        manifest["native_monsters_sha256"],
    ):
        raise ValueError("Native role evidence no longer matches active catalog")
    originals = []
    for row, candidate in candidates:
        route = row["route_key"]
        if install:
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"dungeon_runtime_config:{route}",),
            )
        current = db.execute(
            "SELECT a.policy_version,c.configuration FROM dungeon_runtime_active_configurations a "
            "JOIN dungeon_runtime_configurations c USING(route_key,policy_version) "
            "WHERE a.route_key=%s" + (" FOR UPDATE OF a,c" if install else ""),
            (route,),
        ).fetchone()
        context = db.execute(
            "SELECT policy_version FROM dungeon_context_active_policies WHERE route_key=%s"
            + (" FOR UPDATE" if install else ""),
            (route,),
        ).fetchone()
        if (
            current is None
            or context is None
            or current["policy_version"] != row["source_version"]
            or context["policy_version"] != row["source_version"]
            or canonical_hash(current["configuration"]) != row["source_sha256"]
        ):
            raise ValueError("Active source policy changed: " + route)
        original = current["configuration"]
        from prepare_generated_dungeon_role_repair import prepare

        expected, _ = prepare(original, native_monsters, version=candidate["version"])
        if expected != candidate:
            raise ValueError("Candidate differs from qualified role-only repair")
        if (
            candidate["topology"] != original["topology"]
            or candidate["route"] != original["route"]
        ):
            raise ValueError("Repair cannot change native topology or entry identity")
        if {
            key: value
            for key, value in candidate["context_policy"].items()
            if key != "policy_version"
        } != {
            key: value
            for key, value in original["context_policy"].items()
            if key != "policy_version"
        } or candidate[
            "level_policy"
        ] != original[
            "level_policy"
        ]:
            raise ValueError("Repair cannot change entry or native level policy")
        before = [
            (room["order"], sum(monster["count"] for monster in room["monsters"]))
            for room in original["compiled_plan"]["rooms"]
        ]
        after = [
            (room["order"], sum(monster["count"] for monster in room["monsters"]))
            for room in candidate["compiled_plan"]["rooms"]
        ]
        if before != after:
            raise ValueError("Repair cannot change room orders or quantities")
        originals.append(
            dict(
                route_key=route,
                policy_version=row["source_version"],
                configuration=original,
            )
        )
    if not install:
        return dict(
            qualified=True,
            installed=False,
            candidates=len(candidates),
            future_runs_only=True,
        )
    if backup is None:
        raise ValueError("Applying repairs requires an exclusive backup path")
    # Save the exact old policies before the transaction's first mutation.
    # Immutable old configurations remain in PostgreSQL after activation too.
    with Path(backup).open("x") as destination:
        json.dump(
            dict(
                created_at=datetime.now(timezone.utc).isoformat(),
                catalog=dict(catalog),
                originals=originals,
                manifest=manifest,
            ),
            destination,
            indent=2,
        )
        destination.write("\n")
        destination.flush()
        os.fsync(destination.fileno())
    for _, candidate in candidates:
        install_configuration(db, candidate)
    return dict(
        qualified=True,
        installed=True,
        candidates=len(candidates),
        future_runs_only=True,
        backup=str(backup),
        backup_sha256=hashlib.sha256(Path(backup).read_bytes()).hexdigest(),
        policies=[
            dict(
                route_key=row["route_key"],
                source_version=row["source_version"],
                candidate_version=row["candidate_version"],
                candidate_sha256=row["candidate_sha256"],
            )
            for row, _ in candidates
        ],
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.receipt is not None and args.receipt.exists():
        raise ValueError("Receipt path already exists")
    manifest = json.loads(args.manifest.read_text())
    candidates = load_candidates(manifest)
    from wakfu_server.postgres import Database

    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        min_size=1,
        max_size=1,
    )
    try:
        with database.connection() as db:
            if not args.apply:
                db.execute("SET TRANSACTION READ ONLY")
            result = apply(
                db, manifest, candidates, install=args.apply, backup=args.backup
            )
        result["manifest_sha256"] = hashlib.sha256(
            args.manifest.read_bytes()
        ).hexdigest()
        if args.receipt is not None:
            with args.receipt.open("x") as destination:
                json.dump(result, destination, indent=2)
                destination.write("\n")
                destination.flush()
                os.fsync(destination.fileno())
        print(json.dumps(result, sort_keys=True))
    finally:
        database.close()


if __name__ == "__main__":
    main()
