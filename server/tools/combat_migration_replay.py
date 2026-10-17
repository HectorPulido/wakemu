#!/usr/bin/env python3
"""Compare historical family backends only in an explicitly pinned external engine.

Both archived workers decode the same sealed capsule and install its pinned catalog
before loading the engine. Neither worker commits state to a live fight. Exact
typed-state and packet digests include identity and ordering; equality is
qualified only for requested family selections actually observed in both executions. Selection
counts prove branch resolution only; scenario assertions must establish effects.
"""
import argparse
from collections import Counter
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig

SERVER = Path(__file__).resolve().parents[1]
SCHEMA = "wakemu-combat-archived-family-differential-v2"
_ISOLATION_VIOLATIONS = []


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


# Historical v1 wire vocabulary, never a live runtime policy import.
HISTORICAL_FAMILIES = (
    "vitality",
    "states",
    "retained",
    "summons",
    "lifecycle",
    "entry",
    "delivery",
)


def validate_historical_root(root, expected_source_sha256):
    """Require an explicit archive; never fall back to the active engine."""
    root = Path(root).resolve()
    if (
        root == SERVER.resolve()
        or (root / "wakfu_server").resolve() == (SERVER / "wakfu_server").resolve()
        or not (root / "wakfu_server" / "combat" / "combat_core_migration.py").is_file()
    ):
        raise ValueError("Pinned external historical engine unavailable")
    if (
        not isinstance(expected_source_sha256, str)
        or len(expected_source_sha256) != 64
        or any(char not in "0123456789abcdef" for char in expected_source_sha256)
    ):
        raise ValueError("Explicit historical engine SHA256 required")
    if historical_source_sha256(root) != expected_source_sha256:
        raise ValueError(
            "Historical engine does not match the explicitly pinned source"
        )
    return root


