#!/usr/bin/env python3
"""Export real native item TGA graphics as shop PNG or compact JPEG assets."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import zipfile

from PIL import Image


def export_icons(
    native_path, selection_path, archive_path, output, image_format="jpeg"
):
    native = json.loads(Path(native_path).read_text())
    graphics = {int(row["reference"]): int(row["gfx_id"]) for row in native["items"]}
    with Path(selection_path).open(newline="") as source:
        references = sorted({int(row["reference"]) for row in csv.DictReader(source)})
    output = Path(output)
    icons = output / "icons"
    icons.mkdir(parents=True, exist_ok=True)
    entries = []
    missing = []
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        for reference in references:
            graphic = graphics.get(reference, 0)
            member = f"icons/items/64/{graphic}.tga"
            if not graphic or member not in names:
                missing.append({"reference": reference, "gfx_id": graphic})
                continue
            png_path = icons / f"{reference}.png"
            # Preserve existing transparent PNG originals when exporting JPEG.
            if image_format == "jpeg" and png_path.is_file():
                with Image.open(png_path) as original:
                    image = original.convert("RGBA")
            else:
                # Pillow decodes native TGA origin and alpha flags correctly.
                with Image.open(io.BytesIO(archive.read(member))) as original:
                    image = original.convert("RGBA")
            image.thumbnail((128, 128), Image.Resampling.LANCZOS)
            if image_format == "jpeg":
                matte = Image.new("RGB", image.size, (32, 32, 32))
                matte.paste(image, mask=image.getchannel("A"))
                matte.save(
                    icons / f"{reference}.jpg", format="JPEG", quality=82, optimize=True
                )
            else:
                image.save(png_path, format="PNG", optimize=True)
            entries.append(
                {
                    "reference": reference,
                    "gfx_id": graphic,
                    "width": image.width,
                    "height": image.height,
                }
            )
    manifest = {
        "source": str(archive_path),
        "selection": str(selection_path),
        "selection_sha256": hashlib.sha256(
            Path(selection_path).read_bytes()
        ).hexdigest(),
        "count": len(entries),
        "format": image_format,
        "jpeg_quality": 82 if image_format == "jpeg" else None,
        "jpeg_matte_rgb": [32, 32, 32] if image_format == "jpeg" else None,
        "png_bytes": sum(p.stat().st_size for p in icons.glob("*.png")),
        "jpeg_bytes": sum(p.stat().st_size for p in icons.glob("*.jpg")),
        "missing": missing,
        "icons": entries,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    if missing:
        raise RuntimeError(
            f"{len(missing)} selected items lack native icons; see manifest.json"
        )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--native",
        default=".runtime/local/item-shop-inventory-20261011/native-types.json",
    )
    parser.add_argument(
        "--selection", default="docs/reports/item-pricing-20261011/prices.csv"
    )
    parser.add_argument("--archive", default="client/contents/gui_jar/gui.jar")
    parser.add_argument("--output", default=".runtime/local/shop-assets")
    parser.add_argument("--format", choices=("jpeg", "png"), default="jpeg")
    args = parser.parse_args()
    result = export_icons(
        args.native, args.selection, args.archive, args.output, args.format
    )
    print(
        json.dumps(
            {
                "exported": result["count"],
                "missing": len(result["missing"]),
                "output": args.output,
            }
        )
    )


if __name__ == "__main__":
    main()
