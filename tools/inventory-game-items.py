"""Build a traceable, overlapping item inventory from a frozen native snapshot."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path


def build(snapshot, cosmetics, native_types=None):
    docs = snapshot["documents"]
    items = {
        r["reference"]: r
        for r in docs["item-stack-rules.json"]["items"]
        if r["reference"] > 0
    }
    equipment = {r["reference"]: r for r in docs["item-equipment-rules.json"]["items"]}
    actions = {r["reference"]: r for r in docs["item-action-rules.json"]["items"]}
    effects = {r["reference"]: r for r in docs["item-equipment-effects.json"]["items"]}
    memberships = collections.defaultdict(dict)

    def add(ref, category, reason):
        if ref in items:
            memberships[ref].setdefault(category, []).append(reason)

    for ref, row in equipment.items():
        slots = set(row["slots"])
        if slots & {0, 3, 4, 5, 7, 8, 10, 12, 13, 15, 16, 17}:
            add(ref, "weapons-equipment", "native equipment slots " + str(row["slots"]))
        if slots & {4, 7, 8}:
            add(ref, "dofus-accessories", "native ring or necklace slot")
        if slots in ({22}, {24}):
            add(ref, "pets-mounts", "native pet/mount slot " + str(row["slots"]))
        if 23 in slots:
            add(ref, "cosmetics", "native costume slot 23")
    for ref, row in items.items():
        if "dofus" in (row.get("name") or "").lower():
            add(
                ref,
                "dofus-accessories",
                "Dofus in native Spanish item name; not a Dofus equipment slot",
            )
    for row in cosmetics["items"]:
        ref = row["reference"]
        active = actions.get(ref, {})
        if (
            active.get("use_action_class") == "bIt"
            and active.get("use_action_id") == row["action_id"]
        ):
            add(ref, "cosmetics", "native cosmetic action " + row["category_name"])
    action_categories = {
        "bIs": ("cosmetics", "learn title"),
        "bIw": ("cosmetics", "learn emote"),
        "bHY": ("cosmetics", "play emote"),
        "bHv": ("cosmetics", "equipment appearance"),
        "bHT": ("cosmetics", "mimibiote"),
        "bIb": ("cosmetics", "recustomization"),
        "bIv": ("haven-bag", "haven bag customization"),
    }
    for ref, row in actions.items():
        if row.get("use_action_class") in action_categories:
            cat, reason = action_categories[row["use_action_class"]]
            add(ref, cat, "native use action " + reason)
    for row in docs["native-finisher-items.json"]["items"]:
        add(row["reference"], "cosmetics", "native finisher definition")
    for row in docs["haven-bag-furniture-catalog.json"]["items"]:
        add(
            row["item_ref"],
            "haven-bag",
            "native portable furniture template " + str(row["template_id"]),
        )
    for row in docs["item-healing-rules.json"]["items"]:
        add(row["reference"], "healing", "native healing item effects")
    for row in docs["item-shard-effects.json"]["items"]:
        add(row["reference"], "smithmagic", "native enchantment shard effects")
    for row in docs["item-sublimations.json"]["items"]:
        add(row["reference"], "smithmagic", "native sublimation " + row["type"])
    type_items = {r["reference"]: r for r in (native_types or {}).get("items", [])}
    types = {r["type_id"]: r for r in (native_types or {}).get("types", [])}

    def ancestors(type_id):
        seen = set()
        while type_id in types and type_id not in seen:
            seen.add(type_id)
            type_id = types[type_id]["parent_id"]
        return seen

    for ref, row in type_items.items():
        lineage = ancestors(row["type_id"])
        if lineage & {100, 118, 218, 521, 604}:
            add(
                ref,
                "weapons-equipment",
                "native equipment/tool/bag/set type " + str(row["type_id"]),
            )
        if lineage & {103, 120, 849}:
            add(
                ref, "dofus-accessories", "native accessory type " + str(row["type_id"])
            )
        if lineage & {582, 611}:
            add(ref, "pets-mounts", "native pet or mount type " + str(row["type_id"]))
        if 525 in lineage or 595 in lineage:
            add(ref, "cosmetics", "native cosmetic type " + str(row["type_id"]))
        if 295 in lineage:
            add(ref, "haven-bag", "native haven bag type " + str(row["type_id"]))
        if lineage & {745, 747, 751}:
            add(ref, "healing", "native bread/meal/drink type; healing not implied")
        if 602 in lineage:
            add(
                ref,
                "smithmagic",
                "native smithmagic/enchantment type " + str(row["type_id"]),
            )
    for ref, row in type_items.items():
        if row["type_id"] == 849:
            memberships[ref].pop("pets-mounts", None)
    rows = []
    for ref, item in sorted(items.items()):
        rule = equipment.get(ref, {})
        rows.append(
            dict(
                reference=ref,
                name_es=item.get("name", ""),
                categories="|".join(sorted(memberships[ref])),
                evidence=json.dumps(
                    memberships[ref], ensure_ascii=False, sort_keys=True
                ),
                level=type_items.get(ref, {}).get(
                    "level",
                    rule.get(
                        "minimum_level", effects.get(ref, {}).get("item_level", "")
                    ),
                ),
                native_type_id=type_items.get(ref, {}).get("type_id", ""),
                native_type_name=types.get(
                    type_items.get(ref, {}).get("type_id"), {}
                ).get("name_es", ""),
                native_rarity_id=type_items.get(ref, {}).get("rarity_id", ""),
                confirmed_healing=ref
                in {r["reference"] for r in docs["item-healing-rules.json"]["items"]},
                equipment_slots=json.dumps(rule.get("slots", [])),
                stack_maximum=item["maximum"],
                use_action_class=actions.get(ref, {}).get("use_action_class") or "",
                use_action_id=actions.get(ref, {}).get("use_action_id") or "",
                has_use_criteria=actions.get(ref, {}).get("use_has_criteria", False),
                command=f"!item {ref} 1",
            )
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument(
        "--cosmetic-source", type=Path, default=Path(".runtime/local/cosmetic-review")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("docs/reports/item-shop-inventory-20261011")
    )
    parser.add_argument("--native-types", type=Path, required=True)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text())
    cosmetic_path = args.cosmetic_source / "native-cosmetic-actions.json"
    rows = build(
        snapshot,
        json.loads(cosmetic_path.read_text()),
        json.loads(args.native_types.read_text()),
    )
    args.output.mkdir(parents=True, exist_ok=True)

    def write(name, selected):
        with (args.output / name).open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(selected)

    write("all-items.csv", rows)
    write(
        "dofus-named-items.csv",
        [r for r in rows if "dofus" in (r["name_es"] or "").lower()],
    )
    write("confirmed-healing.csv", [r for r in rows if r["confirmed_healing"]])
    write("fish-resources.csv", [r for r in rows if r["native_type_id"] == 308])
    counts = {}
    for category in [
        "weapons-equipment",
        "dofus-accessories",
        "pets-mounts",
        "cosmetics",
        "haven-bag",
        "healing",
        "smithmagic",
    ]:
        selected = [r for r in rows if category in r["categories"].split("|")]
        write(category + ".csv", selected)
        counts[category] = len(selected)
    write("unclassified-items.csv", [r for r in rows if not r["categories"]])
    summary = dict(
        revision=snapshot["revision"],
        native_items=len(rows),
        categories=counts,
        classified_unique=sum(bool(r["categories"]) for r in rows),
        unclassified=sum(not r["categories"] for r in rows),
        source_sha256={
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [args.snapshot, cosmetic_path, args.native_types]
        },
        classification="Native structural evidence; categories overlap. Healing includes food candidates with confirmed_healing flag. Fish resources exported separately. Unclassified records retained for audit.",
    )
    summary["artifacts_sha256"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(args.output.glob("*.csv"))
    }
    summary["client_sha256"] = {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [
            Path("client/lib/wakfu-client.jar"),
            Path("client/contents/i18n/i18n_es.jar"),
        ]
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
