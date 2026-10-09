"""Offline all-class normal owned casts after production Ready and actual turns.

Each legal deck chunk receives its own Ready initialization. Cast candidates
are independent previews of that baseline; representative commits use private
RuntimeMessages clones. An optional mode commits every prepared attempt in a
separate clone. This is a baseline map, not all conditional gameplay.
"""
import argparse
from collections import Counter, deque
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import random
import struct

import audit_ready_start as ready_audit
from class_spell_eligible_targets import eligible_cast_targets
from wakfu_server.combat_class_initialization import BREEDS
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import server_runtime, prepare_server_spell
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.combat_morph_spellbook import morph_record
from wakfu_server.combat_conditions import UnknownCondition
from wakfu_server.combat_effect_dispatch import UnsupportedEffectExecution
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import available_spells, ACTIVE_SLOT_LEVELS, validate_deck


def actual_state_ledgers(fight):
    """Capture actual ordered Qf entries; never synthesize a state or manager."""
    owners = {}
    for identity, actor in fight.actors.items():
        owners[str(identity)] = dict(
            carrier="fighter",
            entries=[asdict(entry) for entry in actor.state_ledger.entries],
        )
    for carrier, attribute in (
        ("active_area", "native_effect_areas"),
        ("retired_area", "native_retired_area_managers"),
    ):
        for identity, row in getattr(fight, attribute, {}).items():
            ledger = row.get("state_ledger")
            if ledger is not None:
                owners[str(identity)] = dict(
                    carrier=carrier, entries=[asdict(entry) for entry in ledger.entries]
                )
    return owners


def deck_cases(breeds, levels):
    if (
        not breeds
        or not levels
        or any(type(breed) is not int or breed not in BREEDS for breed in breeds)
        or any(type(level) is not int or not 1 <= level <= 200 for level in levels)
    ):
        raise ValueError("Known class IDs and legal owned character levels required")
    queues, cases, inventory = {}, [], []
    for breed in sorted(breeds):
        for level in sorted(levels):
            available = available_spells(breed, level)
            active = sorted(row["id"] for row in available if row["kind"] == "active")
            capacity = sum(level >= threshold for threshold in ACTIVE_SLOT_LEVELS)
            chunks = [
                active[offset : offset + capacity]
                for offset in range(0, len(active), capacity)
            ] or [[]]
            queues[breed, level] = deque(chunks)
            cases.extend((breed, level, None) for _ in chunks)
            inventory.append(
                dict(
                    breed=breed,
                    level=level,
                    active_references=active,
                    passive_references=sorted(
                        row["id"] for row in available if row["kind"] == "passive"
                    ),
                    slot_capacity=capacity,
                    legal_deck_chunks=chunks,
                    passive_policy="baseline has native innates and no optional passive deck",
                )
            )

    def provider(breed, level, passive):
        return queues[breed, level].popleft()

    return cases, provider, inventory


def root_failure(error, trace=()):
    causes, current = [], error
    while current is not None and current not in causes:
        causes.append(current)
        current = current.__cause__ or current.__context__
    first = next((row for row in trace if row.get("status") == "failed"), {})
    native = getattr(error, "native_casting_result", None)
    code = getattr(error, "cast_validation_code", None)
    kind = (
        "unsupported_predicate"
        if any(isinstance(value, UnknownCondition) for value in causes)
        else "resource_rejection"
        if code == "insufficient_resources"
        else "legal_target_rejection"
        if native
        in {"twE", "twF", "twG", "twH", "twI", "twJ", "twT", "twU", "twV", "twX", "twY"}
        else "effect_family_or_provider"
        if any(isinstance(value, UnsupportedEffectExecution) for value in causes)
        else "authority_or_lifecycle_guard"
    )
    return dict(
        kind=kind,
        error=type(error).__name__,
        reason=str(error),
        root_error=type(causes[-1]).__name__,
        root_reason=str(causes[-1]),
        native_casting_result=native,
        validation_code=code,
        first_failed_effect=first,
    )


