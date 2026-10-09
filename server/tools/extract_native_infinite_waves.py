#!/usr/bin/env python3
"""Extract the separate native aLF catalog; never synthesize wave compositions."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def validate_rows(rows):
    if not isinstance(rows, list) or not rows:
        raise ValueError("Missing native infinite-wave catalog")
    identities = set()
    for row in rows:
        for key in ("id", "raw_cpb", "raw_cpc", "raw_rI", "raw_cpf", "raw_cnn"):
            if type(row.get(key)) is not int:
                raise ValueError("Invalid native field " + key)
        if row["id"] <= 0 or row["id"] in identities:
            raise ValueError("Duplicate or invalid native definition")
        identities.add(row["id"])
        refs = row.get("raw_cpd_cpi")
        locations = row.get("raw_cpe")
        if not isinstance(refs, list) or any(
            type(i) is not int or i <= 0 for i in refs
        ):
            raise ValueError("Invalid native reference list")
        if not isinstance(locations, list) or any(
            not isinstance(location, dict)
            or type(location.get("raw_arM")) is not int
            or type(location.get("raw_cnn")) is not int
            for location in locations
        ):
            raise ValueError("Invalid native exterior/type list")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--jdk", type=Path, required=True, help="JDK home, version 21+")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="wakemu-rift-extract-") as directory:
        temp = Path(directory)
        subprocess.run(
            [
                str(args.jdk / "bin/javac"),
                "-proc:none",
                "-cp",
                "client/lib/*",
                "-d",
                str(temp),
                "client-tools/java/RiftCatalogProbe.java",
            ],
            cwd=ROOT,
            check=True,
        )
        raw = temp / "raw.json"
        subprocess.run(
            [
                str(args.jdk / "bin/java"),
                "-cp",
                str(temp) + ":client/lib/*",
                "RiftCatalogProbe",
                str(raw),
            ],
            cwd=ROOT,
            check=True,
        )
        rows = validate_rows(json.loads(raw.read_text()))
    monsters = json.loads((ROOT / "server/protocol/monsters.json").read_text())[
        "monsters"
    ]
    known = {row["ref"] for row in monsters}
    unknown = sorted({ref for row in rows for ref in row["raw_cpd_cpi"]} - known)
    result = dict(
        source="aLF via apw; baV loads byY; raw fields retained",
        definitions=rows,
        unresolved_monster_references=unknown,
        client_jar_sha256=hashlib.sha256(
            (ROOT / "client/lib/wakfu-client.jar").read_bytes()
        ).hexdigest(),
        limits="Catalog supplies reference pools, not per-wave composition/count/order/timing/rewards",
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Extracted {len(rows)} definitions; unresolved references: {len(unknown)}")


if __name__ == "__main__":
    main()
