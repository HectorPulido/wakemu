"""Prepare immutable candidates from read-only active configuration exports."""
import argparse
import hashlib
import json
from pathlib import Path

from audit_dungeon_generated_roles import audit
from prepare_generated_dungeon_role_repair import prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configurations", type=Path, required=True)
    parser.add_argument("--native-monsters", type=Path, required=True)
    parser.add_argument("--versions", type=Path, required=True)
    parser.add_argument("--catalog-revision", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()
    rows = json.loads(args.configurations.read_text())
    native = json.loads(args.native_monsters.read_text())["monsters"]
    versions = {
        row["route_key"]: row["maximum_version"]
        for row in json.loads(args.versions.read_text())
    }
    inventory = {row["route_key"]: row for row in audit(rows, native)["configurations"]}
    manifest = dict(
        catalog_revision=args.catalog_revision,
        native_monsters_sha256=hashlib.sha256(
            args.native_monsters.read_bytes()
        ).hexdigest(),
        native_monsters_path=str(args.native_monsters.resolve()),
        candidates=[],
        blocked=[],
        future_runs_only=True,
        installed=False,
    )
    args.output_directory.mkdir()
    for row in rows:
        findings = inventory[row["route_key"]]
        needs_repair = any(
            entry["identity_source"] != "preserved_known_identity"
            for entry in findings["early_native_bosses"]
        )
        if findings["policy"] != "generated_native_species_policy" or not needs_repair:
            continue
        try:
            candidate, receipt = prepare(
                row["configuration"], native, version=versions[row["route_key"]] + 1
            )
        except ValueError as error:
            manifest["blocked"].append(
                dict(route_key=row["route_key"], reason=str(error))
            )
            continue
        path = args.output_directory / (row["route_key"] + ".json")
        with path.open("x") as destination:
            json.dump(candidate, destination, indent=2)
            destination.write("\n")
        manifest["candidates"].append(
            dict(
                route_key=row["route_key"],
                source_version=row["policy_version"],
                source_sha256=receipt["original_sha256"],
                candidate_version=candidate["version"],
                candidate_sha256=receipt["candidate_sha256"],
                path=str(path.resolve()),
            )
        )
    with (args.output_directory / "manifest.json").open("x") as destination:
        json.dump(manifest, destination, indent=2)
        destination.write("\n")
    print(
        json.dumps(
            dict(candidates=len(manifest["candidates"]), blocked=manifest["blocked"]),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
