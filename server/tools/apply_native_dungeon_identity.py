"""Apply selected exact dungeon identities; never infer template IDs or import runtime data."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import re
import zipfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(root, index, routes_path, composition_path, slug):
    root = root.resolve()
    for source in index["sources"].values():
        path = (root / source["path"]).resolve()
        if not path.is_relative_to(root) or digest(path) != source["sha256"]:
            raise ValueError("Native index source hash or path mismatch")
    matches = [row for row in index["guide_links"] if row["guide_slug"] == slug]
    if len(matches) != 1 or matches[0]["status"] != "exact_unique":
        raise ValueError("Selected guide identity is unresolved or ambiguous")
    link = matches[0]
    if (
        len(link["candidates"]) != 1
        or link["candidates"][0]["id"] != link["client_definition_id"]
    ):
        raise ValueError("Native identity evidence is inconsistent")
    definitions = json.loads(
        (root / index["sources"]["definitions"]["path"]).read_text()
    )
    candidates = [
        row for row in definitions if row["id"] == link["client_definition_id"]
    ]
    expected = dict(link["candidates"][0])
    native_name = expected.pop("name_fr")
    if candidates != [expected]:
        raise ValueError("Native definition evidence changed")
    catalog = json.loads((root / index["sources"]["catalog"]["path"]).read_text())
    originals = [row for row in catalog["dungeons"] if row["dungeon"]["slug"] == slug]
    document = json.loads(composition_path.read_text())
    if originals != [document] or document["source"]["url"] != link["guide_url"]:
        raise ValueError("Composition changed since index generation")
    if "i18n" not in index["sources"]:
        raise ValueError("Native localization source is required")
    if "i18n" in index["sources"]:
        archive = root / index["sources"]["i18n"]["path"]
        properties = (
            zipfile.ZipFile(archive).read("texts_fr.properties").decode("utf-8")
        )
        matches = re.findall(
            r"^content\.137\." + str(expected["id"]) + r"=(.*)$",
            properties,
            re.MULTILINE,
        )
        decoded = [
            re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m[1], 16)), name)
            for name in matches
        ]
        if decoded != [native_name] or native_name not in link["exact_names_checked"]:
            raise ValueError("Native localization evidence contradicts exact link")
    routes = [
        row
        for row in json.loads(routes_path.read_text())
        if row["definition_id"] == link["client_definition_id"]
    ]
    if len(routes) != 1:
        raise ValueError(
            "Entry route is absent or ambiguous; template cannot be inferred"
        )
    route = routes[0]
    if (
        route["start_map_id"] not in expected["raw_aHA"]
        or route["entry_map_id"] != expected["raw_arM"]
    ):
        raise ValueError("Entry route contradicts native map evidence")
    identity = {
        "client_definition_id": expected["id"],
        "client_template_id": route["template_id"],
        "client_asset_map_id": route["start_map_id"],
    }
    if any(type(value) is not int or value <= 0 for value in identity.values()):
        raise ValueError("Native identity values must be positive integers")
    updated = copy.deepcopy(document)
    for key, value in identity.items():
        if updated["dungeon"][key] not in (None, value):
            raise ValueError("Existing dungeon identity conflicts with evidence")
        updated["dungeon"][key] = value
    report = {
        "schema_version": 1,
        "runtime_imported": False,
        "slug": slug,
        "identity": identity,
        "composition_sha256_before": digest(composition_path),
        "route_catalog_sha256": digest(routes_path),
        "entry_route": route,
        "native_name_contract": index["name_contract"],
        "native_sources": index["sources"],
    }
    return updated, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--routes", type=Path, required=True)
    parser.add_argument("--composition", type=Path, required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    updated, report = prepare(
        args.root,
        json.loads(args.index.read_text()),
        args.routes,
        args.composition,
        args.slug,
    )
    report["native_index_sha256"] = digest(args.index)
    if args.apply:
        if args.backup is None or args.backup.exists():
            raise ValueError("Applying requires a new backup path")
        original = args.composition.read_bytes()
        if hashlib.sha256(original).hexdigest() != report["composition_sha256_before"]:
            raise ValueError("Composition changed during preflight")
        args.backup.parent.mkdir(parents=True, exist_ok=True)
        with args.backup.open("xb") as handle:
            handle.write(original)
        with tempfile.NamedTemporaryFile(
            mode="w", dir=args.composition.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(updated, ensure_ascii=False, indent=2) + "\n")
        try:
            if args.composition.read_bytes() != original:
                raise ValueError("Composition changed before replacement")
            os.replace(temporary, args.composition)
        finally:
            temporary.unlink(missing_ok=True)
    report["applied"] = args.apply
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"identity": report["identity"], "applied": report["applied"]}))


if __name__ == "__main__":
    main()
