#!/usr/bin/env python3
"""Run the AI selector inside the existing local World container."""
import argparse
from pathlib import Path
import subprocess
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--use", choices=("current", "jondo"))
    mode.add_argument("--status", action="store_true")
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args(argv)
    repository = next(
        (p for p in Path(__file__).resolve().parents if (p / "compose.yaml").is_file()),
        None,
    )
    if repository is None:
        parser.error("Cannot locate the local Compose project")
    command = [
        "docker",
        "compose",
        "--project-directory",
        str(repository),
        "-f",
        str(repository / "compose.yaml"),
        "exec",
        "-T",
        "world",
        "python3",
        "/app/ai-service/scripts/ai_backend.py",
        "--config",
        "/data/ai-backend.json",
    ]
    if args.status:
        command.append("--status")
    else:
        command.extend(
            [
                "--use",
                args.use,
                "--health-host",
                "ai" if args.use == "current" else "ai-jondo",
                "--timeout",
                str(args.timeout),
            ]
        )
    try:
        return subprocess.run(command, cwd=repository, check=False).returncode
    except OSError as error:
        print("AI backend unchanged: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
