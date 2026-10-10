"""Join native cosmetic/action exports with a frozen published catalog snapshot."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import zipfile


def build(actions, cosmetics, rules, effects, equipment, names):
    rule_index = {row["reference"]: row for row in rules["items"]}
    effect_index = {row["reference"]: row for row in effects["items"]}
    equipment_index = {row["reference"]: row for row in equipment["items"]}
    action_index = {row["reference"]: row for row in actions["items"]}
    cosmetic_index = {row["reference"]: row for row in cosmetics["items"]}
    supported = {
        1: "source_pending_manual",
        3: "manual_accepted_r63",
        4: "source_pending_manual",
        5: "existing_finisher_support",
        6: "source_pending_manual",
    }
    categories = []
    for kind in actions["categories"]:
        items = []
        for row in cosmetics["items"]:
            if row["category"] != kind["id"]:
                continue
            reference = row["reference"]
            active = rule_index.get(reference)
            matches = (
                active is not None
                and active.get("use_action_class") == "bIt"
                and active.get("use_action_id") == row["action_id"]
            )
            items.append(
                {
                    **row,
                    "name_es": names.get(reference),
                    "published_action_matches": matches,
                    "command": f"!item {reference} 1" if matches else None,
                }
            )
        categories.append(
            {
                **kind,
                "count": len(items),
                "learning": "bIt_implemented" if items else "no_bIt_source_in_export",
                "selection": supported.get(
                    kind["id"], "unsupported_or_other_authority"
                ),
                "items": sorted(items, key=lambda row: row["reference"]),
            }
        )
    external = []
    for cls, label in (
        ("bIs", "title_learning"),
        ("bIw", "emote_learning"),
        ("bIv", "haven_bag_custom_learning"),
        ("bHY", "play_emote_item"),
        ("bHv", "learn_target_equipment_appearance"),
        ("bHT", "mimibiote_interface"),
        ("bIb", "character_recustomization"),
    ):
        rows = [
            {
                **row,
                "name_es": names.get(row["reference"]),
                "command": f"!item {row['reference']} 1"
                if row["reference"] in rule_index
                else None,
            }
            for row in actions["items"]
            if row["class"] == cls
        ]
        external.append(
            {
                "class": cls,
                "kind": label,
                "count": len(rows),
                "status": "not_supported_by_bIt_learning_route",
                "items": rows,
            }
        )
    dofus = []
    for reference, name in sorted(names.items()):
        if "dofus" not in name.lower():
            continue
        native_effects = effect_index.get(reference, {}).get("effects", [])
        dofus.append(
            {
                "reference": reference,
                "name_es": name,
                "native_item_present": reference in rule_index,
                "action": action_index.get(reference),
                "cosmetic": cosmetic_index.get(reference),
                "equipment": equipment_index.get(reference),
                "item_level": effect_index.get(reference, {}).get("item_level"),
                "effects": native_effects,
                "state_refs": sorted(
                    {
                        row["values"][0]
                        for row in native_effects
                        if row.get("generic") == 304 and row.get("values")
                    }
                ),
                "command": f"!item {reference} 1" if reference in rule_index else None,
            }
        )
    return {
        "schema_version": 1,
        "scope": "Installed Wakfu client plus frozen published catalog; no Dofus server data",
        "categories": categories,
        "other_cosmetic_related_actions": external,
        "dofus_named_items": dofus,
        "summary": {
            "native_categories": len(categories),
            "bIt_learning_items": sum(row["count"] for row in categories),
            "published_matching_bIt_items": sum(
                item["published_action_matches"]
                for row in categories
                for item in row["items"]
            ),
            "dofus_named_locale_items": len(dofus),
            "dofus_named_native_items": sum(
                row["native_item_present"] for row in dofus
            ),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=Path(".runtime/local/cosmetic-review")
    )
    parser.add_argument("--output", type=Path, default=Path("docs/reports/cosmetics"))
    args = parser.parse_args()
    source = args.source
    paths = [
        source / "native-item-action-kinds.json",
        source / "native-cosmetic-actions.json",
    ]
    paths += [
        source / "runtime-catalog" / name
        for name in (
            "item-action-rules.json",
            "item-equipment-effects.json",
            "item-equipment-rules.json",
        )
    ]
    with zipfile.ZipFile("client/contents/i18n/i18n_es.jar") as archive:
        texts = dict(
            line.split("=", 1)
            for line in archive.read("texts_es.properties").decode().splitlines()
            if "=" in line
        )
    names = {
        int(key[11:]): value
        for key, value in texts.items()
        if key.startswith("content.15.")
    }
    result = build(*(json.loads(path.read_text()) for path in paths), names)
    result["published_release"] = json.loads(
        (source / "runtime-catalog/release.json").read_text()
    )["revision"]
    result["source_sha256"] = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
        + [
            Path("client/lib/wakfu-client.jar"),
            Path("client/contents/i18n/i18n_es.jar"),
        ]
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "inventory.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    with (args.output / "cosmetic-items.csv").open("w") as output:
        writer = csv.writer(output)
        writer.writerow(
            (
                "category",
                "category_name",
                "reference",
                "name_es",
                "action_id",
                "published_matches",
                "command",
            )
        )
        for category in result["categories"]:
            for item in category["items"]:
                writer.writerow(
                    (
                        category["id"],
                        category["name"],
                        item["reference"],
                        item["name_es"],
                        item["action_id"],
                        item["published_action_matches"],
                        item["command"],
                    )
                )
    with (args.output / "cosmetic-related-actions.csv").open("w") as output:
        writer = csv.writer(output)
        writer.writerow(
            (
                "action_class",
                "kind",
                "reference",
                "name_es",
                "action_id",
                "has_criteria",
                "command",
                "status",
            )
        )
        for kind in result["other_cosmetic_related_actions"]:
            for item in kind["items"]:
                writer.writerow(
                    (
                        kind["class"],
                        kind["kind"],
                        item["reference"],
                        item["name_es"],
                        item["action_id"],
                        item["has_criteria"],
                        item["command"],
                        kind["status"],
                    )
                )
    with (args.output / "dofus-named-items.csv").open("w") as output:
        writer = csv.writer(output)
        writer.writerow(
            (
                "reference",
                "name_es",
                "native_item_present",
                "level",
                "action_class",
                "cosmetic_category",
                "effect_generics",
                "state_refs",
                "command",
            )
        )
        for item in result["dofus_named_items"]:
            writer.writerow(
                (
                    item["reference"],
                    item["name_es"],
                    item["native_item_present"],
                    item["item_level"],
                    (item["action"] or {}).get("class"),
                    (item["cosmetic"] or {}).get("category"),
                    ";".join(str(row["generic"]) for row in item["effects"]),
                    ";".join(map(str, item["state_refs"])),
                    item["command"],
                )
            )
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
