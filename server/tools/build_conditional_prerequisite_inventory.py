"""All scoped conditional prerequisite signatures from existing typed matrix only."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

MATRIX = Path(
    "docs/reports/combat-inventory/class-casting-precondition-matrix-20261008.json"
)
PLAN = Path("docs/reports/combat-inventory/class-casting-transition-plan-20261008.json")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run():
    matrix = json.loads(MATRIX.read_text())
    plan = json.loads(PLAN.read_text())
    assert len(matrix["rows"]) == 651
    signatures, domain_rows, evidence = {}, defaultdict(set), []
    proved, removal = set(), set()
    removal_observations = []
    for p in sorted(
        Path(".runtime/combat-review-20261008").glob(
            "class-conditional-transitions-*.json"
        )
    ):
        if p.name == "class-conditional-transitions-all75-final-01.json":
            continue
        report = json.loads(p.read_text())
        stable = (
            report.get("source_stable") is True
            and report.get("transition_tool_stable", True) is True
        )
        report_proof = []
        for row in report.get("rows", []):
            access = row.get("runtime_access", {})
            case = access.get("case", {})
            key = (case.get("spell"), case.get("branch"))
            if stable and access.get("conditional_branch_verified") is True:
                proved.add(key)
                report_proof.append(
                    dict(
                        spell=key[0],
                        branch=key[1],
                        breed=case.get("breed"),
                        level=case.get("level"),
                    )
                )
            if stable and access.get("removal_control_verified") is True:
                removal.add(key)
                controls = [
                    attempt.get("removal_control")
                    for parent in access.get("attempts", [])
                    for attempt in parent.get("conditional_attempts", [])
                    if isinstance(attempt.get("removal_control"), dict)
                ]
                removal_observations.append(
                    dict(
                        spell=key[0],
                        branch=key[1],
                        level=case.get("level"),
                        report=str(p),
                        top_label=access.get("removal_control_status"),
                        nested_controls=[
                            dict(
                                status=c.get("status"),
                                mechanism=c.get("removal_mechanism"),
                            )
                            for c in controls
                        ],
                        limit="Generic top label does not establish expiry; preserve actual nested consumption/removal mechanism",
                    )
                )
        evidence.append(
            dict(
                path=str(p),
                sha256=sha(p),
                source_stable=report.get("source_stable"),
                accepted_exact_cases=report_proof,
            )
        )
    all75_path = Path(
        ".runtime/combat-review-20261008/class-conditional-evidence-all75.json"
    )
    all75 = json.loads(all75_path.read_text()) if all75_path.exists() else None
    if all75:
        stable = (
            all75["metadata"].get("source_stable") is True
            and all75["metadata"]["source_before"] == all75["metadata"]["source_after"]
        )
        if not stable:
            raise ValueError("Unstable full75 provenance")
        for row in all75["rows"]:
            case = row["case"]
            if row.get("removal_control_verified") is True:
                removal.add((case["spell"], case["branch"]))
                removal_observations.append(
                    dict(
                        spell=case["spell"],
                        branch=case["branch"],
                        level=case["level"],
                        report=all75["report"],
                        nested_controls=row["controls"],
                        top_label=row.get("removal_control_status"),
                    )
                )
        all75["frozen_case_counts"] = dict(
            cases=len(all75["rows"]),
            on_verified=sum(
                r.get("conditional_branch_verified") is True for r in all75["rows"]
            ),
            off_verified=sum(
                r.get("removal_control_verified") is True for r in all75["rows"]
            ),
        )
    baseline_proof = None
    all_committed_imports = []
    for compact_path in sorted(
        list(
            Path(".runtime/combat-review-20261008").glob(
                "class-conditional-committed-*.json"
            )
        )
        + ([all75_path] if all75 else [])
    ):
        from conditional_committed_observations import reconcile

        compact = json.loads(compact_path.read_text())
        metadata = compact["metadata"]
        if metadata.get("source_stable") is not True or metadata.get(
            "source_before"
        ) != metadata.get("source_after"):
            raise ValueError("Unstable compact normal commit provenance")
        contract_hash = metadata["source_before"].get(
            "server/protocol/native-spell-casting.json.gz"
        )
        if not contract_hash:
            raise ValueError("Missing native casting source identity")
        for observation in compact["observations"]:
            observation["source_contract_sha256"] = contract_hash
        baseline_proof = reconcile(compact["observations"], matrix)
        baseline_proof["committed_attempts"] = len(compact["observations"])
        baseline_proof["committed_origin_counts"] = dict(
            Counter(row["origin"] for row in compact["observations"])
        )
        baseline_proof["baseline_selected_attempts"] = sum(
            row["native_casting_selection"].get("selected_origin") == "baseline"
            for row in compact["observations"]
        )
        baseline_proof["conditional_selected_attempts"] = sum(
            row["native_casting_selection"].get("selected_origin") == "conditional"
            for row in compact["observations"]
        )
        baseline_proof["unique_selected_branch_keys"] = [
            list(k)
            for k in sorted(
                {
                    (r["spell"], r["branch"])
                    for r in baseline_proof["unique_selected_committed"]
                }
            )
        ]
        baseline_proof["known_equivalent_matched_branch_keys"] = [
            list(k)
            for k in sorted(
                {
                    (r["spell"], r["branch"])
                    for r in baseline_proof["known_matched_committed"]
                }
            )
        ]
        baseline_proof["matrix_casting_source_sha256"] = matrix["sources"][
            "server/protocol/native-spell-casting.json.gz"
        ]
        baseline_proof["executed_casting_source_sha256"] = contract_hash
        baseline_proof["source_contract_identity_matches_frozen_matrix"] = (
            contract_hash
            == matrix["sources"]["server/protocol/native-spell-casting.json.gz"]
        )
        baseline_proof[
            "identity_limit"
        ] = "Exact current reference/index/raw criterion matched; native whole-table hash divergence remains explicit, no silent flags equivalence inferred"
        for observation in (
            baseline_proof["unique_selected_committed"]
            + baseline_proof["known_matched_committed"]
        ):
            proved.add((observation["spell"], observation["branch"]))
        all_committed_imports.append(
            dict(path=str(compact_path), report=compact["report"], **baseline_proof)
        )
        evidence.append(
            dict(
                path=str(compact_path),
                sha256=sha(compact_path),
                report_sha256=compact["report_sha256"],
                source_stable=True,
                proof_scope="actual committed baseline selections; not producer/ON-OFF semantics",
            )
        )
    for row in matrix["rows"]:
        key = (row["spell"], row["branch"])
        for call in row["calls"]:
            domain = call["family"]
            if domain == "state" and (
                call["function"] in ("GetStateLevel", "HasStateFromLevel")
                or call.get("enclosing_comparison_tests")
            ):
                domain = "state_threshold_counter"
            domain_rows[domain].add(key)
            payload = {
                k: call.get(k)
                for k in (
                    "function",
                    "arguments",
                    "enclosing_not_parity",
                    "enclosing_comparison_tests",
                    "selector_contract",
                )
            }
            identity = hashlib.sha256(
                json.dumps(payload, sort_keys=True).encode()
            ).hexdigest()
            entry = signatures.setdefault(
                identity,
                dict(
                    signature=payload,
                    producer_domain=domain,
                    branches=[],
                    producer_candidates=[],
                    execution_proof="no exact branch proof imported",
                ),
            )
            entry["branches"].append(
                dict(
                    spell=key[0],
                    branch=key[1],
                    breeds=row["breeds"],
                    criterion_raw=row["criterion_raw"],
                    changes=row["changes"],
                    baseline_range_first_level=row.get("baseline_range_first_level"),
                    conditional_range_first_level=row.get(
                        "conditional_range_first_level"
                    ),
                    baseline_cost_first_level=row.get("baseline_cost_first_level"),
                    conditional_cost_first_level=row.get(
                        "conditional_cost_first_level"
                    ),
                )
            )
            if key in proved:
                entry[
                    "execution_proof"
                ] = "at least one exact branch/level observed; other callers/levels remain unknown"
            if call.get("source_candidates"):
                entry["producer_candidates"].append(call["source_candidates"])
    all_keys = {(r["spell"], r["branch"]) for r in matrix["rows"]}
    proved &= all_keys
    removal &= all_keys
    stages = Counter(r["stage"] for r in plan["plans"])
    domains = []
    for domain, keys in sorted(domain_rows.items()):
        domains.append(
            dict(
                domain=domain,
                branch_count=len(keys),
                observed_any_level_branch_count=len(keys & proved),
                no_imported_exact_branch_proof_count=len(keys - proved),
                requirements={
                    "owned_book_or_deck": "legal deck membership and actual grants/current book level",
                    "state": "actual source application plus selector ledger and negative guards",
                    "state_threshold_counter": "actual parameter-derived stack/level, modulo/comparison boundary, native counter events",
                    "live_characteristic": "native AP/MP/WP/HP current/max and real cost/turn changes",
                    "retained_effect": "native reference/UID manager ownership, guarded installation/removal",
                    "actor_or_cell_geometry": "legal movement/distance, actual PV/cell selector and terrain",
                    "summon_controller_or_morph": "actual constructor, controller, profile/current book and ownership",
                    "physical_carry": "actual carrier/carry relation and cleanup",
                    "fight_context": "complete actual fight type/context authority",
                }.get(domain, "inspect exact typed call"),
            )
        )
    current_hashes = {
        path: sha(Path(path)) for path in matrix["sources"] if Path(path).exists()
    }
    source_identity_status = {
        path: (
            "matched"
            if current_hashes.get(path) == value
            else "different"
            if path in current_hashes
            else "missing"
        )
        for path, value in matrix["sources"].items()
    }
    out = dict(
        full75_frozen_case_evidence=all75,
        historically_unusable_state_candidates=[
            3333,
            3699,
            6752,
            6872,
            7647,
            7950,
            9309,
            9315,
        ],
        unavailable_candidate_limit="Bounded source candidate qualification, not missing code or full alternative-producer proof;9315 actualCinetosisproducer exists",
        committed_baseline_observations=next(
            (r for r in all_committed_imports if r["path"].endswith("normal635.json")),
            None,
        ),
        all_committed_imports=all_committed_imports,
        removal_observations=removal_observations,
        current_source_identity_status=source_identity_status,
        current_source_hashes=current_hashes,
        shared_producer_evidence_not_branch_certification={
            "resource923": "actual owned8405 payment; does not establish all57 live-characteristic branches",
            "captured324": "actual owned descriptor/book/availability and Recall13; not all10 ownership branches",
            "copy1002": "actual8559 allocated7066 lifecycle; PA death stress separate",
            "microbot339": "actual placement/movement/recreation; not all14 geometry branches",
            "morph933": "actualL200 source-sequence lifecycle05 parent5900book,independent8588/8589/8590commits,8588restoration andforeign/expiredUID negatives;notallconditionalbranches",
            "native_turn1037": "WP regeneration policy, explicit source-order policy; focused6908/0 full-WP ON and actualspell-consumption OFF verified L20/L200, otherthresholdbranches unknown",
        },
        schema_version=1,
        scope="All651 conditional branches286references; prerequisite groups overlap, not additive functional denominator",
        sources={str(MATRIX): sha(MATRIX), str(PLAN): sha(PLAN)},
        frozen_source_hashes=matrix["sources"],
        source_matrix_reported_stable=matrix["sources_stable"],
        denominators=dict(
            classes=18,
            conditional_branches=651,
            conditional_references=286,
            prerequisite_signatures=len(signatures),
            state_candidate_branches=stages["state_transition_candidates"],
            other_or_negative_guard_branches=stages[
                "nonstate_or_negative_guard_preparation"
            ],
            bounded_state_executor_cases=75,
            bounded_state_executor_candidate_states=40,
            all_state_executor_prerequisite_states=48,
        ),
        exact_execution=dict(
            any_observed_level_branch_keys=[list(k) for k in sorted(proved)],
            observed_any_level_branches=len(proved),
            no_imported_exact_branch_proof=len(all_keys - proved),
            removal_observed_any_level_branches=len(removal),
            limit="No claim over every level, selector, parameter, ON/OFF branch, interaction or runtime context",
        ),
        domains=domains,
        signatures=signatures,
        evidence=evidence,
        next_general_steps=[
            "Close full-WP/counter preparation through native end-turn1037 and exact ancestor guards; repeat only currently focused missing signatures",
            "Select one legitimate producer sequence per novel prerequisite signature (book membership, thresholds, resource current/max, retained identity, owned summon, carry, distance); avoid Cartesian passive/deck repetition",
            "Each selected branch requires actual chosen conditional index and selected flags/cost/range, real commit, then native removal/expiry OFF control",
            "Negative/dynamic state guards and ungranted extras remain explicit unavailable prerequisites; never inject a state or force criterion True",
        ],
    )
    p = Path(
        "docs/reports/combat-inventory/class-conditional-prerequisite-inventory-20261008.json"
    )
    p.write_text(json.dumps(out, indent=2) + "\n")
    text = [
        "# Complete scoped conditional prerequisite inventory",
        "",
        "The source matrix contains651 branches on286 references across18 classes. The bounded transition executor has75 cases for40 usable candidate states out of48 state prerequisites; this is a candidate fixture set, not the complete conditional map. Source candidate edges and actual execution evidence are separate.",
        "",
        "| Shared prerequisite producer | Branches | Some exact level observed | No imported exact branch proof |",
        "|---|---:|---:|---:|",
    ]
    for r in domains:
        text.append(
            f"| {r['domain']} | {r['branch_count']} | {r['observed_any_level_branch_count']} | {r['no_imported_exact_branch_proof_count']} |"
        )
    text += [
        "",
        f"There are{len(signatures)} exact call/argument/polarity/comparison/selector signatures. Groups overlap. Imported stable focused reports and available compact committed baseline selections establish some exact-level branch observation for{len(proved)} branch keys;{len(all_keys-proved)} have no imported exact branch proof. This means unobserved in these reports, not unimplemented or unreachable. Removal evidence covers{len(removal)} keys at some observed level. No global functional percentage follows.",
        "",
        "[Machine-readable contracts and exact evidence identities](class-conditional-prerequisite-inventory-20261008.json) preserve raw comparison and modulo expressions, selector contracts, native producer candidates, guards, call polarity and report hashes. The matrix is a frozen source projection; current source hash differences are listed explicitly in JSON and do not silently refresh its denominator. No new parser, JVM or runtime catalog is launched.",
        "",
        "The next general work is legitimate producer composition: native stack/counter thresholds and full-WP end-event1037; legal deck/grant/current-book requirements; native resource current/max; retained reference/UID ownership; actual summon/controller/carry relationships; and legal distance/cell changes. A state-presence-only pass cannot satisfy these combined predicates. Choose one source-qualified sequence for each new signature, then assert chosen conditional index and resulting flags/cost/range through a committed cast, followed by actual removal/expiry OFF control. Missing authority remains unknown; negative guards are not positive state requirements.",
    ]
    for baseline_proof in all_committed_imports:
        text += [
            "",
            f"The compact import {baseline_proof['report']} contains{baseline_proof['committed_attempts']} committed attempts: origin counts {baseline_proof['committed_origin_counts']}. It contributes{len(baseline_proof['unique_selected_committed'])} uniquely selected committed conditional attempts on{len(baseline_proof['unique_selected_branch_keys'])} exact branch keys;{len(baseline_proof['known_matched_committed'])} known equivalent multi-match observations. The remaining baseline selections do not prove a positive conditional branch or its OFF/producer lifecycle. Executed native casting-table hash matches the frozen matrix: {baseline_proof['source_contract_identity_matches_frozen_matrix']}. Attempts do not increase the635 ordinary spell-level denominator.",
        ]
    if all75:
        text += [
            "",
            "The full75 frozen report contains75 Ready cases,18 ON cases and5 OFF cases (57 ON pending /70 OFF pending). Case counts remain distinct from unique651 branch keys.40 usable candidate states out of48 do not exhaust prerequisites. The earlier unusable9315 candidate is not a missing-code proof: an actual Cinetosis producer exists in independent scoped evidence.",
        ]
    if any("7651-consumption" in r["report"] for r in removal_observations):
        text += [
            "",
            "The latest6908/0 focus verifies levels20 and200 ON plus OFF via **actual owned spell consumption**. Its nested control is actual_consumption_and_branch_restoration_verified, not generic timer expiry. The top-level removal-or-expiry label is retained but does not change the source-qualified mechanism.",
        ]
    p.with_suffix(".md").write_text("\n".join(text) + "\n")
    print(out["denominators"])
    print(out["exact_execution"])
    print(domains)


if __name__ == "__main__":
    run()
