"""Promote reviewed dungeon data for future runs; default is read-only review."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from prepare_reviewed_dungeon_configuration import prepare
from wakfu_server.dungeon_runtime_config import canonical_hash, install_configuration


def bundle_file(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Reviewed evidence path escapes its bundle")
    return path


def apply(db, manifest, root, *, install=False, backup=None):
    if (
        manifest.get("repair_kind") != "reviewed-dungeon-guide-data-v1"
        or manifest.get("future_runs_only") is not True
        or manifest.get("installed") is not False
    ):
        raise ValueError("Explicit uninstalled reviewed future-run manifest required")
    raw = bundle_file(root, manifest["native_monsters_path"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["native_monsters_sha256"]:
        raise ValueError("Reviewed native monster evidence changed")
    native = json.loads(raw)["monsters"]
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
        raise ValueError("Reviewed evidence differs from active native catalog")
    originals, pending, seen = [], [], set()
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    teleporters = None
    for row in sorted(manifest["candidates"], key=lambda row: row["route_key"]):
        key = row["route_key"]
        if key in seen:
            raise ValueError("Duplicate reviewed route")
        seen.add(key)
        candidate = json.loads(bundle_file(root, row["path"]).read_bytes())
        proposal_raw = bundle_file(root, row["proposal_path"]).read_bytes()
        proposal = json.loads(proposal_raw)
        geometry = json.loads(bundle_file(root, row["geometry_path"]).read_bytes())
        if (
            candidate["version"] != row["candidate_version"]
            or candidate["route"]["key"] != key
            or canonical_hash(candidate) != row["candidate_sha256"]
            or hashlib.sha256(proposal_raw).hexdigest() != row["proposal_sha256"]
            or canonical_hash(geometry) != row["geometry_canonical_sha256"]
        ):
            raise ValueError("Reviewed candidate or evidence changed")
        if install:
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (f"dungeon_runtime_config:{key}",),
            )
        current = db.execute(
            "SELECT a.policy_version,c.configuration FROM dungeon_runtime_active_configurations a "
            "JOIN dungeon_runtime_configurations c USING(route_key,policy_version) "
            "WHERE a.route_key=%s" + (" FOR UPDATE OF a,c" if install else ""),
            (key,),
        ).fetchone()
        context = db.execute(
            "SELECT policy_version FROM dungeon_context_active_policies WHERE route_key=%s"
            + (" FOR UPDATE" if install else ""),
            (key,),
        ).fetchone()
        allowed = {
            (source["version"], source["sha256"]) for source in row["allowed_sources"]
        }
        if (
            current is None
            or context is None
            or (current["policy_version"], canonical_hash(current["configuration"]))
            not in allowed
            or context["policy_version"] != current["policy_version"]
        ):
            raise ValueError("Reviewed source does not match an approved frozen policy")
        original = current["configuration"]
        actual_geometry = native_catalog.load(
            DATA_ROOT / "combat-maps" / f"{original['route']['start_map_id']}.json"
        )
        if canonical_hash(actual_geometry) != row["geometry_canonical_sha256"]:
            raise ValueError("Reviewed terrain differs from active native geometry")
        if proposal["room_scope"] == "native_entry_component":
            if teleporters is None:
                teleporters = native_catalog.load(
                    DATA_ROOT / "native-generic-teleporters.json"
                )
            route = original["route"]
            sources = [
                source
                for source in teleporters
                if (source["map_id"], source["id"])
                == (route["entry_map_id"], route["entry_object_id"])
            ]
            destinations = [
                destination
                for source in sources
                for destination in source["destinations"]
                if destination["destination_id"] == route["destination_id"]
            ]
            if (
                len(destinations) != 1
                or destinations[0]["map_id"] != geometry["map_id"]
                or [destinations[0][coordinate] for coordinate in ("x", "y", "z")]
                != proposal["native_entry"]
            ):
                raise ValueError(
                    "Reviewed single room is not tied to actual native entry"
                )
        if (
            prepare(
                original,
                proposal,
                native,
                actual_geometry,
                version=candidate["version"],
            )
            != candidate
        ):
            raise ValueError(
                "Reviewed candidate differs from recomputed guide/native data"
            )
        collision = db.execute(
            "SELECT configuration FROM dungeon_runtime_configurations WHERE route_key=%s AND policy_version=%s",
            (key, candidate["version"]),
        ).fetchone()
        if (
            collision is not None
            and canonical_hash(collision["configuration"]) != row["candidate_sha256"]
        ):
            raise ValueError(
                "Reviewed immutable target version already has other content"
            )
        originals.append(
            dict(
                route_key=key,
                policy_version=current["policy_version"],
                configuration=original,
            )
        )
        pending.append(candidate)
    if not pending:
        raise ValueError("Reviewed manifest contains no configurations")
    if install:
        if backup is None:
            raise ValueError("Reviewed application requires an exclusive backup")
        with Path(backup).open("x") as destination:
            json.dump(
                dict(
                    created_at=datetime.now(timezone.utc).isoformat(),
                    originals=originals,
                    manifest=manifest,
                ),
                destination,
                indent=2,
            )
            destination.write("\n")
            destination.flush()
            os.fsync(destination.fileno())
        for candidate in pending:
            install_configuration(db, candidate)
    return dict(
        qualified=True,
        installed=install,
        future_runs_only=True,
        candidates=len(pending),
        policies=[
            dict(
                route_key=candidate["route"]["key"],
                version=candidate["version"],
                sha256=canonical_hash(candidate),
            )
            for candidate in pending
        ],
        backup=None if not install else str(backup),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.receipt is not None and args.receipt.exists():
        raise ValueError("Reviewed receipt path already exists")
    manifest = json.loads(args.manifest.read_bytes())
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
                db,
                manifest,
                args.manifest.parent,
                install=args.apply,
                backup=args.backup,
            )
        result["manifest_sha256"] = hashlib.sha256(
            args.manifest.read_bytes()
        ).hexdigest()
        if args.receipt is not None:
            with args.receipt.open("x") as destination:
                json.dump(result, destination, indent=2)
                destination.write("\n")
        print(json.dumps(result, sort_keys=True))
    finally:
        database.close()


if __name__ == "__main__":
    main()
