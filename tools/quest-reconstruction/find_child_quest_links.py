#!/usr/bin/env python3
"""Find reviewed-candidate child missions explicitly named by parent objectives.

This is an evidence index, not an installer. Translated names and objective
text suggest relationships but do not prove an original server side effect.
Ambiguous translated titles and conflicting languages are retained visibly.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import unicodedata


ROOT = Path(__file__).resolve().parents[2]
PREFIX = {
    "en": re.compile(r"^\s*complete\s+the\s+quest\s*:?\s+", re.I),
    "es": re.compile(r"^\s*completar\s+la\s+misi[oó]n\s*:?\s+", re.I),
    "fr": re.compile(r"^\s*accomplir\s+la\s+qu[eê]te\s*:?\s+", re.I),
    "pt": re.compile(r"^\s*completar\s+a\s+(?:miss[aã]o|conquista)\s*:?\s+", re.I),
}


def normalize(value):
    """Normalize spacing, punctuation and Unicode case, not title semantics."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def referenced_title(language, objective):
    if not isinstance(objective, str) or language not in PREFIX:
        return None
    match = PREFIX[language].match(objective)
    if match is None:
        return None
    title = objective[match.end() :].strip()
    pairs = (('"', '"'), ("“", "”"), ("«", "»"))
    for opening, closing in pairs:
        if title.startswith(opening) and title.endswith(closing) and len(title) > 1:
            title = title[len(opening) : -len(closing)].strip()
            break
    return normalize(title) if title else None


def extract(data):
    definitions = data["definitions"]
    translated = data["translations"]
    title_indexes = {}
    for language in PREFIX:
        texts = translated.get(language, {})
        index = defaultdict(set)
        for row in definitions:
            if row.get("native_class") != "aJM" or row.get("aqb") is not False:
                continue
            title = texts.get(f'content.62.{row["d"]}')
            if isinstance(title, str) and title.strip():
                index[normalize(title)].add(row["d"])
        title_indexes[language] = index

    candidates = []
    for parent in definitions:
        if parent.get("native_class") != "aJM" or parent.get("aqb") is not False:
            continue
        for objective in parent.get("cjJ", []):
            evidence = []
            for language in PREFIX:
                texts = translated.get(language, {})
                text = texts.get(f'content.64.{objective["d"]}')
                title = referenced_title(language, text)
                if title is None:
                    continue
                ids = sorted(title_indexes[language].get(title, set()) - {parent["d"]})
                if ids:
                    evidence.append(
                        {"language": language, "objective_text": text, "child_ids": ids}
                    )
            if not evidence:
                continue
            supported = set.intersection(*(set(row["child_ids"]) for row in evidence))
            if len(supported) == 1 and all(
                len(row["child_ids"]) == 1 for row in evidence
            ):
                status = (
                    "unique_exact_multilingual"
                    if len(evidence) > 1
                    else "unique_exact_single_language"
                )
            elif len(supported) == 1:
                status = "resolved_by_cross_language"
            elif supported:
                status = "ambiguous"
            else:
                status = "conflicting_languages"
            candidates.append(
                {
                    "parent_id": parent["d"],
                    "objective_id": objective["d"],
                    "objective_prerequisite": objective.get("ckc", ""),
                    "objective_completion_criterion": objective.get("cke", ""),
                    "objective_counters": objective.get("ckf", []),
                    "status": status,
                    "possible_child_ids": sorted(supported),
                    "evidence": evidence,
                }
            )
    return candidates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--definitions",
        type=Path,
        default=ROOT / ".runtime/quest-extraction/native-quest-definitions.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    candidates = extract(json.loads(args.definitions.read_text(encoding="utf-8")))
    result = {
        "schema": "quest-child-link-candidates-v1",
        "policy": "Textual candidates only; never install without independent event and activation evidence.",
        "candidates": candidates,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    counts = defaultdict(int)
    for candidate in candidates:
        counts[candidate["status"]] += 1
    print(
        json.dumps(
            {"candidate_objectives": len(candidates), "statuses": counts},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
