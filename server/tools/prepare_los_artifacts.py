#!/usr/bin/env python3
"""Build ordered static LOS derivatives with serial bounded workers."""
import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

from wakfu_server import native_catalog
from wakfu_server.combat_native_los_ray import prepare_columns
from wakfu_server.paths import DATA_ROOT
from wakfu_server.prepared_los import build_artifact, load_artifact
from wakfu_server.prepared_geometry import ArtifactUnavailable
from prepare_geometry_artifacts import run_isolated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--map", type=int)
    choice.add_argument("--all", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--memory-limit-mib", type=int, default=512)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.memory_limit_mib < 64:
        parser.error("Memory limit must be at least 64 MiB")
    args.output.mkdir(parents=True, exist_ok=True)
    if not args.worker:
        # One coordinator for this output directory, including separate invocations.
        with (
            (args.output.parent / ".prepared-static-build.lock").open(
                "a"
            ) as global_lock,
            (args.output / ".build.lock").open("a") as lock,
        ):
            try:
                fcntl.flock(global_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError(
                    "A static preparation build is already running"
                ) from error
            revision = native_catalog.release()
            inventory = native_catalog.document_hashes()
            maps = (
                sorted(
                    int(match.group(1))
                    for name in inventory
                    if (
                        match := re.fullmatch(
                            r"native-los-topology/([1-9][0-9]*)\.json", name
                        )
                    )
                )
                if args.all
                else [args.map]
            )
            environment_revision = os.environ.get("WAKFU_CATALOG_REVISION")
            os.environ["WAKFU_CATALOG_REVISION"] = revision
            try:
                for map_id in maps:
                    run_isolated(
                        [
                            sys.executable,
                            str(Path(__file__).resolve()),
                            "--worker",
                            "--map",
                            str(map_id),
                            "--output",
                            str(args.output),
                        ],
                        args.memory_limit_mib,
                    )
            finally:
                if environment_revision is None:
                    os.environ.pop("WAKFU_CATALOG_REVISION", None)
                else:
                    os.environ["WAKFU_CATALOG_REVISION"] = environment_revision
            print(
                json.dumps({"complete": True, "maps": len(maps), "revision": revision})
            )
        return
    if args.all:
        parser.error("A worker must process exactly one map")
    revision = native_catalog.release()
    inventory = native_catalog.document_hashes()
    maps = (
        sorted(
            int(match.group(1))
            for name in inventory
            if (match := re.fullmatch(r"native-los-topology/([1-9][0-9]*)\.json", name))
        )
        if args.all
        else [args.map]
    )
    for map_id in maps:
        started = time.perf_counter()
        name = f"native-los-topology/{map_id}.json"
        raw = native_catalog.read_bytes(DATA_ROOT / name)
        if hashlib.sha256(raw).hexdigest() != inventory[name]:
            raise ValueError("Published LOS source hash changed")
        reused = True
        try:
            existing = load_artifact(
                args.output,
                map_id=map_id,
                revision=revision,
                source_sha256=inventory[name],
            )
            del existing
        except ArtifactUnavailable:
            reused = False
            build_artifact(
                args.output, map_id=map_id, revision=revision, source_raw=raw
            )
        started_load = time.perf_counter()
        result = load_artifact(
            args.output,
            map_id=map_id,
            revision=revision,
            source_sha256=inventory[name],
        )
        prepared_seconds = time.perf_counter() - started_load
        started_baseline = time.perf_counter()
        expected = prepare_columns(json.loads(raw), map_id)
        baseline_seconds = time.perf_counter() - started_baseline
        if result != expected:
            raise ValueError(f"LOS column equivalence failed for {map_id}")
        print(
            json.dumps(
                {
                    "map_id": map_id,
                    "revision": revision,
                    "equivalent": True,
                    "reused": reused,
                    "columns": len(expected),
                    "baseline_seconds": baseline_seconds,
                    "prepared_seconds": prepared_seconds,
                    "seconds": round(time.perf_counter() - started, 6),
                }
            ),
            flush=True,
        )
        del result, expected, raw
    print(json.dumps({"complete": True, "maps": len(maps), "revision": revision}))


if __name__ == "__main__":
    main()
