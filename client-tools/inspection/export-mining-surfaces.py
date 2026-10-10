#!/usr/bin/env python3
"""Export native suitable terrain, explicitly distinct from fixed mining spawns."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile


def eligibility(resources, grounds):
    minerals = [
        row
        for row in resources
        if any(
            action["profession_id"] == 73
            for stage in row["stage_definitions"]
            for action in stage["actions"]
        )
    ]
    result = {}
    for ground in grounds:
        allowed = [
            row["resource_reference"]
            for row in minerals
            if ground["resources"].get(
                str(row["resource_reference"]),
                ground["families"].get(str(row["family_id"]), 0),
            )
            > 0
        ]
        if allowed:
            result[str(ground["ground_id"])] = sorted(allowed)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--maps", nargs="*", default=[])
    parser.add_argument("--navigation-dir", type=Path)
    parser.add_argument("--metadata-output", type=Path)
    args = parser.parse_args()
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    root = Path(__file__).resolve().parents[2]
    resources = native_catalog.load(DATA_ROOT / "plant-resources.json")
    grounds = native_catalog.load(DATA_ROOT / "planting-grounds.json")
    java_home = os.environ.get("JAVA_HOME")
    if not java_home:
        raise SystemExit("Set JAVA_HOME to JDK21 or later")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.metadata_output:
        minerals = [
            row
            for row in resources
            if any(
                action["profession_id"] == 73
                for stage in row["stage_definitions"]
                for action in stage["actions"]
            )
        ]
        args.metadata_output.write_text(
            json.dumps(
                dict(
                    schema_version=1,
                    evidence_kind="native_mineral_metadata_not_spawn",
                    mineral_count=len(minerals),
                    minerals=minerals,
                ),
                indent=2,
            )
            + "\n"
        )
    with tempfile.TemporaryDirectory(prefix="wakemu-mining-inspection-") as folder:
        directory = Path(folder)
        source = directory / "eligibility.json"
        source.write_text(json.dumps(eligibility(resources, grounds)))
        subprocess.run(
            [
                str(Path(java_home) / "bin/javac"),
                "-proc:none",
                "-cp",
                str(root / "client/lib/*"),
                "-d",
                folder,
                str(root / "client-tools/inspection/ExportMiningSurfaces.java"),
                str(root / "client-tools/inspection/ExportMiningNavigation.java"),
            ],
            check=True,
        )
        subprocess.run(
            [
                str(Path(java_home) / "bin/java"),
                "-Djava.awt.headless=true",
                "-cp",
                folder + ":" + str(root / "client/lib/*"),
                "ExportMiningSurfaces",
                str(root / "client"),
                str(source),
                str(args.output.resolve()),
                *args.maps,
            ],
            check=True,
        )
        if args.navigation_dir:
            args.navigation_dir.mkdir(parents=True, exist_ok=True)
            evidence = json.loads(args.output.read_text())
            maps = sorted({row["map_id"] for row in evidence["candidate_surfaces"]})
            manifest = []
            import hashlib

            for map_id in maps:
                output = args.navigation_dir / f"{map_id}.json"
                result = subprocess.run(
                    [
                        str(Path(java_home) / "bin/java"),
                        "-Xmx1g",
                        "-Djava.awt.headless=true",
                        "-cp",
                        folder + ":" + str(root / "client/lib/*"),
                        "ExportMiningNavigation",
                        str(map_id),
                        str(output.resolve()),
                        str(args.output.resolve()),
                    ],
                    capture_output=True,
                    text=True,
                )
                row = dict(map_id=map_id, returncode=result.returncode)
                if result.returncode:
                    row["error"] = result.stderr
                else:
                    data = json.loads(output.read_text())
                    row.update(
                        file=str(output),
                        sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                        cells=len(data["cells"]),
                        edges=len(data["edges"]),
                        resource_targets=len(data["resource_approaches"]),
                        usable_targets=sum(
                            bool(item["approaches"])
                            for item in data["resource_approaches"]
                        ),
                        decode_errors=data["decode_errors"],
                    )
                manifest.append(row)
                (args.navigation_dir / "index.json").write_text(
                    json.dumps(
                        dict(
                            schema_version=1,
                            complete=len(manifest) == len(maps),
                            all_targets_usable=all(
                                row.get("returncode") == 0
                                and row.get("usable_targets")
                                == row.get("resource_targets")
                                for row in manifest
                            ),
                            maps=manifest,
                        ),
                        indent=2,
                    )
                    + "\n"
                )
                print(
                    f"Navigation map {map_id}: status {result.returncode}", flush=True
                )


if __name__ == "__main__":
    main()
