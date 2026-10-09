#!/usr/bin/env python3
"""Validate archived dungeon evidence without treating it as runtime spawn data."""
import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]


def validate_document(document, schema, guide=None, check_files=False):
    errors = [
        f"schema: {error.json_path}: {error.message}"
        for error in Draft202012Validator(
            schema, format_checker=FormatChecker()
        ).iter_errors(document)
    ]
    if errors:
        return errors
    source = document["source"]
    aliases = {source["url"]}
    if guide is not None:
        aliases = set(guide.get("aliases", [])) | {guide["canonical_url"]}
        if source["url"] not in aliases:
            errors.append("source URL does not match the indexed guide")
    orders = [room["order"] for room in document["rooms"]]
    if orders != sorted(set(orders)):
        errors.append("room orders must be unique and increasing")
    complete_rooms = True
    for room in document["rooms"]:
        if room["composition_status"] != "complete":
            complete_rooms = False
        if room["composition_status"] == "complete" and not room["monsters"]:
            errors.append(f"room {room['order']}: complete composition has no monsters")
        evidence = list(room["evidence"])
        for monster in room["monsters"]:
            unknown = {
                key
                for key in ("ref_id", "count", "min_level", "max_level")
                if monster[key] is None
            }
            if monster["role"] == "unknown":
                unknown.add("role")
            if unknown != set(monster["unknown_fields"]):
                errors.append(
                    f"room {room['order']}: inconsistent unknown_fields for {monster['name']}"
                )
            if monster["min_level"] is not None and monster["max_level"] is not None:
                if monster["min_level"] > monster["max_level"]:
                    errors.append(
                        f"room {room['order']}: minimum level exceeds maximum"
                    )
            if room["composition_status"] == "complete" and monster["count"] is None:
                errors.append(
                    f"room {room['order']}: complete composition has unknown count"
                )
            evidence.extend(monster["evidence"])
        for item in evidence:
            image_urls = (
                {image["url"] for image in guide.get("images", [])} if guide else set()
            )
            allowed_urls = aliases | image_urls if item["kind"] == "image" else aliases
            if (
                item["kind"] != "client_catalog"
                and item["source_url"] not in allowed_urls
            ):
                errors.append(
                    f"room {room['order']}: evidence URL belongs to another guide"
                )
            if check_files:
                path = Path(item["archive_path"])
                path = path if path.is_absolute() else ROOT / path
                if not path.is_file():
                    errors.append(
                        f"room {room['order']}: missing evidence file {item['archive_path']}"
                    )
    if document["extraction"]["status"] == "complete" and (
        not orders or not complete_rooms
    ):
        errors.append(
            "complete extraction requires at least one room and all compositions complete"
        )
    if check_files:
        directory = Path(source["archive_directory"])
        directory = directory if directory.is_absolute() else ROOT / directory
        hashes = (
            {
                hashlib.sha256(p.read_bytes()).hexdigest()
                for p in directory.iterdir()
                if p.is_file() and p.suffix in (".html", ".txt")
            }
            if directory.is_dir()
            else set()
        )
        if source["article_sha256"] not in hashes:
            errors.append("article SHA-256 does not match archived HTML or text")
    return errors


def validate_archive(index, directory, schema, check_files=False):
    guides = index["guides"]
    by_url = {
        alias: guide
        for guide in guides
        for alias in set(guide.get("aliases", [])) | {guide["canonical_url"]}
    }
    documents, errors, seen = [], {}, {}
    for path in sorted(directory.glob("*.json")):
        try:
            document = json.loads(path.read_text())
        except (ValueError, OSError) as exc:
            errors[str(path)] = [str(exc)]
            continue
        url = document.get("source", {}).get("url")
        guide = by_url.get(url)
        problems = validate_document(document, schema, guide, check_files)
        if guide is None:
            problems.append("source URL is absent from canonical index")
        else:
            canonical = guide["canonical_url"]
            if canonical in seen:
                problems.append(f"duplicate guide also in {seen[canonical]}")
            seen[canonical] = str(path)
        if problems:
            errors[str(path)] = problems
        documents.append(document)
    missing = [
        guide["canonical_url"] for guide in guides if guide["canonical_url"] not in seen
    ]
    return {
        "files": len(documents),
        "indexed_guides": len(guides),
        "missing": missing,
        "errors": errors,
        "valid": not missing and not errors,
        "independently_reviewed": sum(
            d.get("extraction", {}).get("reviewed") is True for d in documents
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--archive", type=Path, default=ROOT / ".runtime/local/methodwakfu-dungeons"
    )
    parser.add_argument("--check-files", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    schema = json.loads(
        (ROOT / "server/protocol/dungeon-room-composition.schema.json").read_text()
    )
    Draft202012Validator.check_schema(schema)
    result = validate_archive(
        json.loads((args.archive / "canonical-index.json").read_text()),
        args.archive / "compositions",
        schema,
        args.check_files,
    )
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered)
    print(rendered, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
