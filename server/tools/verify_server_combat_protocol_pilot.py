"""Hash-bound original-consumer verification of actual server-produced bytes."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from verify_combat_reconstruction_native import ROOT, digest


def verify(java_home, pilot):
    java_home, pilot = Path(java_home).resolve(), Path(pilot).resolve()
    receipt_path = pilot / "server-native-proof.json"
    if receipt_path.exists():
        raise ValueError(
            "Preserve previous native pilot receipt; use a new pilot directory"
        )
    metadata = json.loads((pilot / "server-pilot.json").read_text())
    if metadata.get("schema") != "wakemu-server-protocol-pilot-v1":
        raise ValueError("Unknown server pilot metadata")
    fixtures = {
        name + ".bin": row["sha256"] for name, row in metadata["packets"].items()
    }
    for name, value in fixtures.items():
        if Path(name).name != name or digest(pilot / name) != value:
            raise ValueError("Changed server packet input")
    sources = [
        ROOT / "sniffer/java/VerifyCombatReconstructionSlice.java",
        ROOT / "sniffer/java/VerifyServerCombatReconstructionPilot.java",
    ]
    before = {str(path.relative_to(ROOT)): digest(path) for path in sources}
    classpath = {
        str(p.relative_to(ROOT)): digest(p)
        for p in sorted((ROOT / "client/lib").glob("*.jar"))
    }
    bdata = {
        str(p.relative_to(ROOT)): digest(p)
        for p in sorted((ROOT / "client/contents/bdata").glob("*.jar"))
    }
    environment = {
        key: value
        for key, value in os.environ.items()
        if key
        not in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "CLASSPATH")
    }
    java, javac = str(java_home / "bin/java"), str(java_home / "bin/javac")
    identity = subprocess.run(
        [java, "-version"],
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    with tempfile.TemporaryDirectory(prefix="native-server-pilot-") as classes:
        compile_command = [
            javac,
            "-proc:none",
            "--release",
            "21",
            "-cp",
            str(ROOT / "client/lib/*"),
            "-d",
            classes,
            *map(str, sources),
        ]
        compilation = subprocess.run(
            compile_command,
            cwd=ROOT,
            env=environment,
            capture_output=True,
            timeout=60,
            check=False,
        )
        (pilot / "server-native-compile.stdout.log").write_bytes(compilation.stdout)
        (pilot / "server-native-compile.stderr.log").write_bytes(compilation.stderr)
        command = [
            java,
            "-cp",
            classes + ":" + str(ROOT / "client/lib/*"),
            "VerifyServerCombatReconstructionPilot",
            str(pilot),
        ]
        process = None
        if compilation.returncode == 0:
            process = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                capture_output=True,
                timeout=60,
                check=False,
            )
            (pilot / "server-native.stdout.log").write_bytes(process.stdout)
            (pilot / "server-native.stderr.log").write_bytes(process.stderr)
        compiled = {
            str(p.relative_to(classes)): digest(p)
            for p in sorted(Path(classes).rglob("*.class"))
        }
    observations = pilot / "server-native-observations.json"
    observed = json.loads(observations.read_text()) if observations.is_file() else {}
    stable = (
        before == {str(p.relative_to(ROOT)): digest(p) for p in sources}
        and classpath
        == {
            str(p.relative_to(ROOT)): digest(p)
            for p in sorted((ROOT / "client/lib").glob("*.jar"))
        }
        and bdata
        == {
            str(p.relative_to(ROOT)): digest(p)
            for p in sorted((ROOT / "client/contents/bdata").glob("*.jar"))
        }
        and all(digest(pilot / name) == value for name, value in fixtures.items())
    )
    receipt = dict(
        schema="wakemu-independent-server-protocol-proof-v1",
        source=before,
        classpath=classpath,
        bdata=bdata,
        fixtures=fixtures,
        class_files=compiled,
        java=dict(
            executable=java, version=identity.stderr, executable_sha256=digest(java)
        ),
        javac=dict(executable=javac, executable_sha256=digest(javac)),
        runner_sha256=digest(__file__),
        compile_command=compile_command,
        command=command,
        compile_returncode=compilation.returncode,
        returncode=process.returncode if process else None,
        source_stable=stable,
        instrumentation="none",
        server_metadata_sha256=digest(pilot / "server-pilot.json"),
        observations_sha256=digest(observations) if observations.is_file() else None,
        complete=bool(
            compilation.returncode == 0
            and process is not None
            and process.returncode == 0
            and stable
            and observed.get("completed_normally") is True
        ),
    )
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java-home", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    args = parser.parse_args()
    receipt = verify(args.java_home, args.pilot)
    print(
        json.dumps(
            {key: receipt[key] for key in ("complete", "returncode", "source_stable")}
        )
    )
    return 0 if receipt["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
