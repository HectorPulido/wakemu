#!/usr/bin/env python3
"""Compare scoped summon creation values against original native ffx samples."""
import argparse
import hashlib
import json
from pathlib import Path

from import_class_summon_dependencies import entries, select
from wakfu_server.combat_actor_snapshot import native_npc_creation_values


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    catalog_path = root / "server/protocol/native-actor-characteristics.json"
    implementation = root / "server/wakfu_server/combat/combat_actor_snapshot.py"
    sources = {
        str(path): digest(path) for path in (args.native, catalog_path, implementation)
    }
    native = json.loads(args.native.read_text())
    catalog = dict(
        characteristics=dict(entries(catalog_path, "characteristics")),
        npc_profiles=select(catalog_path, "npc_profiles", set(native["profiles"])),
    )
    mismatches = []
    checked = 0
    for reference, profile in native["profiles"].items():
        for level, expected in profile["characteristics_at_levels"].items():
            actual = native_npc_creation_values(
                int(reference), int(level), catalog=catalog
            )
            if set(actual) != {int(identity) for identity in expected}:
                raise ValueError("Incomplete native characteristic sample")
            for identity, value in actual.items():
                checked += 1
                if value != expected[str(identity)]:
                    mismatches.append(
                        dict(
                            profile=int(reference),
                            level=int(level),
                            characteristic=identity,
                            native=expected[str(identity)],
                            actual=value,
                        )
                    )
    stable = sources == {
        str(path): digest(path) for path in (args.native, catalog_path, implementation)
    }
    report = dict(
        scope="39 static class-referenced profiles, native ffx creation at0/1/20/200/245; no captured-profile claim",
        characteristic_snapshots_checked=checked,
        mismatches=mismatches,
        sources_stable=stable,
        source_sha256=sources,
    )
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            dict(checked=checked, mismatches=len(mismatches), sources_stable=stable)
        )
    )
    if mismatches or not stable:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
