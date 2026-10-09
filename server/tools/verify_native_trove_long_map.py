"""Compare local PV-map topology against exported installed-client operations."""
import argparse
import hashlib
import json
from pathlib import Path

from wakfu_server.combat_trove_long_map import NativeTroveLongMap


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("oracle", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    contract = json.loads(
        (root / "server/protocol/native-trove-long-map.json").read_text()
    )
    native_jars = [
        root / "client/lib/wakfu-client.jar",
        root / "client/lib" / contract["trove_jar_name"],
    ]
    tracked = [
        Path(__file__).resolve(),
        root / "server/wakfu_server/combat/combat_trove_long_map.py",
        root / "server/protocol/native-trove-long-map.json",
        root / "sniffer/java/ExportNativeTroveLongMap.java",
        args.oracle,
        *native_jars,
    ]
    before = {str(path): digest(path) for path in tracked}
    rows = json.loads(args.oracle.read_text())
    mapping = NativeTroveLongMap()
    mismatches = []
    for index, row in enumerate(rows):
        if row["operation"] not in ("put", "remove"):
            raise ValueError("Unknown native oracle operation")
        getattr(mapping, row["operation"])(row["key"])
        actual = dict(
            capacity=len(mapping.state["keys"]),
            size=mapping.state["size"],
            free=mapping.state["free"],
            compact_removes=mapping.state["compact_removes"],
            order=list(mapping.order()),
        )
        differences = {
            key: dict(expected=row[key], actual=value)
            for key, value in actual.items()
            if row[key] != value
        }
        if differences:
            mismatches.append(dict(index=index, differences=differences))
    after = {str(path): digest(path) for path in tracked}
    result = dict(
        operations=len(rows),
        compared_fields=["capacity", "size", "free", "compact_removes", "order"],
        mismatches=mismatches,
        source_stable=before == after,
        source_hashes=before,
    )
    result["native_jar_hashes_match"] = (
        before[str(native_jars[0])] == contract["client_jar_sha256"]
        and before[str(native_jars[1])] == contract["trove_jar_sha256"]
    )
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "source_hashes"}
        )
    )
    return (
        0
        if not mismatches
        and result["source_stable"]
        and result["native_jar_hashes_match"]
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
