"""Resolve typographic title variants without translating or fuzzy name matching."""
import argparse
import copy
import json
from pathlib import Path
import re
import unicodedata


def normalized_title(text):
    text = re.sub(r"\s+Niv\.\s*\d+\s*$", "", text)
    text = unicodedata.normalize("NFKC", text).casefold().strip()
    text = re.sub(r"^(?:la|le|les)\s+", "", text)
    return "".join(character for character in text if character.isalnum())


def refine(index):
    output = copy.deepcopy(index)
    for link in output["guide_links"]:
        if link["status"] == "exact_unique":
            continue
        title = normalized_title(link["guide_name"])
        candidates = [
            row
            for row in output["native_dungeons"]
            if normalized_title(row["name_fr"]) == title
        ]
        level = re.search(r"Niv\.\s*(\d+)\s*$", link["guide_name"])
        if len(candidates) > 1 and level:
            candidates = [row for row in candidates if row["raw_aWb"] == int(level[1])]
        link["normalized_candidates"] = candidates
        if len(candidates) == 1:
            link.update(
                status="exact_unique",
                client_definition_id=candidates[0]["id"],
                candidates=candidates,
                identity_matching="typographic_title_normalization",
                normalization_policy="Unicode NFKC, casefold, punctuation removal, leading French definite article removal; optional explicit guide level equals native raw_aWb",
            )
    output["summary"]["exact_unique"] = sum(
        row["status"] == "exact_unique" for row in output["guide_links"]
    )
    output["summary"]["unmatched"] = sum(
        row["status"] == "unmatched" for row in output["guide_links"]
    )
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = refine(json.loads(args.input.read_text()))
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(output["summary"]))
