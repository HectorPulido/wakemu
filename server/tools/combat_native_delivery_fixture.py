#!/usr/bin/env python3
"""Export a private native fixture and exercise the real incident CLI.

This creates a synthetic encounter with actual class/runtime/snapshot/Registry
producers. It is fixture evidence, not a captured live client incident. No client
or gameplay services are started. Capture/record needs the published catalogs;
replay subprocesses deliberately receive no database/cache credentials.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

SERVER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER))
sys.path.insert(0, str(SERVER / "tests"))
BACKEND_ENV = (
    "WAKFU_DATABASE_URL",
    "WAKFU_DATABASE_PASSWORD_FILE",
    "WAKFU_REDIS_URL",
    "WAKFU_COMBAT_INCIDENT_DIR",
    "WAKFU_COMBAT_INCIDENT_MODE",
)


def _private_write(path, raw):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)


def _json_write(path, value):
    _private_write(path, (json.dumps(value, allow_nan=False, indent=2) + "\n").encode())


def _run_cli(name, arguments, output, *, offline=False):
    environment = dict(os.environ)
    if offline:
        for key in BACKEND_ENV:
            environment.pop(key, None)
    command = [
        sys.executable,
        str(SERVER / "tools" / "combat_reproduce.py"),
        *arguments,
    ]
    process = subprocess.run(
        command, env=environment, cwd=SERVER.parent, capture_output=True, timeout=300
    )
    _private_write(output / (name + ".stdout.json"), process.stdout)
    _private_write(output / (name + ".stderr.log"), process.stderr)
    try:
        summary = json.loads(process.stdout)
    except (ValueError, UnicodeDecodeError):
        summary = None
    return dict(
        command=shlex.join(command),
        exit_code=process.returncode,
        backend_environment_removed=offline,
        summary=summary,
        stdout_file=name + ".stdout.json",
        stderr_file=name + ".stderr.log",
    )


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


def export_fixture(output, *, verify_cli=False):
    """Run the already validated native integration fixture without a test runner."""
    from test_combat_shared_delivery_incident_replay import (
        SharedDeliveryIncidentReplayTests,
    )
    from wakfu_server.combat_incident_replay import write_incident, LIVE_RECIPE
    from wakfu_server.combat_delivery_reproduction import verify_delivery_evidence
    from wakfu_server.combat_reproduction_state import decode_state, encode_state

    output = Path(output).resolve()
    if output.exists():
        raise ValueError("Use a new private output directory")
    output.mkdir(parents=True, mode=0o700)
    (
        receipt,
        sidecar,
        actual_after,
        replay,
    ) = SharedDeliveryIncidentReplayTests().capture_and_replay()
    qualification = verify_delivery_evidence(
        receipt, [sidecar], expected_after=actual_after, replay_outcome=replay
    )
    _require(
        qualification["shared_delivery_qualified"],
        "Native fixture delivery did not qualify",
    )
    _require(
        not qualification["client_reconstruction_verified"],
        "Unexpected client reconstruction claim",
    )
    write_incident(output / "request.json", receipt)
    _json_write(output / "delivery-sidecar.json", sidecar)
    _json_write(
        output / "capture-summary.json", dict(replay=replay, delivery=qualification)
    )

    tampered = copy.deepcopy(sidecar)
    attempts = decode_state(tampered["attempts"])
    batch = attempts[0]["batches"][0]
    opcode, payload = batch["packets"][0]
    batch["packets"] = ((opcode, payload + b"tampered-delivery"), *batch["packets"][1:])
    tampered["attempts"] = encode_state(attempts)
    _json_write(output / "tampered-sidecar.json", tampered)
    cli = []
    manifest = dict(
        schema="wakemu-native-delivery-cli-fixture-v1",
        origin="synthetic-native-existing-participant-snapshot-and-class-action-fixture",
        fixture="server/tests/test_combat_shared_delivery_incident_replay.py",
        source_sha256=receipt["identity"]["source"]["sha256"],
        dispatcher_sha256=receipt["identity"]["dispatcher_sha256"],
        catalog_revision=receipt["identity"]["catalog"]["revision"],
        provider_recipe=LIVE_RECIPE,
        request="request.json",
        sidecar="delivery-sidecar.json",
        tampered_sidecar="tampered-sidecar.json",
        client_reconstruction_verified=False,
        cli=cli,
    )
    if verify_cli:
        bundle = output / "bundle"
        common = ["--provider-recipe", LIVE_RECIPE]
        recorded = _run_cli(
            "record",
            [
                "record-incident",
                "--request",
                str(output / "request.json"),
                "--output",
                str(bundle),
                *common,
            ],
            output,
        )
        cli.append(dict(stage="record", **recorded))
        _require(
            recorded["exit_code"] == 0
            and type(recorded["summary"]) is dict
            and recorded["summary"].get("operation_matches") is True,
            "Strict record-incident failed; inspect its private stdout/stderr",
        )
        arguments = [
            "replay-incident",
            "--bundle",
            str(bundle),
            *common,
            "--delivery-sidecar",
            str(output / "delivery-sidecar.json"),
        ]
        repeated = []
        for index in (1, 2):
            run = _run_cli("replay-" + str(index), arguments, output, offline=True)
            cli.append(dict(stage="replay-" + str(index), **run))
            summary = run["summary"]
            _require(
                run["exit_code"] == 0 and type(summary) is dict,
                "Offline replay-incident failed; inspect its private stdout/stderr",
            )
            _require(
                all(
                    summary.get(field) is True
                    for field in (
                        "operation_matches",
                        "mailbox_matches",
                        "source_matches",
                        "dispatcher_matches",
                        "catalog_matches",
                        "bootstrap_qualified",
                        "dispatch_qualified",
                        "shared_delivery_qualified",
                    )
                ),
                "Offline replay did not preserve strict identity and complete delivery qualification",
            )
            _require(
                summary["delivery"]["client_reconstruction_verified"] is False
                and summary["delivery"]["client_receipt_confirmed"] is False,
                "Offline replay made an unsupported client claim",
            )
            repeated.append(summary)
        _require(
            repeated[0] == repeated[1], "Repeated fresh-process replay summaries differ"
        )
        rejected = _run_cli(
            "tampered",
            [
                "replay-incident",
                "--bundle",
                str(bundle),
                *common,
                "--delivery-sidecar",
                str(output / "tampered-sidecar.json"),
            ],
            output,
            offline=True,
        )
        cli.append(dict(stage="tampered", **rejected))
        _require(
            rejected["exit_code"] == 1
            and type(rejected["summary"]) is dict
            and rejected["summary"].get("operation_matches") is True
            and rejected["summary"].get("shared_delivery_qualified") is False
            and rejected["summary"]["delivery"]["routing_matches"] is False,
            "Tampered sidecar did not receive the expected explicit rejection",
        )
        manifest["cli_verified"] = True
        manifest["repeated_replay_equal"] = True
        manifest["tampered_sidecar_rejected"] = True
    else:
        manifest["cli_verified"] = False
    _json_write(output / "manifest.json", manifest)
    return dict(
        output=str(output),
        manifest="manifest.json",
        source_sha256=manifest["source_sha256"],
        catalog_revision=manifest["catalog_revision"],
        cli_verified=manifest["cli_verified"],
        shared_delivery_qualified=True,
        client_reconstruction_verified=False,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--verify-cli",
        action="store_true",
        help="Record a catalog bundle, replay twice without backend credentials, and reject tampered bytes",
    )
    args = parser.parse_args(argv)
    print(json.dumps(export_fixture(args.output, verify_cli=args.verify_cli), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