def numeric_summary(inventory, source_rows):
    expected = {
        (item["breed"], item["level"], reference)
        for item in inventory
        for reference in item["active_references"]
    }
    normal, grants = {}, {}
    normal_observations = grant_observations = 0
    for source in source_rows:
        for action in source.get("runtime_access", {}).get("actions", []):
            key = (source["breed"], source["level"], action["reference"])
            if action["origin"] == "normal_owned_deck":
                normal.setdefault(key, []).append(action)
                normal_observations += 1
            elif action["origin"] == "actual_ready_grant":
                grants.setdefault(key, []).append(action)
                grant_observations += 1
    counts = Counter()
    if set(normal) - expected:
        raise AssertionError(
            "Normal cast observations exceed the owned class inventory"
        )
    commit_selected = commit_passed = commit_rejected = commit_mixed = 0
    for key in expected:
        rows = normal.get(key, [])
        attempts = [attempt for row in rows for attempt in row.get("attempts", [])]
        prepared = any(attempt.get("prepared") for attempt in attempts)
        commits = [
            attempt.get("commit", attempt.get("representative_commit"))
            for attempt in attempts
            if "commit" in attempt or "representative_commit" in attempt
        ]
        passed = any(commit["status"] == "committed" for commit in commits)
        rejected = any(commit["status"] == "rejected" for commit in commits)
        commit_selected += bool(commits)
        commit_passed += passed
        commit_rejected += rejected
        commit_mixed += passed and rejected
        if prepared:
            counts["prepared"] += 1
        elif not rows:
            counts["not_reached_ready_or_owned_turn"] += 1
        elif attempts:
            counts["effect_transaction_rejected"] += 1
        else:
            statuses = {row["status"] for row in rows}
            bucket = (
                "legal_complete_search_no_context"
                if "no_eligible_context" in statuses
                else "bounded_search_no_context"
                if "bounded_search_exhausted" in statuses
                else "target_authority_unresolved"
                if "eligibility_authority_unresolved" in statuses
                else "access_or_audit_authority_rejected"
            )
            counts[bucket] += 1
    for key in (
        "prepared",
        "not_reached_ready_or_owned_turn",
        "effect_transaction_rejected",
        "legal_complete_search_no_context",
        "bounded_search_no_context",
        "target_authority_unresolved",
        "access_or_audit_authority_rejected",
    ):
        counts.setdefault(key, 0)
    total = len(expected)
    if sum(counts.values()) != total:
        raise AssertionError("Normal cast preparation partition lost inventory entries")
    normal_attempts = [
        attempt
        for rows in normal.values()
        for row in rows
        for attempt in row.get("attempts", [])
    ]
    prepared_attempts = sum(
        bool(attempt.get("prepared")) for attempt in normal_attempts
    )
    selected_attempts = sum(
        "commit" in attempt or "representative_commit" in attempt
        for attempt in normal_attempts
    )
    return dict(
        normal=dict(
            expected_spell_level_pairs=total,
            audited_spell_level_pairs=len(set(normal) & expected),
            observed_rows=normal_observations,
            duplicate_observed_rows=normal_observations - len(normal),
            preparation_partition=dict(counts),
            prepared_percent=round(100 * counts["prepared"] / total, 3) if total else 0,
            commit_selected_spell_level_pairs=commit_selected,
            commit_passed_spell_level_pairs=commit_passed,
            commit_rejected_spell_level_pairs=commit_rejected,
            commit_mixed_outcome_spell_level_pairs=commit_mixed,
            commit_passed_percent=round(100 * commit_passed / total, 3) if total else 0,
            commit_counts_can_overlap_only_when_mixed=True,
            prepared_without_successful_commit=counts["prepared"] - commit_passed,
            prepared_attempt_count=prepared_attempts,
            commit_attempt_count=selected_attempts,
            prepared_attempts_without_commit=prepared_attempts - selected_attempts,
            baseline_percent_is_not_global_gameplay_percentage=True,
        ),
        grants=dict(
            distinct_ready_available_spell_level_pairs=len(grants),
            observed_rows=grant_observations,
            repeated_rows_across_deck_chunks=grant_observations - len(grants),
            excluded_from_normal_denominator=True,
        ),
    )


