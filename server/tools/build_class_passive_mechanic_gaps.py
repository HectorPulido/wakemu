"""Standard-library inventory of a frozen passive audit, never a runtime replay."""
import gzip
import argparse
from collections import Counter, defaultdict, deque
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAPH = ROOT / ".runtime/combat-review-20261007/mechanic-graph/native-graph.jsonl.gz"
DEFAULT = (
    ROOT
    / ".runtime/combat-review-20261008/class-passive-mechanics-optimized-full-01.json"
)
OUTPUT = (
    ROOT / "docs/reports/combat-inventory/class-passive-mechanic-gap-inventory-20261008"
)


def identity(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def failure_key(phase, failure):
    effect = failure.get("first_failed_effect") or {}
    diagnostic = failure.get("diagnostic") or {}
    return json.dumps(
        dict(
            phase=phase,
            kind=failure.get("kind"),
            reason=failure.get("root_reason") or failure.get("reason"),
            effect_reference=effect.get("effect_reference"),
            family=effect.get("effect_class"),
            native_casting_result=failure.get("native_casting_result"),
            criterion=diagnostic.get("criterion"),
            casting_flags=diagnostic.get("selected_casting_flags"),
        ),
        sort_keys=True,
    )


def build(report_path=DEFAULT, graph_path=GRAPH, output=OUTPUT):
    builder_before = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    raw = report_path.read_bytes()
    report = json.loads(raw)
    if not all(
        report.get(key) for key in ("finished", "source_stable", "source_tool_stable")
    ):
        raise ValueError("Frozen completed source-stable passive report required")
    cases, action_counts, cause_cases = [], Counter(), defaultdict(list)
    omitted, pairs, observed_refs = [], defaultdict(set), set()
    for row in report["rows"]:
        case = dict(breed=row["breed"], level=row["level"], passive=row["passive"])
        runtime = row.get("runtime_access", {})
        for stage in ("lifecycle", "movement"):
            section = runtime.get(stage, {})
            failure = section.get("first_root_failure") or section.get("last_failure")
            if failure:
                cause_cases[failure_key(stage, failure)].append(case)
        for action in runtime.get("actions", []):
            action_counts[action["status"]] += 1
            pairs[action["reference"]].add(row["level"])
            failure = action.get("first_root_failure")
            if failure:
                cause_cases[failure_key("selection", failure)].append(
                    dict(case, action=action["reference"])
                )
            for attempt in action.get("attempts", []):
                failure = attempt.get("first_root_failure")
                if failure:
                    cause_cases[
                        failure_key(attempt.get("failed_stage", "transaction"), failure)
                    ].append(
                        dict(
                            case,
                            action=action["reference"],
                            target=attempt.get("target"),
                        )
                    )
                observed_refs.update(
                    event["effect_reference"]
                    for event in attempt.get("trace", [])
                    if event.get("status") == "completed"
                    and type(event.get("effect_reference")) is int
                )
        for field in (
            "turn_trace",
            "cast_passive_trace",
            "lifecycle_passive_trace",
            "movement_passive_trace",
        ):
            observed_refs.update(
                event["effect_reference"]
                for event in runtime.get(field, [])
                if event.get("status") == "completed"
                and type(event.get("effect_reference")) is int
            )
        for action in runtime.get("omitted_actions", []):
            item = dict(case, action=action["reference"], origin=action["origin"])
            omitted.append(item)
            pairs[action["reference"]].add(row["level"])
        cases.append(
            dict(
                case,
                ready=row["status"],
                lifecycle=runtime.get("lifecycle", {}).get("status"),
                movement=runtime.get("movement", {}).get("status"),
                actions=[
                    dict(
                        reference=action["reference"],
                        origin=action["origin"],
                        status=action["status"],
                    )
                    for action in runtime.get("actions", [])
                ],
                omitted_count=len(runtime.get("omitted_actions", [])),
            )
        )
    if len(cases) != report["planned_case_count"] or len(
        {(case["breed"], case["level"], case["passive"]) for case in cases}
    ) != len(cases):
        raise ValueError("Passive-case denominator missing or duplicated")
    graph_before = hashlib.sha256(graph_path.read_bytes()).hexdigest()
    if graph_before != report["original_graph_sha256"]:
        raise ValueError("Native graph identity differs from the frozen runtime report")
    effects, roots, states = {}, {}, {}
    missing_state_sources = set()
    with gzip.open(graph_path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            kind, ref = row["kind"], row["reference"]
            if kind == "spell" and ref in pairs:
                roots[ref] = {
                    level: row["root_samples"].get(str(level), [])
                    for level in pairs[ref]
                }
            elif kind == "state":
                if row.get("native_missing") or "level_samples" not in row:
                    missing_state_sources.add(ref)
                states[ref] = sorted(
                    {
                        effect
                        for sample in row.get("level_samples", {}).values()
                        for effect in sample.get("roots", [])
                    }
                )
            elif kind == "effect":
                metadata = row.get("native_metadata") or {}
                contract = dict(
                    family=row["family"],
                    runner=row.get("native_runner_class"),
                    parameters=row.get("raw_parameters"),
                    criterion=row.get("criterion_raw"),
                    flags=metadata.get("native_effect_flags"),
                    masks=metadata.get("target_masks"),
                    selector=metadata.get("native_target_selector"),
                    subscription=row.get("subscription"),
                    timing=metadata.get("native_timing_definition"),
                )
                effects[ref] = dict(
                    contract,
                    signature=identity(contract),
                    children=row.get("children_ordered", []),
                    applied_states=sorted(
                        {
                            edge["reference"]
                            for edge in row.get("classified_reference_samples", [])
                            if row["family"] == 304
                            and edge["kind"] == "state"
                            and edge["reference"] > 0
                            and 0 <= edge["sample_level"] <= 245
                        }
                    ),
                )
    if graph_before != hashlib.sha256(graph_path.read_bytes()).hexdigest():
        raise ValueError("Original graph changed during stdlib inventory")
    completed_signatures = {
        effects[ref]["signature"] for ref in observed_refs if ref in effects
    }
    closure_cache = {}

    def closure(reference, level):
        key = (reference, level)
        if key in closure_cache:
            return closure_cache[key]
        pending, seen, missing, missing_states = (
            deque(roots.get(reference, {}).get(level, [])),
            set(),
            set(),
            set(),
        )
        while pending:
            ref = pending.popleft()
            if ref in seen:
                continue
            seen.add(ref)
            effect = effects.get(ref)
            if effect is None:
                missing.add(ref)
                continue
            pending.extend(effect["children"])
            for state in effect["applied_states"]:
                if state not in states or state in missing_state_sources:
                    missing_states.add(state)
                pending.extend(states.get(state, []))
        result = dict(
            effect_references=sorted(seen),
            missing_effect_references=sorted(missing),
            graph_spell_missing=reference not in roots,
            missing_native_state_references=sorted(missing_states),
            signatures=sorted(
                {effects[ref]["signature"] for ref in seen if ref in effects}
            ),
        )
        closure_cache[key] = result
        return result

    grouped = defaultdict(list)
    for item in omitted:
        grouped[item["breed"], item["level"], item["action"], item["origin"]].append(
            item["passive"]
        )
    omitted_inventory, unique_omitted_refs, unique_signatures = [], set(), set()
    family_refs, mechanism_cases = defaultdict(set), defaultdict(list)
    candidates = []
    for (breed, level, ref, origin), passive_ids in sorted(grouped.items()):
        projected = closure(ref, level)
        native_refs = set(projected["effect_references"])
        unique_omitted_refs.update(native_refs)
        signatures = set(projected["signatures"])
        unique_signatures.update(signatures)
        novel = signatures - completed_signatures
        item = dict(
            breed=breed,
            level=level,
            action=ref,
            origin=origin,
            passive_references=sorted(set(passive_ids)),
            omitted_occurrences=len(passive_ids),
            **projected,
            unobserved_contract_signatures=sorted(novel)
        )
        omitted_inventory.append(item)
        for native_ref in native_refs:
            if native_ref in effects:
                family_refs[effects[native_ref]["family"]].add(native_ref)
        for signature in signatures:
            mechanism_cases[signature].append(
                dict(
                    breed=breed,
                    level=level,
                    action=ref,
                    passive_references=sorted(set(passive_ids)),
                )
            )
        if origin == "normal_owned_deck" and novel:
            candidates.append(
                dict(
                    breed=breed,
                    level=level,
                    action=ref,
                    passive_references=sorted(set(passive_ids)),
                    source_novelty_units=novel,
                )
            )
    # Source novelty is only a scheduling proxy; no graph edge certifies guard reachability.
    uncovered = set(unique_signatures - completed_signatures)
    next_cases = []
    # Start with one source-relevant class context each; shared primitive success
    # in another class cannot certify this class's actor/condition/event path.
    for breed in sorted({candidate["breed"] for candidate in candidates}):
        local = [candidate for candidate in candidates if candidate["breed"] == breed]
        candidate = max(
            local,
            key=lambda value: (
                len(value["source_novelty_units"] & uncovered),
                -value["level"],
                -value["action"],
            ),
        )
        added = candidate["source_novelty_units"] & uncovered
        next_cases.append(
            dict(
                breed=candidate["breed"],
                level=candidate["level"],
                action=candidate["action"],
                passive_references=candidate["passive_references"],
                new_source_contract_units=len(added),
                proposed_passive=candidate["passive_references"][0],
                class_context_representative=True,
                legal_fixture_preflight_required=True,
            )
        )
        uncovered.difference_update(added)
        candidates.remove(candidate)
    while candidates and uncovered and len(next_cases) < 36:
        candidate = max(
            candidates,
            key=lambda value: (
                len(value["source_novelty_units"] & uncovered),
                -value["breed"],
                -value["level"],
                -value["action"],
            ),
        )
        added = candidate["source_novelty_units"] & uncovered
        if not added:
            break
        next_cases.append(
            dict(
                breed=candidate["breed"],
                level=candidate["level"],
                action=candidate["action"],
                passive_references=candidate["passive_references"],
                new_source_contract_units=len(added),
                proposed_passive=candidate["passive_references"][0],
                legal_fixture_preflight_required=True,
            )
        )
        uncovered.difference_update(added)
        candidates.remove(candidate)
    signatures_to_refs = defaultdict(list)
    for ref in unique_omitted_refs:
        if ref in effects:
            signatures_to_refs[effects[ref]["signature"]].append(ref)
    mechanism_inventory = [
        dict(
            signature=signature,
            contract={
                key: value
                for key, value in effects[refs[0]].items()
                if key not in ("signature", "children", "applied_states")
            },
            effect_references=sorted(refs),
            candidate_cases=mechanism_cases[signature],
            completed_in_report=signature in completed_signatures,
            completed_means="at least one accepted runtime context; not all semantic branches",
        )
        for signature, refs in sorted(signatures_to_refs.items())
    ]
    causes = [
        dict(
            json.loads(key),
            count=len(values),
            classes=sorted({case["breed"] for case in values}),
            cases=values,
        )
        for key, values in sorted(
            cause_cases.items(), key=lambda item: (-len(item[1]), item[0])
        )
    ]
    for cause in causes:
        cause["snapshot_classification"] = (
            "conditional_context_or_bounded_target_search"
            if cause["kind"] == "legal_baseline_context_unavailable"
            else "owned_component_authority_unavailable"
            if cause["kind"] == "target_authority_unresolved"
            else "runtime_contract_rejection"
        )
        cause["current_replay_status"] = "not replayed by this stdlib inventory"
        if cause["effect_reference"] == 385223:
            cause[
                "post_report_source_status"
            ] = "parent reports area843 null-target guard fixed;5pure tests; frozen runtime replay pending"
        if cause["reason"] == "Native eHP owned Symbiot component required":
            cause[
                "post_report_source_status"
            ] = "casting_engine reports source-attested fresh-fixture empty component initialization;3pure tests; expected prerequisite rejection requires frozen replay"
        if cause["effect_reference"] == 147263:
            cause[
                "post_report_source_status"
            ] = "parent reports historical QI-byte registration guard fixed with pure regression; this exact passive branch replay pending"
    priorities = [
        dict(
            priority=1,
            mechanism="area-removal843 null target and native QI-byte registration",
            frozen_impacted_cases=33,
            unique_effect_references=[385223, 147263],
            classes=[3, 12],
            action="replay representative existing source cases after frozen fixes, then resume affected passive cycles",
            status="source fixes reported; scoped and bulk runtime replay pending",
        ),
        dict(
            priority=2,
            mechanism="SUMMONER_VISUAL_COPY owned appearance/equipment authority",
            frozen_impacted_cases=15,
            unique_effect_references=[120894],
            classes=[4],
            action="bind source-owned visual/equipment producer and test actual4603 summon under one legal Sram passive",
            status="not verified by frozen bulk339",
        ),
        dict(
            priority=3,
            mechanism="native owned Symbiot component and selected-slot casting authority",
            frozen_impacted_cases=17,
            unique_effect_references=[],
            classes=[2],
            action="reuse legitimate initialized/owned roster fixture and actual7348 production pipeline; no fabricated states or arbitrary monster books",
            status="fresh-fixture producer implemented after report with3pure tests; replay pending; separate324 occupied-owned fixture exists",
        ),
        dict(
            priority=4,
            mechanism="native group-level actor and armor flag contracts",
            frozen_impacted_cases=3,
            unique_effect_references=[371570, 353422],
            classes=[13, 11],
            action="recover shared actor-provider and original1013 flag behavior; replay one representative per contract",
            status="two group-actor and one armor rejection in frozen report",
        ),
        dict(
            priority=5,
            mechanism="conditional summon/state/threshold prerequisites and target diversity",
            frozen_impacted_cases=77,
            unique_effect_references=[],
            classes=[3, 10, 13, 15, 16, 19],
            action="perform legal producer transitions (summon, state generation, SP threshold, obstacle/carry) before selected gated action; vary target enumeration without injected state",
            status="twI/twV in bounded baseline searches; not missing-handler or full-map failure claims",
        ),
        dict(
            priority=6,
            mechanism="new exact source contracts and unexercised timing/element/range/heal/critical branches",
            frozen_impacted_cases=None,
            unique_effect_references=[],
            classes=sorted({case["breed"] for case in cases}),
            action="schedule source-novelty representatives with explicit prerequisite guards, then criterion/event variants; retain omissions",
            status="source projection only; actual reachability and complete semantics unknown",
        ),
    ]
    passive_state_branches, passive_effect_branches = set(), set()
    passive_root_units, native_conditions, subscriptions, grant_effects = (
        set(),
        set(),
        set(),
        set(),
    )
    for case in cases:
        contract = report["original_native_contracts"][
            str(case["passive"]) + "/" + str(case["level"])
        ]
        passive_root_units.update(
            (case["breed"], case["passive"], case["level"], root)
            for root in contract.get("original_roots") or []
        )
        passive_state_branches.update(
            (case["breed"], case["passive"], state)
            for state in contract.get("applied_state_references", [])
        )
        for ref, effect in contract["effect_contracts"].items():
            passive_effect_branches.add(
                (case["breed"], case["passive"], case["level"], int(ref))
            )
            if effect.get("criterion_raw"):
                native_conditions.add(effect["criterion_raw"])
            metadata = effect.get("native_metadata") or {}
            subscriptions.add(
                identity(
                    dict(
                        subscription=effect.get("subscription"),
                        masks=metadata.get("target_masks"),
                        target_code=effect.get("event_target_code"),
                        caster_code=effect.get("event_caster_code"),
                        timing=metadata.get("native_timing_definition"),
                    )
                )
            )
            if effect["family"] == 649:
                grant_effects.add(int(ref))
    actual_states, actual_grants, committed_actions = set(), set(), []
    cleanup_observations = []

    def ledger_ids(ledgers):
        return {
            (owner, entry["uid"]): entry
            for owner, value in ledgers.items()
            for entry in value.get("entries", [])
        }

    for row in report["rows"]:
        runtime = row["runtime_access"]
        actual_grants.update(
            (row["breed"], row["level"], reference)
            for reference in runtime.get("actual_ready_grants", [])
        )
        lifecycle = runtime.get("lifecycle", {})
        before_entries = ledger_ids(lifecycle.get("state_ledgers_before", {}))
        after_entries = ledger_ids(lifecycle.get("state_ledgers_after", {}))
        if lifecycle.get("status") == "actual_end_ack_start_completed":
            removed = set(before_entries) - set(after_entries)
            for key in removed:
                cleanup_observations.append(
                    dict(
                        breed=row["breed"],
                        passive=row["passive"],
                        level=row["level"],
                        carrier=key[0],
                        uid=key[1],
                        state=before_entries[key]["reference"],
                        stage="real_end_ack_start_ledger_absence",
                        removal_packet_and_child_retention_semantics="not certified by ledger difference alone",
                    )
                )
        for entry in [*before_entries.values(), *after_entries.values()]:
            actual_states.add((row["breed"], entry["reference"]))
        for action in runtime["actions"]:
            for attempt in action.get("attempts", []):
                commit = attempt.get("representative_commit", {})
                if commit.get("status") == "committed":
                    committed_actions.append(
                        dict(
                            breed=row["breed"],
                            passive=row["passive"],
                            level=row["level"],
                            action=action["reference"],
                            origin=action["origin"],
                            target=attempt.get("target"),
                            packet_count=commit.get("packet_count"),
                        )
                    )
    denominators = dict(
        scope="global across this339-passive gate; not the full class722+extras dependency map",
        classes=dict(planned=18, ready_observed=len({case["breed"] for case in cases})),
        passive_spells=dict(planned=339, cases=len(cases)),
        native_selected_root_units=dict(
            count=len(passive_root_units),
            definition="breed/passive/level/native selected root",
        ),
        potential_passive_effect_branch_units=dict(
            count=len(passive_effect_branches),
            definition="breed/passive/level/effect in conservative source closure; not executed path",
        ),
        potential_passive_state_branch_units=dict(
            count=len(passive_state_branches),
            definition="breed/passive/state native304 dependencies; actual stack/requested level unknown",
        ),
        raw_criterion_variants=dict(
            count=len(native_conditions),
            definition="exact native criterion text; not branch truth proof",
        ),
        subscription_timing_contracts=dict(
            count=len(subscriptions),
            definition="exact native subscription/masks/caster-target codes/timing definition",
        ),
        owned_grant_effect_sources=dict(
            count=len(grant_effects),
            effect_references=sorted(grant_effects),
            available_owner_level_class_spell_units=len(actual_grants),
        ),
        turn_cycles=dict(planned=339, completed=323, unavailable=16),
        movement=dict(planned=339, committed=339),
        selected_actions=dict(
            count=688,
            prepared=559,
            representative_committed=len(committed_actions),
            prepared_without_recorded_commit=559 - len(committed_actions),
        ),
        observed_state_class_pairs=dict(
            count=len(actual_states), pairs=sorted(actual_states)
        ),
        cleanup=dict(
            ledger_absence_observations=len(cleanup_observations),
            limitation="observed end/start removals only; permanent-state teardown and complete child cleanup unverified",
        ),
        gameplay_verified_flags=dict(
            true_cases=sum(
                bool(row.get("gameplay_verified")) for row in report["rows"]
            ),
            false_cases=sum(
                not bool(row.get("gameplay_verified")) for row in report["rows"]
            ),
            interpretation="certification flag; not a functional percentage",
        ),
    )
    output_data = dict(
        schema="class-passive-mechanic-gap-inventory-v1",
        provenance=dict(
            report_path=str(report_path.relative_to(ROOT)),
            report_sha256=hashlib.sha256(raw).hexdigest(),
            native_graph_sha256=graph_before,
            report_source_stable=report["source_stable"],
            report_tool_stable=report["source_tool_stable"],
            builder_sha256=builder_before,
            validation_snapshot_path=".runtime/combat-review-20261008/validation-snapshots/luna-passive-fast-01/validation-snapshot.json",
            validation_snapshot_sha256=hashlib.sha256(
                (
                    ROOT
                    / ".runtime/combat-review-20261008/validation-snapshots/luna-passive-fast-01/validation-snapshot.json"
                ).read_bytes()
            ).hexdigest(),
        ),
        summary=dict(
            passives=len(cases),
            classes=len({item["breed"] for item in cases}),
            ready_status_counts=dict(Counter(item["ready"] for item in cases)),
            lifecycle_status_counts=dict(Counter(item["lifecycle"] for item in cases)),
            movement_status_counts=dict(Counter(item["movement"] for item in cases)),
            action_status_counts=dict(action_counts),
            selected_actions=sum(action_counts.values()),
            omitted_action_occurrences=len(omitted),
            unique_omitted_spell_level_class_origin=len(grouped),
            unique_omitted_spell_references=len({item["action"] for item in omitted}),
            unique_omitted_effect_references=len(unique_omitted_refs),
            unique_omitted_structural_contracts=len(unique_signatures),
            omitted_contracts_with_accepted_context=len(
                unique_signatures & completed_signatures
            ),
            omitted_contracts_without_accepted_context=len(
                unique_signatures - completed_signatures
            ),
            missing_native_spell_cases=sum(
                item["graph_spell_missing"] for item in omitted_inventory
            ),
            missing_native_state_references=sorted(
                {
                    state
                    for item in omitted_inventory
                    for state in item["missing_native_state_references"]
                }
            ),
        ),
        interpretation="3861 omissions are repeated action cases, not3861 broken spells; structural source novelty is not semantic coverage",
        denominators=denominators,
        cleanup_observations=cleanup_observations,
        committed_action_cases=committed_actions,
        priorities=priorities,
        causes=causes,
        cases=cases,
        omitted_action_inventory=omitted_inventory,
        omitted_family_inventory=[
            dict(
                family=family,
                unique_effect_count=len(refs),
                effect_references=sorted(refs),
            )
            for family, refs in sorted(family_refs.items())
        ],
        unique_mechanisms=mechanism_inventory,
        next_bulk=dict(
            policy="one source-relevant context per class, then bounded source-novelty representatives and legal prerequisite transitions; no Cartesian replay",
            proposed_cases=next_cases,
            remaining_unobserved_source_units=len(uncovered),
            budget=dict(
                source_novelty_ready_cases=len(next_cases),
                source_novelty_ordinary_casts=len(next_cases),
                regression_or_authority_cases=6,
                maximum_ready_cases=len(next_cases) + 6,
                maximum_legitimate_prerequisite_transitions=12,
                source_contract_novelty_potential=len(
                    unique_signatures - completed_signatures
                )
                - len(uncovered),
                estimated_wall_time="not inferred; measure frozen first two cases",
            ),
            must_first_close=[
                "Enutrof3 lifecycle healing843 source385223 target authority",
                "owned Osa roster producer for17 granted-action availability cases",
                "classify35 transaction rejection roots separately from77 bounded target searches",
            ],
            guard_and_native_level_semantics="potential304 state-root union across source levels; not executable schedule",
        ),
        full_passive_semantics_verified=False,
        full_client_verified=False,
    )
    if (
        builder_before != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        or hashlib.sha256(raw).hexdigest()
        != hashlib.sha256(report_path.read_bytes()).hexdigest()
    ):
        raise ValueError("Inventory builder or frozen report changed during analysis")
    output.parent.mkdir(parents=True, exist_ok=True)
    full = json.dumps(output_data, separators=(",", ":")).encode()
    full_path = output.with_suffix(".full.json")
    full_path.write_bytes(full)
    manifest = {
        key: output_data[key]
        for key in (
            "schema",
            "provenance",
            "summary",
            "denominators",
            "priorities",
            "causes",
            "next_bulk",
            "full_passive_semantics_verified",
            "full_client_verified",
        )
    }
    manifest.update(
        full_inventory_artifact=full_path.name,
        full_inventory_sha256=hashlib.sha256(full_path.read_bytes()).hexdigest(),
    )
    output.with_suffix(".json").write_text(json.dumps(manifest, indent=2) + "\n")
    with output.with_suffix(".csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "breed",
                "level",
                "action",
                "origin",
                "omitted_occurrences",
                "passive_references",
                "unique_effects",
                "unobserved_contracts",
                "graph_spell_missing",
            ],
        )
        writer.writeheader()
        for item in omitted_inventory:
            writer.writerow(
                {
                    **{
                        key: item[key]
                        for key in (
                            "breed",
                            "level",
                            "action",
                            "origin",
                            "omitted_occurrences",
                            "graph_spell_missing",
                        )
                    },
                    "passive_references": " ".join(
                        map(str, item["passive_references"])
                    ),
                    "unique_effects": len(item["effect_references"]),
                    "unobserved_contracts": len(item["unobserved_contract_signatures"]),
                }
            )
    return output_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT)
    parser.add_argument("--graph", type=Path, default=GRAPH)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = build(args.report, args.graph, args.output)
    print(json.dumps(result["summary"]))
