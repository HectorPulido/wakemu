#!/usr/bin/env python3
"""Index native class components, preserving common innates as a separate layer."""
import ast
from collections import Counter, defaultdict
import csv, gzip, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "docs/reports/combat-inventory"
GRAPH = REPORTS / "class-native-mechanic-graph-20261007.json"


def read(path):
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def integer_expression(node):
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.BinOp):
        left, right = integer_expression(node.left), integer_expression(node.right)
        if isinstance(node.op, ast.BitOr):
            return left | right
        if isinstance(node.op, ast.LShift):
            return left << right
    raise ValueError("Unknown native selector source declaration")


def csv_write(path, rows):
    if not rows:
        return
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (list, dict))
                    else value
                    for key, value in row.items()
                }
            )


def main():
    inputs = [
        GRAPH,
        REPORTS / "verification-ledger-20261007.json",
        ROOT / "server/protocol/breed-innate-definitions.json",
        ROOT / "server/wakfu_server/combat/combat_effect_targets.py",
        ROOT / "server/wakfu_server/combat/combat_effect_area.py",
        Path(__file__),
    ]
    before = {str(path.relative_to(ROOT)): digest(path) for path in inputs}
    graph = read(GRAPH)
    nodes = graph["nodes"]
    edges = graph["edges"]
    ledger = read(inputs[1])
    innates = read(inputs[2])
    by_source = defaultdict(list)
    for edge in edges:
        levels = edge.get("sample_levels")
        if levels is not None and not any(0 <= level <= 245 for level in levels):
            continue
        by_source[edge["source"]].append(edge["target"])

    def closure(seeds):
        seen = set()
        pending = list(seeds)
        while pending:
            key = pending.pop()
            if key in seen:
                continue
            seen.add(key)
            pending.extend(by_source.get(key, ()))
        return seen

    def components(seen):
        result = defaultdict(list)
        for key in sorted(seen):
            result[key.split(":", 1)[0]].append(key)
        return dict(result)

    classes = []
    class_csv = []
    state_reverse = defaultdict(list)
    area_reverse = defaultdict(list)
    for breed in sorted(innates["breeds"], key=lambda row: row["breed"]):
        identity = breed["breed"]
        owned = [row for row in ledger["spells"] if identity in row["breeds"]]
        native_innates = [f"state:{row['reference']}" for row in breed["innate_states"]]
        innate_closure = closure(native_innates)
        spell_closure = closure([f"spell:{row['spell_id']}" for row in owned])
        combined = spell_closure | innate_closure
        direct = components(spell_closure)
        innate = components(innate_closure)
        specific = components(spell_closure - innate_closure)
        row = {
            "breed": identity,
            "native_class_name": breed["name_bdata"],
            "class_spell_ids": [
                r["spell_id"] for r in owned if r["origin"] == "class_catalog"
            ],
            "class_extra_ids": [
                r["spell_id"] for r in owned if r["origin"] == "class_linked_extra"
            ],
            "spell_labels": {str(r["spell_id"]): r["name"] for r in owned},
            "innate_seed_states": native_innates,
            "spell_dependency_components": direct,
            "innate_dependency_components": innate,
            "spell_components_not_in_innates": specific,
            "guarded_mechanic_reachability": "unknown",
            "complete_class_mechanics_specification": "unknown",
            "unknown_native_definitions": [
                key
                for key in sorted(combined)
                if nodes.get(key, {}).get("native_missing")
            ],
        }
        classes.append(row)
        class_csv.append(
            {
                "breed": identity,
                "native_class_name": breed["name_bdata"],
                "class_spells": len(row["class_spell_ids"]),
                "extras": len(row["class_extra_ids"]),
                "direct_spell_states": len(direct.get("state", [])),
                "innate_states": len(innate.get("state", [])),
                "direct_spell_areas": len(direct.get("area", [])),
                "direct_spell_profiles": len(direct.get("profile", [])),
                "direct_spell_native_condition_classes": len(
                    direct.get("native_condition_class", [])
                ),
                "native_missing_states": [
                    key
                    for key in row["unknown_native_definitions"]
                    if key.startswith("state:")
                ],
                "mechanic_completion": "unknown",
            }
        )
        for key in combined:
            if key.startswith("state:"):
                state_reverse[key].append(identity)
            elif key.startswith("area:"):
                area_reverse[key].append(identity)
    supported_types = {"HOUR", "GLYPH", "AURA", "GATE", "FAKE_FIGHTER"}
    area_rows = []
    for key, node in nodes.items():
        if node["kind"] != "area" or "native_evidence_line" not in node:
            continue
        prototype = (node.get("native_prototype") or {}).get("native_class")
        area_rows.append(
            {
                "reference": node["reference"],
                "native_prototype_class": prototype,
                "native_type": node.get("native_type"),
                "dependent_classes": area_reverse.get(key, []),
                "entry_masks": node.get("entry_masks"),
                "exit_masks": node.get("exit_masks"),
                "removal_masks": node.get("removal_masks"),
                "area_properties": node.get("area_properties"),
                "root_effects": [
                    target for target in by_source[key] if target.startswith("effect:")
                ],
                "creation_source_route": "conditional audited type branch present"
                if node.get("native_type") in supported_types
                else "no audited type branch observed",
                "owner_affiliation_contract": "shared capture implemented; per-prototype runtime unknown",
                "stat_initialization_contract": "prototype-dependent authority; complete domain unknown",
                "QI_registration_contract": "actual bcO/slot/history required; per-prototype runtime unknown",
                "activation_event_contract": "shared callback route present; native causes and all masks not fully verified",
                "removal_expiration_contract": "shared route present; all lifecycle cases unknown",
                "manual_client_contract": "unknown",
            }
        )
    area_rows.sort(key=lambda row: row["reference"])
    selector_source = ast.parse(inputs[3].read_text())
    known = None
    for node in ast.walk(selector_source):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "known_flags"
            for target in node.targets
        ):
            known = integer_expression(node.value)
    if known is None:
        raise ValueError("Missing native selector policy flag declaration")
    masks = defaultdict(list)
    for key, node in nodes.items():
        if node["kind"] == "effect" and "native_metadata" in node:
            selector = node["native_metadata"]["native_target_selector"]
            label = json.dumps(selector, sort_keys=True, separators=(",", ":"))
            masks[label].append(node["reference"])
    selector_rows = []
    for label, references in sorted(masks.items()):
        selector = json.loads(label)
        mask = selector.get("mask") if selector is not None else None
        selector_rows.append(
            {
                "selector_class": None if selector is None else selector["class"],
                "native_mask": mask,
                "dependent_effect_ids": references,
                "source_known_flag_mask": known,
                "unhandled_mask_bits": mask & ~known
                if type(mask) is int and mask >= 0
                else None,
                "source_route": "null-area policy present"
                if selector is None
                else "fcE flag branch present"
                if selector["class"] == "fcE"
                and type(mask) is int
                and mask >= 0
                and not mask & ~known
                else "unhandled selector class or flags",
                "runtime_native_actor_fact_producers": "required; complete domain unknown",
                "semantic_client_contract": "unknown",
            }
        )
    after = {str(path.relative_to(ROOT)): digest(path) for path in inputs}
    if before != after:
        raise ValueError("Component source snapshot changed during build")
    report = {
        "schema": 1,
        "scope": "18class component indices from native roots/references; spell dependencies separated from common innates",
        "sources_before": before,
        "sources_after": after,
        "sources_stable": True,
        "counts": {
            "classes": len(classes),
            "areas": len(area_rows),
            "selector_contracts": len(selector_rows),
        },
        "classes": classes,
        "state_to_classes": dict(sorted(state_reverse.items())),
        "area_to_classes": dict(sorted(area_reverse.items())),
        "areas": area_rows,
        "target_selectors": selector_rows,
        "limitations": [
            "Reachability and full class mechanic contracts unknown; constant-false branches preserved.",
            "Native_condition_class includes operators and literal wrappers, not only function predicates.",
            "Source route presence does not establish adequate actual runtime context or successful execution.",
            "Mask bits retain native fcE meaning; seven definition target masks remain separately typed in original graph.",
            "Common innates may reach cosmetic/KO branches; do not label every class spell broken from that fanout.",
        ],
    }
    with open(
        REPORTS / "class-native-mechanic-components-20261007.json", "wt"
    ) as stream:
        json.dump(report, stream, separators=(",", ":"), ensure_ascii=False)
    csv_write(REPORTS / "class-native-mechanic-components-20261007.csv", class_csv)
    csv_write(REPORTS / "class-native-area-contracts-20261007.csv", area_rows)
    csv_write(
        REPORTS / "class-native-target-selector-contracts-20261007.csv", selector_rows
    )
    print(
        json.dumps(
            {
                "counts": report["counts"],
                "area_prototypes": dict(
                    Counter(row["native_prototype_class"] for row in area_rows)
                ),
                "stable": True,
            }
        )
    )


if __name__ == "__main__":
    main()
