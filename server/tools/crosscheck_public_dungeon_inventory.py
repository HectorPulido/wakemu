"""Compare the archived public listing to native identities without fuzzy merges."""
from collections import Counter
import json
from pathlib import Path
import re
import unicodedata


def normalize(text):
    text = re.sub(r"\s+Niv\.\s*\d+\s*$", "", text)
    return re.sub(
        r"[^a-z0-9]",
        "",
        unicodedata.normalize("NFKD", text.casefold())
        .encode("ascii", "ignore")
        .decode(),
    )


def run():
    directory = Path("docs/reports/dungeons")
    public = json.loads((directory / "public-current-index.json").read_text())
    inventory = json.loads((directory / "inventory.json").read_text())
    names = {}
    for row in inventory["records"]:
        candidates = [
            (row["native"] or {}).get("name_fr", ""),
            row.get("name_es") or "",
        ]
        candidates.extend(g.get("name", "") for g in row["guides"])
        candidates.extend(g["slug"].replace("-", " ") for g in row["guides"])
        for name in candidates:
            if name:
                names.setdefault(normalize(name), set()).add(row["key"])
    for record in public["records"]:
        matches = sorted(names.get(normalize(record["name_fr"]), set()))
        record["local_identity_candidates"] = matches
        record["identity_status"] = (
            "normalized_unique"
            if len(matches) == 1
            else "ambiguous"
            if matches
            else "unresolved_name_not_proof_absent"
        )
    public["summary"] = {
        "public_listing_rows": len(public["records"]),
        "public_unique_names": len({r["name_fr"] for r in public["records"]}),
        "category_counts": dict(
            Counter(
                "quest"
                if "Quêtes" in r["public_section"]
                else "event"
                if "Événementiels" in r["public_section"]
                else "level_dungeon"
                for r in public["records"]
            )
        ),
        "identity_counts": dict(
            Counter(r["identity_status"] for r in public["records"])
        ),
    }
    (directory / "public-current-crosscheck.json").write_text(
        json.dumps(public, ensure_ascii=False, indent=2) + "\n"
    )
    lines = [
        "# Public-version crosscheck",
        "",
        "Checked 2026-10-09 against the [WakfuLabs public index](https://wakfulabs.com/dungeons/) and [MethodWakfu dungeon index](https://methodwakfu.com/donjons/). These are community references, not an official exhaustive game registry. Official wakfu.com searches returned no accessible matching source, so present-live completeness is not certified.",
        "",
        "## Version and scope",
        "",
        "The public listing has 120 dungeon listing rows: 109 level-bracket entries, seven quest entries and four event entries. Mineral Tower occurs in three level brackets, giving 118 distinct display names. Ten dimensional rifts appear separately on the page and are excluded from these dungeon totals; ultimate bosses are reviewed separately. Counts describe source coverage, not game totals.",
        "",
        "Our installed-client inventory has 151 native definitions plus five legacy guide entries. A native catalog can retain legacy, Neo-server, quest and rift definitions that are not equivalent to current public guide entries. Conversely an unmatched public spelling does not prove a missing client dungeon. No fuzzy identity is activated.",
        "",
        "Room-count differences are material: the public index now labels multiple dungeons with two rooms while older guide-derived configurations retain three or four. For example Blopera is two publicly versus four locally; E-Bou two versus four; Crocodailles two versus four. Therefore guide publication dates and per-room compositions must be checked before correcting runtime layouts.",
        "",
        "New-looking names are not automatically missing: Machines de Nox, Clan de Bworkana, Primassifs and Férociraptors are checked against native IDs below. They must not be treated as new unsupported game content based only on an incomplete 87-guide bundle.",
        "",
        "## Listing reconciliation",
        "",
        "| Public name | Category / format | Local identity candidates | Status |",
        "| --- | --- | --- | --- |",
    ]
    for record in public["records"]:
        values = [
            record["name_fr"],
            record["public_section"] + " / " + str(record["format"]),
            ", ".join(record["local_identity_candidates"])
            or "None by conservative name match",
            record["identity_status"],
        ]
        lines.append("| " + " | ".join(v.replace("|", "\\|") for v in values) + " |")
    lines.extend(
        [
            "",
            "## Remaining completeness work",
            "",
            "Resolve unmatched spellings using exact localized IDs, maps, entrance objects and source room plans; do not assume absence. Quest and event entries need independent map/quest authority discovery, and event availability dates. Current public page alone does not describe hidden rooms, interaction scripts or boss mechanics. The complete native object inventory and guide provenance remain in inventory.json and DETAILS.md.",
            "",
            "Reproduce crosscheck: `python3 server/tools/crosscheck_public_dungeon_inventory.py`. Public input is the dated structured listing in public-current-index.json; refresh from the linked source before making future version assertions.",
            "",
        ]
    )
    (directory / "PUBLIC-VERSION-CROSSCHECK.md").write_text("\n".join(lines))
    print(json.dumps(public["summary"], indent=2))


if __name__ == "__main__":
    run()
