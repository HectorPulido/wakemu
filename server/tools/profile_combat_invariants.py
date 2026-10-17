"""Measure native-fixture preparation and diagnostic inspection separately."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time


ROOT = Path(__file__).resolve().parents[2]


def profile(*, iterations=25):
    if type(iterations) is not int or not 1 <= iterations <= 1000:
        raise ValueError("Bounded iteration count required")
    sys.path.insert(0, str(ROOT / "server"))
    sys.path.insert(0, str(ROOT / "server/tests"))
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT
    from wakfu_server.combat_invariants import Boundary, check_prepared_boundary
    from wakfu_server.combat_invariant_resources import ResourceAuthority
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.combat_reproduction import source_identity
    from wakfu_server.combat_reproduction_state import encode_state
    from test_combat_spell_transaction import SpellTransactionTests

    source_before = source_identity()
    started = time.perf_counter_ns()
    documents = (
        "native-actor-characteristics.json",
        "native-class-copy-characteristics.json",
    )
    hashes = native_catalog.document_hashes()
    authority = ResourceAuthority.from_documents(
        revision=native_catalog.release(),
        actor_bytes=native_catalog.read_bytes(DATA_ROOT / documents[0]),
        copy_bytes=native_catalog.read_bytes(DATA_ROOT / documents[1]),
        actor_sha256=hashes[documents[0]],
        copy_sha256=hashes[documents[1]],
    )
    authority_seconds = (time.perf_counter_ns() - started) / 1e9
    started = time.perf_counter_ns()
    _, _, fight = SpellTransactionTests().native_server_fixture(15, 20, native_qi=True)
    runtime = RuntimeMessages(fight, clock=lambda: 0.0)
    fixture_seconds = (time.perf_counter_ns() - started) / 1e9
    started = time.perf_counter_ns()
    before = encode_state((fight, runtime), preserve_scalars=True)
    fingerprint_seconds = (time.perf_counter_ns() - started) / 1e9
    boundary = Boundary("profile.native_fixture", "prepared")
    samples, reports = [], []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        report = check_prepared_boundary(
            fight, runtime, boundary, resource_authority=authority
        )
        samples.append((time.perf_counter_ns() - started) / 1e6)
        reports.append(report)
    unchanged = before == encode_state((fight, runtime), preserve_scalars=True)
    source_after = source_identity()
    warm = samples[1:] or samples
    result = dict(
        schema="wakemu-combat-invariant-profile-v1",
        fixture_origin="existing-SpellTransactionTests.native_server_fixture-breed15-level20-nativeQI",
        preparation_seconds=dict(
            resource_authority=authority_seconds,
            native_fixture=fixture_seconds,
            initial_graph_fingerprint=fingerprint_seconds,
        ),
        check_milliseconds=dict(
            first_after_setup=samples[0],
            warm_median=statistics.median(warm),
            warm_min=min(warm),
            warm_max=max(warm),
            total=sum(samples),
        ),
        iterations=iterations,
        actor_count=len(fight.actors),
        area_count=len(fight.native_effect_areas),
        retained_count=len(fight.native_retained_records),
        resource_authority=authority.as_dict(),
        source_sha256=source_before["sha256"],
        python=source_before["python"],
        source_stable=source_before == source_after,
        graph_unchanged=unchanged,
        findings_identical=all(report == reports[0] for report in reports),
        report=reports[0].as_dict(),
        limits="One two-actor native fixture; no live overhead or large-population guarantee. "
        "Setup, source hashing, graph checks and process finalization are outside timed inspection.",
        profiler_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    result["verified"] = (
        unchanged
        and result["source_stable"]
        and result["findings_identical"]
        and not reports[0].violations
        and not any(row.invariant == "coverage.limit" for row in reports[0].findings)
    )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=25)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("Use a new private output path")
    result = profile(iterations=args.iterations)
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "verified",
                    "preparation_seconds",
                    "check_milliseconds",
                    "graph_unchanged",
                )
            }
        )
    )
    return 0 if result["verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
