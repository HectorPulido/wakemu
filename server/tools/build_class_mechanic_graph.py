#!/usr/bin/env python3
"""Prepare and index a native class-only metadata graph without combat imports.

Native parameter/root samples are expectations for those exact primitives, not
expected gameplay outcomes or proof that their guarded branches are reachable.
"""
import gzip
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / ".runtime/combat-review-20261007/mechanic-graph"
REPORTS = ROOT / "docs/reports/combat-inventory"


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_text())


def prepare():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    ledger = read(REPORTS / "verification-ledger-20261007.json")
    innates = read(ROOT / "server/protocol/breed-innate-definitions.json")
    profiles = read(ROOT / "server/protocol/native-class-summon-abilities.json")[
        "profiles"
    ]
    spells = {row["spell_id"] for row in ledger["spells"]}
    spells.update(
        ability["reference"]
        for profile in profiles.values()
        for ability in profile["abilities"]
    )
    seeds = {
        "spell": sorted(spells),
        "state": sorted(
            {
                state["reference"]
                for breed in innates["breeds"]
                for state in breed["innate_states"]
            }
        ),
        "profile": sorted(map(int, profiles)),
    }
    seed_path = PRIVATE / "seeds.json"
    seed_path.write_text(json.dumps(seeds, indent=2) + "\n")
    paths = [
        seed_path,
        ROOT / "sniffer/java/ExportClassMechanicGraph.java",
        ROOT / "sniffer/java/ExportClassSummonEffectTrees.java",
        ROOT / "sniffer/java/ExportEffectRuntimeMetadata.java",
        ROOT / "server/protocol/native-class-summon-abilities.json",
        ROOT / "server/protocol/breed-innate-definitions.json",
        REPORTS / "verification-ledger-20261007.json",
    ]
    paths.extend(sorted((ROOT / "client/lib").glob("*.jar")))
    paths.extend(sorted((ROOT / "client/contents/bdata").glob("*.jar")))
    sources = {str(path.relative_to(ROOT)): sha(path) for path in paths}
    (PRIVATE / "sources-before.json").write_text(json.dumps(sources, indent=2) + "\n")
    print(
        json.dumps(
            {
                "seeds": {key: len(value) for key, value in seeds.items()},
                "sources": len(sources),
            }
        )
    )


def grouped(values):
    """Retain exact level membership; no extrapolation beyond sampled levels."""
    groups = {}
    for level, value in values.items():
        key = json.dumps(value, sort_keys=True, separators=(",", ":"))
        if key not in groups:
            groups[key] = {"sample_levels": [], "native_value": value}
        groups[key]["sample_levels"].append(int(level))
    return list(groups.values())


def native_condition_classes(value):
    result = set()
    if isinstance(value, dict):
        if "native_class" in value:
            result.add(value["native_class"])
        for child in value.values():
            result.update(native_condition_classes(child))
    elif isinstance(value, list):
        for child in value:
            result.update(native_condition_classes(child))
    return result


