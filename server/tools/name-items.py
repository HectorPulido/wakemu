#!/usr/bin/env python3
"""Add native Spanish names to item catalogs without network access."""
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    with zipfile.ZipFile(ROOT / "client/contents/i18n/i18n_es.jar") as jar:
        text = jar.read("texts_es.properties").decode("utf-8")
    names = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        if sep and key.startswith("content.15."):
            names[int(key.removeprefix("content.15."))] = value
    for path in sorted((ROOT / "server/protocol").glob("item-*.json")):
        data = json.loads(path.read_text())
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            continue
        rows = data["items"]
        for row in rows:
            original = dict(row)
            reference = row["reference"]
            row.clear()
            row.update(reference=reference, name=names.get(reference))
            row.update(
                {k: v for k, v in original.items() if k not in ("reference", "name")}
            )
        data["name_locale"] = "es"
        data["name_source"] = "i18n_es.jar/texts_es.properties; content.15.<reference>"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
        print(
            f'{path.name}: {sum(r["name"] is not None for r in rows)}/{len(rows)} names'
        )


if __name__ == "__main__":
    main()
