"""Compact audited native policies without changing their destinations or order.

This is an offline conversion/equivalence benchmark; runtime remains unchanged.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time


def convert(directory, map_id, output):
    began = time.perf_counter()
    grouped = {}
    old_bytes = 0
    checksums = {}
    provenance = None
    rows_per_height = {}
    for height in range(1, 26):
        path = directory / f"{map_id}-h{height}-r0-j4.json.gz"
        old_bytes += path.stat().st_size
        with gzip.open(path, "rt") as source:
            policy = json.load(source)
        if (policy["map_id"], policy["height"], policy["radius"], policy["jump"]) != (
            map_id,
            height,
            0,
            4,
        ):
            raise ValueError("Unexpected native policy identity")
        if provenance is None:
            provenance = policy["archive_sha256"]
        if provenance != policy["archive_sha256"]:
            raise ValueError("Mixed client archives")
        digest = hashlib.sha256()
        rows_per_height[height] = len(policy["rows"])
        for src, xy, dst in policy["rows"]:
            key = (*src, xy[0] - src[0], xy[1] - src[1])
            if abs(key[3]) + abs(key[4]) != 1:
                raise ValueError("Non-cardinal query")
            if dst is not None and dst[:2] != xy:
                raise ValueError("Destination column changed")
            z = None if dst is None else dst[2]
            grouped.setdefault(key, {}).setdefault(z, 0)
            if any(mask & (1 << (height - 1)) for mask in grouped[key].values()):
                raise ValueError("Duplicate native query")
            grouped[key][z] |= 1 << (height - 1)
            digest.update(json.dumps([list(key), z], separators=(",", ":")).encode())
        checksums[height] = digest.hexdigest()
    # Keep native source/query iteration order, ensuring exact checksum comparison.
    rows = [
        [*key, [[mask, z] for z, mask in choices.items()]]
        for key, choices in grouped.items()
    ]
    full = (1 << 25) - 1
    if any(sum(mask for mask, z in row[5]) != full for row in rows):
        raise ValueError("Incomplete height coverage")
    data = dict(
        schema_version=1,
        map_id=map_id,
        radius=0,
        jump=4,
        heights=[1, 25],
        archive_sha256=provenance,
        source="Lossless native faz.B/Sm first-surface policy compaction; each [x,y,z,dx,dy,[[height_bitmask,destination_z_or_null]]] query preserves original result",
        rows=rows,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(data, separators=(",", ":")).encode()
    output.write_bytes(gzip.compress(raw, compresslevel=9, mtime=0))
    conversion_seconds = time.perf_counter() - began
    read_start = time.perf_counter()
    decoded = json.loads(gzip.decompress(output.read_bytes()))
    load_seconds = time.perf_counter() - read_start
    verify_start = time.perf_counter()
    for height in range(1, 26):
        digest = hashlib.sha256()
        count = 0
        for row in decoded["rows"]:
            matches = [z for mask, z in row[5] if mask & (1 << (height - 1))]
            if len(matches) != 1:
                raise ValueError("Ambiguous compact result")
            digest.update(
                json.dumps([row[:5], matches[0]], separators=(",", ":")).encode()
            )
            count += 1
        if count != rows_per_height[height] or digest.hexdigest() != checksums[height]:
            raise ValueError(f"Policy equivalence failed for height {height}")
    return dict(
        map_id=map_id,
        queries=len(rows),
        heights=25,
        distinct_results=sum(len(row[5]) for row in rows),
        old_bytes=old_bytes,
        compact_bytes=output.stat().st_size,
        raw_bytes=len(raw),
        size_reduction_percent=100 * (1 - output.stat().st_size / old_bytes),
        conversion_seconds=conversion_seconds,
        load_seconds=load_seconds,
        verification_seconds=time.perf_counter() - verify_start,
        equivalent_heights=25,
        policy_sha256=checksums,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("map_id", type=int)
    parser.add_argument(
        "--directory", type=Path, default=Path("server/protocol/forced-transitions")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    report = convert(args.directory, args.map_id, args.output)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