def index(native_path, output):
    before = read(PRIVATE / "sources-before.json")
    current = {key: sha(ROOT / key) for key in before}
    if before != current:
        raise ValueError(
            "Native graph source hashes changed since preparation; do not accredit export"
        )
    nodes = {}
    edges = []
    reverse = defaultdict(list)
    unknown = []
    families = Counter()
    native_counts = Counter()

    def edge(source, target, kind, **facts):
        value = dict(
            source=source, target=target, kind=kind, reachability="unknown", **facts
        )
        edges.append(value)
        reverse[target].append(len(edges) - 1)

    with gzip.open(native_path, "rt") as stream:
        for line_number, line in enumerate(stream, 1):
            row = json.loads(line)
            kind = row["kind"]
            key = f"{kind}:{row['reference']}"
            if key in nodes:
                raise ValueError(f"Duplicate native node {key}")
            native_counts[kind] += 1
            node = {
                "kind": kind,
                "reference": row["reference"],
                "native_evidence_line": line_number,
                "reachability": "unknown",
                "mechanic_semantics": "unclassified",
                "criterion_raw": row.get("criterion_raw"),
                "native_missing": row.get("native_missing", False),
                "native_export_exception": row.get("native_export_exception"),
            }
            if node["native_missing"] or node["native_export_exception"]:
                unknown.append(key)
                nodes[key] = node
                continue
            if kind == "effect":
                family = row["family"]
                families[family] += 1
                node.update(
                    family=family,
                    native_runner_class=row["native_runner_class"],
                    raw_parameters=row["raw_parameters"],
                    native_definition=row["native_definition"],
                    reference_semantics=row["reference_semantics"],
                    native_criterion_structure=row["criterion_native"],
                    native_metadata=row["native_metadata"],
                    subscription=row["subscription"],
                    owner_on_caster=row["owner_on_caster"],
                    reverse_subscription=row["reverse_subscription"],
                    global_subscription=row["global_subscription"],
                    event_target_code=row["event_target_code"],
                    event_caster_code=row["event_caster_code"],
                    event_priority=row["event_priority"],
                    event_execution_count=row["event_execution_count"],
                    suppresses_level_one=row["suppresses_level_one"],
                    parameter_sample_levels=sorted(map(int, row["samples"])),
                    minimum_level=row["minimum_level"],
                    maximum_level=row["maximum_level"],
                )
                for native_class in sorted(
                    native_condition_classes(row["criterion_native"])
                ):
                    edge(
                        key,
                        f"native_condition_class:{native_class}",
                        "native_parsed_criterion_class",
                        criterion_raw=row["criterion_raw"],
                        predicate_semantics="unknown",
                    )
                for position, child in enumerate(row["children_ordered"]):
                    edge(
                        key, f"effect:{child}", "ordered_group_child", position=position
                    )
                ref_groups = defaultdict(list)
                for sample in row["classified_reference_samples"]:
                    ref_groups[
                        (sample["kind"], sample["reference"], sample["parameter_slot"])
                    ].append(sample["sample_level"])
                for (target_kind, reference, slot), levels in sorted(
                    ref_groups.items()
                ):
                    edge(
                        key,
                        f"{target_kind}:{reference}",
                        "native_parameter_reference",
                        parameter_slot=slot,
                        sample_levels=levels,
                        evaluation_mode="eVh.rpA",
                        execution_override_semantics="unknown",
                    )
                metadata = row["native_metadata"]
                for method, bits in zip(
                    ("aZG", "aZH", "aZI", "aZJ", "aZK", "aZL", "aZO"),
                    metadata["target_masks"],
                ):
                    if bits is not None:
                        for bit in bits:
                            edge(
                                key,
                                f"native_mask_bit:{method}:{bit}",
                                "native_definition_mask",
                                native_method=method,
                                bit=bit,
                                combat_event_semantics="unclassified_preserved_channel",
                            )
                for channel, triggers in metadata["native_hmi_actions"].items():
                    for position, trigger in enumerate(triggers):
                        edge(
                            key,
                            f"hmi_trigger:{trigger['id']}",
                            "native_hmi_trigger",
                            channel=channel,
                            position=position,
                            native_trigger=trigger,
                            combat_event_semantics="not_inferred_from_HMI",
                        )
            elif kind == "spell":
                node.update(
                    native_cast_criterion=row["native_cast_criterion"],
                    native_casting_definition=row["native_casting_definition"],
                    maximum_level=row["maximum_level"],
                    root_sample_groups=grouped(row["root_samples"]),
                )
                root_levels = defaultdict(list)
                for level, roots in row["root_samples"].items():
                    for position, root in enumerate(roots):
                        root_levels[(position, root)].append(int(level))
                for (position, root), levels in sorted(root_levels.items()):
                    edge(
                        key,
                        f"effect:{root}",
                        "native_spell_root",
                        position=position,
                        sample_levels=levels,
                    )
            elif kind == "state":
                node.update(
                    native_definition=row["native_definition"],
                    native_container=row["native_container"],
                    level_sample_groups=grouped(row["level_samples"]),
                )
                for position, root in enumerate(row["raw_roots"]):
                    edge(
                        key,
                        f"effect:{root}",
                        "native_state_raw_root",
                        position=position,
                    )
                root_levels = defaultdict(list)
                for level, sample in row["level_samples"].items():
                    for position, root in enumerate(sample["roots"]):
                        root_levels[(position, root)].append(int(level))
                for (position, root), levels in sorted(root_levels.items()):
                    edge(
                        key,
                        f"effect:{root}",
                        "native_state_selected_root",
                        position=position,
                        sample_levels=levels,
                    )
            elif kind == "area":
                node.update(
                    native_definition=row["native_definition"],
                    native_prototype=row["native_prototype"],
                    native_type=row["type"],
                    entry_masks=row["entry_masks"],
                    exit_masks=row["exit_masks"],
                    removal_masks=row["removal_masks"],
                    area_properties=row["area_properties"],
                )
                for position, root in enumerate(row["raw_roots"]):
                    edge(
                        key, f"effect:{root}", "native_area_raw_root", position=position
                    )
                for channel in ("entry_masks", "exit_masks", "removal_masks"):
                    for bit in row[channel] or []:
                        edge(
                            key,
                            f"area_mask:{channel}:{bit}",
                            "native_area_mask",
                            channel=channel,
                            bit=bit,
                        )
            elif kind == "profile":
                node["native_ability_profile"] = row["native_ability_profile"]
                for position, ability in enumerate(
                    row["native_ability_profile"]["abilities"]
                ):
                    edge(
                        key,
                        f"spell:{ability['reference']}",
                        "native_profile_ability",
                        position=position,
                        native_ability=ability,
                    )
            nodes[key] = node
    native_node_count = len(nodes)
    for target in sorted(reverse):
        if target not in nodes:
            virtual_kind = target.split(":", 1)[0]
            nodes[target] = {
                "kind": virtual_kind,
                "reference_key": target,
                "reachability": "unknown",
                "native_definition_exported": False,
                "evidence": "stored native metadata or sampled reference edge only",
                "unexpanded_reason": "not_a_traversed_native_definition",
            }
    after = {key: sha(ROOT / key) for key in before}
    if before != after:
        raise ValueError("Sources changed while indexing native graph")
    report = {
        "schema": 1,
        "scope": "Class813 definitions plus native class innates and only39class-referenced summon profiles; no general monster or AI execution",
        "sources_before": before,
        "sources_after": after,
        "sources_stable": True,
        "native_export": {
            "path": str(native_path.relative_to(ROOT)),
            "sha256": sha(native_path),
        },
        "counts": dict(native_counts),
        "native_definition_node_count": native_node_count,
        "total_typed_nodes": len(nodes),
        "index_tool_sha256": sha(Path(__file__)),
        "effect_family_counts": {str(k): v for k, v in sorted(families.items())},
        "unknown_native_nodes": unknown,
        "dynamic_reachability": "unknown",
        "functional_completion_percent": None,
        "expectation_domains": [
            "Exact native sampled root selection and order",
            "Exact native parameter/probability/timing samples in native export",
            "Actual stored selectors, criterion structures, masks and subscription metadata",
        ],
        "unproved_domains": [
            "Runtime criterion evaluation and branch reachability",
            "Runner C/application outcomes and context-derived references",
            "Reference-producing families outside304/eYQ/649/307",
            "Deep reflective subobjects marked depth_limit/cycle_or_shared_identity remain unknown; raw criterion text retained fully",
            "Full transformation or class-mechanic classification",
            "Live events, lifecycle and client application",
        ],
        "nodes": nodes,
        "edges": edges,
        "reverse_index": dict(sorted(reverse.items())),
    }
    temporary = output.with_name(output.name + ".tmp")
    with open(temporary, "wt") as stream:
        json.dump(report, stream, separators=(",", ":"))
    temporary.replace(output)
    summary = {
        key: report[key]
        for key in (
            "scope",
            "counts",
            "effect_family_counts",
            "unknown_native_nodes",
            "sources_stable",
            "dynamic_reachability",
            "expectation_domains",
            "unproved_domains",
        )
    }
    summary["graph_path"] = str(output.relative_to(ROOT))
    summary["graph_sha256"] = sha(output)
    summary["edges"] = len(edges)
    summary["reverse_index_nodes"] = len(reverse)
    summary_path = output.with_suffix(".summary.json")
    summary_temporary = summary_path.with_name(summary_path.name + ".tmp")
    summary_temporary.write_text(json.dumps(summary, indent=2) + "\n")
    summary_temporary.replace(summary_path)
    print(
        json.dumps(
            {
                "counts": dict(native_counts),
                "edges": len(edges),
                "unknown": len(unknown),
                "stable": True,
            }
        )
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument(
        "--native", type=Path, default=PRIVATE / "native-graph.jsonl.gz"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPORTS / "class-native-mechanic-graph-20261007.json",
    )
    args = parser.parse_args()
    if args.prepare:
        prepare()
    else:
        index(args.native, args.output)


if __name__ == "__main__":
    main()
