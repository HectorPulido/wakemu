"""Prepare exact-name/species-context resolutions without modifying evidence."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import unicodedata
import re


import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dungeon_reference_names import NAME_NORMALIZATION_POLICY, normalized_name


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Source path escapes repository")
    return path


def build_report(root, index, names, *, native_name_catalog, composition_directory):
    root = root.resolve()
    for source in index["sources"].values():
        if digest(safe_path(root, source["path"])) != source["sha256"]:
            raise ValueError("Native index source hash mismatch: " + source["path"])
    if (
        digest(safe_path(root, names["source"]["archive"]))
        != names["source"]["archive_sha256"]
    ):
        raise ValueError("Native name archive hash mismatch")
    definitions_source = index["sources"]["definitions"]
    definitions = json.loads(safe_path(root, definitions_source["path"]).read_text())
    by_id = {row["id"]: row for row in definitions}
    links = {row["guide_slug"]: row for row in index["guide_links"]}
    by_name = {}
    for row in names["monsters"]:
        by_name.setdefault(row["name_fr"], []).append(row["ref"])
    by_normalized_name = {}
    for row in names["monsters"]:
        if isinstance(row["name_fr"], str):
            by_normalized_name.setdefault(normalized_name(row["name_fr"]), []).append(
                row["ref"]
            )
    records = []
    for path in sorted(safe_path(root, composition_directory).glob("*.json")):
        document = json.loads(path.read_text())
        link = links.get(document["dungeon"]["slug"])
        context = None
        if link and link["status"] == "exact_unique":
            definition = by_id.get(link["client_definition_id"])
            if definition is None:
                raise ValueError("Native guide identity missing from definitions")
            context = dict(
                catalog=definitions_source["path"],
                catalog_sha256=definitions_source["sha256"],
                definition_id=definition["id"],
                species_field="raw_cno",
                species_refs=definition["raw_cno"],
            )
        for room in document["rooms"]:
            for number, monster in enumerate(room["monsters"]):
                exact_candidates = sorted(by_name.get(monster["name"], []))
                candidates = sorted(
                    set(by_normalized_name.get(normalized_name(monster["name"]), []))
                )
                remaining = [
                    ref
                    for ref in candidates
                    if context is None or ref in context["species_refs"]
                ]
                status = (
                    "resolved"
                    if len(remaining) == 1
                    else "ambiguous"
                    if remaining
                    else "unmatched"
                )
                records.append(
                    dict(
                        composition=str(path.relative_to(root)),
                        composition_sha256=digest(path),
                        room_order=room["order"],
                        monster_index=number,
                        guide_name=monster["name"],
                        name_key_contract=names["source"]["key_contract"],
                        native_name_catalog=native_name_catalog,
                        exact_name_candidates=exact_candidates,
                        normalized_name_candidates=candidates,
                        name_normalization_policy=NAME_NORMALIZATION_POLICY,
                        normalized_guide_name=normalized_name(monster["name"]),
                        context=context,
                        remaining_candidates=remaining,
                        status=status,
                        resolved_ref=remaining[0] if status == "resolved" else None,
                    )
                )
    return dict(
        schema_version=1,
        runtime_imported=False,
        matching_policy="Conservative normalized French typography intersected with exact native dungeon species pools; accents, articles and plurals retained; no fuzzy matching.",
        summary=dict(Counter(row["status"] for row in records)),
        records=records,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--index", required=True)
    parser.add_argument("--names", required=True)
    parser.add_argument("--compositions", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    report = build_report(
        root,
        json.loads(safe_path(root, args.index).read_text()),
        json.loads(safe_path(root, args.names).read_text()),
        native_name_catalog=args.names,
        composition_directory=args.compositions,
    )
    target = safe_path(root, args.output)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
