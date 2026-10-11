"""Attach explicit contract and event-producer evidence to the static inventory."""
from collections import defaultdict
import csv
import hashlib
import json


def enrich(result, catalogs, root, private):
    registry = catalogs["effect-characteristic-registry.json"]["effects"]
    runtime_producers = json.loads((private / "runtime-producers.json").read_text())
    intrinsic = json.loads((private / "intrinsic-events.json").read_text())
    producers = defaultdict(list)
    for ref, row in runtime_producers.items():
        for event in row["event_ids"]:
            producers[event].append(
                dict(
                    kind="compiled_definition_extra_mask",
                    reference=int(ref),
                    effect_class=row["effect_class"],
                )
            )
    for name, document in intrinsic.items():
        if name == "effect-characteristic-registry.json":
            continue
        for cls, row in document["effects"].items():
            for event in row["events"]:
                producers[event].append(
                    dict(
                        kind="native_runner_intrinsic_catalog",
                        effect_class=int(cls),
                        catalog=name,
                    )
                )
    import ast

    displacement_path = (
        root / "server/wakfu_server/combat/combat_displacement_events.py"
    )
    for node in ast.parse(displacement_path.read_text()).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "BASE_EVENT_IDS"
            for target in node.targets
        ):
            for cls, ids in ast.literal_eval(node.value).items():
                for event in ids:
                    producers[event].append(
                        dict(
                            kind="audited_runner_producer",
                            effect_class=cls,
                            source=str(displacement_path.relative_to(root)),
                        )
                    )
    explicit = {
        500: "combat_attack_preparation.py",
        1: "combat_ordinary_events.py",
        2: "combat_damage_events.py",
        5: "combat_damage_events.py",
        6: "combat_damage_events.py",
        7: "combat_damage_events.py",
        8: "combat_damage_events.py",
        9: "combat_damage_events.py",
        11: "combat_damage_events.py",
        60: "combat_cost_payment_events.py",
        77: "combat_resource_loss.py",
        79: "combat_resource_loss.py",
        185: "combat_displacement_events.py",
        1001: "combat_turn_events.py",
        1002: "combat_turn_events.py",
        1003: "combat_start_events.py",
        1005: "combat_voluntary_movement_events.py",
        1010: "combat_death_events.py",
        1015: "combat_finisher_events.py",
        1018: "combat_finisher_events.py",
        1024: "combat_cast_events.py",
        1025: "combat_cast_events.py",
        1028: "combat_start_events.py",
        1037: "combat_turn_events.py",
        2130: "combat_summon_handler.py",
        2188: "combat_cost_payment_events.py",
        2233: "combat_damage_events.py",
        2234: "combat_cost_payment_events.py",
        2246: "combat_breeze_payment_events.py",
        2263: "combat_cost_payment_events.py",
    }
    policies = {
        500,
        1001,
        1002,
        1003,
        1005,
        1010,
        1015,
        1018,
        1024,
        1025,
        1028,
        1037,
        2188,
        2234,
        2263,
    }
    for event, path in explicit.items():
        producers[event].append(
            dict(
                kind="explicit_server_boundary_policy"
                if event in policies
                else "audited_runner_producer",
                source="server/wakfu_server/combat/" + path,
            )
        )
    events = {}
    for ref, row in result["effects"].items():
        cls = row["effect_class"]
        contract = registry.get(str(cls))
        row["characteristic_registry_contract"] = contract
        row["parameter_contract_gaps"] = []
        if contract:
            accepted = contract.get("parameter_contract", {}).get("supported_counts")
            if accepted is not None and row["parameter_count"] not in accepted:
                row["parameter_contract_gaps"].append(
                    "characteristic_registry_parameter_count_not_supported"
                )
        if cls in (20, 31, 41, 191) and len(row["parameters"]) != 6:
            row["parameter_contract_gaps"].append(
                "maximum_resource_requires_three_parameter_pairs"
            )
        if not row["retained_metadata"]:
            row["parameter_contract_gaps"].append("missing_retained_metadata")
        row["required_event_ids"] = []
        retained = row["retained_metadata"] or {}
        if retained.get("subscription"):
            masks = row["metadata"].get("target_masks", [None] * 7)
            for index, mask in enumerate(masks[:6]):
                for event in mask or []:
                    entry = events.setdefault(
                        str(event),
                        dict(
                            event_id=event,
                            effect_refs=[],
                            scroll_refs=[],
                            mask_indexes=[],
                            producer_candidates=producers[event],
                            status="producer_candidates_present_reachability_unverified"
                            if producers[event]
                            else "no_integrated_producer_identified",
                        ),
                    )
                    entry["effect_refs"].append(int(ref))
                    entry["mask_indexes"].append(index)
                    row["required_event_ids"].append(event)
            row["required_event_ids"] = sorted(set(row["required_event_ids"]))
    for item in result["items"]:
        item["required_event_ids"] = sorted(
            {
                event
                for ref in item["effect_refs"]
                if str(ref) in result["effects"]
                for event in result["effects"][str(ref)]["required_event_ids"]
            }
        )
        item["events_without_identified_producer"] = [
            event
            for event in item["required_event_ids"]
            if events[str(event)]["status"] == "no_integrated_producer_identified"
        ]
        item["parameter_contract_gap_effects"] = [
            ref
            for ref in item["effect_refs"]
            if str(ref) in result["effects"]
            and result["effects"][str(ref)]["parameter_contract_gaps"]
        ]
        if item["events_without_identified_producer"]:
            item["gaps"].append("subscription_event_producer_not_identified")
        if item["parameter_contract_gap_effects"]:
            item["gaps"].append("unsupported_or_missing_parameter_contract")
        for event in item["required_event_ids"]:
            events[str(event)]["scroll_refs"].append(item["reference"])
    for row in events.values():
        row["effect_refs"] = sorted(set(row["effect_refs"]))
        row["scroll_refs"] = sorted(set(row["scroll_refs"]))
        row["mask_indexes"] = sorted(set(row["mask_indexes"]))
    result["subscription_events"] = dict(
        sorted(events.items(), key=lambda item: int(item[0]))
    )
    result["counts"]["subscription_event_ids"] = len(events)
    result["counts"]["subscription_events_without_identified_producer"] = sorted(
        int(k) for k, v in events.items() if not v["producer_candidates"]
    )
    from collections import Counter

    result["counts"]["scrolls_by_gap"] = dict(
        Counter(g for row in result["items"] for g in row["gaps"])
    )
    result["counts"]["unsupported_criteria_effects"] = sum(
        row["condition_validation"]
        != "syntax_and_signature_supported_context_still_required"
        for row in result["effects"].values()
    )
    result["counts"]["parameter_contract_gap_effects"] = sum(
        bool(row["parameter_contract_gaps"]) for row in result["effects"].values()
    )
    result["source_sha256"].update(
        {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (root / "server/wakfu_server/combat").glob("*.py")
        }
    )
    for name in (
        "catalog-index.json",
        "runtime-effects.json",
        "runtime-producers.json",
        "intrinsic-events.json",
        "condition-aliases.json",
        "set-current.json",
        "set-current-contracts.json",
        "patterns.json",
    ):
        result["source_sha256"][
            str((private / name).relative_to(root))
        ] = hashlib.sha256((private / name).read_bytes()).hexdigest()
    result["catalog_document_hashes"] = json.loads(
        (private / "catalog-index.json").read_text()
    )["documents"]
    output = root / "docs/reports/sublimation-combat-inventory"
    for filename, records, fields in (
        (
            "scrolls.csv",
            result["items"],
            [
                "reference",
                "name",
                "type",
                "roots",
                "state_refs",
                "effect_refs",
                "missing_primitive_classes",
                "unsupported_criterion_effects",
                "uncompiled_effect_refs",
                "required_event_ids",
                "events_without_identified_producer",
                "parameter_contract_gap_effects",
                "gaps",
            ],
        ),
        (
            "states.csv",
            list(result["states"].values()),
            ["reference", "name", "maximum_level", "effect_refs"],
        ),
        (
            "events.csv",
            list(events.values()),
            [
                "event_id",
                "status",
                "mask_indexes",
                "effect_refs",
                "scroll_refs",
                "producer_candidates",
            ],
        ),
    ):
        with (output / filename).open("w") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for record in records:
                writer.writerow(
                    {
                        k: json.dumps(v, ensure_ascii=False)
                        if isinstance(v, (list, dict))
                        else v
                        for k, v in record.items()
                        if k in fields
                    }
                )
    result["source_sha256"].update(
        {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (root / "docs/reports/sublimation-combat-inventory").glob(
                "*.py"
            )
        }
    )
    condition_source = root / "server/wakfu_server/combat/combat_conditions.py"
    import ast

    tree = ast.parse(condition_source.read_text())
    condition_functions = {}
    for row in result["effects"].values():
        for name in row["condition_functions"]:
            entry = condition_functions.setdefault(
                name,
                dict(
                    name=name,
                    effect_refs=[],
                    scroll_refs=[],
                    source_lines=sorted(
                        {
                            node.lineno
                            for node in ast.walk(tree)
                            if isinstance(node, ast.Constant) and node.value == name
                        }
                    ),
                    status="signature_present_context_unverified"
                    if name != "HasWeaponType"
                    else "missing_evaluator_native_eMV_contract_identified",
                ),
            )
            entry["effect_refs"].append(row["reference"])
    for item in result["items"]:
        for name in item["condition_functions"]:
            condition_functions[name]["scroll_refs"].append(item["reference"])
    for row in condition_functions.values():
        row["effect_refs"] = sorted(set(row["effect_refs"]))
    result["condition_functions"] = dict(sorted(condition_functions.items()))
    with (output / "classes.csv").open("w") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "effect_class",
                "primitive_status",
                "native_runner",
                "fixed_stat_name",
                "parameter_counts",
                "effect_refs",
                "scroll_refs",
            ],
        )
        writer.writeheader()
        for cls, row in result["classes"].items():
            contract = registry.get(cls, {})
            writer.writerow(
                dict(
                    effect_class=cls,
                    primitive_status=row["primitive_status"],
                    native_runner=contract.get("runner", ""),
                    fixed_stat_name=contract.get("fixed_stat_name", ""),
                    parameter_counts=json.dumps(
                        sorted(
                            {
                                result["effects"][str(ref)]["parameter_count"]
                                for ref in row["effect_refs"]
                            }
                        )
                    ),
                    effect_refs=json.dumps(row["effect_refs"]),
                    scroll_refs=json.dumps(row["scroll_refs"]),
                )
            )
    with (output / "criteria.csv").open("w") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "reference",
                "criterion",
                "condition_functions",
                "condition_validation",
            ],
        )
        writer.writeheader()
        for row in result["effects"].values():
            if row["criterion"]:
                writer.writerow(
                    {
                        k: json.dumps(row[k]) if isinstance(row[k], list) else row[k]
                        for k in writer.fieldnames
                    }
                )
