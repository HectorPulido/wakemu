#!/usr/bin/env python3
"""Build a deterministic requirement register, without importing combat catalogs.

Structural dependencies establish required work, never dynamic reachability or
functional success. Evidence is an explicit report with assertions and hashes.
"""
import gzip
import argparse
import ast
import importlib.util
import io
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from import_class_summon_dependencies import entries
from class_native_requirement_sources import (
    merged_nodes,
    verified_projection,
    referenced_projection_owners,
)

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "docs/reports/combat-inventory"
STATUSES = ("fullcycle_verified", "primitive_only", "absent", "blocked", "unverified")
PHASES = {
    "state": (
        "initialization",
        "application",
        "subscription_dispatch",
        "duration_expiry",
        "removal",
        "delivery",
    ),
    "area": (
        "creation",
        "ownership_geometry",
        "spatial_registration",
        "subscription_dispatch",
        "expiry_removal",
        "delivery",
    ),
    "profile": (
        "creation",
        "native_actor_initialization",
        "spellbook_access",
        "casting",
        "resource_consumption",
        "subscription_dispatch",
        "removal",
        "delivery",
    ),
}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as stream:
        return json.load(stream)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def argument_kind(raw):
    value = raw.strip()
    if value.startswith(('"', "'")):
        return "string_literal"
    if value.lower() in ("true", "false"):
        return "boolean_literal"
    try:
        int(value)
        return "integer_literal"
    except ValueError:
        return "native_expression_unclassified"


def level_runs(levels):
    runs = []
    for level in sorted(levels):
        if runs and level == runs[-1][1] + 1:
            runs[-1][1] = level
        else:
            runs.append([level, level])
    return runs


def asserted_outcomes_match(report, outcomes):
    if not isinstance(outcomes, list) or not outcomes:
        return False
    try:
        for assertion in outcomes:
            actual = report
            for component in assertion["report_pointer"].strip("/").split("/"):
                actual = (
                    actual[int(component)]
                    if isinstance(actual, list)
                    else actual[component]
                )
            if actual != assertion["expected"]:
                return False
    except (KeyError, IndexError, ValueError, TypeError):
        return False
    return True


