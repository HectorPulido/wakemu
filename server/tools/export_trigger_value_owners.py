#!/usr/bin/env python3
"""Export original Qe.a owners, including overrides inherited by eVi runners."""
import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "server/protocol/native-trigger-value-owners.json",
    )
    args = parser.parse_args()
    source = ROOT / "server/protocol/native-runner-corpse-policy.json"
    rows = json.loads(source.read_text())["effects"]
    classes = sorted({row["runner"] for row in rows.values()})
    compiled = ROOT / ".runtime/local"
    compiled.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "javac",
            "-proc:none",
            "-cp",
            str(ROOT / "client/lib/*"),
            "-d",
            str(compiled),
            str(ROOT / "sniffer/java/ProbeNativeTriggerValue430.java"),
        ],
        check=True,
    )
    result = subprocess.run(
        [
            "java",
            "-cp",
            str(compiled) + os.pathsep + str(ROOT / "client/lib/*"),
            "ProbeNativeTriggerValue430",
            *classes,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    owners = dict(line.split() for line in result.stdout.splitlines())
    if set(owners) != set(classes):
        raise ValueError("Incomplete native source-runner method export")
    exported = {
        "source": "Installed Qe.a(int,float,boolean); reflected declaring owner",
        "effects": {
            key: {"runner": row["runner"], "owner": owners[row["runner"]]}
            for key, row in rows.items()
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(exported, indent=2) + "\n")
    print(
        json.dumps(
            {
                "prototypes": len(rows),
                "runner_classes": len(classes),
                "output": str(args.output),
            }
        )
    )


if __name__ == "__main__":
    main()
