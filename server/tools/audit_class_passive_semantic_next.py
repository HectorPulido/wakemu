"""Bounded source-selected passive semantic cases after frozen bulk339.

Each case requests one real owned or granted action and legal native Ready.
Source novelty and prerequisite failures remain separate from semantics proven.
"""
import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path

import audit_ready_start as ready
from audit_class_passive_mechanics import PassiveAudit, native_contracts
from wakfu_server.spells import (
    available_spells,
    ACTIVE_SLOT_LEVELS,
    encode_deck,
    validate_deck,
)

ROOT = Path(__file__).resolve().parents[2]
PLAN = (
    ROOT
    / "docs/reports/combat-inventory/class-passive-mechanic-gap-inventory-20261008.json"
)
REPORT = (
    ROOT
    / ".runtime/combat-review-20261008/class-passive-mechanics-optimized-full-01.json"
)


def planned_semantic_cases(plan, report):
    records = [
        dict(
            breed=row["breed"],
            level=row["level"],
            passive=row["proposed_passive"],
            action=row["action"],
            source_novelty_units=row["new_source_contract_units"],
            purpose="source_novelty",
            fixture_context="native_fresh_pc",
        )
        for row in plan["next_bulk"]["proposed_cases"]
    ]
    regression_refs = (385223, 147263, 120894, 371570, 353422)
    for reference in regression_refs:
        cause = next(
            row for row in plan["causes"] if row["effect_reference"] == reference
        )
        case = cause["cases"][0]
        original = next(
            row
            for row in report["rows"]
            if (row["breed"], row["level"], row["passive"])
            == (case["breed"], case["level"], case["passive"])
        )
        action = (
            case.get("action")
            or original["runtime_access"]["representative_action_plan"][
                "owned_references"
            ][0]
        )
        records.append(
            dict(
                breed=case["breed"],
                level=case["level"],
                passive=case["passive"],
                action=action,
                source_novelty_units=0,
                purpose="contract_regression_" + str(reference),
                fixture_context="native_fresh_pc",
            )
        )
    cause = next(
        row
        for row in plan["causes"]
        if row["reason"] == "Native eHP owned Symbiot component required"
    )
    case = cause["cases"][0]
    records.append(
        dict(
            breed=case["breed"],
            level=case["level"],
            passive=case["passive"],
            action=case["action"],
            source_novelty_units=0,
            purpose="owned_roster_grant_prerequisite",
            fixture_context="source_owned_captured_roster",
        )
    )
    queues, action_keys = defaultdict(deque), {}
    for row in records:
        available = available_spells(row["breed"], row["level"])
        active = sorted(spell["id"] for spell in available if spell["kind"] == "active")
        if row["passive"] not in {
            spell["id"] for spell in available if spell["kind"] == "passive"
        }:
            raise ValueError(
                "Source-selected passive is not legally owned at this level"
            )
        if row["action"] not in active:
            matching = [
                source
                for source in report["rows"]
                if (source["breed"], source["level"], source["passive"])
                == (row["breed"], row["level"], row["passive"])
            ]
            if not any(
                row["action"]
                in source.get("runtime_access", {}).get("actual_ready_grants", [])
                for source in matching
            ):
                raise ValueError(
                    "Requested action lacks direct ownership or original Ready grant evidence"
                )
        capacity = sum(row["level"] >= value for value in ACTIVE_SLOT_LEVELS)
        chosen = ([row["action"]] if row["action"] in active else []) + active
        row["active_deck"] = list(dict.fromkeys(chosen))[:capacity]
        validate_deck(
            encode_deck(row["active_deck"], [row["passive"]]),
            row["breed"],
            row["level"],
        )
        key = (row["breed"], row["level"], row["passive"])
        queues[key].append(row)
        action_key = (*key, tuple(row["active_deck"]))
        if action_key in action_keys and action_keys[action_key] != row["action"]:
            original_deck = row["active_deck"]
            for offset in range(1, len(original_deck)):
                rotated = original_deck[offset:] + original_deck[:offset]
                alternate = (*key, tuple(rotated))
                if (
                    alternate not in action_keys
                    or action_keys[alternate] == row["action"]
                ):
                    row["active_deck"], action_key = rotated, alternate
                    validate_deck(
                        encode_deck(rotated, [row["passive"]]),
                        row["breed"],
                        row["level"],
                    )
                    break
            else:
                raise ValueError(
                    "Cannot distinguish declared actions with a legal deck ordering"
                )
        action_keys[action_key] = row["action"]
    return records, queues, action_keys


