"""Verify actual owned Pandawa carry/throw logical delivery with original Java."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from verify_combat_reconstruction_native import ROOT, digest


def verify(java_home, reports, output):
    java_home, reports, output = (
        Path(java_home).resolve(),
        Path(reports).resolve(),
        Path(output).resolve(),
    )
    if output.exists():
        raise ValueError("Preserve native carry evidence in a new output directory")
    envelope = json.loads(reports.read_text())
    data = envelope.get("evidence", envelope)
    if data.get("schema") != "wakemu-pilot-pandawa-delivery-v1":
        raise ValueError("Actual owned Pandawa old/new delivery report required")
    output.mkdir(parents=True, mode=0o700)
    sources = [
        ROOT / "sniffer/java" / name
        for name in (
            "VerifyCombatReconstructionSlice.java",
            "VerifyPilotMovementQueue.java",
            "VerifyPilotDisplacementQueue.java",
            "VerifyPilotCarryQueue.java",
        )
    ]
    hashes = {str(path.relative_to(ROOT)): digest(path) for path in sources}
    jars = {
        str(path.relative_to(ROOT)): digest(path)
        for path in sorted((ROOT / "client/lib").glob("*.jar"))
    }
    bdata = {
        str(path.relative_to(ROOT)): digest(path)
        for path in sorted((ROOT / "client/contents/bdata").glob("*.jar"))
    }
    environment = {
        key: value
        for key, value in os.environ.items()
        if key
        not in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "CLASSPATH")
    }
    java, javac = java_home / "bin/java", java_home / "bin/javac"
    results = []
    with tempfile.TemporaryDirectory(prefix="pilot-carry-native-") as classes:
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
        for branch in ("legacy", "pilot"):
            stages = data["stages"][branch]
            if len(stages) != 2 or [row["spell"] for row in stages] != [6847, 6848]:
                raise ValueError("Exact actual owned carry then throw stages required")
            packet_files = []
            for index, stage in enumerate(stages):
                if len(stage["packets"]) != 1 or stage["packets"][0]["opcode"] != 12613:
                    raise ValueError(
                        "One actual native carry/throw application per stage required"
                    )
                path = output / f"{branch}-{index}.bin"
                path.write_bytes(bytes.fromhex(stage["packets"][0]["payload_hex"]))
                packet_files.append(path)
            initial = stages[0]["before"]["positions"]
            observation = output / f"{branch}-observations.json"
            command = [
                str(java),
                "-cp",
                classes + ":" + str(ROOT / "client/lib/*"),
                "VerifyPilotCarryQueue",
                *map(str, packet_files),
                str(observation),
                "7",
                "-7",
                *map(str, initial["7"]),
                *map(str, initial["-7"]),
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
                (output / f"{branch}.stdout.log").write_bytes(stdout)
                (output / f"{branch}.stderr.log").write_bytes(stderr)
            native = json.loads(observation.read_text()) if observation.exists() else {}
            expected = [
                {
                    boundary: {
                        component: {
                            actor: stage[boundary][component][actor]
                            for actor in ("7", "-7")
                        }
                        for component in ("positions", "relations")
                    }
                    for boundary in ("before", "after")
                }
                for stage in stages
            ]
            native_stages = native.get("stages", [])
            matched = len(native_stages) == 2 and all(
                all(
                    native_stage[boundary] == expected_stage[boundary]
                    for boundary in ("before", "after")
                )
                for native_stage, expected_stage in zip(native_stages, expected)
            )
            results.append(
                dict(
                    id=branch,
                    packets_sha256=[digest(path) for path in packet_files],
                    native=native,
                    expected=expected,
                    positions_and_relations_match=matched,
                    returncode=execution.returncode if execution else None,
                    observations_sha256=digest(observation)
                    if observation.exists()
                    else None,
                    complete=bool(
                        execution
                        and execution.returncode == 0
                        and native.get("completed_normally") is True
                        and matched
                    ),
                )
            )
        class_files = {
            str(path.relative_to(classes)): digest(path)
            for path in sorted(Path(classes).rglob("*.class"))
        }
    stable = (
        hashes == {str(path.relative_to(ROOT)): digest(path) for path in sources}
        and jars
        == {
            str(path.relative_to(ROOT)): digest(path)
            for path in sorted((ROOT / "client/lib").glob("*.jar"))
        }
        and bdata
        == {
            str(path.relative_to(ROOT)): digest(path)
            for path in sorted((ROOT / "client/contents/bdata").glob("*.jar"))
        }
    )
    result = dict(
        schema="wakemu-pilot-carry-native-proof-v1",
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
        input_provenance=envelope.get("source_hashes", {}),
        class_files=class_files,
        cases=results,
        complete=stable and all(row["complete"] for row in results),
        scope="original native carry/throw definitions, eWB/eZE, eGj ownership and aVo/aER callbacks; renderer parenting/script skipped",
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
