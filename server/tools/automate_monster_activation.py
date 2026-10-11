"""Run the fenced native NPC activation pipeline for any covered level cohort.

Exports and previews are read-only. Publication is an explicit final phase;
this command never activates a release or restarts a running server.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def pipeline_commands(args):
    """Use one immutable candidate and receipt through every approval gate."""
    from psycopg.conninfo import conninfo_to_dict

    connection_options = conninfo_to_dict(args.dsn)
    if "password" in connection_options:
        raise ValueError(
            "DSN must not contain an inline password; use the password file"
        )
    work = args.output.resolve()
    if (ROOT / ".runtime").resolve() not in work.parents:
        raise ValueError("Activation work must remain beneath .runtime")
    prepare = [
        sys.executable,
        str(ROOT / "server/tools/prepare_monster_spell_activation.py"),
        "--coverage",
        str(args.coverage),
        "--bundle",
        str(args.bundle),
        "--output",
        str(work / "candidate"),
        "--dsn",
        args.dsn,
        "--password-file",
        str(args.password_file),
        "--registry",
        str(args.registry),
        "--setters",
        str(args.setters),
        "--max-level",
        str(args.max_level),
    ]
    for reference in args.only_ref or []:
        prepare.extend(("--only-ref", str(reference)))
    validator = [
        sys.executable,
        str(ROOT / "server/tools/validate_monster_spell_activation.py"),
        "--candidate",
        str(work / "candidate"),
        "--native-monsters",
        str(args.bundle / "monsters.json.gz"),
    ]
    recovery_options = (
        ["--recovery-search"] if getattr(args, "recovery_search", False) else []
    )
    return [
        ("prepare", prepare),
        (
            "previews",
            validator
            + recovery_options
            + ["--output", str(work / "previews.json"), "--skip-class-tests"],
        ),
        (
            "commit_and_classes",
            validator
            + [
                "--output",
                str(work / "validation.json"),
                "--extend-results",
                str(work / "previews.json"),
                "--class-tests-only",
            ],
        ),
        (
            "finalize",
            [
                sys.executable,
                str(ROOT / "server/tools/finalize_monster_spell_activation.py"),
                str(work / "candidate"),
                str(work / "validation.json"),
                str(work / "validated"),
            ],
        ),
        (
            "stage",
            [
                sys.executable,
                str(ROOT / "server/tools/stage_monster_spell_activation.py"),
                str(work / "validated"),
                "--dsn",
                args.dsn,
                "--password-file",
                str(args.password_file),
            ]
            + (["--stage"] if args.stage else []),
        ),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "coverage",
        "bundle",
        "output",
        "password-file",
        "registry",
        "setters",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument(
        "--dsn", required=True, help="PostgreSQL DSN without an inline password"
    )
    parser.add_argument("--max-level", type=int, default=9)
    parser.add_argument("--only-ref", type=int, action="append")
    parser.add_argument(
        "--recovery-search",
        action="store_true",
        help="Search bounded native prerequisites and nonoverlapping target witnesses",
    )
    parser.add_argument(
        "--stage",
        action="store_true",
        help="Publish an inactive fully validated release",
    )
    args = parser.parse_args()
    commands = pipeline_commands(args)
    args.output.mkdir(parents=True, exist_ok=False)
    environment = dict(os.environ)
    from psycopg.conninfo import make_conninfo

    environment["WAKFU_DATABASE_URL"] = make_conninfo(
        args.dsn, password=args.password_file.read_text().strip()
    )
    receipt = {
        "schema": "native-npc-activation-pipeline-v1",
        "activated": False,
        "phases": [],
    }
    for phase, command in commands:
        with (args.output / (phase + ".log")).open("w") as stream:
            outcome = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
            )
        receipt["phases"].append({"phase": phase, "returncode": outcome.returncode})
        (args.output / "pipeline.json").write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt["phases"][-1]), flush=True)
        if outcome.returncode:
            raise SystemExit(outcome.returncode)


if __name__ == "__main__":
    main()