class NormalCastAudit:
    def __init__(
        self,
        *,
        candidate_limit=32,
        maximum_eligible=2,
        action_selector=None,
        commit_each_prepared=False
    ):
        if type(commit_each_prepared) is not bool:
            raise ValueError("Explicit normal cast commit policy required")
        self.candidate_limit, self.maximum_eligible = candidate_limit, maximum_eligible
        self.action_selector = action_selector
        self.commit_each_prepared = commit_each_prepared
        self.committed_families, self.committed_classes = set(), set()

    def should_commit(self, families, class_key):
        return (
            self.commit_each_prepared
            or bool(families - self.committed_families)
            or class_key not in self.committed_classes
        )

    def commit_prepared(
        self, baseline, transaction, stats_serializer, actor_id, new_families
    ):
        """Commit only a private RuntimeMessages branch, preserving the baseline."""
        before = snapshot(baseline.fight)
        resources_before = {
            str(k): v
            for k, v in baseline.fight.actors[actor_id].effect_stats.items()
            if k in (1, 2, 3, 4)
        }
        branch = deepcopy(baseline)
        try:
            packets = commit_spell_transaction(
                branch, transaction, stats_serializer=stats_serializer
            )
            committed = snapshot(branch.fight)
            checkpoint = json.dumps(
                committed, allow_nan=False, sort_keys=True, separators=(",", ":")
            )
            resources_after = {
                str(k): v
                for k, v in branch.fight.actors[actor_id].effect_stats.items()
                if k in (1, 2, 3, 4)
            }
            return dict(
                status="committed",
                packet_count=len(packets),
                packet_opcode_counts=dict(
                    Counter(str(packet[0]) for packet in packets)
                ),
                prepared_effect_packet_opcode_counts=dict(
                    Counter(str(packet[0]) for packet in transaction.packets)
                ),
                costs=deepcopy(transaction.plan["costs"]),
                state_ledgers_after=actual_state_ledgers(branch.fight),
                new_executed_families=sorted(new_families),
                plain_json_snapshot=True,
                checkpoint_sha256=hashlib.sha256(checkpoint.encode()).hexdigest(),
                phase_after=branch.fight.phase,
                current_actor_id=None
                if branch.fight.current is None
                else branch.fight.current.id,
                owned_grants_after=sorted(granted_spells(branch.fight, actor_id)),
                resources_before=resources_before,
                resources_after=resources_after,
                net_resource_changes={
                    key: resources_after[key] - value
                    for key, value in resources_before.items()
                },
                net_resource_changes_include_effects=True,
                baseline_preserved=True,
            )
        finally:
            if snapshot(baseline.fight) != before:
                raise AssertionError("Isolated normal cast commit changed its baseline")

    def __call__(
        self, runtime, character, monster, deck, initial_packets, stats_serializer
    ):
        original = snapshot(runtime.fight)
        baseline = deepcopy(runtime)
        advances = []
        turn_trace = []
        try:
            for _ in range(max(2, len(baseline.fight.actors) * 4)):
                if baseline.fight.phase != "active":
                    raise ValueError("Actual fight ended before the owned PC turn")
                if baseline.awaiting_ack is not None:
                    ack = baseline.awaiting_ack
                    with combat_diagnostic_scope(
                        lambda **event: turn_trace.append(event), limit=4096
                    ):
                        packets = baseline.acknowledge_turn(struct.pack(">i", ack))
                    advances.append(
                        dict(
                            actor_id=None,
                            ack=ack,
                            packet_count=len(packets),
                            stage="actual_pending_turn_acknowledged",
                        )
                    )
                    continue
                current = baseline.fight.current
                if (
                    current is not None
                    and current.id == character["id"]
                    and baseline.awaiting_ack is None
                ):
                    break
                if current is None:
                    raise ValueError("Missing actual current actor in Ready runtime")
                with combat_diagnostic_scope(
                    lambda **event: turn_trace.append(event), limit=4096
                ):
                    packets = (
                        baseline.end_turn(
                            current.owner_id, current.id, current.turn_count
                        )
                        if current.controlled
                        else baseline.end_server_turn(
                            current.id, baseline.fight.turn_id
                        )
                    )
                    ack = baseline.awaiting_ack
                    if ack is not None:
                        packets += baseline.acknowledge_turn(struct.pack(">i", ack))
                advances.append(
                    dict(actor_id=current.id, ack=ack, packet_count=len(packets))
                )
            else:
                raise ValueError("Bounded actual turn cycle did not reach the owned PC")
        except Exception as error:
            return dict(
                status="turn_baseline_unavailable",
                turns=advances,
                turn_trace=turn_trace,
                first_root_failure=root_failure(error, turn_trace),
                source_preserved=snapshot(runtime.fight) == original,
            )
        fight = baseline.fight
        source = snapshot(fight)
        actor = fight.actors[character["id"]]
        _, adapter = server_runtime(
            character,
            {monster["id"]: monster},
            deck,
            action_id=baseline.action_id + 1,
            critical=False,
            rng=random.Random(17),
        )

        def los(origin, target, current):
            return authoritative_visible(
                current.map_id,
                origin,
                target,
                current,
                blocking_footprints={
                    value.id: {value.position[:2]}
                    for value in current.actors.values()
                    if value.hp > 0
                },
            )

        parsed = validate_deck(deck, character["breed"], character["level"])
        actions = [
            dict(reference=ref, uid=(actor.id << 32) | ref, origin="normal_owned_deck")
            for ref in parsed["active"]
            if ref
        ]
        actions.extend(
            dict(reference=ref, uid=row["uid"], origin="actual_ready_grant")
            for ref, row in sorted(granted_spells(fight, actor.id).items())
        )
        form = morph_record(fight, actor.id)
        if form is not None:
            actions.extend(
                dict(reference=ref, uid=ref, origin="actual_ready_morph_book")
                for ref in form["levels"]
            )
        omitted_actions = []
        if self.action_selector is not None:
            if not callable(self.action_selector):
                raise ValueError("Normal owned action selector must be callable")
            selected = list(self.action_selector(actions))
            if any(action not in actions for action in selected):
                raise ValueError("Action selector invented a non-owned action")
            omitted_actions = [action for action in actions if action not in selected]
            actions = selected
        rows = []
        for action in actions:
            row = dict(action, attempts=[])
            trace = []
            try:
                selection = eligible_cast_targets(
                    fight,
                    character,
                    deck,
                    action["uid"],
                    adapter=adapter,
                    line_of_sight=los,
                    actor_id=actor.id,
                    limit=self.candidate_limit,
                    maximum_eligible=self.maximum_eligible,
                )
                row["target_selection"] = dict(
                    selection,
                    eligible=[
                        dict(target=value["target"]) for value in selection["eligible"]
                    ],
                )
                if not selection["eligible"]:
                    first = next(
                        (
                            value
                            for value in selection["rejected"]
                            if value["authority_unresolved"]
                        ),
                        next(iter(selection["rejected"]), {}),
                    )
                    row["first_root_failure"] = dict(
                        kind="target_authority_unresolved"
                        if first.get("authority_unresolved")
                        else "legal_baseline_context_unavailable",
                        reason=first.get("reason"),
                        native_casting_result=first.get("native_casting_result"),
                        validation_code=first.get("validation_code"),
                        diagnostic=first.get("native_casting_diagnostic"),
                    )
                for candidate in selection["eligible"]:
                    target = candidate["target"]
                    trace = []
                    attempt = dict(
                        target=target, branch="independent_actual_turn_baseline"
                    )
                    attempt["state_ledgers_before"] = actual_state_ledgers(fight)
                    stage = "effect_transaction"
                    try:
                        with combat_diagnostic_scope(
                            lambda **event: trace.append(event), limit=4096
                        ):
                            transaction = prepare_server_spell(
                                struct.pack(">qqiih", actor.id, action["uid"], *target),
                                character,
                                {monster["id"]: monster},
                                fight,
                                actor.owner_id,
                                deck,
                                action_id=baseline.action_id + 1,
                                line_of_sight=los,
                                critical=False,
                                rng=random.Random(17),
                            )
                        if snapshot(fight) != source:
                            raise AssertionError("Spell preview changed source fight")
                        families = {
                            event["effect_class"]
                            for event in trace
                            if event.get("status") == "completed"
                            and type(event.get("effect_class")) is int
                        }
                        attempt.update(
                            status="prepared_transaction",
                            costs=transaction.plan["costs"],
                            native_casting_selection=transaction.plan.get(
                                "native_casting_selection"
                            ),
                            native_casting_flags=transaction.plan.get(
                                "native_casting_flags"
                            ),
                            native_casting_diagnostic=transaction.plan.get(
                                "native_casting_diagnostic"
                            ),
                            prepared=True,
                            packet_count=len(transaction.packets),
                            executed_families=sorted(families),
                            trace_complete=not any(
                                event.get("effects_omitted", 0) for event in trace
                            ),
                        )
                        class_key = (character["breed"], character["level"])
                        new_families = families - self.committed_families
                        if self.should_commit(families, class_key):
                            stage = (
                                "each_prepared_commit"
                                if self.commit_each_prepared
                                else "representative_commit"
                            )
                            commit_key = (
                                "commit"
                                if self.commit_each_prepared
                                else "representative_commit"
                            )
                            attempt[commit_key] = self.commit_prepared(
                                baseline,
                                transaction,
                                stats_serializer,
                                actor.id,
                                new_families,
                            )
                            self.committed_families.update(families)
                            self.committed_classes.add(class_key)
                    except Exception as error:
                        failure = root_failure(error, trace)
                        attempt.update(
                            status="prepared_transaction_commit_rejected"
                            if attempt.get("prepared")
                            else "rejected",
                            failed_stage=stage,
                            first_root_failure=failure,
                        )
                        if stage in ("representative_commit", "each_prepared_commit"):
                            attempt[
                                "commit"
                                if self.commit_each_prepared
                                else "representative_commit"
                            ] = dict(status="rejected", first_root_failure=failure)
                    attempt["trace"] = trace
                    attempt["source_preserved"] = snapshot(fight) == source
                    if not attempt["source_preserved"]:
                        raise AssertionError("Normal cast audit source mutation")
                    row["attempts"].append(attempt)
                row["status"] = (
                    "prepared_transaction"
                    if any(attempt.get("prepared") for attempt in row["attempts"])
                    else "effect_transaction_rejected"
                    if row["attempts"]
                    else selection["status"]
                )
            except Exception as error:
                row.update(
                    status="audit_or_authority_rejected",
                    first_root_failure=root_failure(error, trace),
                )
            rows.append(row)
        preserved = snapshot(fight) == source and snapshot(runtime.fight) == original
        if not preserved:
            raise AssertionError("Normal cast baseline audit mutated its source")
        return dict(
            status="normal_cast_baseline_audited",
            turns=advances,
            current_actor_id=actor.id,
            turn_trace=turn_trace,
            source_preserved=True,
            actions=rows,
            omitted_actions=omitted_actions,
            normal_deck_references=parsed["active"],
            actual_ready_grants=sorted(granted_spells(fight, actor.id)),
            gameplay_verified=False,
            candidate_limit=self.candidate_limit,
            maximum_eligible=self.maximum_eligible,
            commit_policy="each_prepared"
            if self.commit_each_prepared
            else "representative",
            representative_committed_families=sorted(self.committed_families),
        )