def historical_source_sha256(root):
    """Verify the engine/interpreter identity with stdlib before archive imports."""
    paths = sorted(
        path
        for path in (root / "wakfu_server").rglob("*")
        if path.is_file() and path.suffix in (".py", ".json")
    )
    paths.extend(path for path in (root / "protocol_codec.py",) if path.is_file())
    files = {
        path.relative_to(root).as_posix(): _digest(path.read_bytes())
        for path in paths
        if not path.is_symlink() and "__pycache__" not in path.parts
    }
    python = {
        "implementation": sys.implementation.name,
        "version": list(sys.version_info[:3]),
    }
    return _digest(
        json.dumps(
            dict(files=files, python=python),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    )


def _read_only(event, args):
    """Fail closed on service access and filesystem mutation in replay workers."""
    if event == "open":
        _, mode, flags = args
        writable = isinstance(mode, str) and any(char in mode for char in "wax+")
        writable |= isinstance(flags, int) and bool(
            flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        )
        if writable:
            _ISOLATION_VIOLATIONS.append(event)
            raise PermissionError("Migration replay forbids filesystem writes")
    if event.startswith("socket.") or event in {
        "subprocess.Popen",
        "os.system",
        "os.fork",
        "os.forkpty",
        "os.posix_spawn",
        "os.exec",
        "os.remove",
        "os.rename",
        "os.rmdir",
        "os.mkdir",
        "os.link",
        "os.symlink",
        "os.chmod",
        "os.chown",
        "os.truncate",
        "os.utime",
    }:
        _ISOLATION_VIOLATIONS.append(event)
        raise PermissionError("Migration replay forbids external effects: " + event)


def _worker(
    bundle,
    name,
    kind,
    provider_recipe,
    families,
    backend,
    historical_root,
    expected_source_sha256,
):
    sys.dont_write_bytecode = True
    historical_root = validate_historical_root(historical_root, expected_source_sha256)
    sys.path.insert(0, str(historical_root))
    runner_sha256 = _digest(Path(__file__).read_bytes())
    sys.addaudithook(_read_only)
    # Catalog installation precedes all native engine imports. The canonical
    # migration policy is pure and may already have validated command options.
    from wakfu_server.combat_reproduction_catalog import ReplayCatalog

    path = bundle / name
    capsule_bytes = path.read_bytes()
    catalog_manifest_bytes = (bundle / "catalog.json").read_bytes()
    observed = Counter()

    def observe(family, selected):
        observed[(family, selected)] += 1

    with ReplayCatalog(bundle).install():
        from wakfu_server.combat_core_migration import (
            family_backend_scope,
            migration_observation_scope,
        )
        from wakfu_server.combat_reproduction import source_identity, catalog_identity

        source = source_identity()
        if source["sha256"] != expected_source_sha256:
            raise ValueError(
                "Historical engine does not match the explicitly pinned source"
            )
        catalog = catalog_identity()
        with family_backend_scope(
            {family: backend for family in families}
        ), migration_observation_scope(observe):
            if kind == "case":
                from wakfu_server.combat_reproduction import (
                    read_case,
                    verify_catalog_bundle,
                    execute_case,
                    compare_expectation,
                )

                capsule = read_case(path)
                verify_catalog_bundle(capsule, bundle)
                result = execute_case(capsule, allow_source_drift=False)
                outcome_sha256 = result["sha256"]
                baseline_matches = compare_expectation(capsule, result)["matches"]
            elif kind == "recipient":
                from wakfu_server.combat_recipient_reproduction import (
                    read_recipient_case,
                    execute_recipient_case,
                    compare_recipient_expectation,
                )
                from wakfu_server.combat_reproduction import verify_catalog_bundle

                capsule = read_recipient_case(path)
                verify_catalog_bundle(capsule, bundle)
                result = execute_recipient_case(
                    capsule, backend=backend, allow_source_drift=False
                )
                outcome_sha256 = result["sha256"]
                baseline_matches = compare_recipient_expectation(
                    capsule, backend, result
                )["matches"]
            else:
                from wakfu_server.combat_incident_replay import (
                    read_incident,
                    verify_incident_bundle,
                    replay_runtime_incident,
                )

                capsule = read_incident(path)
                verify_incident_bundle(capsule, bundle)
                result = replay_runtime_incident(
                    capsule,
                    provider_recipe=provider_recipe,
                    allow_source_drift=False,
                )
                outcome_sha256 = result["actual_sha256"]
                baseline_matches = result["operation_matches"]
        if source_identity() != source or catalog_identity() != catalog:
            raise ValueError("Replay source or catalog changed during execution")
    # Runtime action adapters report ordinary exceptions as deterministic
    # outcomes. An attempted external effect must never become a passing pair
    # of identical gameplay errors, even when an adapter caught the exception.
    if _ISOLATION_VIOLATIONS:
        raise RuntimeError("Replay attempted a forbidden external effect")
    if path.read_bytes() != capsule_bytes:
        raise ValueError("Replay capsule changed during execution")
    if (bundle / "catalog.json").read_bytes() != catalog_manifest_bytes:
        raise ValueError("Replay catalog manifest changed during execution")
    if _digest(Path(__file__).read_bytes()) != runner_sha256:
        raise ValueError("Migration replay runner changed during execution")
    # No state, private identity, packet payload or exception message is emitted.
    return dict(
        schema=SCHEMA,
        backend=backend,
        families=families,
        historical_server_root=str(historical_root),
        expected_source_sha256=expected_source_sha256,
        capsule_sha256=_digest(capsule_bytes),
        runner_sha256=runner_sha256,
        catalog_manifest_sha256=_digest(catalog_manifest_bytes),
        source_sha256=source["sha256"],
        catalog=catalog,
        outcome_sha256=outcome_sha256,
        status=result["status"],
        baseline_matches=baseline_matches,
        observations=[
            dict(family=family, backend=selected, count=count)
            for (family, selected), count in sorted(observed.items())
        ],
        isolation="fresh-interpreter-read-only-offline-catalog",
    )


def compare_workers(legacy, shared, families):
    """Compare exact outcomes while rejecting stale evidence and missing backend selections."""
    identity_fields = (
        "schema",
        "capsule_sha256",
        "catalog_manifest_sha256",
        "runner_sha256",
        "source_sha256",
        "catalog",
        "families",
        "isolation",
    )
    mismatches = [
        field for field in identity_fields if legacy.get(field) != shared.get(field)
    ]
    if legacy.get("backend") != "legacy" or shared.get("backend") != "shared":
        mismatches.append("backend")
    if legacy.get("families") != families:
        mismatches.append("requested_families")
    missing = []
    for result, backend in ((legacy, "legacy"), (shared, "shared")):
        for family in families:
            if not any(
                row.get("family") == family
                and row.get("backend") == backend
                and type(row.get("count")) is int
                and row["count"] > 0
                for row in result.get("observations", [])
            ):
                missing.append(dict(family=family, backend=backend))
    equivalent = (
        not mismatches
        and legacy.get("outcome_sha256") is not None
        and legacy.get("outcome_sha256") == shared.get("outcome_sha256")
        and legacy.get("status") == shared.get("status")
    )
    return dict(
        schema=SCHEMA,
        matches=equivalent,
        qualified=equivalent and not missing,
        identity_mismatches=mismatches,
        missing_family_selection=missing,
        legacy=legacy,
        shared=shared,
        scope="exact-captured-operation-only-not-full-family-or-client-acceptance",
        baseline_expectation_matches=(
            legacy.get("baseline_matches") is True
            and shared.get("baseline_matches") is True
        ),
        qualification="backend-equivalence-only-not-successful-gameplay",
        selection_counts_prove_effect_execution=False,
        live_commit=False,
        live_delivery=False,
    )


def _run_worker(args, backend):
    # -I -S excludes environment paths and site startup hooks. The explicitly
    # selected interpreter's dependency directory is the only added site path.
    bootstrap = (
        "import runpy,sys;sys.path.append("
        + repr(sysconfig.get_path("purelib"))
        + ");sys.argv="
        + repr(
            [
                str(Path(__file__).resolve()),
                "--worker",
                "--bundle",
                str(args.bundle),
                "--capsule",
                args.capsule,
                "--kind",
                args.kind,
                "--backend",
                backend,
                "--families",
                ",".join(args.families),
                "--historical-server-root",
                str(args.historical_server_root),
                "--expected-source-sha256",
                args.expected_source_sha256,
            ]
            + (
                ["--provider-recipe", args.provider_recipe]
                if args.provider_recipe
                else []
            )
        )
        + ";runpy.run_path("
        + repr(str(Path(__file__).resolve()))
        + ",run_name='__main__')"
    )
    process = subprocess.run(
        [sys.executable, "-I", "-S", "-B", "-c", bootstrap],
        capture_output=True,
        text=True,
        timeout=args.timeout,
    )
    if process.returncode:
        raise RuntimeError(
            "Isolated " + backend + " replay failed; exit " + str(process.returncode)
        )
    return json.loads(process.stdout)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--capsule", default="case.json")
    parser.add_argument(
        "--kind", choices=("case", "incident", "recipient"), default="case"
    )
    parser.add_argument(
        "--recorded-recipient-change",
        action="store_true",
        help="For recipient capsules only, reproduce separately recorded backend outputs instead of requiring equality",
    )
    parser.add_argument("--provider-recipe")
    parser.add_argument("--families", required=True)
    parser.add_argument("--historical-server-root", required=True, type=Path)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--backend", choices=("legacy", "shared"), help=argparse.SUPPRESS
    )
    args = parser.parse_args(argv)
    args.bundle = args.bundle.resolve()
    path = (args.bundle / args.capsule).resolve()
    if path.parent != args.bundle or path.suffix != ".json":
        parser.error("Capsule must be a JSON file directly inside the bundle")
    args.families = args.families.split(",")
    family_names = HISTORICAL_FAMILIES
    try:
        args.historical_server_root = validate_historical_root(
            args.historical_server_root, args.expected_source_sha256
        )
    except ValueError as error:
        parser.error(str(error))
    if (
        not args.families
        or len(set(args.families)) != len(args.families)
        or any(family not in family_names for family in args.families)
    ):
        parser.error("Families must be distinct members of: " + ", ".join(family_names))
    if args.kind == "incident" and not args.provider_recipe:
        parser.error("Incident replay requires an explicit provider recipe")
    if args.recorded_recipient_change and args.kind != "recipient":
        parser.error("Recorded corrections require a typed recipient capsule")
    if args.timeout <= 0:
        parser.error("Timeout must be positive")
    if args.worker:
        if args.backend is None or args.output is not None:
            parser.error("Worker requires backend and forbids output files")
        # Legacy engine initialization may print diagnostics. Keep stdout a
        # single bounded receipt rather than exposing arbitrary private data.
        with redirect_stdout(io.StringIO()):
            result = _worker(
                args.bundle,
                args.capsule,
                args.kind,
                args.provider_recipe,
                args.families,
                args.backend,
                args.historical_server_root,
                args.expected_source_sha256,
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    if args.backend is not None:
        parser.error("Backend is only accepted by isolated workers")
    input_hash = _digest(path.read_bytes())
    legacy = _run_worker(args, "legacy")
    shared = _run_worker(args, "shared")
    result = compare_workers(legacy, shared, args.families)
    if args.recorded_recipient_change:
        result["qualified"] = (
            not result["identity_mismatches"]
            and not result["missing_family_selection"]
            and result["baseline_expectation_matches"]
        )
        result[
            "qualification"
        ] = "recorded-recipient-correction-reproduction-not-native-oracle"
        result["intentional_backend_difference"] = not result["matches"]
    if _digest(path.read_bytes()) != input_hash:
        raise ValueError("Input capsule changed between worker executions")
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
    print(raw.decode(), end="")
    return 0 if result["qualified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
