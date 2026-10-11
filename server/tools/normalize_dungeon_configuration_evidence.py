"""Version frozen dungeon evidence without changing JSON-normalized gameplay."""
import argparse
import hashlib
import json
from pathlib import Path


def normalize_configuration(configuration, *, version):
    """Rebuild owned frozen hashes, retaining exact persisted gameplay content."""
    from wakfu_server.dungeon_runtime_config import (
        prepare_configuration,
        canonical_hash,
    )

    source = json.loads(json.dumps(configuration))
    result = prepare_configuration(
        source["compiled_plan"],
        source["topology"],
        source["route"],
        version=version,
        provenance=source["provenance"],
    )
    for field in ("compiled_plan", "topology", "route", "level_policy"):
        if result[field] != source[field]:
            raise ValueError("Evidence normalization changes gameplay: " + field)
    persisted = json.loads(json.dumps(result))
    for key, field in (
        ("plan", "compiled_plan"),
        ("topology", "topology"),
        ("route", "route"),
    ):
        if canonical_hash(persisted[field]) != persisted["evidence_hashes"][key]:
            raise ValueError("Normalized evidence does not survive persistence: " + key)
    if canonical_hash(result) != canonical_hash(persisted):
        raise ValueError("Normalized configuration canonical round-trip differs")
    return result


def main():
    from wakfu_server.dungeon_runtime_config import canonical_hash

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", type=int, default=15)
    parser.add_argument("--targets", type=int, nargs="+", default=[141, 136])
    args = parser.parse_args()
    output = Path(f".runtime/local/native-evidence-normalized-v{args.version}-20261010")
    output.mkdir(exist_ok=True)
    records = []
    for identity in args.targets:
        source = Path(
            f".runtime/local/hybrid-native-full-room-v7-20261010/native_dungeon_{identity}.json"
        )
        original = json.loads(source.read_text())
        config = normalize_configuration(original, version=args.version)
        target = output / source.name
        serialized = json.dumps(config, indent=2) + "\n"
        target.write_text(serialized)
        records.append(
            dict(
                key=f"native:{identity}",
                route=config["route"]["key"],
                path=str(target),
                status="offline_configuration_prepared",
                source_path=str(source),
                source_file_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                configuration_sha256=canonical_hash(config),
                configuration_canonical_sha256=canonical_hash(config),
                configuration_file_sha256=hashlib.sha256(
                    serialized.encode()
                ).hexdigest(),
                gameplay_semantics_unchanged=True,
                evidence_integrity_verified=True,
                source_only=True,
                rooms=len(config["compiled_plan"]["rooms"]),
            )
        )
    report = Path(
        f"docs/reports/dungeons/NATIVE-EVIDENCE-NORMALIZED-CANDIDATES-V{args.version}-20261010.json"
    )
    report.write_text(
        json.dumps(
            dict(
                scope="Source-only evidence normalization; persisted plan/topology/route/level policy identical; no gameplay or runtime changes",
                records=records,
            ),
            indent=2,
        )
        + "\n"
    )
    print(report)


if __name__ == "__main__":
    main()
