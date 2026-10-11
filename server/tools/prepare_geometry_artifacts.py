#!/usr/bin/env python3
"""Build and exhaustively compare native prepared derivatives without services."""
import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from wakfu_server import native_catalog
from wakfu_server.combat_geometry import prepare_geometry
from wakfu_server.combat_forced_terrain import prepare_compact_index
from wakfu_server.paths import DATA_ROOT
from wakfu_server.prepared_geometry import build_artifact


def resident_kib(pid):
    """Linux containers need no process utilities; macOS uses its system ps."""
    if sys.platform.startswith("linux"):
        try:
            for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
        except FileNotFoundError:
            return 0
        return 0
    sample = subprocess.run(
        ["ps", "-o", "rss=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    return int(sample.stdout.strip() or 0)


def run_isolated(command, memory_limit_mib):
    """Run one map at a time and stop before an oversized worker consumes RAM."""
    limit_kib = memory_limit_mib * 1024
    with subprocess.Popen(command) as worker:
        try:
            while worker.poll() is None:
                if resident_kib(worker.pid) > limit_kib:
                    raise RuntimeError(
                        f"Geometry worker exceeded {memory_limit_mib} MiB; stopped"
                    )
                time.sleep(0.1)
            if worker.returncode:
                raise RuntimeError(f"Geometry worker failed: {worker.returncode}")
        finally:
            if worker.poll() is None:
                worker.kill()
                worker.wait()


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
                raise RuntimeError("A geometry build is already running") from error
            revision = native_catalog.release()
            inventory = native_catalog.document_hashes()
            maps = (
                sorted(
                    int(match.group(1))
                    for name in inventory
                    if (match := re.fullmatch(r"combat-maps/([1-9][0-9]*)\.json", name))
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
            if (match := re.fullmatch(r"combat-maps/([1-9][0-9]*)\.json", name))
        )
        if args.all
        else [args.map]
    )
    for map_id in maps:
        started = time.perf_counter()
        name = f"combat-maps/{map_id}.json"
        raw = native_catalog.read_bytes(DATA_ROOT / name)
        forced_name = f"forced-transitions/{map_id}.json"
        forced_raw = (
            native_catalog.read_bytes(DATA_ROOT / forced_name)
            if forced_name in inventory
            else None
        )
        if hashlib.sha256(raw).hexdigest() != inventory[name]:
            raise ValueError("Published geometry hash changed")
        if (
            forced_raw is not None
            and hashlib.sha256(forced_raw).hexdigest() != inventory[forced_name]
        ):
            raise ValueError("Published forced terrain hash changed")
        result = build_artifact(
            args.output,
            map_id=map_id,
            revision=revision,
            geometry_raw=raw,
            forced_raw=forced_raw,
        )
        expected = prepare_geometry(json.loads(raw))
        if result.geometry != expected:
            raise ValueError(f"Geometry equivalence failed for {map_id}")
        expected_forced = (
            None
            if forced_raw is None
            else prepare_compact_index(json.loads(forced_raw), map_id, 0, 4)
        )
        if result.forced_index != expected_forced:
            raise ValueError(f"Forced terrain equivalence failed for {map_id}")
        print(
            json.dumps(
                {
                    "map_id": map_id,
                    "revision": revision,
                    "equivalent": True,
                    "cells": len(expected.cells),
                    "edges": len(expected.edges),
                    "seconds": round(time.perf_counter() - started, 6),
                }
            ),
            flush=True,
        )
        del result, expected, expected_forced, raw, forced_raw
    print(json.dumps({"complete": True, "maps": len(maps), "revision": revision}))


if __name__ == "__main__":
    main()
