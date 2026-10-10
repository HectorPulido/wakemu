"""Explicit reversible activation of verified candidates; never restarts world."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path


def activate(store, candidates, evidence, backup_path, *, apply=False):
    from wakfu_server.maps import dungeon_runtime_config as configs
    from wakfu_server.maps.dungeon_native_flow import enabled

    verified = {
        r["route"]
        for r in evidence["records"]
        if r["status"] == "isolated_postgres_lifecycle_and_economy_passed"
    }
    selected = [
        r
        for r in candidates["records"]
        if r["status"] == "offline_configuration_prepared"
    ]
    if {r["route"] for r in selected} - verified:
        raise ValueError("Candidate lacks complete isolated lifecycle/economy evidence")
    for path, digest in evidence["source_sha256"].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
            raise ValueError("Lifecycle evidence source changed: " + path)
    with store.connection() as db:
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended('native-physical-candidate-activation',0))"
        )
        registry = db.execute(
            "SELECT value FROM settings WHERE name='dungeon_runtime_routes'"
        ).fetchone()
        if registry is None:
            raise ValueError("Runtime native route registry is absent")
        registered = {r["key"]: r for r in registry["value"]["routes"]}
        backup = dict(
            created_at=datetime.now(timezone.utc).isoformat(),
            scope="Restore active configuration/context pointers; immutable versions retained",
            settings=[],
            context_active=[],
            context_versions=[],
        )
        actions = []
        pending = []
        for row in selected:
            key = row["route"]
            candidate = json.loads(Path(row["path"]).read_text())
            if registered.get(key) != candidate["route"]:
                raise ValueError(
                    "Candidate route does not match active native registry: " + key
                )
            current = configs.active_configuration(db, key)
            backup["settings"] += db.execute(
                "SELECT name,value FROM settings WHERE name=%s OR name LIKE %s",
                (
                    "dungeon_runtime_active:" + key,
                    "dungeon_runtime_config:" + key + ":v%",
                ),
            ).fetchall()
            backup["context_active"] += db.execute(
                "SELECT * FROM dungeon_context_active_policies WHERE route_key=%s",
                (key,),
            ).fetchall()
            backup["context_versions"] += db.execute(
                "SELECT * FROM dungeon_context_policy_versions WHERE route_key=%s",
                (key,),
            ).fetchall()
            if enabled(current["topology"]):
                actions.append(
                    dict(
                        route=key,
                        name=row["name"],
                        status="preserved_existing_native_physical_configuration",
                        version=current["version"],
                    )
                )
                continue
            maximum = (
                db.execute(
                    "SELECT max(policy_version) AS version FROM dungeon_context_policy_versions WHERE route_key=%s",
                    (key,),
                ).fetchone()["version"]
                or 0
            )
            proposed = configs.prepare_configuration(
                candidate["compiled_plan"],
                candidate["topology"],
                candidate["route"],
                version=maximum + 1,
                provenance=candidate["provenance"],
            )
            pending.append(proposed)
            actions.append(
                dict(
                    route=key,
                    name=row["name"],
                    status="activated" if apply else "prepared",
                    previous_version=current["version"],
                    version=proposed["version"],
                    boss_mechanics="incomplete_explicit_dev_flow_activation",
                )
            )
        if apply:
            if backup_path.exists():
                raise ValueError("Activation backup path already exists")
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(json.dumps(backup, indent=2, default=str) + "\n")
            for proposed in pending:
                configs.install_configuration(db, proposed)
        return dict(
            applied=apply,
            backup=str(backup_path) if apply else None,
            actions=actions,
            limitations="Boss AI/spell mechanics incomplete; explicit DEV flow/composition/gate/exit activation. Existing runs retain pinned versions. No restart performed.",
        )


def main():
    from wakfu_server.store import Store

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--backup", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    p.add_argument(
        "--candidates",
        type=Path,
        default=Path("docs/reports/dungeons/AUTOMATIC-COMPLETE-CANDIDATES.json"),
    )
    p.add_argument(
        "--evidence",
        type=Path,
        default=Path("docs/reports/dungeons/AUTOMATIC-PG-LIFECYCLE-ECONOMY.json"),
    )
    args = p.parse_args()
    store = Store(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
    )
    try:
        result = activate(
            store,
            json.loads(args.candidates.read_text()),
            json.loads(args.evidence.read_text()),
            args.backup,
            apply=args.apply,
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
