"""Export pricing evidence from a pinned native recipe snapshot; never mutate runtime."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

REVISION = "677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d"


def build(source, curated):
    raw = source.read_bytes()
    document = json.loads(raw)
    definitions = collections.defaultdict(list)
    stations = collections.Counter(
        row["definition_id"]
        for row in document["craft_table_instances"]
        if row.get("status") == "resolved"
    )
    for definition in document["craft_table_definition_rows"]:
        for recipe_id in definition["allowed_recipe_ids"]:
            definitions[recipe_id].append(definition)
    by_item = collections.defaultdict(lambda: {"recipes": []})
    for recipe in document["recipes"]:
        rid = recipe["recipe_id"]
        station_rows = definitions[rid]
        matching = [
            row
            for row in station_rows
            if row["profession_id"] == recipe["profession_id"]
        ]
        unsupported = bool(
            recipe["raw_clT"]
            or recipe["raw_cvc"]
            or recipe["raw_cvd"]
            or recipe["raw_ckE"]
        )
        for product in recipe["products"]:
            ref = product["item_id"]
            inputs = [
                {
                    "reference": row["item_id"],
                    "quantity": row["quantity"],
                    "extra_raw": row["extra_raw"],
                }
                for row in recipe["ingredients"]
            ]
            self_input = any(row["reference"] == ref for row in inputs)
            entry = dict(
                recipe_id=rid,
                profession_id=recipe["profession_id"],
                minimum_level=recipe["minimum_level"],
                raw_duration=recipe["raw_duration"],
                yield_quantity=product["quantity"],
                ingredients=inputs,
                ingredient_slot_count=len(inputs),
                ingredient_total_quantity=sum(row["quantity"] for row in inputs),
                station_definition_ids=sorted(
                    row["definition_id"] for row in station_rows
                ),
                matching_profession_station_ids=sorted(
                    row["definition_id"] for row in matching
                ),
                station_instance_count=sum(
                    stations[row["definition_id"]] for row in station_rows
                ),
                has_criteria=bool(
                    recipe["raw_clT"] or recipe["raw_cvc"] or recipe["raw_cvd"]
                ),
                unsupported_runtime_criteria_or_flags=unsupported,
                self_input=self_input,
                net_self_yield=product["quantity"]
                - sum(row["quantity"] for row in inputs if row["reference"] == ref),
                runtime_recipe_policy_supported=bool(station_rows) and not unsupported,
                usable_for_cost=bool(station_rows)
                and not unsupported
                and not self_input,
                executable=bool(station_rows) and not unsupported,
                raw_fields={
                    key: value
                    for key, value in recipe.items()
                    if key.startswith("raw_")
                },
            )
            by_item[str(ref)]["recipes"].append(entry)
    for row in by_item.values():
        row["recipes"].sort(key=lambda recipe: recipe["recipe_id"])
        row["recipe_count"] = len(row["recipes"])
        row["productive_recipe_count"] = sum(
            not recipe["self_input"] or recipe["net_self_yield"] > 0
            for recipe in row["recipes"]
        )
        row["supported_productive_recipe_count"] = sum(
            recipe["runtime_recipe_policy_supported"]
            and (not recipe["self_input"] or recipe["net_self_yield"] > 0)
            for recipe in row["recipes"]
        )
    graph = {
        int(ref): {
            i["reference"]
            for r in row["recipes"]
            if r["usable_for_cost"]
            for i in r["ingredients"]
        }
        for ref, row in by_item.items()
    }
    visiting, visited, cycles = set(), set(), []

    def visit(node, path):
        if node in visiting:
            cycles.append(path[path.index(node) :] + [node])
            return
        if node in visited:
            return
        visiting.add(node)
        for child in sorted(graph.get(node, ())):
            visit(child, path + [node])
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        visit(node, [])
    ids = {row["reference"] for row in csv.DictReader(curated.open())}
    summary = dict(
        dependency_cycle_paths=cycles,
        native_recipes=len(document["recipes"]),
        distinct_outputs=len(by_item),
        curated_outputs=len(ids & set(by_item)),
        curated_supported_productive_outputs=sum(
            bool(by_item[ref]["supported_productive_recipe_count"])
            for ref in ids & set(by_item)
        ),
        self_input_recipes=sum(
            any(
                i["item_id"] == p["item_id"]
                for i in r["ingredients"]
                for p in r["products"]
            )
            for r in document["recipes"]
        ),
        recipes_with_unsupported_criteria_or_flags=sum(
            bool(r["raw_clT"] or r["raw_cvc"] or r["raw_cvd"] or r["raw_ckE"])
            for r in document["recipes"]
        ),
        recipes_without_station_membership=sum(
            not definitions[r["recipe_id"]] for r in document["recipes"]
        ),
        all_ingredient_refs=len(
            {i["item_id"] for r in document["recipes"] for i in r["ingredients"]}
        ),
    )
    return dict(
        metadata=dict(
            revision=REVISION,
            source_path=str(source),
            source_sha256=hashlib.sha256(raw).hexdigest(),
            quantity_unit="per recipe batch; divide total input cost by yield_quantity",
            currency_cost="No verified direct currency charge exported; raw fields retained without invented semantics",
            ingredient_qualifiers="extra_raw preserves native cvm; nonzero alone does not imply unsupported or dynamic ingredients",
            dynamic_inputs="Only explicit native item IDs and quantities exported. No invented substitutes; criteria/secret rules flagged separately",
            runtime_scope="Station membership and recipe criteria policy checked against crafting.py; profession/player/access/ingredient authorization remains context dependent",
        ),
        by_item=dict(sorted(by_item.items(), key=lambda pair: int(pair[0]))),
        summary=summary,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=Path(".runtime/local/item-pricing-20261011/craft-recipes.json"),
    )
    parser.add_argument(
        "--curated",
        type=Path,
        default=Path("docs/reports/item-shop-inventory-20261011/curated/all-items.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".runtime/local/item-pricing-20261011/crafts.json"),
    )
    args = parser.parse_args()
    result = build(args.source, args.curated)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
