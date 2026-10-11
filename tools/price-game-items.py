"""Generate an evidence-backed, offline unit-price proposal for curated Wakemu items."""
import argparse
import collections
import csv
import hashlib
import json
import math
from pathlib import Path


def read_json(path):
    return json.loads(Path(path).read_text())


def rounded(value):
    if value < 1000:
        step = 10
    elif value < 10000:
        step = 100
    elif value < 100000:
        step = 1000
    elif value < 1000000:
        step = 10000
    else:
        step = 100000
    return int(math.ceil(value / step) * step)


class Pricing:
    def __init__(
        self, inventory, snapshot, native, drops, crafts, plants, policy, overrides=None
    ):
        self.inventory = {int(row["reference"]): row for row in inventory}
        self.docs = snapshot["documents"]
        self.policy = policy
        self.overrides = overrides or {}
        self.native = {r["reference"]: r for r in native["items"]}
        self.types = {r["type_id"]: r for r in native["types"]}
        self.stacks = {
            r["reference"]: r for r in self.docs["item-stack-rules.json"]["items"]
        }
        self.effects = {
            r["reference"]: r for r in self.docs["item-equipment-effects.json"]["items"]
        }
        self.actions = {
            r["reference"]: r for r in self.docs["item-action-rules.json"]["items"]
        }
        self.healing = {
            r["reference"]: r for r in self.docs["item-healing-rules.json"]["items"]
        }
        self.shards = {
            r["reference"]: r for r in self.docs["item-shard-effects.json"]["items"]
        }
        self.drops = drops["items"]
        self.crafts = crafts["by_item"]
        self.harvest = collections.defaultdict(list)
        for resource in plants:
            for stage in resource["stage_definitions"]:
                for action in stage["actions"]:
                    if action.get("criteria"):
                        continue
                    for ref in action.get("product_references", []):
                        if ref > 0:
                            self.harvest[ref].append(action)
        self.memo = {}
        self.blocked_recipes = set()
        self._block_cycles()

    def lineage(self, type_id):
        seen = set()
        while type_id in self.types and type_id not in seen:
            seen.add(type_id)
            type_id = self.types[type_id]["parent_id"]
        return seen

    def group(self, ref):
        if ref in self.policy["true_dofus_refs"]:
            return "dofus"
        item = self.native.get(ref, {})
        t = item.get("type_id", -1)
        lineage = self.lineage(t)
        if t == 745:
            return "bread"
        if t in {747, 751}:
            return "food"
        if t == 582:
            return "pet"
        if t == 611:
            return "mount"
        if lineage & {581, 849, 850}:
            return "pet_accessory"
        if t == 812:
            return "sublimation"
        if 602 in lineage:
            return "enchantment"
        if t == 218:
            return "bag"
        if t in {537, 480}:
            return "tool"
        if lineage & {100, 118} or t == 646:
            return "equipment"
        specific = {
            647: "costume",
            827: "skin",
            707: "skin",
            595: "skin",
            560: "skin",
            512: "title",
            710: "aura",
            476: "emote",
            744: "sprint",
            743: "finisher",
            294: "haven_gem",
            543: "chest_upgrade",
            447: "station",
            652: "world_building",
            853: "world_building",
        }
        if t in specific:
            return specific[t]
        if 295 in lineage:
            return "furniture"
        if (
            t in {419, 309}
            and "semilla" in (self.stacks.get(ref, {}).get("name") or "").lower()
        ):
            return "seed"
        if 758 in lineage or t == 531:
            return "resource"
        if 761 in lineage or t in {739, 852}:
            return "refined_material"
        if 551 in lineage or t in {603, 614, 649, 844, 846}:
            return "quest_token"
        if 757 in lineage or t in {594, 630, 752, 631, 696, 738, 815, 838}:
            return "consumable"
        return "other"

    def _recipes(self, ref):
        return [
            r
            for r in self.crafts.get(str(ref), {}).get("recipes", [])
            if r["usable_for_cost"] and r["yield_quantity"] > 0
        ]

    def _block_cycles(self):
        # Tarjan SCC: reject only recipes with an ingredient inside the same
        # cyclic component. Alternate acyclic recipes remain eligible.
        graph = {}
        for key in self.crafts:
            graph[int(key)] = {
                i["reference"]
                for r in self._recipes(int(key))
                for i in r["ingredients"]
            }
        number, low, stack, on_stack, components = {}, {}, [], set(), []

        def visit(node):
            number[node] = low[node] = len(number)
            stack.append(node)
            on_stack.add(node)
            for target in sorted(graph.get(node, ())):
                if target not in number:
                    visit(target)
                    low[node] = min(low[node], low[target])
                elif target in on_stack:
                    low[node] = min(low[node], number[target])
            if low[node] == number[node]:
                component = set()
                while True:
                    member = stack.pop()
                    on_stack.remove(member)
                    component.add(member)
                    if member == node:
                        break
                components.append(component)

        for node in sorted(graph):
            if node not in number:
                visit(node)
        for component in components:
            for ref in component:
                for recipe in self._recipes(ref):
                    if any(i["reference"] in component for i in recipe["ingredients"]):
                        self.blocked_recipes.add(recipe["recipe_id"])

    def baseline(self, ref):
        item = self.native.get(ref, {})
        group = self.group(ref)
        if group == "dofus":
            return self.policy["true_dofus_price"], 1, 1, item.get("level", 1)
        config = self.policy["groups"][group]
        level = item.get("level", 0)
        # Native level 0/1 does not encode cosmetic or companion utility.
        effective = config["default_level"] if level <= 1 else level
        level_factor = (1 + effective / config["level_scale"]) ** config["exponent"]
        rarity_factor = (
            self.policy["rarities"].get(str(item.get("rarity_id", 1)), {"factor": 1})[
                "factor"
            ]
            ** config["rarity_power"]
        )
        base = config["base"] * level_factor * rarity_factor
        if ref in self.healing:
            strengths = [
                abs(e.get("value_at_item_level", 0))
                for e in self.healing[ref]["effects"]
                if e.get("generic") == 25
            ]
            if strengths:
                base *= min(2, max(0.8, math.sqrt(max(strengths) / 100)))
        if ref in {27083, 27093}:
            base = 100  # Modern mass-consumption shard/powder currencies.
        return base, level_factor, rarity_factor, effective

    def procurement(self, ref, base):
        group = self.group(ref)
        flags = []
        drop = self.drops.get(str(ref), {})
        candidates = []
        for route in drop.get("routes", []):
            if not route["runtime_supported"] or route["expected_quantity_base"] <= 0:
                continue
            factor = max(
                1,
                (1 / route["expected_quantity_base"])
                ** self.policy["drop"]["expected_attempt_exponent"],
            )
            factor = min(self.policy["drop"]["maximum_factor"], factor)
            factor *= (
                1 + route["monster_min_level"] / self.policy["drop"]["level_scale"]
            )
            if route["boss_classification"] == "boss":
                factor *= self.policy["drop"]["boss_factor"]
            conditional = bool(route["conditions"] or route["native_csF"] > 0)
            if conditional:
                factor *= self.policy["drop"]["conditional_factor"]
            candidates.append((factor, route, conditional))
        if candidates:
            factor, route, conditional = min(
                candidates,
                key=lambda x: (x[0], x[1]["monster_reference"], x[1]["row_index"]),
            )
            if conditional:
                flags.append("conditional_drop_access")
            return dict(
                raw=base * factor,
                factor=factor,
                route="conditional_drop" if conditional else "drop",
                drop=route,
                flags=flags,
                confidence="medium" if conditional else "high",
            )
        if ref in self.harvest:
            route = min(
                self.harvest[ref],
                key=lambda a: (a["minimum_level"], a["duration_ms"], a["action_id"]),
            )
            factor = 1 + route["minimum_level"] / 250 + route["duration_ms"] / 60000
            return dict(
                raw=base * factor,
                factor=factor,
                route="harvest_catalog",
                drop={},
                flags=["harvest_yield_not_quantified"],
                confidence="medium",
            )
        factor = self.policy["groups"][group]["unknown_source_factor"]
        if group in {"resource", "seed", "quest_token"}:
            flags.append("alternative_source_likely")
        flags.append("no_verified_drop_craft_or_harvest")
        if drop:
            flags.append("native_drop_rows_unusable")
        return dict(
            raw=base * factor,
            factor=factor,
            route="unresolved_source_policy",
            drop={},
            flags=flags,
            confidence="low",
        )

    def price(self, ref):
        if ref in self.memo:
            return self.memo[ref]
        group = self.group(ref)
        base, level_factor, rarity_factor, effective = self.baseline(ref)
        if group == "dofus":
            result = dict(
                price=self.policy["true_dofus_price"],
                base=base,
                level_factor=level_factor,
                rarity_factor=rarity_factor,
                effective_level=effective,
                route="dofus_premium_policy",
                factor=1,
                drop={},
                flags=["true_equipable_dofus"],
                confidence="policy",
                recipe={},
                craft_cost=0,
                craft_labor=0,
                craft_depth=0,
                craft_inputs=[],
            )
            self.memo[ref] = result
            return result
        config = self.policy["groups"][group]
        procurement = self.procurement(ref, base)
        options = []
        cyclic = False
        for recipe in self._recipes(ref):
            if recipe["recipe_id"] in self.blocked_recipes:
                cyclic = True
                continue
            inputs = [(i, self.price(i["reference"])) for i in recipe["ingredients"]]
            if not inputs:
                continue
            cost = (
                sum(i["quantity"] * p["price"] for i, p in inputs)
                / recipe["yield_quantity"]
            )
            labor = (
                recipe["minimum_level"]
                * self.policy["craft"]["labor_per_profession_level"]
                + recipe["ingredient_slot_count"]
                * self.policy["craft"]["labor_per_ingredient_slot"]
                + recipe["raw_duration"]
                / 1000
                * self.policy["craft"]["labor_per_second"]
            ) / recipe["yield_quantity"]
            # Attribute the higher of utility and replacement cost, with a
            # modest service premium. A craft does not multiply rarity twice.
            raw = max(base, cost + labor) * self.policy["craft"]["service_markup"]
            options.append((raw, recipe, cost, labor, inputs))
        option = (
            min(options, key=lambda x: (x[0], x[1]["recipe_id"])) if options else None
        )
        result = dict(
            procurement,
            base=base,
            level_factor=level_factor,
            rarity_factor=rarity_factor,
            effective_level=effective,
            recipe={},
            craft_cost=0,
            craft_labor=0,
            craft_depth=0,
            craft_inputs=[],
        )
        if option:
            raw, recipe, cost, labor, inputs = option
            result.update(
                recipe=recipe,
                craft_cost=cost,
                craft_labor=labor,
                craft_depth=1 + max(p["craft_depth"] for _, p in inputs),
                craft_inputs=[
                    dict(
                        reference=i["reference"],
                        quantity=i["quantity"],
                        unit_price=p["price"],
                        curated=i["reference"] in self.inventory,
                    )
                    for i, p in inputs
                ],
            )
            # Drop is primary when documented. For the remaining items, use
            # the cheaper of a documented harvest and a supported craft.
            if procurement["route"] == "unresolved_source_policy" or (
                procurement["route"] == "harvest_catalog" and raw < procurement["raw"]
            ):
                result.update(
                    raw=raw,
                    factor=raw / base,
                    route="craft",
                    confidence="medium",
                    flags=[],
                )
            if result["route"] == "craft":
                if any(p["confidence"] == "low" for _, p in inputs):
                    result["flags"].append("uncertain_ingredient_cost")
                    result["confidence"] = "low"
                if any(i["reference"] not in self.inventory for i, _ in inputs):
                    result["flags"].append("ingredient_not_in_curated_shop")
                if any(p["recipe"] and p["route"] == "craft" for _, p in inputs):
                    result["flags"].append("intermediate_crafting")
        elif self.crafts.get(str(ref)):
            result["flags"].append("recipe_present_but_no_supported_acyclic_route")
        if cyclic:
            result["flags"].append("cyclic_recipe_skipped")
        raw = result["raw"]
        result["price"] = min(
            config["cap"],
            self.policy["maximum"],
            max(self.policy["minimum"], rounded(raw)),
        )
        if raw > config["cap"]:
            result["flags"].append("category_cap_applied")
        if result["craft_cost"] and result["price"] < result["craft_cost"]:
            result["flags"].append("below_shop_ingredient_cost")
        if self.native.get(ref, {}).get("rarity_id") == 10:
            result["flags"].append("admin_quality_hold")
        if group in {"quest_token", "world_building"}:
            result["flags"].append("progression_or_system_eligibility_hold")
        if self.native.get(ref, {}).get("type_id") == 626:
            result["flags"].append("legacy_rune_functionality_hold")
        override = self.overrides.get(str(ref))
        if override:
            result["price"] = override["price_kamas"]
            if (
                not isinstance(result["price"], int)
                or not self.policy["minimum"]
                <= result["price"]
                <= self.policy["maximum"]
            ):
                raise ValueError(f"Invalid manual price for {ref}")
            if result["price"] > config["cap"]:
                result["flags"].append("manual_category_cap_exception")
            result["flags"] = [
                flag for flag in result["flags"] if flag != "below_shop_ingredient_cost"
            ]
            if result["craft_cost"] and result["price"] < result["craft_cost"]:
                result["flags"].append("below_shop_ingredient_cost")
        self.memo[ref] = result
        return result


