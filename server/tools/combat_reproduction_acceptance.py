"""Fresh-process acceptance for existing offline reproduction bundles.

Uses combat_reproduce.py unchanged. Success requires normal process exit and
the structured --output result, never a matching line printed before a hang.
Logs and results remain in a newly created private output directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
MAX_RESULT_BYTES = 1024 * 1024


def python_identity():
    """Actual launcher identity; every child uses this exact executable."""
    return {
        "implementation": platform.python_implementation(),
        "version": list(sys.version_info[:3]),
        "executable": str(Path(sys.executable).resolve()),
    }


def offline_environment(root):
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("WAKFU_DATABASE", "WAKFU_REDIS", "WAKFU_CATALOG", "PG"))
        and key not in ("DATABASE_URL", "REDIS_URL", "PYTHONPATH", "PYTHONHOME")
    }
    environment["PYTHONPATH"] = str(Path(root) / "server")
    return environment


def _private_file(path):
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    return os.fdopen(descriptor, "wb")


def _read_result(path):
    try:
        if path.stat().st_size > MAX_RESULT_BYTES:
            return None
        with path.open("rb") as stream:
            raw = stream.read(MAX_RESULT_BYTES + 1)
        if len(raw) > MAX_RESULT_BYTES:
            return None
        result = json.loads(raw) if raw else None
    except (OSError, ValueError):
        return None
    return result if isinstance(result, dict) else None


def _valid_case(name):
    return (
        isinstance(name, str)
        and re.fullmatch(r"[A-Za-z0-9_.-]+\.json", name) is not None
        and name not in ("..json",)
    )


def run_case(root, bundle, case, output, label, timeout, allow_source_drift=False):
    root, bundle, output = (
        Path(root).resolve(),
        Path(bundle).resolve(),
        Path(output).resolve(),
    )
    if not _valid_case(case):
        raise ValueError("Case must be a JSON filename directly inside the bundle")
    paths = {
        kind: output / (label + suffix)
        for kind, suffix in (
            ("stdout", ".stdout.log"),
            ("stderr", ".stderr.log"),
            ("result", ".result.json"),
        )
    }
    with _private_file(paths["result"]):
        pass
    command = [
        sys.executable,
        str(root / "server/tools/combat_reproduce.py"),
        "replay",
        "--bundle",
        str(bundle),
        "--case",
        case,
        "--output",
        str(paths["result"]),
    ]
    if allow_source_drift:
        command.append("--allow-source-drift")
    started = time.perf_counter()
    timed_out = False
    returncode = None
    with _private_file(paths["stdout"]) as stdout, _private_file(
        paths["stderr"]
    ) as stderr:
        try:
            process = subprocess.run(
                command,
                cwd=root,
                env=offline_environment(root),
                stdout=stdout,
                stderr=stderr,
                timeout=timeout,
                check=False,
            )
            returncode = process.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
    result = _read_result(paths["result"])
    valid_hash = (
        isinstance(result, dict)
        and isinstance(result.get("result_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", result["result_sha256"]) is not None
    )
    valid_metadata = bool(
        result
        and result.get("status") in ("accepted", "rejected")
        and isinstance(result.get("source_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", result["source_sha256"])
        and type(result.get("source_matches")) is bool
        and isinstance(result.get("catalog_revision"), str)
        and result["catalog_revision"]
    )
    passed = bool(
        not timed_out
        and returncode == 0
        and valid_hash
        and valid_metadata
        and result.get("matches") is True
        and result.get("catalog_matches") is True
        and (result.get("source_matches") is True or allow_source_drift)
    )
    status = (
        "timeout"
        if timed_out
        else "nonzero-exit"
        if returncode != 0
        else "missing-or-invalid-result"
        if result is None
        else "passed"
        if passed
        else "result-mismatch"
    )
    return {
        "case": case,
        "label": label,
        "status": status,
        "passed": passed,
        "launcher_python": python_identity(),
        "returncode": returncode,
        "timed_out": timed_out,
        "wall_ms": round((time.perf_counter() - started) * 1000, 3),
        "result_sha256": result.get("result_sha256") if result else None,
        "matches": result.get("matches") if result else None,
        "source_matches": result.get("source_matches") if result else None,
        "source_sha256": result.get("source_sha256") if result else None,
        "catalog_matches": result.get("catalog_matches") if result else None,
        "catalog_revision": result.get("catalog_revision") if result else None,
        "action_status": result.get("status") if result else None,
        "logs": {kind: path.name for kind, path in paths.items()},
    }


def _tamper(root, bundle, case, output, timeout, allow_source_drift):
    original = (bundle / "catalog.json").read_bytes()
    original_hash = hashlib.sha256(original).hexdigest()
    with tempfile.TemporaryDirectory(
        prefix="tampered-bundle-", dir=output
    ) as temporary:
        copied = Path(temporary) / "bundle"
        if any(path.is_symlink() for path in bundle.rglob("*")):
            raise ValueError("Tamper copy requires a bundle without symlinks")

        def link_or_copy(source, destination):
            try:
                return os.link(source, destination)
            except OSError:
                return shutil.copy2(source, destination)

        shutil.copytree(bundle, copied, copy_function=link_or_copy)
        manifest = json.loads(original)
        manifest["version"] = -1
        target = copied / "catalog.json"
        # All other copied files are read-only inputs. Unlink the hardlinked
        # manifest before changing it so the original bundle cannot be edited.
        target.unlink()
        with _private_file(target) as stream:
            stream.write(json.dumps(manifest).encode())
        result = run_case(
            root, copied, case, output, "tamper", timeout, allow_source_drift
        )
        stderr = output / result["logs"]["stderr"]
        with stderr.open("rb") as stream:
            rejection_marker = b"Unsupported catalog provenance/version" in stream.read(
                1024 * 1024
            )
        unchanged = (
            hashlib.sha256((bundle / "catalog.json").read_bytes()).hexdigest()
            == original_hash
        )
        result["tamper_rejected"] = bool(
            not result["timed_out"]
            and result["returncode"] not in (None, 0)
            and result["matches"] is None
            and rejection_marker
            and unchanged
        )
        result["original_bundle_unchanged"] = unchanged
        result["original_manifest_sha256"] = original_hash
        result["infrastructure_rejection_marker"] = rejection_marker
        return result


def accept(
    bundle,
    cases,
    output,
    *,
    root=ROOT,
    timeout=180,
    repeat_case=None,
    tamper=False,
    allow_source_drift=False,
):
    root, bundle, output = (
        Path(root).resolve(),
        Path(bundle).resolve(),
        Path(output).resolve(),
    )
    if (
        not 1 <= timeout <= 600
        or not cases
        or len(cases) > 64
        or len(set(cases)) != len(cases)
    ):
        raise ValueError(
            "Require 1–64 unique cases and timeout between 1 and 600 seconds"
        )
    if (
        any(not _valid_case(case) for case in cases)
        or repeat_case is not None
        and repeat_case not in cases
    ):
        raise ValueError(
            "Declared cases must be direct bundle JSON filenames; repeat must name a declared case"
        )
    if not output.is_relative_to(root / ".runtime") or output.exists():
        raise ValueError("Use a new directory inside the frozen checkout .runtime")
    output.mkdir(parents=True, mode=0o700)
    reports = [
        run_case(
            root, bundle, case, output, f"case-{index:02d}", timeout, allow_source_drift
        )
        for index, case in enumerate(cases)
    ]
    repeated = None
    if repeat_case:
        repeated = run_case(
            root, bundle, repeat_case, output, "repeat", timeout, allow_source_drift
        )
        first = next(report for report in reports if report["case"] == repeat_case)
        repeated["identical_hash"] = bool(
            first["passed"]
            and repeated["passed"]
            and first["result_sha256"] == repeated["result_sha256"]
        )
    tampered = (
        _tamper(root, bundle, cases[0], output, timeout, allow_source_drift)
        if tamper
        else None
    )
    report = {
        "schema": "wakemu-fresh-process-reproduction-acceptance-v1",
        "python": python_identity(),
        "runner_sha256": hashlib.sha256(
            Path(__file__).resolve().read_bytes()
        ).hexdigest(),
        "replayer_sha256": hashlib.sha256(
            (root / "server/tools/combat_reproduce.py").read_bytes()
        ).hexdigest(),
        "cases": reports,
        "repeat": repeated,
        "tamper": tampered,
        "allow_source_drift": allow_source_drift,
        "offline_policy": "database-redis-catalog-and-postgresql-environment-removed",
        "complete": all(case["passed"] for case in reports)
        and (repeated is None or repeated["identical_hash"])
        and (tampered is None or tampered["tamper_rejected"]),
    }
    with _private_file(output / "acceptance.json") as stream:
        stream.write((json.dumps(report, indent=2, sort_keys=True) + "\n").encode())
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--case", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--repeat-case")
    parser.add_argument("--tamper", action="store_true")
    parser.add_argument("--allow-source-drift", action="store_true")
    args = parser.parse_args(argv)
    report = accept(
        args.bundle,
        args.case,
        args.output,
        root=args.root,
        timeout=args.timeout,
        repeat_case=args.repeat_case,
        tamper=args.tamper,
        allow_source_drift=args.allow_source_drift,
    )
    print(
        json.dumps(
            {
                "complete": report["complete"],
                "cases": len(report["cases"]),
                "repeat_verified": report["repeat"]["identical_hash"]
                if report["repeat"]
                else None,
                "tamper_rejected": report["tamper"]["tamper_rejected"]
                if report["tamper"]
                else None,
            }
        )
    )
    return 0 if report["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
