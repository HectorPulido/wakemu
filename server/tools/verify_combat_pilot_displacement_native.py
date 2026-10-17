"""Native logical recipient endpoint evidence for actual old/new displacement reports."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from verify_combat_reconstruction_native import ROOT, digest


def positions(state):
    """Read only explicit actor positions from a reproduction graph, no imports."""
    nodes = state["nodes"]
    root = dict(nodes[state["root"]["ref"]]["items"])
    actors = nodes[root["actors"]["ref"]]
    result = {}
    for identity, reference in actors["items"]:
        actor = nodes[reference["ref"]]
        if actor["kind"] != "object" or actor["type"] != "Actor":
            raise ValueError("Explicit captured Actor required")
        attributes = dict(nodes[actor["attrs"]["ref"]]["items"])
        cell = nodes[attributes["position"]["ref"]]["items"]
        if len(cell) != 3 or not all(type(part) is int for part in cell):
            raise ValueError("Explicit captured actor coordinates required")
        result[str(identity)] = cell
    return result


def verify(java_home, reports, output):
    from wakfu_server.combat_protocol_reconstruction import decode_packet

    java_home, output = Path(java_home).resolve(), Path(output).resolve()
    reports = Path(reports).resolve()
    if output.exists():
        raise ValueError("Use a new private native displacement evidence directory")
    data = json.loads(reports.read_text())
    if data.get("schema") not in (
        "wakemu-native-displacement-actual-v1",
        "wakemu-pilot-native-displacement-inputs-v1",
    ):
        raise ValueError("Actual displacement differential export required")
    output.mkdir(parents=True, mode=0o700)
    sources = [
        ROOT / "sniffer/java/VerifyCombatReconstructionSlice.java",
        ROOT / "sniffer/java/VerifyPilotMovementQueue.java",
        ROOT / "sniffer/java/VerifyPilotDisplacementQueue.java",
    ]
    source_hashes = {str(path.relative_to(ROOT)): digest(path) for path in sources}
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
    with tempfile.TemporaryDirectory(prefix="pilot-displacement-native-") as classes:
        compiled = subprocess.run(
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
        (output / "compile.stdout.log").write_bytes(compiled.stdout)
        (output / "compile.stderr.log").write_bytes(compiled.stderr)
        records = []
        if data["schema"] == "wakemu-native-displacement-actual-v1":
            for case in data["cases"]:
                report = case["observation"]
                for branch in ("legacy", "candidate"):
                    records.append(
                        dict(
                            id=report["case_id"] + "-" + branch,
                            before_positions=positions(report["before"]),
                            after_positions=positions(report[branch]["state"]),
                            packets=report[branch]["packets"],
                        )
                    )
        else:
            records = data["records"]
        for record in records:
            before = record["before_positions"]
            journal = record["packets"]
            if len(journal) != 1 or journal[0]["opcode"] != 12613:
                raise ValueError(
                    "One exact actual displacement packet per isolated case required"
                )
            payload = bytes.fromhex(journal[0]["payload"])
            decoded = decode_packet(12613, payload)
            effect = decoded["effect"]
            if effect["family"] not in (300, 301, 340, 422):
                raise ValueError("Displacement family outside current pilot proof")
            source, target = str(effect["caster"]), str(effect["target"])
            name = f"displacement-{len(results)}"
            packet = output / (name + ".bin")
            packet.write_bytes(payload)
            observation = output / (name + "-observations.json")
            command = [
                str(java),
                "-cp",
                classes + ":" + str(ROOT / "client/lib/*"),
                "VerifyPilotDisplacementQueue",
                str(packet),
                str(observation),
                *map(str, before[source]),
                *map(str, before[target]),
                str(ROOT / "client/contents/bdata"),
            ]
            execution = None
            if compiled.returncode == 0:
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
                (output / (name + ".stdout.log")).write_bytes(stdout)
                (output / (name + ".stderr.log")).write_bytes(stderr)
            native = json.loads(observation.read_text()) if observation.exists() else {}
            expected_all = record["after_positions"]
            expected = {source: expected_all[source], target: expected_all[target]}
            results.append(
                dict(
                    id=record["id"],
                    opcode=12613,
                    payload_sha256=digest(packet),
                    recipient=journal[0]["recipient"],
                    initial_positions={source: before[source], target: before[target]},
                    expected_positions=expected,
                    native=native,
                    observations_sha256=digest(observation)
                    if observation.exists()
                    else None,
                    returncode=execution.returncode if execution else None,
                    complete=bool(
                        execution
                        and execution.returncode == 0
                        and native.get("completed_normally") is True
                        and native.get("executed_positions") == expected
                    ),
                )
            )
        class_files = {
            str(path.relative_to(classes)): digest(path)
            for path in sorted(Path(classes).rglob("*.class"))
        }
    stable = (
        source_hashes == {str(path.relative_to(ROOT)): digest(path) for path in sources}
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
        schema="wakemu-pilot-displacement-native-proof-v1",
        source=source_hashes,
        classpath=jars,
        bdata=bdata,
        source_stable=stable,
        instrumentation="none",
        compile_returncode=compiled.returncode,
        java_sha256=digest(java),
        javac_sha256=digest(javac),
        runner_sha256=digest(__file__),
        input_sha256=digest(reports),
        input_provenance=data["source_hashes"],
        class_files=class_files,
        cases=results,
        complete=stable and bool(results) and all(row["complete"] for row in results),
        scope="original native definitions/hydrated displacement/aVo logical cbj/aER; visual script/wait skipped",
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