def build(output, evidence_path=None):
    paths = {
        "graph": REPORTS / "class-native-mechanic-graph-20261007.json",
        "components": REPORTS / "class-native-mechanic-components-20261007.json",
        "conditions": REPORTS / "class-condition-gap-inventory.json",
        "casting": REPORTS / "class-casting-gap-inventory-20261007.json",
        "local_parser": ROOT / "server/wakfu_server/combat/combat_local_criteria.py",
        "capturable": ROOT / "server/protocol/native-class-captured-profiles.json",
        "captured_dependencies": REPORTS
        / "class-captured-dependency-inventory-20261007.json",
        "captured_typed": REPORTS
        / "class-captured-native-typed-closure-20261008.jsonl.gz",
        "captured_manifest": REPORTS
        / "class-captured-native-typed-closure-20261008.json",
        "captured_runtime": ROOT
        / "server/protocol/native-class-captured-effect-closure.json",
        "source_helper": ROOT / "server/tools/class_native_requirement_sources.py",
        "referenced_typed": REPORTS
        / "class-triggered426-native-typed-closure-20261008.jsonl.gz",
        "referenced_manifest": REPORTS
        / "class-triggered426-native-typed-closure-20261008.json",
        "captured_provenance": REPORTS
        / "native-class-captured-domain-export-20261007.json",
    }
    if evidence_path:
        paths["evidence"] = evidence_path.resolve()
    paths["generator"] = Path(__file__).resolve()
    before = {str(p.relative_to(ROOT)): sha(p) for p in paths.values()}
    components, conditions, casting = (
        read(paths[k]) for k in ("components", "conditions", "casting")
    )
    if (
        len(components["classes"]) != 18
        or len({row["breed"] for row in components["classes"]}) != 18
    ):
        raise ValueError(
            "Class requirement inputs must contain all 18 unique native classes"
        )
    membership = defaultdict(lambda: defaultdict(lambda: defaultdict(set)))
    for breed in components["classes"]:
        for scope in ("spell_dependency_components", "innate_dependency_components"):
            for nodes in breed[scope].values():
                for node in nodes:
                    membership[node][breed["breed"]][scope].add(node)
    captured_dependencies = read(paths["captured_dependencies"])
    captured_manifest, captured_references = verified_projection(
        paths["captured_typed"], paths["captured_manifest"], paths["captured_runtime"]
    )
    captured_dependencies["node_references"] = {
        plural: captured_references[kind]
        for plural, kind in {
            "spells": "spell",
            "states": "state",
            "areas": "area",
            "effects": "effect",
        }.items()
    }
    captured_kind_names = {
        "spells": "spell",
        "states": "state",
        "areas": "area",
        "effects": "effect",
    }
    for plural, references in captured_dependencies["node_references"].items():
        for reference in references:
            node = captured_kind_names[plural] + ":" + str(reference)
            membership[node][2]["captured_dependency_components"].add(node)
    for reference in captured_references["profile"]:
        node = "profile:" + str(reference)
        membership[node][2]["captured_dependency_components"].add(node)
    referenced_manifest, referenced_owners = referenced_projection_owners(
        paths["referenced_typed"], paths["referenced_manifest"], membership
    )
    for node, breeds in referenced_owners.items():
        for breed in breeds:
            membership[node][breed]["triggered_dependency_components"].add(node)
    units = {}
    condition_metadata = {row["name"]: row for row in conditions["conditions"]}
    spec = importlib.util.spec_from_file_location(
        "requirement_local_parser", paths["local_parser"]
    )
    local_parser = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(local_parser)

    def unit(key, category, contract):
        if key not in units:
            units[key] = dict(
                id=key,
                category=category,
                contract=contract,
                status="unverified",
                status_reason="No current full-cycle evidence bound to this complete contract",
                dynamic_reachability="unknown",
                affected_class_nodes={},
                evidence=[],
                requirements={},
            )
        return units[key]

    def attach(record, node, extra_classes=()):
        for breed, scopes in membership.get(node, {}).items():
            target = record["affected_class_nodes"].setdefault(str(breed), {})
            for scope in scopes:
                target.setdefault(scope, set()).add(node)
        for breed in extra_classes:
            record["affected_class_nodes"].setdefault(str(breed), {}).setdefault(
                "casting_dependencies", set()
            ).add(node)

    nodes_seen = Counter()
    unclassified_reference_slots = defaultdict(list)
    for key, node in merged_nodes(
        paths["graph"], paths["captured_typed"], paths["referenced_typed"]
    ):
        kind = node["kind"]
        if kind not in ("effect", "spell", "state", "area", "profile"):
            continue
        nodes_seen[kind] += 1
        raw = node.get("criterion_raw")
        if raw:
            normalized = (
                raw.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
            )
            try:
                parsed = local_parser.parse_local_criterion(normalized)
            except Exception as error:
                record = unit(
                    "condition_parse:" + key,
                    "condition_parse",
                    {"native_node": key, "original_expression_sha256": digest(raw)},
                )
                record.update(
                    status="blocked",
                    status_reason="Current local parser cannot classify the native expression",
                    parser_error=str(error),
                )
                attach(record, key)
            else:
                for call in ast.walk(parsed):
                    if (
                        not isinstance(call, ast.Call)
                        or not isinstance(call.func, ast.Name)
                        or call.func.id.startswith("__wakemu_")
                    ):
                        continue
                    name = call.func.id
                    shape = [
                        ("literal:" + type(arg.value).__name__)
                        if isinstance(arg, ast.Constant)
                        else type(arg).__name__
                        for arg in call.args
                    ]
                    metadata = condition_metadata.get(name, {})
                    record = unit(
                        "condition_signature:" + name + ":" + digest(shape)[:16],
                        "condition_signature",
                        {
                            "name": name,
                            "observed_argument_shape": shape,
                            "native_class": metadata.get("native_class"),
                            "required_cycle": [
                                "native_signature",
                                "observed_argument_variants",
                                "PV_null_cell_selection",
                                "authoritative_provider",
                                "positive_negative_results",
                                "guarded_runtime_dispatch",
                            ],
                        },
                    )
                    attach(record, key)
                    arguments = [
                        ast.dump(arg, include_attributes=False) for arg in call.args
                    ]
                    record["requirements"].setdefault(
                        digest(arguments),
                        {"argument_AST": arguments, "native_nodes": []},
                    )["native_nodes"].append(key)
                    record["historical_route_observation"] = {
                        "status": metadata.get("status", "unknown"),
                        "source_report": str(paths["conditions"].relative_to(ROOT)),
                        "does_not_establish_current_semantic_status": True,
                    }
        if node.get("native_missing") or node.get("native_export_exception"):
            record = unit(
                "native_definition:" + key, "native_definition", {"node": key}
            )
            record.update(
                status="blocked",
                status_reason="Native export has an explicitly missing/failed definition",
            )
            record["requirements"][key] = {
                "native_missing": node.get("native_missing"),
                "native_export_exception": node.get("native_export_exception"),
            }
            attach(record, key)
            continue
        if kind == "effect":
            if node.get("reference_semantics") == "not_classified_by_this_exporter":
                unclassified_reference_slots[node["family"]].append(key)
            family = str(node["family"])
            record = unit(
                "effect_family:" + family,
                "effect_family",
                {
                    "family": int(family),
                    "native_runner_class": node["native_runner_class"],
                    "required_cycle": [
                        "C_preparation",
                        "guards",
                        "target_resolution",
                        "application",
                        "L1_L2_L3_L4",
                        "subscriptions",
                        "retention_expiry_removal",
                        "client_delivery",
                    ],
                },
            )
            variant = {
                field: node.get(field)
                for field in (
                    "raw_parameters",
                    "native_definition",
                    "native_metadata",
                    "subscription",
                    "owner_on_caster",
                    "reverse_subscription",
                    "global_subscription",
                    "event_target_code",
                    "event_caster_code",
                    "event_priority",
                    "event_execution_count",
                    "suppresses_level_one",
                )
            }
            variant_id = digest(variant)
            requirement = record["requirements"].setdefault(
                variant_id,
                dict(
                    native_contract=variant,
                    effect_nodes=[],
                    sampled_level_domains={},
                    dynamic_reachability="unknown",
                ),
            )
            requirement["effect_nodes"].append(key)
            requirement["sampled_level_domains"][key] = {
                "minimum": node.get("minimum_level"),
                "maximum": node.get("maximum_level"),
                "sample_level_runs": level_runs(
                    node.get("parameter_sample_levels", [])
                ),
                "native_evidence_line": node.get("native_evidence_line"),
            }
            attach(record, key)
        elif kind in PHASES:
            for phase in PHASES[kind]:
                record = unit(
                    f"{kind}_lifecycle:{phase}",
                    kind + "_lifecycle",
                    {
                        "phase": phase,
                        "native_kind": kind,
                        "requirement": "Every attached native definition and its source-derived variants",
                    },
                )
                attach(record, key)
                record["requirements"][key] = {
                    "native_evidence_line": node.get("native_evidence_line"),
                    "definition_sha256": digest(node),
                }
        elif kind == "spell":
            record = unit(
                "class_access:spell_native_level_domain",
                "class_access",
                {
                    "required_cycle": [
                        "innate_or_deck_or_grant_permission",
                        "native_level_domain",
                        "ordinary_cast_validation",
                        "casting_and_effect_resolution",
                        "delivery",
                    ]
                },
            )
            attach(record, key)
            record["requirements"][key] = {
                "maximum_level": node.get("maximum_level"),
                "native_evidence_line": node.get("native_evidence_line"),
            }

    # Capture-owned casting definitions were not part of the original851
    # class casting expression inventory. Preserve complete native contracts
    # instead of inferring textual signatures from obfuscated AST fields.
    from class_native_requirement_sources import captured_rows

    for key, node in captured_rows(paths["captured_typed"]):
        if node["kind"] != "spell":
            continue
        record = unit(
            "captured_casting_native_contract",
            "captured_casting_contract",
            {
                "class_id": 2,
                "required_cycle": [
                    "native_casting_field_variants",
                    "native_criterion_AST_and_authoritative_providers",
                    "level_zero_and_normal_roots",
                    "permission_validation",
                    "positive_negative_casts",
                    "resource_spend_and_delivery",
                ],
            },
        )
        record["requirements"][key] = {
            field: node.get(field)
            for field in (
                "native_class",
                "maximum_level",
                "native_casting_definition",
                "native_cast_criterion",
                "root_samples",
                "protected",
            )
        }
        attach(record, key, [2])

    for key, node in captured_rows(paths["referenced_typed"]):
        if node["kind"] != "spell":
            continue
        record = unit(
            "referenced_casting_native_contract",
            "referenced_casting_contract",
            {
                "required_cycle": [
                    "original_native_casting_definition",
                    "native_criterion_and_provider",
                    "zero_and_normal_casting_flags_costs",
                    "permission_and_source",
                    "runtime_cast_and_delivery",
                ]
            },
        )
        record["requirements"][key] = {
            field: node.get(field)
            for field in (
                "maximum_level",
                "native_casting_definition",
                "native_cast_criterion",
                "root_samples",
            )
        }
        record["requirements"][key][
            "zero_casting_flags_costs_verified"
        ] = referenced_manifest["zero_casting_verified"]
        attach(record, key)

    for structure in conditions["native_structural_classes"]:
        if structure["textual_names"]:
            continue
        record = unit(
            "native_criterion_structure:" + structure["native_class"],
            "native_criterion_structure",
            {
                "native_class": structure["native_class"],
                "role": structure["role"],
                "required_cycle": [
                    "native_type_operator_or_literal_contract",
                    "actual_expression_execution",
                    "boundary_and_negative_results",
                    "guarded_runtime_dispatch",
                ],
            },
        )
        for node in structure["effect_nodes"]:
            attach(record, node)
        record["requirements"]["native_nodes"] = structure["effect_nodes"]

    for selector in components["target_selectors"]:
        record = unit(
            "target_selector:" + selector["selector_class"],
            "target_selector",
            {
                "native_selector_class": selector["selector_class"],
                "required_cycle": [
                    "all_native_mask_combinations",
                    "PV_null_cell_types",
                    "authoritative_actor_facts",
                    "positive_negative_selection",
                    "ordered_dispatch",
                ],
            },
        )
        mask = str(selector["native_mask"])
        record["requirements"][mask] = {
            "native_mask": selector["native_mask"],
            "native_effect_nodes": [
                "effect:" + str(value) for value in selector["dependent_effect_ids"]
            ],
        }
        for node in record["requirements"][mask]["native_effect_nodes"]:
            attach(record, node)

    captured = read(paths["capturable"])
    for plural, references in captured_dependencies["node_references"].items():
        kind = captured_kind_names[plural]
        record = unit(
            "captured_native_projection:" + kind,
            "captured_dependency_projection",
            {
                "native_kind": kind,
                "class_id": 2,
                "required_cycle": [
                    "complete_original_native_metadata",
                    "all_level_zero_and_normal_variants",
                    "complete_typed_reference_closure",
                    "mechanical_unit_integration",
                ],
            },
        )
        record.update(
            status="unverified",
            status_reason="Original typed/level-zero projection and runtime structural import verified; normal dispatch lifecycle is unverified",
        )
        for reference in references:
            node = kind + ":" + str(reference)
            attach(record, node, [2])
            record["requirements"][node] = {
                "reference": reference,
                "typed_projection": "original_verified",
                "runtime_dispatch": "unverified",
            }
        record["affected_class_nodes"] = {
            "2": {
                "captured_dependency_components": {
                    kind + ":" + str(reference) for reference in references
                }
            }
        }
    pending_profiles = captured_dependencies["pending_profile_ids"]
    record = unit(
        "captured_nested_profile_closure",
        "captured_dependency_projection",
        {
            "class_id": 2,
            "required_cycle": [
                "native307creation_descriptor",
                "profile_initial_state_and_book",
                "complete_scoped_native_dependency_closure",
            ],
        },
    )
    record.update(
        status="unverified",
        status_reason="All eight nested profiles are present in exact typed projection; runtime creation and lifecycle remain unverified",
    )
    record["requirements"]["pending_profile_ids"] = []
    record["requirements"]["projected_nested_profile_ids"] = pending_profiles
    if not set(pending_profiles) <= set(captured_references["profile"]):
        raise ValueError("Nested profile typed closure incomplete")
    record["requirements"]["native307_edges"] = captured_dependencies[
        "nested_summon_effect_profiles"
    ]
    for reference in pending_profiles:
        attach(record, "captured_nested_profile:" + str(reference), [2])

    for phase in PHASES["profile"]:
        record = unit(
            "captured_profile_lifecycle:" + phase,
            "captured_profile_lifecycle",
            {
                "phase": phase,
                "native_scope": "Exact33class-Osa capturable profiles, no general monster spells",
                "required_cycle": [
                    "original_capture_guard",
                    "owned_roster_access",
                    "native_profile_contract",
                    "complete_scoped_effect_state_area_dependency_closure",
                    "actual_runtime_cycle",
                ],
            },
        )
        for identity, profile in sorted(captured["profiles"].items()):
            node = "captured_profile:" + str(identity)
            attach(record, node, [2])
            record["requirements"][node] = {
                "native_profile": profile,
                "effect_state_area_closure_status": "pending",
            }

    for expression in casting["expressions"]:
        for call in expression.get("native_calls", []):
            shape = [argument_kind(arg) for arg in call["arguments_raw"]]
            identity = call["name"] + ":" + digest(shape)[:16]
            record = unit(
                "casting_condition_signature:" + identity,
                "casting_condition_signature",
                {
                    "name": call["name"],
                    "observed_argument_kinds": shape,
                    "native_class": call.get("native_class"),
                    "declared_native_signatures": call.get(
                        "declared_argument_signatures"
                    ),
                    "required_cycle": [
                        "native_signature",
                        "authoritative_provider",
                        "positive_negative_results",
                        "permission_valid_cast_with_original_guard",
                    ],
                },
            )
            node = "spell:" + str(expression["spell_id"])
            attach(record, node, expression["class_ids"])
            record["requirements"].setdefault(
                digest(call["arguments_raw"]),
                {"arguments_raw": call["arguments_raw"], "spell_nodes": []},
            )["spell_nodes"].append(node)

    for spell in casting["spells"]:
        node = "spell:" + str(spell["spell_id"])
        for name, value in spell["native_casting"].items():
            record = unit(
                "casting_feature:" + name,
                "casting_feature",
                {
                    "native_feature": name,
                    "required_cycle": [
                        "native_sampled_values",
                        "server_producer",
                        "allowed_disallowed_casts",
                        "resources_and_delivery",
                    ],
                },
            )
            attach(record, node, spell["class_ids"])
            record["requirements"].setdefault(
                digest(value), {"native_value": value, "spell_nodes": []}
            )["spell_nodes"].append(node)

    for breed in components["classes"]:
        record = unit(
            "class_access:breed:" + str(breed["breed"]),
            "class_access",
            {
                "breed": breed["breed"],
                "native_class_name": breed["native_class_name"],
                "required_cycle": [
                    "character_creation",
                    "Ready",
                    "innate_execution",
                    "deck_access",
                    "grants_transformations",
                    "states_areas_summons",
                    "turn_events",
                    "casting_delivery",
                    "removal_death_cleanup",
                ],
            },
        )
        for reference in breed["class_spell_ids"] + breed["class_extra_ids"]:
            attach(record, "spell:" + str(reference), [breed["breed"]])
        record["affected_class_nodes"] = {
            str(breed["breed"]): {
                "direct_class_access_seeds": {
                    "spell:" + str(reference)
                    for reference in breed["class_spell_ids"] + breed["class_extra_ids"]
                }
            }
        }

    evidence = read(evidence_path) if evidence_path else {"claims": []}
    rejected = []
    for claim in evidence.get("claims", []):
        key = claim["unit_id"]
        if key not in units:
            rejected.append({"unit_id": key, "reason": "Unknown unit"})
            continue
        mismatches = [
            path
            for path, expected in claim.get("source_sha256", {}).items()
            if not (ROOT / path).exists() or sha(ROOT / path) != expected
        ]
        report = ROOT / claim["report_path"]
        valid = (
            not mismatches
            and claim.get("source_sha256")
            and report.exists()
            and sha(report) == claim.get("report_sha256")
            and asserted_outcomes_match(read(report), claim.get("asserted_outcomes"))
        )
        status = claim.get("status")
        if status == "fullcycle_verified":
            valid = (
                valid
                and claim.get("complete_contract_sha256")
                == digest(units[key]["contract"])
                and claim.get("requirements_sha256")
                == digest(units[key]["requirements"])
                and claim.get("all_required_variants_asserted") is True
                and claim.get("positive_and_negative_cases_asserted") is True
            )
        if not valid or status not in STATUSES:
            rejected.append(
                {
                    "unit_id": key,
                    "reason": "Evidence incomplete or invalidated",
                    "changed_sources": mismatches,
                }
            )
            continue
        units[key].update(status=status, status_reason=claim["scope"])
        units[key]["evidence"].append(claim)

    for record in units.values():
        record["affected_class_nodes"] = {
            breed: {scope: sorted(nodes) for scope, nodes in scopes.items()}
            for breed, scopes in sorted(
                record["affected_class_nodes"].items(), key=lambda pair: int(pair[0])
            )
        }
        record["requirement_variant_count"] = len(record["requirements"])
        record["contract_sha256"] = digest(record["contract"])
        record["requirements_sha256"] = digest(record["requirements"])
    after = {str(p.relative_to(ROOT)): sha(p) for p in paths.values()}
    if before != after:
        raise ValueError("Source inventories changed during requirement generation")
    counts = Counter(record["status"] for record in units.values())
    output_data = {
        "schema": 1,
        "scope": "All 18 native classes, innates, fixed class summons and exact 33 class-Osa capturable profile requirements",
        "source_sha256": before,
        "sources_stable": True,
        "generator_sha256": sha(Path(__file__)),
        "units": [units[key] for key in sorted(units)],
        "counts_by_status": dict(counts),
        "counts_by_category": dict(
            Counter(record["category"] for record in units.values())
        ),
        "unit_index": [
            {
                "id": r["id"],
                "category": r["category"],
                "status": r["status"],
                "affected_breeds": sorted(map(int, r["affected_class_nodes"])),
                "contract_sha256": r["contract_sha256"],
                "requirements_sha256": r["requirements_sha256"],
            }
            for r in sorted(units.values(), key=lambda row: row["id"])
        ],
        "current_register_unit_count": len(units),
        "fullcycle_verified_units": counts["fullcycle_verified"],
        "native_breed_names": {
            str(r["breed"]): r["native_class_name"] for r in components["classes"]
        },
        "class_id_policy": "Native aKe.d breed IDs, never component/list position",
        "global_denominator_final": False,
        "global_verified_mechanics_denominator": None,
        "global_verified_mechanics_percent": None,
        "native_reference_slot_classification_unverified": [
            dict(
                family=family,
                native_nodes=sorted(nodes),
                source_status="not_classified_by_this_exporter",
                is_reference_producer=None,
            )
            for family, nodes in sorted(unclassified_reference_slots.items())
        ],
        "pending_scope": [
            "Native reference producers still marked unclassified/unknown by graph",
            "Original five referenced426 spell zero casting flags/costs pending",
        ],
        "counting_policy": "One unweighted contract unit; every attached exact variant is required for fullcycle verification",
        "reachability_policy": "Attached nodes are structural requirements; native sampled availability is not dynamic reachability",
        "status_policy": "Default unverified. Explicit current report assertions only; no inference from handler registration or passing test counts",
        "rejected_or_invalidated_evidence": rejected,
        "native_nodes_seen": dict(nodes_seen),
    }
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(output_data, stream, separators=(",", ":"))
    temporary.replace(output)
    summary = {key: value for key, value in output_data.items() if key != "units"}
    summary["artifact_sha256"] = sha(output)
    output.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [
        "# Class mechanic requirement register",
        "",
        "Native class IDs follow original aKe.d:2=OSAMODAS,9=CRA; these are not component positions.",
        "",
        f'Current register: {len(units)} unweighted contract units; {counts["fullcycle_verified"]} full-cycle verified.',
        "Exact captured typed and level-zero projection, including eight nested profiles, is integrated. The register denominator remains provisional because native reference producers are still unclassified; ordinary runtime dispatch remains unverified.",
        "",
        "| Category | Units | Full cycle | Primitive only | Absent | Blocked | Unverified |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for category in sorted({r["category"] for r in units.values()}):
        rows = [r for r in units.values() if r["category"] == category]
        counter = Counter(r["status"] for r in rows)
        lines.append(
            "| "
            + category
            + " | "
            + str(len(rows))
            + " | "
            + " | ".join(str(counter[s]) for s in STATUSES)
            + " |"
        )
    lines.extend(
        [
            "",
            "| Explicit metadata gap | Class IDs | Required records |",
            "|---|---|---:|",
        ]
    )
    for record in sorted(
        (r for r in units.values() if r["status"] == "blocked"),
        key=lambda row: row["id"],
    ):
        breeds = ",".join(sorted(record["affected_class_nodes"], key=int))
        count = len(record["requirements"])
        if record["id"] == "captured_nested_profile_closure":
            count = len(record["requirements"]["pending_profile_ids"])
        lines.append("| " + record["id"] + " | " + breeds + " | " + str(count) + " |")
    lines.extend(
        [
            "",
            "Each machine-record lists exact affected class nodes, native variants and evidence hashes.",
            "Changed evidence hashes invalidate the claim and leave its unit unverified. Historical route presence is retained only as a diagnostic.",
            "No functional percentage is inferred from Ready cases, imported definitions, primitive native oracles, registered handlers or test totals.",
        ]
    )
    output.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print(
        json.dumps(
            {
                "units": len(units),
                "statuses": dict(counts),
                "global_denominator_final": False,
            }
        )
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=REPORTS / "class-mechanic-requirements-20261007.json",
    )
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    build(args.output, args.evidence)


if __name__ == "__main__":
    main()
