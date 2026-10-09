"""Export evidence-based exact guide/native dungeon links without importing runtime data."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile


def strip_level_suffix(title):
    """Remove the website's trailing display level; preserve the actual name exactly."""
    return re.sub(r"\s+Niv\.\s*\d+\s*$", "", title).strip()


def export_index(definitions, properties, guides, canonical):
    names = {}
    for line in properties.splitlines():
        match = re.match(r"^content\.137\.(\d+)=(.*)$", line)
        if match:
            names[int(match[1])] = re.sub(
                r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m[1], 16)), match[2]
            )
    native = [
        dict(definition, name_fr=names.get(definition["id"]))
        for definition in definitions
    ]
    by_name = {}
    for row in native:
        if row["name_fr"]:
            by_name.setdefault(row["name_fr"], []).append(row)
    titles = {row["canonical_url"]: row["title"] for row in canonical["guides"]}
    links = []
    for guide in guides["dungeons"]:
        url = guide["source"]["url"]
        exact_names = {guide["dungeon"]["name"]}
        if url in titles:
            exact_names.add(strip_level_suffix(titles[url]))
        candidates = {
            row["id"]: row for name in exact_names for row in by_name.get(name, [])
        }
        rows = sorted(candidates.values(), key=lambda row: row["id"])
        links.append(
            {
                "guide_url": url,
                "guide_slug": guide["dungeon"]["slug"],
                "guide_name": guide["dungeon"]["name"],
                "exact_names_checked": sorted(exact_names),
                "status": "exact_unique"
                if len(rows) == 1
                else "ambiguous"
                if rows
                else "unmatched",
                "client_definition_id": rows[0]["id"] if len(rows) == 1 else None,
                "candidates": rows,
            }
        )
    return {
        "schema_version": 1,
        "runtime_imported": False,
        "name_contract": "bqf.getName -> aTF.a(137, eQL.d()); content.137.<aKU.id>",
        "matching_policy": "Exact text only; strip trailing website Niv.<number>; no case folding, punctuation aliases, translation or fuzzy matching.",
        "summary": {
            "native_definitions": len(native),
            "native_names_found": sum(bool(row["name_fr"]) for row in native),
            "guides": len(links),
            **{
                status: sum(row["status"] == status for row in links)
                for status in ("exact_unique", "ambiguous", "unmatched")
            },
        },
        "native_dungeons": native,
        "guide_links": links,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--definitions", type=Path, required=True)
    parser.add_argument("--i18n", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--canonical-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = zipfile.ZipFile(args.i18n).read("texts_fr.properties")
    result = export_index(
        json.loads(args.definitions.read_text()),
        raw.decode("utf-8"),
        json.loads(args.catalog.read_text()),
        json.loads(args.canonical_index.read_text()),
    )
    result["sources"] = {
        label: {
            "path": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for label, path in [
            ("definitions", args.definitions),
            ("i18n", args.i18n),
            ("catalog", args.catalog),
            ("canonical_index", args.canonical_index),
        ]
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
