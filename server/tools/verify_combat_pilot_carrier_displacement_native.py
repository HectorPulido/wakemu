"""Original native displacement of actual captured registered carry partners."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from verify_combat_reconstruction_native import ROOT, digest
from wakfu_server.combat.combat_pilot_carrier_displacement_reconstruction import (
    modeled_carrier_displacement,
    normalize_view,
)


def verify(java_home, reports, output):
    java_home, reports, output = map(
        lambda path: Path(path).resolve(), (java_home, reports, output)
    )
    if output.exists():
        raise ValueError("Preserve all previous evidence; use a new output directory")
    data = json.loads(reports.read_text())
    if data.get(
        "schema"
    ) != "wakemu-pilot-native-carrier-displacement-inputs-v1" or not data.get(
        "records"
    ):
        raise ValueError("Actual native carrier handler entry records required")
    output.mkdir(parents=True, mode=0o700)
    sources = [
        ROOT / "sniffer/java" / name
        for name in (
            "VerifyCombatReconstructionSlice.java",
            "VerifyPilotMovementQueue.java",
            "VerifyPilotDisplacementQueue.java",
            "VerifyPilotCarryQueue.java",
            "VerifyPilotCarrierDisplacementQueue.java",
        )
    ]
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in sources}

    def inventory(directory):
        return {
            str(path.relative_to(ROOT)): digest(path)
            for path in sorted(directory.glob("*.jar"))
        }

    jars, bdata = inventory(ROOT / "client/lib"), inventory(
        ROOT / "client/contents/bdata"
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if key
        not in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "CLASSPATH")
    }
    java, javac = java_home / "bin/java", java_home / "bin/javac"
    results = []
    with tempfile.TemporaryDirectory(prefix="pilot-carrier-native-") as classes:
        compilation = subprocess.run(
            [
                str(javac),
                "-proc:none",
                "--release",
                "21",
                "-cp",
                str(ROOT / "client/lib/*"),
                "-d",
                classes,
                *map(str, sources),
            ],
            cwd=output,
            env=environment,
            capture_output=True,
            timeout=60,
            check=False,
        )
        (output / "compile.stdout.log").write_bytes(compilation.stdout)
        (output / "compile.stderr.log").write_bytes(compilation.stderr)
        for index, record in enumerate(data["records"]):
            positions, relations = normalize_view(record["before"])
            normalize_view(record["after"])
            if not any(row["carried"] is not None for row in relations.values()):
                raise ValueError("Actual captured registered carrier pair required")
            journal = record["packets"]
            if len(journal) != 1 or journal[0]["opcode"] != 12613:
                raise ValueError("One exact actual displacement application required")
            payload = bytes.fromhex(
                journal[0].get("payload", journal[0].get("payload_hex", ""))
            )
            decoded, modeled = modeled_carrier_displacement(
                (12613, payload), record["before"]
            )
            packet = output / f"case-{index}.bin"
            packet.write_bytes(payload)
            actors = output / f"case-{index}-actors.tsv"
            actors.write_text(
                "".join(
                    "\t".join(
                        map(
                            str,
                            (
                                identity,
                                *cell,
                                relations[identity]["carried"]
                                if relations[identity]["carried"] is not None
                                else "null",
                            ),
                        )
                    )
                    + "\n"
                    for identity, cell in positions.items()
                )
            )
            observation = output / f"case-{index}-observations.json"
            command = [
                str(java),
                "-cp",
                classes + ":" + str(ROOT / "client/lib/*"),
                "VerifyPilotCarrierDisplacementQueue",
                str(packet),
                str(observation),
                str(actors),
                str(ROOT / "client/contents/bdata"),
            ]
            execution = None
            if compilation.returncode == 0:
                try:
                    execution = subprocess.run(
                        command,
                        cwd=output,
                        env=environment,
                        capture_output=True,
                        timeout=15,
                        check=False,
                    )
                    stdout, stderr = execution.stdout, execution.stderr
                except subprocess.TimeoutExpired as error:
                    stdout, stderr = error.stdout or b"", error.stderr or b""
                (output / f"case-{index}.stdout.log").write_bytes(stdout)
                (output / f"case-{index}.stderr.log").write_bytes(stderr)
            native = json.loads(observation.read_text()) if observation.exists() else {}
            expected_positions, expected_relations = normalize_view(record["after"])
            expected = dict(
                positions={str(k): list(v) for k, v in expected_positions.items()},
                relations={str(k): v for k, v in expected_relations.items()},
            )
            initial = dict(
                positions={str(k): list(v) for k, v in positions.items()},
                relations={str(k): v for k, v in relations.items()},
            )
            identity_match = all(
                native.get(key) == decoded["effect"][effect_key]
                for key, effect_key in (
                    ("family", "family"),
                    ("generic_effect", "definition"),
                    ("uid", "uid"),
                    ("caster", "caster"),
                    ("target", "target"),
                )
            )
            complete = bool(
                execution
                and execution.returncode == 0
                and native.get("completed_normally") is True
                and native.get("before") == initial
                and native.get("after") == modeled == expected
                and identity_match
                and native.get("action_id") == decoded["action"]
                and native.get("native_completed_action_ids") == [decoded["action"]]
                and native.get("queue_drained") is True
            )
            results.append(
                dict(
                    id=record["id"],
                    opcode=12613,
                    payload_sha256=digest(packet),
                    recipient=journal[0]["recipient"],
                    initial=initial,
                    expected=expected,
                    modeled=modeled,
                    native=native,
                    returncode=execution.returncode if execution else None,
                    observations_sha256=digest(observation)
                    if observation.exists()
                    else None,
                    complete=complete,
                )
            )
        class_files = {
            str(path.relative_to(classes)): digest(path)
            for path in sorted(Path(classes).rglob("*.class"))
        }
    stable = (
        hashes == {str(path.relative_to(ROOT)): digest(path) for path in sources}
        and jars == inventory(ROOT / "client/lib")
        and bdata == inventory(ROOT / "client/contents/bdata")
    )
    result = dict(
        schema="wakemu-pilot-carrier-displacement-native-proof-v1",
        source=hashes,
        classpath=jars,
        bdata=bdata,
        source_stable=stable,
        instrumentation="none",
        compile_returncode=compilation.returncode,
        java_sha256=digest(java),
        javac_sha256=digest(javac),
        runner_sha256=digest(__file__),
        input_sha256=digest(reports),
        input_provenance=data.get("source_hashes", {}),
        class_files=class_files,
        cases=results,
        complete=stable and bool(results) and all(row["complete"] for row in results),
        scope="actual native handler snapshots; original eGj carry setup and implicit partner displacement callbacks; no rendering",
    )
    (output / "proof.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java-home", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.java_home, args.reports, args.output)
    print(json.dumps(dict(complete=result["complete"], cases=len(result["cases"]))))
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
