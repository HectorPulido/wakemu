"""Export a complete item census and an evidence-based item-use inventory.

Inputs are frozen read-only catalog snapshots, original-client type metadata,
and the reviewed server action audit. This tool never contacts a game server.
"""
import argparse
import ast
import collections
import csv
import hashlib
import json
from pathlib import Path


ACTION_NAMES = {
    "bHA": "Guild creation and identity items",
    "bHB": "Sublimation scrolls",
    "bHE": "Companion activation",
    "bHF": "Item conversion and chest upgrades",
    "bHI": "Fixed item grants and packages",
    "bHJ": "Random gifts and boxes",
    "bHK": "Character experience grants",
    "bHQ": "Monster elimination bombs",
    "bHS": "Fragment merging",
    "bHT": "Legacy Mimobionte",
    "bHU": "Books and background displays",
    "bHX": "Pet experience actions",
    "bHY": "Immediate emotes and transformations",
    "bHv": "Transespejo appearance learning",
    "bHw": "Achievement activation",
    "bHx": "Restat activation",
    "bHy": "Kama grants",
    "bHz": "Ranch creature acquisition",
    "bIA": "Ranch building learning",
    "bIB": "Single recipe learning",
    "bIa": "Fireworks and script execution",
    "bIb": "Appearance, sex and class recustomization",
    "bIg": "Treasure searching",
    "bIi": "Seed planting",
    "bIk": "Monster spawning",
    "bIl": "Set unpacking",
    "bIn": "Scenario and treasure map activation",
    "bIq": "Teleportation",
    "bIr": "Recall to respawn point",
    "bIs": "Title learning",
    "bIt": "Cosmetic learning",
    "bIv": "Haven Bag appearance learning",
    "bIw": "Emote learning",
    "bIx": "Furniture learning",
    "bIz": "Multiple recipe learning",
}
NO_ACTION_NAMES = {
    631: "Profession boosts without an explicit action",
    745: "Bread and food without an explicit action",
    746: "Candies and buffs without an explicit action",
    747: "Meals and drinks without an explicit action",
    751: "Anti-KO consumables without an explicit action",
    752: "Other scrolls without an explicit action",
    738: "Transformations without an explicit action",
    594: "Pet consumables without an explicit action",
    810: "Evolution stones with unconfirmed use semantics",
}


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path, rows):
    assert rows, path
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def build(args):
    snapshot, supplement, audit, native = map(
        load, (args.snapshot, args.supplement, args.action_support, args.types)
    )
    assert snapshot["revision"] == supplement["revision"] == audit["catalog_revision"]
    documents = snapshot["documents"]
    items = {
        r["reference"]: r
        for r in documents["item-stack-rules.json"]["items"]
        if r["reference"] > 0
    }
    actions = {r["reference"]: r for r in documents["item-action-rules.json"]["items"]}
    typed = {r["reference"]: r for r in native["items"] if r["reference"] > 0}
    types = {r["type_id"]: r for r in native["types"]}
    assert set(items) == set(
        typed
    ), "Type export does not cover the current item references"
    supported = {r["reference"]: r for r in audit["items"]}
    food = {r for values in audit["pet_food_references"].values() for r in values}
    healing_catalog = {
        r["reference"]: r for r in documents["item-healing-rules.json"]["items"]
    }
    # Execute the actual pure predicate in isolation, without importing catalogs
    # or creating a DB/Redis connection. Bind its source hash in the receipt.
    source = Path("server/wakfu_server/items/inventory_consumables.py")
    module = ast.parse(source.read_text())
    predicate = next(
        n
        for n in module.body
        if isinstance(n, ast.FunctionDef) and n.name == "healing_plan"
    )
    namespace = {"CATALOG": healing_catalog}
    exec(
        compile(ast.Module(body=[predicate], type_ignores=[]), str(source), "exec"),
        namespace,
    )
    healing = set()
    for ref in healing_catalog:
        try:
            namespace["healing_plan"](ref)
            healing.add(ref)
        except ValueError:
            pass
    assert healing == {
        r["reference"] for r in audit["healing"] if r["status"] == "implemented"
    }
    cosmetics = {
        r["item_ref"]: r["category"]
        for r in snapshot["tables"]["native_cosmetic_learning_actions"]
    }

    def lineage(tid):
        found = set()
        while tid in types and tid not in found:
            found.add(tid)
            tid = types[tid]["parent_id"]
        return found

    effects = {
        r["reference"]: r for r in documents["item-equipment-effects.json"]["items"]
    }
    rows = []
    for ref, item in sorted(items.items()):
        action = actions[ref]
        cls = action.get("use_action_class") or ""
        tid = typed[ref]["type_id"]
        direct = bool(cls) or 106 in lineage(tid) or tid in (594, 738, 810)
        status, route, evidence, notes = "outside_direct_scope", "", "", ""
        family = ""
        if cls:
            decision = supported[ref]
            status, route = decision["status"], decision["route"]
            evidence = "|".join(decision["evidence"])
            notes = decision["reason"]
            family = "action:" + cls
        elif direct:
            family = "type:" + str(tid)
            if ref in healing:
                status, route = "implemented", "12659"
                notes = "Flat neutral self-healing outside combat; living wounded owner required"
            elif tid == 594 and ref in food:
                status, route = "implemented", "12767"
                notes = "Feed a supported owned pet/mount; direct double-click is not a healing food use"
            elif tid == 810:
                status = "needs_native_review"
                notes = "No explicit use action or exported effects; actual evolution contract is unconfirmed"
            else:
                status = "missing"
                notes = (
                    "No supported generic food effect or dedicated item-use route found"
                )
            evidence = "server/local_game_server.py:11196|server/wakfu_server/items/inventory_consumables.py:22"
        downstream = ""
        if ref in cosmetics and cosmetics[ref] not in (1, 3, 4, 5, 6, 7):
            downstream = (
                "Learning exists; cosmetic preset selection category is unsupported"
            )
        if ref == 23951:
            downstream = "Knowledge 20223 persists, but the original client has no executable emote definition"
        if ref in (19456, 19469, 19470, 19471, 25081, 25085, 25088, 31499):
            downstream = "Recipe knowledge is supported; this book has a retired recipe output (see recipe contract audit)"
        if cls == "bIA":
            downstream = "Building learning only; ranch animals and breeding are separate missing systems"
        if cls == "bHv":
            downstream = "Default catalog appearance learning; instance-specific appearance overrides lack authority"
        contexts = []
        if ref in food:
            contexts.append("pet_feeding_12767")
        if 602 in lineage(tid):
            contexts.append("enchantment_or_legacy_material")
        if tid == 317:
            contexts.append("dungeon_key")
        if tid == 294:
            contexts.append("haven_bag_room_gem")
        if tid == 543:
            contexts.append("haven_chest_capacity_item")
        rows.append(
            dict(
                reference=ref,
                name_es=item.get("name", ""),
                native_type_id=tid,
                native_type_name_es=types[tid]["name_es"],
                direct_scope=direct,
                family=family,
                use_action_class=cls,
                use_action_id=action.get("use_action_id") or "",
                implementation_status=status,
                route=route,
                implementation_notes=notes,
                downstream_limits=downstream,
                secondary_contexts="|".join(contexts),
                healing_registry=ref in healing_catalog,
                healing_accepted=ref in healing,
                cosmetic_category=cosmetics.get(ref, ""),
                effect_generics="|".join(
                    str(v)
                    for v in sorted(
                        {e["generic"] for e in effects.get(ref, {}).get("effects", [])}
                    )
                ),
                legacy_exchange_flag=action.get("use_has_criteria", False),
                evidence=evidence,
                command=f"!item {ref} 1",
            )
        )
    selected = [r for r in rows if r["direct_scope"]]
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "all-items.csv", rows)
    write_csv(output / "consumables-and-actions.csv", selected)
    write_csv(
        output / "pending-items.csv",
        [
            r
            for r in selected
            if r["implementation_status"]
            in ("missing", "code_present_disabled", "needs_native_review")
        ],
    )
    write_csv(
        output / "partial-usability.csv",
        [r for r in selected if r["downstream_limits"]],
    )
    write_csv(
        output / "healing-registry.csv", [r for r in rows if r["healing_registry"]]
    )
    write_csv(
        output / "context-items.csv", [r for r in rows if r["secondary_contexts"]]
    )

    families = []
    for family in sorted({r["family"] for r in selected}):
        members = [r for r in selected if r["family"] == family]
        cls = members[0]["use_action_class"]
        name = (
            ACTION_NAMES[cls] if cls else NO_ACTION_NAMES[members[0]["native_type_id"]]
        )
        counts = collections.Counter(r["implementation_status"] for r in members)
        families.append(
            dict(
                family=family,
                name=name,
                items=len(members),
                implemented=counts["implemented"],
                missing=counts["missing"],
                disabled=counts["code_present_disabled"],
                needs_native_review=counts["needs_native_review"],
                with_downstream_caveat=sum(
                    bool(r["downstream_limits"]) for r in members
                ),
                example_reference=members[0]["reference"],
                example_name_es=members[0]["name_es"],
                example_command=members[0]["command"],
            )
        )
    write_csv(output / "by-use-family.csv", families)
    type_rows = []
    for tid, definition in sorted(types.items()):
        members = [r for r in rows if r["native_type_id"] == tid]
        included = [r for r in members if r["direct_scope"]]
        counts = collections.Counter(r["implementation_status"] for r in included)
        type_rows.append(
            dict(
                native_type_id=tid,
                parent_id=definition["parent_id"],
                name_es=definition["name_es"],
                catalog_items=len(members),
                explicit_actions=sum(bool(r["use_action_class"]) for r in members),
                direct_scope_items=len(included),
                implemented=counts["implemented"],
                missing=counts["missing"],
                disabled=counts["code_present_disabled"],
                needs_native_review=counts["needs_native_review"],
            )
        )
    write_csv(output / "by-native-type.csv", type_rows)
    result = dict(
        revision=snapshot["revision"],
        catalog_items=len(rows),
        native_types=len(type_rows),
        explicit_action_items=len(supported),
        explicit_action_families=len(ACTION_NAMES),
        direct_scope_items=len(selected),
        direct_scope_families=len(families),
        implementation_counts=dict(
            collections.Counter(r["implementation_status"] for r in selected)
        ),
        note="Implementation means a mapped server route, not graphical acceptance of every item. Downstream usability caveats are separate. Context uses overlap and must not be added.",
        source_sha256={
            str(p): sha(p)
            for p in (
                args.snapshot,
                args.supplement,
                args.action_support,
                args.types,
                source,
            )
        },
        artifacts_sha256={p.name: sha(p) for p in sorted(output.glob("*.csv"))},
    )
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    base = Path(".runtime/item-actions-inventory-20261019")
    parser.add_argument("--snapshot", type=Path, default=base / "catalog.json")
    parser.add_argument("--supplement", type=Path, default=base / "supplement.json")
    parser.add_argument(
        "--action-support", type=Path, default=base / "action-support.json"
    )
    parser.add_argument(
        "--types",
        type=Path,
        default=Path(
            "agents_docs/reports/item-shop-inventory-20261011/native-types.json"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("agents_docs/reports/item-actions-inventory-20261019"),
    )
    print(json.dumps(build(parser.parse_args()), indent=2))
