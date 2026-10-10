"""Resolve boss identities from exact archived guide headings and native names."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def extract(inventory, names):
    by_ref = {m["ref"]: m.get("name_fr") for m in names["monsters"]}
    records = []
    for dungeon in inventory["records"]:
        evidence = []
        for guide in dungeon["guides"]:
            path = Path(guide["source"]["archive_directory"]) / "article.txt"
            if not path.is_file():
                continue
            raw = path.read_bytes()
            for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
                match = re.fullmatch(
                    r"\s*\d+(?:\.\d+)*\s*[–—-]\s*(.+?)\s*\(Boss\)\s*", line
                )
                if not match:
                    continue
                matches = [
                    m["ref_id"]
                    for m in dungeon["native_species_pool"]
                    if by_ref.get(m["ref_id"]) == match.group(1).strip()
                ]
                if len(matches) == 1:
                    evidence.append(
                        dict(
                            ref_id=matches[0],
                            native_name=match.group(1).strip(),
                            source_url=guide["source"]["url"],
                            archive_path=str(path),
                            article_sha256=hashlib.sha256(raw).hexdigest(),
                            line=line_number,
                            excerpt=line,
                        )
                    )
        references = sorted({e["ref_id"] for e in evidence})
        records.append(
            dict(
                key=dungeon["key"],
                boss_references=references if len(references) == 1 else [],
                status="exact_native_name_in_boss_heading"
                if len(references) == 1
                else "unresolved",
                evidence=evidence,
            )
        )
    return dict(
        schema_version=1,
        authority="Archived explicit boss heading joined to exact native French name within dungeon species pool; no inferred levels or room counts",
        native_names_source=names["source"],
        records=records,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory", type=Path, default=Path("docs/reports/dungeons/inventory.json")
    )
    parser.add_argument(
        "--names",
        type=Path,
        default=Path(
            ".runtime/local/methodwakfu-dungeons/native-monster-names-fr.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "docs/reports/dungeons/EXACT-BOSS-IDENTITY-EVIDENCE-20261010.json"
        ),
    )
    args = parser.parse_args()
    result = extract(
        json.loads(args.inventory.read_text()), json.loads(args.names.read_text())
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {"resolved": sum(bool(r["boss_references"]) for r in result["records"])}
        )
    )


if __name__ == "__main__":
    main()
