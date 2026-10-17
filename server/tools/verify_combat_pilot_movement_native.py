"""Verify exact server movement bytes through original native endpoint/FIFO code.

Inputs are records containing id, opcode13624, payload_hex and explicit initial
position. Each record runs in a separate original-JAR process with a detached
actor and headless visual/timing fixtures. Historical evidence is never edited.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from verify_combat_reconstruction_native import ROOT, digest


def verify(java_home, inputs, output):
    java_home, output = Path(java_home).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Use a new private native movement evidence directory")
    records = json.loads(Path(inputs).read_text())
    if not isinstance(records, list) or not 1 <= len(records) <= 256:
        raise ValueError("Require bounded explicit movement input records")
    output.mkdir(parents=True, mode=0o700)
    sources = [
        ROOT / "sniffer/java/VerifyCombatReconstructionSlice.java",
        ROOT / "sniffer/java/VerifyPilotMovementQueue.java",
    ]
    source_hashes = {str(path.relative_to(ROOT)): digest(path) for path in sources}
    jars = {
        str(path.relative_to(ROOT)): digest(path)
        for path in sorted((ROOT / "client/lib").glob("*.jar"))
    }
    environment = {
        key: value
        for key, value in os.environ.items()
        if key
        not in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "CLASSPATH")
    }
    java, javac = java_home / "bin/java", java_home / "bin/javac"
    results = []
    with tempfile.TemporaryDirectory(prefix="pilot-movement-native-") as classes:
        compile_command = [
            str(javac),
            "-proc:none",
            "--release",
            "21",
            "-cp",
            str(ROOT / "client/lib/*"),
            "-d",
            classes,
            *map(str, sources),
        ]
        compiled = subprocess.run(
            compile_command,
            cwd=output,
            env=environment,
            capture_output=True,
            timeout=60,
            check=False,
        )
        (output / "compile.stdout.log").write_bytes(compiled.stdout)
        (output / "compile.stderr.log").write_bytes(compiled.stderr)
        for index, record in enumerate(records):
            if (
                not isinstance(record, dict)
                or record.get("opcode") != 13624
                or not isinstance(record.get("id"), str)
            ):
                raise ValueError("Explicit movement case identity/opcode required")
            cell = record.get("initial_position")
            if (
                not isinstance(cell, list)
                or len(cell) != 3
                or not all(type(value) is int for value in cell)
            ):
                raise ValueError("Explicit initial actor position required")
            payload = bytes.fromhex(record["payload_hex"])
            if not 1 <= len(payload) <= 1024 * 1024:
                raise ValueError("Movement payload outside bounds")
            name = f"movement-{index}"
            packet = output / (name + ".bin")
            packet.write_bytes(payload)
            observation = output / (name + "-observations.json")
            command = [
                str(java),
                "-cp",
                classes + ":" + str(ROOT / "client/lib/*"),
                "VerifyPilotMovementQueue",
                str(packet),
                str(observation),
                *map(str, cell),
            ]
            executed = None
            if compiled.returncode == 0:
                try:
                    executed = subprocess.run(
                        command,
                        cwd=output,
                        env=environment,
                        capture_output=True,
                        timeout=15,
                        check=False,
                    )
                    (output / (name + ".stdout.log")).write_bytes(executed.stdout)
                    (output / (name + ".stderr.log")).write_bytes(executed.stderr)
                except subprocess.TimeoutExpired as error:
                    (output / (name + ".stdout.log")).write_bytes(error.stdout or b"")
                    (output / (name + ".stderr.log")).write_bytes(error.stderr or b"")
            native = json.loads(observation.read_text()) if observation.exists() else {}
            results.append(
                dict(
                    id=record["id"],
                    opcode=13624,
                    payload_sha256=digest(packet),
                    initial_position=cell,
                    returncode=executed.returncode if executed else None,
                    native=native,
                    observations_sha256=digest(observation)
                    if observation.exists()
                    else None,
                    complete=bool(
                        executed
                        and executed.returncode == 0
                        and native.get("completed_normally") is True
                        and native.get("queue_drained") is True
                    ),
                )
            )
        class_files = {
            str(path.relative_to(classes)): digest(path)
            for path in sorted(Path(classes).rglob("*.class"))
        }
    stable = source_hashes == {
        str(path.relative_to(ROOT)): digest(path) for path in sources
    } and jars == {
        str(path.relative_to(ROOT)): digest(path)
        for path in sorted((ROOT / "client/lib").glob("*.jar"))
    }
    result = dict(
        schema="wakemu-pilot-movement-native-proof-v1",
        source=source_hashes,
        classpath=jars,
        java_sha256=digest(java),
        javac_sha256=digest(javac),
        runner_sha256=digest(__file__),
        input_sha256=digest(inputs),
        class_files=class_files,
        compile_returncode=compiled.returncode,
        instrumentation="none",
        source_stable=stable,
        cases=results,
        complete=stable and all(row["complete"] for row in results),
        scope="original endpoint and timer/FIFO completion under detached headless fixture; no rendering",
    )
    (output / "proof.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java-home", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.java_home, args.inputs, args.output)
    print(json.dumps(dict(complete=result["complete"], cases=len(result["cases"]))))
    return 0 if result["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
