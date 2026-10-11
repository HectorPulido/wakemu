#!/usr/bin/env python3
"""Build and exhaustively compare native prepared derivatives without services."""
import argparse
import hashlib
import json
import re
import time
from pathlib import Path

from wakfu_server import native_catalog
from wakfu_server.combat_geometry import prepare_geometry
from wakfu_server.combat_forced_terrain import prepare_compact_index
from wakfu_server.paths import DATA_ROOT
from wakfu_server.prepared_geometry import build_artifact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--map", type=int)
    choice.add_argument("--all", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
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
