#!/usr/bin/env python3
"""Locate combat objectives naming native monster references, without asserting event semantics."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[2]
KILL = re.compile(
    r"\b(?:vencer|vence|venced|derrotar|derrota|derrotad|matar|mata|eliminar|elimina|combatir|combate|enfrentarse|enfrenta|aniquilar|aniquila|acabar)\b",
    re.I,
)


def extract(document, language_bytes):
    names = {}
    for line in language_bytes.decode("utf8").splitlines():
        key, sep, value = line.partition("=")
        if sep and key.startswith("content.7.") and key[10:].isdigit() and value:
            names[int(key[10:])] = value
    by_name = {}
    for ref, name in names.items():
        # Exclude markup and templated names: these are unsuitable for plain text matching.
        if len(name) >= 4 and not any(c in name for c in "{}[]<>\\"):
            by_name.setdefault(name.casefold(), []).append(ref)
    pattern = re.compile(
        r"(?<!\w)("
        + "|".join(re.escape(n) for n in sorted(by_name, key=len, reverse=True))
        + r")(?!\w)",
        re.I,
    )
    es = document["translations"]["es"]
    rows = []
    for definition in document["definitions"]:
        if definition["aeV"] not in (1, 2, 3, 4, 5):
            continue
        for objective in definition["cjJ"]:
            sentence = es.get(f"content.64.{objective['d']}", "")
            if not KILL.search(sentence):
                continue
            hits = []
            for match in pattern.finditer(sentence):
                key = match.group().casefold()
                hits.append(
                    {
                        "text": match.group(),
                        "reference_ids": by_name[key],
                        "ambiguous_name": len(by_name[key]) != 1,
                    }
                )
            if not hits:
                continue
            rows.append(
                {
                    "definition_id": definition["d"],
                    "objective_id": objective["d"],
                    "title_es": es.get(f"content.62.{definition['d']}"),
                    "objective_es": sentence,
                    "monster_name_matches": hits,
                    "native_type": definition["aeV"],
                    "minimum_level": definition["cjP"],
                    "duration_seconds": definition["cjL"],
                    "period_seconds": definition["cjU"],
                    "availability_criterion": definition["cjI"],
                    "visibility_criterion": definition["aHe"],
                    "objective_criteria": [objective["ckc"], objective["cke"]],
                    "markers": objective["ckd"],
                    "all_objective_ids": [o["d"] for o in definition["cjJ"]],
                    "native_rewards": definition["cjK"],
                    "event_binding": None,
                }
            )
    return {
        "schema_version": 1,
        "source_sha256": document.get("source_sha256", {}),
        "language_properties_sha256": hashlib.sha256(language_bytes).hexdigest(),
        "warning": "Textual name matches only: references may name variants, families or unintended targets; they do not establish start, kill event or game conditions.",
        "counts": {
            "objectives": len(rows),
            "definitions": len({r["definition_id"] for r in rows}),
            "with_ambiguous_name": sum(
                any(x["ambiguous_name"] for x in r["monster_name_matches"])
                for r in rows
            ),
            "periodic_objectives": sum(r["period_seconds"] > 0 for r in rows),
            "timed_objectives": sum(r["duration_seconds"] > 0 for r in rows),
            "single_objective_definitions": len(
                {r["definition_id"] for r in rows if len(r["all_objective_ids"]) == 1}
            ),
            "types": dict(Counter(str(r["native_type"]) for r in rows)),
        },
        "candidates": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / ".runtime/quest-extraction/native-quest-definitions.json",
    )
    parser.add_argument(
        "--language", type=Path, default=ROOT / "client/contents/i18n/i18n_es.jar"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / ".runtime/quest-reconstruction/named-combat-objectives.json",
    )
    args = parser.parse_args()
    with zipfile.ZipFile(args.language) as archive:
        language = archive.read("texts_es.properties")
    result = extract(json.loads(args.input.read_text()), language)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
