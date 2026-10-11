"""Curate native inventory exports without mutating catalog or player data."""
import argparse
import collections
import csv
import hashlib
import json
import re
import zipfile
from pathlib import Path


def locale_names(language):
    path = Path(f"client/contents/i18n/i18n_{language}.jar")
    with zipfile.ZipFile(path) as archive:
        texts = archive.read(f"texts_{language}.properties").decode("utf8")
    return {
        int(key[11:]): value
        for line in texts.splitlines()
        if "=" in line
        for key, value in [line.split("=", 1)]
        if key.startswith("content.15.")
    }


def exclusion_reasons(row, names, graphics, types, furniture_sources=None):
    ref = int(row["reference"])
    translated = [names[lang].get(ref, "") for lang in names]
    reasons = []
    if not row["name_es"].strip():
        reasons.append("missing_spanish_name")
    # Fragment parts are excluded across every category, not only Dofus.
    if any(re.search(r"fragment", name, re.I) for name in translated):
        reasons.append("fragment_or_fragment_container")
    if any(
        re.search(
            r"\b(admin|administrator|moderador|moderator|modérateur|game\s*master)\b",
            name,
            re.I,
        )
        for name in translated
    ):
        reasons.append("staff_role_name")
    if int(row["native_type_id"]) in {601, 687, 810}:
        reasons.append("native_fragment_type")
    if any(
        re.search(r"\b(test|debug|wip|placeholder)\b|\[(beta|bêta)\]", name, re.I)
        for name in translated
    ):
        reasons.append("test_beta_debug_name")
    if any(
        re.search(
            r"\b(obsolete|deprecated|obsoleto|obsoleta)\b|^(objeto|recurso) antiguo$",
            name,
            re.I,
        )
        for name in translated
    ):
        reasons.append("obsolete_name")
    if int(row["native_type_id"]) in {682, 683}:
        reasons.append("legacy_powder_or_rune")
    if int(row["native_type_id"]) == 604:
        reasons.append("set_container")
    if (
        furniture_sources is not None
        and row["use_action_class"] == "bIx"
        and ref not in furniture_sources
    ):
        reasons.append("missing_portable_furniture_source_mapping")
    lineage = set()
    type_id = int(row["native_type_id"])
    while type_id in types and type_id not in lineage:
        lineage.add(type_id)
        type_id = types[type_id]["parent_id"]
    if lineage & {727, 732, 837}:
        reasons.append("internal_test_or_wip_type")
    # Level zero is normal for pets, skins, emotes, titles and enchantment shards.
    if int(row["level"] or 0) <= 0 and lineage & {100, 118, 218}:
        reasons.append("nonpositive_equipment_level")
    graphic = graphics.get(ref)
    if graphic is None:
        reasons.append("graphics_not_verified")
    elif not graphic["icon_exists"]:
        reasons.append("missing_native_item_icon")
    elif not graphic.get("icon_valid_header", False):
        reasons.append("invalid_native_item_icon")
    return sorted(set(reasons))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=Path("docs/reports/item-shop-inventory-20261011")
    )
    parser.add_argument("--graphics", type=Path, required=True)
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=Path(".runtime/local/item-shop-inventory-20261011/catalog.json"),
    )
    args = parser.parse_args()
    source = args.source
    output = source / "curated"
    output.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader((source / "all-items.csv").open()))
    names = {lang: locale_names(lang) for lang in ["es", "en", "fr"]}
    types = {
        r["type_id"]: r
        for r in json.loads((source / "native-types.json").read_text())["types"]
    }
    graphic_document = json.loads(args.graphics.read_text())
    graphics = {r["reference"]: r for r in graphic_document["items"]}
    snapshot = json.loads(args.snapshot.read_text())
    furniture_sources = {
        r["source_item_ref"]
        for r in snapshot["documents"]["haven-bag-furniture-catalog.json"]["items"]
    }
    rejected, kept = [], []
    for row in rows:
        reasons = exclusion_reasons(row, names, graphics, types, furniture_sources)
        graphic = graphics.get(int(row["reference"]), {})
        enriched = dict(
            row,
            gfx_id=graphic.get("gfx_id", ""),
            icon_path=graphic.get("icon_path", ""),
            exclusion_reasons="|".join(reasons),
        )
        (rejected if reasons else kept).append(enriched)
    fields = list((kept or rejected)[0])

    def write(name, selected):
        with (output / name).open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(selected)

    keep_ids = {r["reference"] for r in kept}
    counts = {}
    for path in sorted(source.glob("*.csv")):
        selected = [
            dict(
                row,
                gfx_id=graphics[int(row["reference"])]["gfx_id"],
                icon_path=graphics[int(row["reference"])]["icon_path"],
                exclusion_reasons="",
            )
            for row in csv.DictReader(path.open())
            if row["reference"] in keep_ids
        ]
        write(path.name, selected)
        counts[path.stem] = len(selected)
    write("excluded-items.csv", rejected)
    summary = dict(
        input_items=len(rows),
        retained=len(kept),
        excluded=len(rejected),
        counts=counts,
        reason_counts=dict(
            collections.Counter(
                reason
                for row in rejected
                for reason in row["exclusion_reasons"].split("|")
            )
        ),
        retained_level_zero=sum(int(r["level"] or 0) == 0 for r in kept),
        source_sha256={
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [
                source / "all-items.csv",
                source / "native-types.json",
                args.graphics,
                args.snapshot,
            ]
        },
        graphics_source=graphic_document.get("source"),
        graphics_archive_sha256=graphic_document.get("archive_sha256"),
        locale_sha256={
            lang: hashlib.sha256(
                Path(f"client/contents/i18n/i18n_{lang}.jar").read_bytes()
            ).hexdigest()
            for lang in names
        },
        scope="Static inventory curation, not gameplay completion certification; no database changes.",
    )
    summary["artifacts_sha256"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(output.glob("*.csv"))
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