def run(
    output,
    *,
    breeds=None,
    levels=(20, 200),
    candidate_limit=32,
    maximum_eligible=2,
    commit_each_prepared=False
):
    breeds = sorted(BREEDS) if breeds is None else sorted(breeds)
    cases, provider, inventory = deck_cases(breeds, levels)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    tool_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    inspector = NormalCastAudit(
        candidate_limit=candidate_limit,
        maximum_eligible=maximum_eligible,
        commit_each_prepared=commit_each_prepared,
    )
    report = ready_audit.run(
        output,
        basics_only=True,
        turn_cycle=True,
        turn_steps=0,
        cases_override=cases,
        on_runtime=inspector,
        active_deck_provider=provider,
    )
    class_map = []
    for item in inventory:
        matching = [
            row
            for row in report["rows"]
            if (row["breed"], row["level"]) == (item["breed"], item["level"])
        ]
        actions = [
            action
            for row in matching
            for action in row.get("runtime_access", {}).get("actions", [])
        ]
        tested = {
            action["reference"]
            for action in actions
            if action["origin"] == "normal_owned_deck"
        }
        class_map.append(
            dict(
                item,
                ready_status_counts=dict(Counter(row["status"] for row in matching)),
                normal_action_status_counts=dict(
                    Counter(
                        action["status"]
                        for action in actions
                        if action["origin"] == "normal_owned_deck"
                    )
                ),
                direct_references_audited=sorted(tested),
                direct_inventory_complete=tested == set(item["active_references"]),
                grant_references_available=sorted(
                    {
                        action["reference"]
                        for action in actions
                        if action["origin"] == "actual_ready_grant"
                    }
                ),
                missing_direct_references=sorted(
                    set(item["active_references"]) - tested
                ),
            )
        )
    failures = Counter()
    for source_row in report["rows"]:
        runtime_failure = source_row.get("runtime_access", {}).get("first_root_failure")
        if runtime_failure:
            failures[
                (
                    runtime_failure["kind"],
                    runtime_failure.get("first_failed_effect", {}).get("effect_class"),
                    runtime_failure.get("root_reason", runtime_failure.get("reason")),
                )
            ] += 1
        for action in source_row.get("runtime_access", {}).get("actions", []):
            records = [action] if not action.get("attempts") else action["attempts"]
            for record in records:
                failure = record.get("first_root_failure")
                if failure:
                    failures[
                        (
                            failure["kind"],
                            failure.get("first_failed_effect", {}).get("effect_class"),
                            failure.get("root_reason", failure.get("reason")),
                        )
                    ] += 1
    report.update(
        normal_cast_inventory=class_map,
        normal_tool_sha256=tool_hash,
        numeric_summary=numeric_summary(inventory, report["rows"]),
        normal_tool_stable=tool_hash
        == hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        all_requested_class_decks_reached=all(
            row["direct_inventory_complete"] for row in class_map
        ),
        normal_cast_scope="all available direct class spells; baseline innates; dynamic grants separately",
        commit_policy="each_prepared" if commit_each_prepared else "representative",
        commit_each_prepared=commit_each_prepared,
        representative_committed_families=sorted(inspector.committed_families),
        optional_passive_variants_verified=False,
        all_conditional_gameplay_verified=False,
    )
    report["normal_root_failure_counts"] = [
        dict(kind=kind, effect_class=family, reason=reason, count=count)
        for (kind, family, reason), count in failures.most_common()
    ]
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--breeds", type=int, nargs="+")
    parser.add_argument("--levels", type=int, nargs="+", default=[20, 200])
    parser.add_argument("--candidate-limit", type=int, default=32)
    parser.add_argument("--maximum-eligible", type=int, default=2)
    parser.add_argument(
        "--commit-each-prepared",
        action="store_true",
        help="Commit every prepared attempt in its own private baseline branch",
    )
    args = parser.parse_args()
    report = run(
        args.output,
        breeds=args.breeds,
        levels=args.levels,
        candidate_limit=args.candidate_limit,
        maximum_eligible=args.maximum_eligible,
        commit_each_prepared=args.commit_each_prepared,
    )
    print(
        json.dumps(
            dict(
                cases=report["expected_cases"],
                status_counts=report["status_counts"],
                classes=len(report["normal_cast_inventory"]),
                inventory_complete=report["all_requested_class_decks_reached"],
            )
        )
    )
