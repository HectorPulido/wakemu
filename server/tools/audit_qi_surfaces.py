"""Compare the pure QI lookup with the original map oracle's full cases."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from wakfu_server.combat_qi_snapshot import NativeQISnapshot
from wakfu_server.combat_qi_surfaces import NativeQISurfaces


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(root, map_id, topology):
    manifest = json.loads((root / "manifest.json").read_text())
    rows = [row for row in manifest["maps"] if row.get("map_id") == map_id]
    if len(rows) != 1 or rows[0]["status"] != "exported":
        raise ValueError("Map has no successful native surface export")
    row = rows[0]
    path = root / f"{map_id}.json"
    observed = {"surface_output": sha256(path), "topology": sha256(topology)}
    if (
        observed["surface_output"] != row["output_sha256"]
        or observed["topology"] != row["source_sha256"]
    ):
        raise ValueError("Native QI export provenance changed")
    data = json.loads(path.read_bytes())
    surfaces = NativeQISurfaces(data, map_id=map_id, source_sha256=observed["topology"])
    counts = dict(valid=0, blocked=0, wrong_z=0, missing_index=0, empty_columns=0)
    for bounds, columns in surfaces.chunks:
        cx, cy, width, height = bounds
        for y in range(cy, cy + height):
            for x in range(cx, cx + width):
                ordered = columns.get((x, y), ())
                if len(ordered) > 63:
                    raise ValueError("Column exceeds original oracle index domain")
                qi = NativeQISnapshot(dict(x=x, y=y, width=1, height=1, cell_masks=[0]))
                for index, expected in enumerate(ordered):
                    # Native ProbeNativeQISurfaces uses the same blocked bit.
                    qi.masks = (0x100 | index,)
                    actual = surfaces.i(qi, x, y, expected.z)
                    if actual != expected:
                        raise AssertionError("Selected native surface mismatch")
                    allowed = expected.bld != -1
                    if surfaces.j(qi, x, y, expected.z) != allowed:
                        raise AssertionError("Native QI.j result mismatch")
                    counts["valid" if allowed else "blocked"] += 1
                    other_z = ((expected.z + 1 + 32768) % 65536) - 32768
                    if surfaces.i(qi, x, y, other_z) is not None or surfaces.j(
                        qi, x, y, other_z
                    ):
                        raise AssertionError("Wrong altitude accepted")
                    counts["wrong_z"] += 1
                qi.masks = (len(ordered),)
                if surfaces.i(qi, x, y, 0) is not None or surfaces.j(qi, x, y, 0):
                    raise AssertionError("Missing surface index accepted")
                counts["missing_index"] += 1
                counts["empty_columns"] += not ordered
                if surfaces.i(qi, x - 1, y, 0) is not None:
                    raise AssertionError("Outside arena accepted")
    after = {"surface_output": sha256(path), "topology": sha256(topology)}
    if observed != after:
        raise ValueError("Native QI input changed during comparison")
    return dict(
        map_id=map_id,
        status="passed",
        counts=counts,
        input_sha256=observed,
        inputs_stable=True,
        scope="Pure lookup against all exported native oracle cases; no runtime or GUI",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--surfaces-root", type=Path, required=True)
    parser.add_argument("--map-id", type=int, required=True)
    parser.add_argument("--topology", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    result = run(args.surfaces_root, args.map_id, args.topology)
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))
