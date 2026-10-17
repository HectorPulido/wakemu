"""Verify actual selected owned area/state UID lifecycles with original Java."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from combat_pilot_area_evidence import CapturedLifecycle, unwrap
from verify_combat_reconstruction_native import ROOT, digest


def records_from_report(path):
    from wakfu_server.combat_protocol_reconstruction import decode_packet

    data = unwrap(json.loads(Path(path).read_text()))
    result = []
    for case in data["cases"]:
        if case["test"] in data.get("failures", ()) or case["test"] in data.get(
            "errors", ()
        ):
            continue
        for pair_index, pair in enumerate(case["observations"]):
            for branch in ("legacy", "pilot"):
                bindings = pair[branch]["runtime_results"]
                frames = []
                for binding_index, binding in enumerate(bindings):
                    for packet_index, packet in enumerate(binding["packets"]):
                        opcode, payload = packet
                        if opcode not in (12613, 13560):
                            continue
                        decoded = decode_packet(opcode, payload)
                        if decoded["effect"]["family"] in (308, 310, 315):
                            frames.append(
                                dict(
                                    packet=packet,
                                    decoded=decoded,
                                    binding=binding_index,
                                    index=packet_index,
                                )
                            )
                area_ids = {
                    frame["decoded"]["effect"]["area_uid"]
                    for frame in frames
                    if frame["decoded"]["kind"] == "effect"
                    and frame["decoded"]["effect"]["family"] in (308, 315)
                }
                groups = []
                for area in sorted(area_ids):
                    selected = [
                        frame
                        for frame in frames
                        if (
                            frame["decoded"]["effect"].get("area_uid") == area
                            or (
                                frame["decoded"]["effect"]["family"] == 310
                                and (
                                    area
                                    in (
                                        frame["decoded"]["effect"]["caster"],
                                        frame["decoded"]["effect"]["target"],
                                    )
                                    or (
                                        frame["decoded"]["effect"]["container_type"]
                                        == 3
                                        and frame["decoded"]["effect"]["container_id"]
                                        == area
                                    )
                                )
                            )
                        )
                    ]
                    if any(
                        frame["decoded"]["kind"] == "effect_remove"
                        for frame in selected
                    ):
                        linked_states = {
                            frame["decoded"]["effect"]["uid"]
                            for frame in selected
                            if frame["decoded"]["effect"]["family"] == 310
                        }
                        groups.append((f"area-{area}", selected, {area}, linked_states))
                state_additions = {
                    frame["decoded"]["effect"]["uid"]
                    for frame in frames
                    if frame["decoded"]["kind"] == "effect"
                    and frame["decoded"]["effect"]["family"] == 310
                }
                state_removals = {
                    frame["decoded"]["effect"]["uid"]
                    for frame in frames
                    if frame["decoded"]["kind"] == "effect_remove"
                    and frame["decoded"]["effect"]["family"] == 310
                }
                for state in sorted(state_additions & state_removals):
                    selected = [
                        frame
                        for frame in frames
                        if frame["decoded"]["effect"]["family"] == 310
                        and frame["decoded"]["effect"]["uid"] == state
                    ]
                    if any(
                        area in area_ids
                        for frame in selected
                        for area in (
                            frame["decoded"]["effect"]["caster"],
                            frame["decoded"]["effect"]["target"],
                        )
                    ):
                        continue
                    if any(
                        frame["decoded"]["effect"]["container_type"] == 3
                        and frame["decoded"]["effect"]["container_id"] in area_ids
                        for frame in selected
                    ):
                        continue
                    groups.append((f"state-{state}", selected, set(), {state}))
                for name, selected, scoped_areas, scoped_states in groups:
                    first, last = (
                        bindings[selected[0]["binding"]],
                        bindings[selected[-1]["binding"]],
                    )
                    if "initial_state" not in first:
                        continue
                    initial = CapturedLifecycle(first["initial_state"])
                    final = CapturedLifecycle(last["state"])

                    def scope(view):
                        return dict(
                            areas={
                                key: row
                                for key, row in view["areas"].items()
                                if int(key) in scoped_areas
                            },
                            states={
                                key: row
                                for key, row in view["states"].items()
                                if int(key) in scoped_states
                                or row["owner"] in scoped_areas
                            },
                        )

                    before = scope(initial.projection())
                    if before != dict(states={}, areas={}):
                        raise ValueError(
                            "Selected lifecycle already exists at actual first binding"
                        )
                    result.append(
                        dict(
                            id=f"{case['test']}-{pair_index}-{branch}-{name}",
                            branch=branch,
                            actor_ids=list(initial.actor_ids()),
                            initial_projection=before,
                            expected_projection=scope(final.projection()),
                            source_locations=[
                                dict(binding=frame["binding"], packet=frame["index"])
                                for frame in selected
                            ],
                            packets=[frame["packet"] for frame in selected],
                        )
                    )
    return data, result


def verify(java_home, reports, output):
    java_home, reports, output = (
        Path(java_home).resolve(),
        Path(reports).resolve(),
        Path(output).resolve(),
    )
    if output.exists():
        raise ValueError(
            "Use a new private native retained lifecycle evidence directory"
        )
    input_data, records = records_from_report(reports)
    if not records:
        raise ValueError(
            "No actual passing scoped creation/removal lifecycle with initial capture"
        )
    output.mkdir(parents=True, mode=0o700)
    sources = [
        ROOT / "sniffer/java" / name
        for name in (
            "VerifyCombatReconstructionSlice.java",
            "VerifyPilotMovementQueue.java",
            "VerifyPilotDisplacementQueue.java",
            "VerifyPilotAreaQueue.java",
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
    with tempfile.TemporaryDirectory(prefix="pilot-area-native-") as classes:
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
        for index, record in enumerate(records):
            directory = output / f"case-{index}"
            directory.mkdir(mode=0o700)
            rows, packet_hashes = [], []
            for packet_index, (opcode, body) in enumerate(record["packets"]):
                name = f"packet-{packet_index}.bin"
                (directory / name).write_bytes(body)
                packet_hashes.append(digest(directory / name))
                rows.append(f"{opcode} {name}")
            (directory / "stream.txt").write_text("\n".join(rows) + "\n")
            observation = directory / "observations.json"
            execution = None
            if compilation.returncode == 0:
                try:
                    execution = subprocess.run(
                        [
                            str(java),
                            "-cp",
                            classes + ":" + str(ROOT / "client/lib/*"),
                            "VerifyPilotAreaQueue",
                            str(directory),
                            str(observation),
                            str(ROOT / "client/contents/bdata"),
                        ],
                        cwd=output,
                        env=environment,
                        capture_output=True,
                        timeout=15,
                        check=False,
                    )
                    stdout, stderr = execution.stdout, execution.stderr
                except subprocess.TimeoutExpired as error:
                    stdout, stderr = error.stdout or b"", error.stderr or b""
                (directory / "native.stdout.log").write_bytes(stdout)
                (directory / "native.stderr.log").write_bytes(stderr)
            native = json.loads(observation.read_text()) if observation.exists() else {}
            result = {key: value for key, value in record.items() if key != "packets"}
            result.update(
                packets_sha256=packet_hashes,
                native=native,
                returncode=execution.returncode if execution else None,
                observations_sha256=digest(observation)
                if observation.exists()
                else None,
                complete=bool(
                    execution
                    and execution.returncode == 0
                    and native.get("completed_normally") is True
                    and native.get("final") == record["expected_projection"]
                ),
            )
            results.append(result)
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
        schema="wakemu-pilot-area-native-proof-v1",
        source=hashes,
        classpath=jars,
        bdata=bdata,
        source_stable=stable,
        instrumentation="none",
        compile_returncode=compilation.returncode,
        java_sha256=digest(java),
        javac_sha256=digest(javac),
        runner_sha256=digest(__file__),
        graph_reader_sha256=digest(ROOT / "server/tools/combat_pilot_area_evidence.py"),
        input_sha256=digest(reports),
        input_provenance=input_data.get("source_hashes", {}),
        class_files=class_files,
        cases=results,
        complete=stable and all(row["complete"] for row in results),
        scope="selected UID creation/retirement callbacks; no unified cross-factory chronology or rendering claim",
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
