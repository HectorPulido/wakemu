"""Generate hash-bound fixtures with the untouched installed Java consumer.

Run separately before focused Python checks. No server catalogs, serializers,
client instrumentation, network connection or game service is imported/started.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path("sniffer/java/VerifyCoreCopyDescriptor.java")
HELPER = Path("sniffer/java/VerifyCombatReconstructionSlice.java")


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def run(java_home, output):
    java_home, output = Path(java_home).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("Use a new native fixture output directory")
    output.mkdir(parents=True, mode=0o700)
    jars = sorted((ROOT / "client/lib").glob("*.jar"))
    if not jars or not (ROOT / "client/lib/wakfu-client.jar").is_file():
        raise ValueError("Require original installed native classpath")
    source_hash = digest(ROOT / SOURCE)
    helper_hash = digest(ROOT / HELPER)
    jar_hashes = {str(p.relative_to(ROOT)): digest(p) for p in jars}
    bdata_hashes = {
        str(p.relative_to(ROOT)): digest(p)
        for p in sorted((ROOT / "client/contents/bdata").glob("*.jar"))
    }
    java = str(java_home / "bin/java")
    javac = str(java_home / "bin/javac")
    # An inherited launcher option could instrument the supposedly original
    # consumer. Do not let client/debug agent settings cross this proof boundary.
    environment = {
        key: value
        for key, value in os.environ.items()
        if key
        not in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "CLASSPATH")
    }
    identity = subprocess.run(
        [java, "-version"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
        env=environment,
    )
    with tempfile.TemporaryDirectory(prefix="combat-native-oracle-") as temporary:
        classes = Path(temporary)
        compile_command = [
            javac,
            "-proc:none",
            "--release",
            "21",
            "-cp",
            str(ROOT / "client/lib/*"),
            "-d",
            str(classes),
            str(ROOT / SOURCE),
            str(ROOT / HELPER),
        ]
        compile_result = subprocess.run(
            compile_command,
            cwd=ROOT,
            capture_output=True,
            timeout=60,
            check=False,
            env=environment,
        )
        (output / "compile.stdout.log").write_bytes(compile_result.stdout)
        (output / "compile.stderr.log").write_bytes(compile_result.stderr)
        command = [
            java,
            "-cp",
            str(classes) + ":" + str(ROOT / "client/lib/*"),
            "VerifyCoreCopyDescriptor",
            str(output),
        ]
        execution = None
        if compile_result.returncode == 0:
            execution = subprocess.run(
                command,
                cwd=ROOT,
                capture_output=True,
                timeout=60,
                check=False,
                env=environment,
            )
            (output / "native.stdout.log").write_bytes(execution.stdout)
            (output / "native.stderr.log").write_bytes(execution.stderr)
        classes_hashes = {
            str(p.relative_to(classes)): digest(p)
            for p in sorted(classes.rglob("*.class"))
        }
    stable = (
        helper_hash == digest(ROOT / HELPER)
        and source_hash == digest(ROOT / SOURCE)
        and jar_hashes
        == {
            str(p.relative_to(ROOT)): digest(p)
            for p in sorted((ROOT / "client/lib").glob("*.jar"))
        }
        and bdata_hashes
        == {
            str(p.relative_to(ROOT)): digest(p)
            for p in sorted((ROOT / "client/contents/bdata").glob("*.jar"))
        }
    )
    fixture_hashes = {p.name: digest(p) for p in sorted(output.glob("*.bin"))}
    observations = output / "observations.json"
    observed = json.loads(observations.read_text()) if observations.is_file() else {}
    receipt = dict(
        schema="wakemu-independent-native-protocol-proof-v1",
        source={str(SOURCE): source_hash, str(HELPER): helper_hash},
        classpath=jar_hashes,
        bdata=bdata_hashes,
        java=dict(
            executable=java,
            version=identity.stderr.decode()
            if isinstance(identity.stderr, bytes)
            else identity.stderr,
            executable_sha256=digest(java),
        ),
        javac=javac,
        compile_command=compile_command,
        command=command,
        javac_sha256=digest(javac),
        runner_sha256=digest(__file__),
        compile_returncode=compile_result.returncode,
        returncode=None if execution is None else execution.returncode,
        class_files=classes_hashes,
        fixtures=fixture_hashes,
        observations_sha256=digest(observations) if observations.is_file() else None,
        source_stable=stable,
        instrumentation="none",
        complete=bool(
            stable
            and execution is not None
            and execution.returncode == 0
            and observed.get("completed_normally") is True
            and fixture_hashes
        ),
    )
    (output / "native-proof.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--java-home", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    receipt = run(args.java_home, args.output)
    print(
        json.dumps(
            {
                key: receipt[key]
                for key in (
                    "complete",
                    "compile_returncode",
                    "returncode",
                    "source_stable",
                )
            }
        )
    )
    return 0 if receipt["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
