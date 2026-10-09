"""Build a state denominator inventory without importing combat runtime."""
import ast
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re

from import_class_summon_dependencies import entries
from build_class_dependency_inventory import declared, dispatch_routes
from build_spell_inventory import literal_handler_families

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/reports/combat-inventory"
DATA = ROOT / "server/protocol"
COMBAT = ROOT / "server/wakfu_server/combat"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1048576), b""):
            value.update(chunk)
    return value.hexdigest()


def main():
    graph_path = REPORT / "class-native-mechanic-graph-20261007.json"
    catalog_path = DATA / "combat-state-definitions.json"
    paths = [
        graph_path,
        catalog_path,
        DATA / "effect-characteristic-registry.json",
        DATA / "breed-innate-definitions.json",
        REPORT / "verification-ledger-20261007.json",
        COMBAT / "combat_effect_runtime.py",
        COMBAT / "combat_effect_dispatch.py",
        COMBAT / "combat_damage_healing.py",
        COMBAT / "combat_displacement.py",
        COMBAT / "combat_state_handler.py",
        COMBAT / "combat_state_application.py",
        COMBAT / "combat_state_parameters.py",
        COMBAT / "combat_definitions.py",
        COMBAT / "combat_state_timing.py",
        COMBAT / "combat_native_timing_context.py",
        COMBAT / "combat_state_ledger.py",
        COMBAT / "combat_state_decurse.py",
        COMBAT / "combat_subscription_runners.py",
        DATA / "state-decurse-rules.json",
        Path(__file__).with_name("import_class_summon_dependencies.py"),
        Path(__file__).with_name("build_class_dependency_inventory.py"),
        Path(__file__).with_name("build_spell_inventory.py"),
        Path(__file__),
    ]
    before = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    with open(graph_path, "rt") as source:
        graph = json.load(source)
    nodes = graph["nodes"]
    states = {key: value for key, value in nodes.items() if value["kind"] == "state"}
    for key, value in states.items():
        if not value.get("native_missing"):
            recorded = (
                value.get("native_definition", {}).get("native_fields", {}).get("aNv.p")
            )
            if recorded != value["reference"]:
                raise ValueError(
                    f"Native state record identity mismatch: {key} versus {recorded}"
                )
    local = {}
    wanted = {str(value["reference"]) for value in states.values()}
    for key, value in entries(catalog_path, "states"):
        if key in wanted:
            local[key] = value
    outgoing = defaultdict(set)
    execution_outgoing = defaultdict(set)
    incoming = defaultdict(set)
    for edge in graph["edges"]:
        outgoing[edge["source"]].add(edge["target"])
        incoming[edge["target"]].add(edge["source"])
        if edge["kind"] in ("native_state_selected_root", "ordered_group_child") or (
            edge["kind"] == "native_parameter_reference"
            and nodes.get(edge["source"], {}).get("family") == 304
            and edge["target"].startswith("state:")
        ):
            execution_outgoing[edge["source"]].add(edge["target"])

    def closure(seeds, adjacency=None):
        adjacency = outgoing if adjacency is None else adjacency
        seen, pending = set(), list(seeds)
        while pending:
            key = pending.pop()
            if key in seen:
                continue
            seen.add(key)
            pending.extend(adjacency[key] - seen)
        return seen

    ledger = json.loads((REPORT / "verification-ledger-20261007.json").read_text())
    innates = json.loads((DATA / "breed-innate-definitions.json").read_text())
    innate_by_breed = {
        row["breed"]: [f"state:{state['reference']}" for state in row["innate_states"]]
        for row in innates["breeds"]
    }
    dependent_spells, dependent_breeds = defaultdict(set), defaultdict(set)
    for spell in ledger["spells"]:
        seeds = [f"spell:{spell['spell_id']}"]
        seeds.extend(
            key for breed in spell["breeds"] for key in innate_by_breed.get(breed, ())
        )
        for key in closure(seeds) & states.keys():
            dependent_spells[key].add(spell["spell_id"])
            dependent_breeds[key].update(spell["breeds"])
    routes = literal_handler_families(
        ast.parse((COMBAT / "combat_effect_runtime.py").read_text())
    )
    routes |= declared(COMBAT / "combat_damage_healing.py", "DAMAGE_FAMILIES")
    routes |= declared(COMBAT / "combat_damage_healing.py", "HEAL_ELEMENTS")
    routes |= declared(COMBAT / "combat_displacement.py", "FAMILIES")
    routes |= dispatch_routes(COMBAT / "combat_effect_dispatch.py")
    routes |= set(
        map(
            int,
            json.loads((DATA / "effect-characteristic-registry.json").read_text())[
                "effects"
            ],
        )
    )
    decurse_rules = json.loads((DATA / "state-decurse-rules.json").read_text())
    rows = []
    for key, native in sorted(states.items(), key=lambda item: item[1]["reference"]):
        reference = native["reference"]
        definition = local.get(str(reference))
        reached = closure([key], execution_outgoing)
        effects = {
            node: nodes[node]
            for node in reached
            if node in nodes and nodes[node]["kind"] == "effect"
        }
        families = sorted({node["family"] for node in effects.values()})
        criteria = sorted(
            {node.get("criterion_raw") for node in effects.values()} - {None, ""}
        )
        groups = native.get("level_sample_groups", [])
        violations, gaps = [], []
        tested_samples = 0
        if definition is not None:
            checks = {
                row["requested_level"]: row
                for row in definition.get("native_level_checks", [])
            }
            for group in groups:
                expected = group.get("native_value", {})
                for requested in group.get("sample_levels", []):
                    selected_level = min(requested, definition["maximum_level"])
                    observed = (
                        dict(
                            definition["levels"][selected_level - 1],
                            level=selected_level,
                        )
                        if 1 <= selected_level <= len(definition.get("levels", []))
                        else checks.get(requested)
                    )
                    if observed is None:
                        continue
                    tested_samples += 1
                    if (
                        observed.get("duration") != expected.get("duration")
                        or observed.get("level") != expected.get("selected_level")
                        or observed.get("effects") != expected.get("roots")
                    ):
                        violations.append(
                            dict(
                                requested_level=requested,
                                native=expected,
                                local={
                                    k: observed.get(k)
                                    for k in ("duration", "level", "effects")
                                },
                            )
                        )
            if any(
                group.get("native_value", {}).get("realtime_duration", 0) > 0
                for group in groups
            ):
                gaps.append("realtime_scheduler_absent")
            if reference in decurse_rules["selective_child_states"]:
                gaps.append("selective_decurse_beneficial_child_classification_absent")
        missing_routes = sorted(set(families) - routes)
        if missing_routes:
            gaps.append("unregistered_transitive_effect_routes")
        applicators = [
            nodes[parent]
            for parent in incoming[key]
            if parent.startswith("effect:") and nodes[parent].get("family") == 304
        ]
        application_modes = []
        for applicator in applicators:
            raw = applicator.get("raw_parameters", [])
            mode = (
                "ordinary_three_parameter_mode"
                if len(raw) == 6 and raw[4:] == [-1, 0] and raw[2] >= 0
                else "requires_native_chance_or_dynamic_parameter_resolution"
            )
            application_modes.append(
                dict(
                    effect_id=applicator["reference"],
                    raw_parameters=raw,
                    mode=mode,
                    criterion=applicator.get("criterion_raw"),
                )
            )
        if any(
            row["mode"] != "ordinary_three_parameter_mode" for row in application_modes
        ):
            gaps.append("304_application_chance_or_dynamic_parameter_domain_unproved")
        status = (
            "absent"
            if native.get("native_missing") or definition is None
            else "broken"
            if violations
            else "partial"
            if gaps
            else "pending_verification"
        )
        row = dict(
            state_id=reference,
            name=None if definition is None else definition.get("name"),
            status=status,
            native_present=not native.get("native_missing", False),
            local_present=definition is not None,
            class_breeds=sorted(dependent_breeds[key]),
            dependent_spell_ids=sorted(dependent_spells[key]),
            reachability="conditional_unknown_not_executed",
            native_sample_groups=groups,
            child_execution_closure="sampled_selected_state_roots_ordered_groups_nested304_only",
            compared_local_samples=tested_samples,
            metadata_violations=violations,
            native_container=native.get("native_container"),
            application_contracts=application_modes,
            application_effect_ids=sorted(
                int(parent.split(":")[1])
                for parent in incoming[key]
                if parent.startswith("effect:") and nodes[parent].get("family") == 304
            ),
            transitive_effect_count=len(effects),
            transitive_families=families,
            unregistered_families=missing_routes,
            criterion_expressions=criteria,
            criterion_functions=sorted(
                {
                    name
                    for criterion in criteria
                    for name in re.findall(r"\b([A-Za-z_]\w*)\s*\(", criterion)
                }
            ),
            known_gaps=gaps,
            semantic_verification="pending",
            client_verification="pending",
            lifecycle_contracts=dict(
                application="partial",
                levels="broken" if violations else "partial",
                accumulation="implemented_shared_unverified_per_state",
                stack="implemented_shared_unverified_per_state",
                duration="partial",
                reset="pending_verification",
                decurse="partial",
                withdrawal="pending_verification",
                qf_retention="partial",
                activation_events="partial",
                expiry="partial",
            ),
        )
        root_ids = sorted(
            {
                root
                for group in groups
                for root in group.get("native_value", {}).get("roots", [])
            }
        )
        row["root_contracts"] = []
        for root in root_ids:
            child = nodes.get(f"effect:{root}", {})
            fields = child.get("native_definition", {}).get("native_fields", {})
            row["root_contracts"].append(
                dict(
                    effect_id=root,
                    family=child.get("family"),
                    runner=child.get("native_runner_class"),
                    criterion=child.get("criterion_raw"),
                    native_event_masks={
                        key: fields.get(key)
                        for key in (
                            "Qa.beA",
                            "Qa.beB",
                            "Qa.beC",
                            "Qa.beD",
                            "Qa.beE",
                            "Qa.beF",
                        )
                    },
                    raw_parameters=child.get("raw_parameters"),
                    route_declared=child.get("family") in routes,
                    activation_semantics="pending_verification_of_event_phase_priority_count_and_actual_sources",
                )
            )
        if definition:
            row["local_policy"] = {
                field: definition.get(field)
                for field in (
                    "maximum_level",
                    "clock_actor",
                    "additive",
                    "replace",
                    "refresh",
                    "protected",
                    "duration_base",
                    "duration_per_level",
                    "tick_at_turn_end",
                    "skip_turn_timer",
                    "realtime_duration_base",
                    "realtime_duration_per_level",
                )
            }
        row["manual_acceptance"] = dict(
            status="pending_legal_applicator_and_expected_condition_resolution",
            steps=[
                "Choose an owning class and a legal direct304 applicator; resolve its native target and criterion first.",
                "Apply the state once; compare selected level, roots and native duration with this row's sample group.",
                "Reapply from the same and a different caster; check additive/replace/refresh/protected policy and child removal.",
                "Trigger every declared child event under both true and false criteria; inspect resources, messages and state level.",
                "Advance the actual clock actor through start/end expiry, then decurse and withdraw/rejoin; verify complete removal.",
            ],
            expected="Native policy/sample metadata, with conditional truth and legal applicability explicitly established; no per-state completion inferred.",
        )
        rows.append(row)
    after = {str(path.relative_to(ROOT)): digest(path) for path in paths}
    per_class = {}
    for breed in sorted({breed for row in rows for breed in row["class_breeds"]}):
        owned = [row for row in rows if breed in row["class_breeds"]]
        per_class[str(breed)] = dict(
            state_count=len(owned),
            statuses=dict(Counter(row["status"] for row in owned)),
            state_ids=[row["state_id"] for row in owned],
        )
    family_dependents = defaultdict(list)
    for row in rows:
        for family in row["unregistered_families"]:
            family_dependents[str(family)].append(row["state_id"])
    report = dict(
        schema=1,
        scope="All native class-dependency states; structural branches, all18classes, no scenario denominator",
        sources_before=before,
        sources_after=after,
        sources_stable=before == after,
        summary=dict(
            state_count=len(rows),
            statuses=dict(Counter(row["status"] for row in rows)),
            classes=sorted({breed for row in rows for breed in row["class_breeds"]}),
            native_missing=[
                row["state_id"] for row in rows if not row["native_present"]
            ],
            complete_semantic_states=0,
            complete_client_states=0,
        ),
        per_class=per_class,
        unregistered_family_state_dependents=dict(family_dependents),
        limitations=[
            "Registered routes are not complete contracts.",
            "Unknown conditional branches remain included.",
            "Child execution closure follows sampled selected roots, ordered groups and nested304; raw references are dependency evidence only.",
            "Native level groups are sampled, not every legal state level or target context.",
            "Source stability covers only the explicitly tracked inputs, not the whole checkout or running server.",
            "Manual steps require native legal-applicator resolution and are not a completed test.",
            "No runtime process, service, client or database was inspected.",
        ],
        states=rows,
    )
    base = REPORT / "class-state-gap-inventory"
    base.with_suffix(".json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    with base.with_suffix(".csv").open("w", newline="") as output:
        columns = [
            "state_id",
            "name",
            "status",
            "class_breeds",
            "dependent_spell_ids",
            "native_present",
            "local_present",
            "compared_local_samples",
            "transitive_effect_count",
            "transitive_families",
            "unregistered_families",
            "known_gaps",
            "reachability",
            "semantic_verification",
            "client_verification",
        ]
        writer = csv.DictWriter(output, columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    column: json.dumps(row[column])
                    if isinstance(row[column], list)
                    else row[column]
                    for column in columns
                }
            )
    summary = report["summary"]
    lines = [
        "# Complete class state gap inventory",
        "",
        f"Native state denominator: **{len(rows)}**. Status counts: `{summary['statuses']}`.",
        f"Native missing references: `{summary['native_missing']}`. Tracked sources stable: **{report['sources_stable']}**.",
        "",
        "This is a state inventory, not a scenario count. No state is accredited as completely semantic/client verified.",
        "`partial` means a concrete shared gap was found; `pending_verification` means local metadata/routes exist without full state behavior proof.",
        "`absent` records missing native/local definitions without claiming the conditional branch is reachable. `broken` records native/local sample contradictions.",
        "",
        "JSON preserves every state, native level group/container, class/spell reverse index, application effect, route gap, criterion and lifecycle dimension.",
        "CSV provides one row per state. Rebuild with `python3 server/tools/build_class_state_gap_inventory.py`.",
        "Native raw definition identities are checked before the build; this avoids mutable-loader record reuse corrupting the denominator.",
        "",
        "| Lifecycle contract | Shared source and remaining limit |",
        "| --- | --- |",
        "| Application/levels | combat_state_handler, combat_state_parameters, combat_definitions; sampled native/local values compared per state |",
        "| Accumulation/replacement/refresh/protection | combat_state_application; shared implementation, per-state sequences pending |",
        "| Duration/expiry | combat_state_timing, combat_native_timing_context, combat_state_ledger; realtime scheduler and timed area clock reject |",
        "| Retention/children | combat_state_handler/state_managers/subscription_runners; null Qf, instant subscribed children and missing subscription families remain guarded |",
        "| Decurse | combat_state_decurse; selective beneficial child classification remains absent |",
        "| Reset/withdraw/client reconnect | Pending per-state verification; a source route is insufficient evidence |",
        "",
        "Every conditional path remains reachability-unknown. A missing transitive family can sit behind a false criterion; this inventory does not declare its owner class broken.",
        "Manual acceptance templates accompany each row, but exact playable applicators and expected event conditions still require resolution before execution.",
        "No services were restarted and no runtime catalog was mutated.",
    ]
    base.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print(json.dumps(dict(summary=summary, sources_stable=report["sources_stable"])))


if __name__ == "__main__":
    main()