def run(
    output, *, plan_path=PLAN, report_path=REPORT, plan_only=False, candidate_limit=16
):
    tool_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    plan_raw, report_raw = plan_path.read_bytes(), report_path.read_bytes()
    plan, previous = json.loads(plan_raw), json.loads(report_raw)
    if hashlib.sha256(report_raw).hexdigest() != plan["provenance"]["report_sha256"]:
        raise ValueError("Semantic case plan and frozen339 report identities differ")
    records, queues, requested = planned_semantic_cases(plan, previous)
    cases = [(row["breed"], row["level"], row["passive"]) for row in records]
    contexts = {}

    def provider(breed, level, passive):
        row = queues[breed, level, passive].popleft()
        contexts["current"] = row
        return row["active_deck"]

    def fixture(character, breed, level, passive):
        row = contexts["current"]
        if row["fixture_context"] != "source_owned_captured_roster":
            return
        # Explicit offline owned fixture, using the same original eligible domain
        # as the source-verified324 transaction; never invent an NPC ability book.
        from wakfu_server.characters.captured_roster import (
            CapturedCreature,
            OwnedCapturedRoster,
        )
        from wakfu_server.combat_captured_profiles import native_captured_profiles

        profile = native_captured_profiles().get("5347")
        if (
            breed != 2
            or profile is None
            or 40 not in profile["fight_properties"]
            or 28 in profile["fight_properties"]
        ):
            raise ValueError("Missing original source-eligible owned capture fixture")
        slots = [None] * 10
        slots[3] = CapturedCreature(3, 5347, "Native owned fixture")
        flags = [False] * 10
        flags[3] = True
        character["captured_roster"] = OwnedCapturedRoster(
            character["id"], tuple(slots), tuple(flags), 3
        ).to_record()

    output = Path(output)
    if plan_only:
        result = dict(finished=True, runtime_executed=False, rows=[])
    else:
        contracts, graph_hash = native_contracts(cases)
        if graph_hash != plan["provenance"]["native_graph_sha256"]:
            raise ValueError("Semantic source graph changed since the gap inventory")
        inspector = PassiveAudit(
            cases, contracts, candidate_limit, requested_actions=requested
        )
        result = ready.run(
            output,
            basics_only=True,
            turn_cycle=True,
            turn_steps=0,
            cases_override=cases,
            active_deck_provider=provider,
            character_fixture_provider=fixture,
            on_runtime=inspector,
        )
        result["requested_action_missing_cases"] = sum(
            row.get("runtime_access", {}).get("requested_action_available") is False
            for row in result["rows"]
        )
    result.update(
        semantic_cases=records,
        semantic_case_count=len(records),
        semantic_class_count=len({row["breed"] for row in records}),
        source_plan_sha256=hashlib.sha256(plan_raw).hexdigest(),
        source_report_sha256=hashlib.sha256(report_raw).hexdigest(),
        source_tool_sha256=tool_hash,
        source_tool_stable=tool_hash
        == hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        declared_action_budget=len(records),
        critical_policy="normal branches only; native critical selection remains unverified",
        prerequisite_transition_policy="no fabricated transitions; unavailable prerequisites retained for dedicated legal producer paths",
        case_purpose_counts=dict(Counter(row["purpose"] for row in records)),
        full_passive_semantics_verified=False,
        full_client_verified=False,
    )
    if plan_path.read_bytes() != plan_raw or report_path.read_bytes() != report_raw:
        raise ValueError("Source semantic plan/report changed during run")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--candidate-limit", type=int, default=16)
    args = parser.parse_args()
    run(args.output, plan_only=args.plan_only, candidate_limit=args.candidate_limit)