def write_csv(path, rows, fields=None):
    with Path(path).open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("docs/reports/item-shop-inventory-20261011/curated/all-items.csv"),
    )
    parser.add_argument(
        "--evidence", type=Path, default=Path(".runtime/local/item-pricing-20261011")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("docs/reports/item-pricing-20261011")
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("docs/reports/item-pricing-20261011/pricing-policy.json"),
    )
    parser.add_argument(
        "--overrides",
        type=Path,
        default=Path("docs/reports/item-pricing-20261011/manual-overrides.json"),
    )
    parser.add_argument(
        "--reviews",
        type=Path,
        default=Path("docs/reports/item-pricing-20261011/manual-review-index.json"),
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path(".runtime/local/item-pricing-20261011/prices-before-review.csv"),
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    inventory = list(csv.DictReader(args.source.open()))
    input_paths = [
        args.source,
        Path(".runtime/local/item-shop-inventory-20261011/catalog.json"),
        Path(".runtime/local/item-shop-inventory-20261011/native-types.json"),
        args.evidence / "drops.json",
        args.evidence / "crafts.json",
        args.evidence / "plant-resources.json",
        args.policy,
    ]
    overrides = read_json(args.overrides) if args.overrides.is_file() else {}
    evidence = [read_json(p) for p in input_paths[1:]]
    automated_engine = Pricing(inventory, *evidence)
    engine = Pricing(inventory, *evidence, overrides=overrides)
    reviews = (
        read_json(args.reviews).get("by_reference", {})
        if args.reviews.is_file()
        else {}
    )
    if reviews and set(reviews) != {row["reference"] for row in inventory}:
        raise ValueError(
            "Manual review scope must match the complete curated inventory"
        )
    rows = []
    for item in sorted(inventory, key=lambda x: int(x["reference"])):
        ref = int(item["reference"])
        priced = engine.price(ref)
        automated_price = automated_engine.price(ref)["price"]
        recipe, drop = priced["recipe"], priced["drop"]
        group = engine.group(ref)
        override = overrides.get(str(ref), {})
        final = override.get("price_kamas", priced["price"])
        if (
            not isinstance(final, int)
            or not engine.policy["minimum"] <= final <= engine.policy["maximum"]
        ):
            raise ValueError(f"Invalid manual price for {ref}")
        flags = sorted(set(priced["flags"]))
        review = reviews.get(str(ref), {})
        if review.get("hold_reasons"):
            flags.append("manual_publication_hold")
        holds = [f for f in flags if f.endswith("_hold")]
        row = dict(
            reference=ref,
            name_es=item["name_es"],
            economic_group=group,
            native_type_id=int(item["native_type_id"]),
            native_type_name=item["native_type_name"],
            level=int(item["level"]),
            effective_pricing_level=priced["effective_level"],
            rarity_id=int(item["native_rarity_id"]),
            rarity_name=engine.policy["rarities"][item["native_rarity_id"]]["name"],
            price_kamas=final,
            automated_price_kamas=automated_price,
            quantity=1,
            currency="kamas",
            categories=item["categories"],
            acquisition=priced["route"],
            evidence_confidence=priced["confidence"],
            base_utility_price=round(priced["base"], 2),
            level_factor=round(priced["level_factor"], 6),
            rarity_factor=round(priced["rarity_factor"], 6),
            acquisition_factor=round(priced["factor"], 6),
            drop_probability_fraction=drop.get("probability", ""),
            drop_expected_quantity=drop.get("expected_quantity_base", ""),
            drop_monster_ref=drop.get("monster_reference", ""),
            drop_monster_name=drop.get("monster_name", ""),
            drop_monster_min_level=drop.get("monster_min_level", ""),
            drop_conditions=json.dumps(drop.get("conditions", []), ensure_ascii=False),
            craft_recipe_id=recipe.get("recipe_id", ""),
            craft_profession_level=recipe.get("minimum_level", ""),
            craft_output_yield=recipe.get("yield_quantity", ""),
            craft_ingredient_cost_per_unit=round(priced["craft_cost"], 2),
            craft_labor_per_unit=round(priced["craft_labor"], 2),
            craft_depth=priced["craft_depth"],
            craft_inputs_json=json.dumps(priced["craft_inputs"], separators=(",", ":")),
            flags="|".join(flags),
            publication_hold="|".join(holds),
            manual_override_reason=override.get("reason", ""),
            manual_override_reviewer=override.get("reviewer", ""),
            manual_review_by=review.get("reviewer", ""),
            manual_review_mode="individual_exception"
            if override
            else ("cohort_review" if review else "pending"),
            manual_hold_reason=" | ".join(review.get("hold_reasons", [])),
            review_status="override_reviewed"
            if override
            else ("cohort_reviewed" if review else "pending_manual_review"),
            policy_version=engine.policy["version"],
        )
        rows.append(row)
    write_csv(args.output / "prices.csv", rows)
    readable_fields = [
        "reference",
        "name_es",
        "economic_group",
        "level",
        "rarity_name",
        "price_kamas",
        "quantity",
        "acquisition",
        "evidence_confidence",
        "review_status",
        "manual_review_by",
        "publication_hold",
        "manual_hold_reason",
    ]
    write_csv(
        args.output / "price-list.csv",
        [{key: row[key] for key in readable_fields} for row in rows],
    )
    write_csv(
        args.output / "publication-holds.csv",
        [row for row in rows if row["publication_hold"]],
    )
    for group in sorted({r["economic_group"] for r in rows}):
        write_csv(
            args.output / f"prices-{group}.csv",
            [r for r in rows if r["economic_group"] == group],
        )
    by_group = []
    for group in sorted({r["economic_group"] for r in rows}):
        selected = [r for r in rows if r["economic_group"] == group]
        values = sorted(r["price_kamas"] for r in selected)
        by_group.append(
            dict(
                group=group,
                count=len(selected),
                minimum=values[0],
                median=values[len(values) // 2],
                p90=values[min(len(values) - 1, int(len(values) * 0.9))],
                maximum=values[-1],
                low_confidence=sum(r["evidence_confidence"] == "low" for r in selected),
                publication_holds=sum(bool(r["publication_hold"]) for r in selected),
            )
        )
    write_csv(args.output / "category-summary.csv", by_group)
    write_csv(args.output / "review-queue.csv", [r for r in rows if r["flags"]])
    deltas = []
    if args.baseline.is_file():
        before = {r["reference"]: r for r in csv.DictReader(args.baseline.open())}
        for row in rows:
            key = str(row["reference"])
            if row["price_kamas"] != int(before[key]["price_kamas"]):
                deltas.append(
                    dict(
                        reference=key,
                        name_es=row["name_es"],
                        economic_group=row["economic_group"],
                        old_price=before[key]["price_kamas"],
                        new_price=row["price_kamas"],
                        override=key in overrides,
                        reason=row["manual_override_reason"],
                        flags=row["flags"],
                    )
                )
        if deltas:
            write_csv(args.output / "price-review-changes.csv", deltas)
    summary = dict(
        items=len(rows),
        minimum=min(r["price_kamas"] for r in rows),
        maximum=max(r["price_kamas"] for r in rows),
        acquisitions=dict(collections.Counter(r["acquisition"] for r in rows)),
        confidence=dict(collections.Counter(r["evidence_confidence"] for r in rows)),
        flags=dict(
            collections.Counter(f for r in rows for f in r["flags"].split("|") if f)
        ),
        overrides=len(overrides),
        cyclic_recipes_skipped=sorted(engine.blocked_recipes),
        source_sha256={
            str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths
        },
        scope="Offline unit-price proposal. No products, balances, catalog data or services changed.",
    )
    if args.overrides.is_file():
        summary["source_sha256"][str(args.overrides)] = hashlib.sha256(
            args.overrides.read_bytes()
        ).hexdigest()
    if args.reviews.is_file():
        summary["source_sha256"][str(args.reviews)] = hashlib.sha256(
            args.reviews.read_bytes()
        ).hexdigest()
    summary["manual_review_coverage"] = len(reviews)
    summary["publication_holds"] = sum(bool(r["publication_hold"]) for r in rows)
    summary["source_sha256"][
        str(Path(__file__).relative_to(Path.cwd()))
    ] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    summary["source_sha256"]["tools/merge-item-price-reviews.py"] = hashlib.sha256(
        Path("tools/merge-item-price-reviews.py").read_bytes()
    ).hexdigest()
    if args.baseline.is_file():
        summary["source_sha256"][str(args.baseline)] = hashlib.sha256(
            args.baseline.read_bytes()
        ).hexdigest()
    summary["changed_prices"] = len(deltas)
    summary["indirect_craft_price_changes"] = sum(not row["override"] for row in deltas)
    summary["final_prices_sha256"] = hashlib.sha256(
        (args.output / "prices.csv").read_bytes()
    ).hexdigest()
    summary["artifacts_sha256"] = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(args.output.glob("*.csv"))
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
