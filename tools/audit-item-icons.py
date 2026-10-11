#!/usr/bin/env python3
"""Audit native item inventory icons against the installed client archive."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-types", type=Path, required=True)
    parser.add_argument(
        "--archive", type=Path, default=Path("client/contents/gui_jar/gui.jar")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    native_bytes = args.native_types.read_bytes()
    native = json.loads(native_bytes)
    items = []
    with zipfile.ZipFile(args.archive) as archive:
        entries = {entry.filename: entry for entry in archive.infolist()}
        for row in native["items"]:
            reference = int(row["reference"])
            gfx_id = int(row["gfx_id"])
            icon_path = f"icons/items/64/{gfx_id}.tga"
            entry = entries.get(icon_path)
            valid = False
            width = height = depth = None
            if entry is not None:
                data = archive.read(icon_path)
                if len(data) >= 18:
                    width = int.from_bytes(data[12:14], "little")
                    height = int.from_bytes(data[14:16], "little")
                    depth = data[16]
                    valid = width > 0 and height > 0 and depth in (8, 16, 24, 32)
            items.append(
                {
                    "reference": reference,
                    "gfx_id": gfx_id,
                    "icon_path": icon_path,
                    "icon_exists": entry is not None,
                    "icon_valid_header": valid,
                    "icon_bytes": entry.file_size if entry else 0,
                    "icon_width": width,
                    "icon_height": height,
                    "icon_pixel_depth": depth,
                }
            )
    result = {
        "source": "Native aLO.bwX -> bGT.a/bJq.Wt -> fpC.bwX -> aTv.zD(itemsIconsPath); client/config.properties:166",
        "scope": "Inventory icon archive entry and TGA header only; equipped models, animations and item behavior are not verified.",
        "archive": str(args.archive),
        "archive_sha256": hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        "native_types": str(args.native_types),
        "native_types_sha256": hashlib.sha256(native_bytes).hexdigest(),
        "items": items,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    missing = sum(not row["icon_exists"] for row in items)
    invalid = sum(row["icon_exists"] and not row["icon_valid_header"] for row in items)
    print(f"{len(items)} items; {missing} missing icons; {invalid} invalid TGA headers")


if __name__ == "__main__":
    main()
