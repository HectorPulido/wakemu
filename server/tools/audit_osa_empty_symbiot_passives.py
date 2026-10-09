#!/usr/bin/env python3
"""Replay the frozen17 Osa authority gaps with the actual fresh empty Symbiot."""
import argparse
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
from wakfu_server.characters.captured_roster import roster_from_character

ROOT = Path(__file__).resolve().parents[2]
PLAN = (
    ROOT
    / "docs/reports/combat-inventory/class-passive-mechanic-gap-inventory-20261008.json"
)


def scoped_cases(plan):
    cause = next(
        row
        for row in plan["causes"]
        if row["reason"] == "Native eHP owned Symbiot component required"
    )
    cases = [dict(row) for row in cause["cases"]]
    if len(cases) != 17 or any(row["breed"] != 2 for row in cases):
        raise ValueError("Frozen17 Osa authority scope changed")
    decks, requests = {}, {}
    for row in cases:
        key = row["breed"], row["level"], row["passive"]
        active = sorted(
            spell["id"]
            for spell in available_spells(row["breed"], row["level"])
            if spell["kind"] == "active"
        )
        if row["action"] not in active:
            raise ValueError("Frozen action is not actually owned at this level")
        capacity = sum(row["level"] >= threshold for threshold in ACTIVE_SLOT_LEVELS)
        deck = list(dict.fromkeys([row["action"], *active]))[:capacity]
        validate_deck(encode_deck(deck, [row["passive"]]), row["breed"], row["level"])
        decks[key] = deck
        requests[(*key, tuple(deck))] = row["action"]
    return cases, decks, requests


def run(output):
    raw = PLAN.read_bytes()
    plan = json.loads(raw)
    cases, decks, requests = scoped_cases(plan)
    triples = [(row["breed"], row["level"], row["passive"]) for row in cases]
    contracts, graph_hash = native_contracts(triples)
    inspector = PassiveAudit(triples, contracts, 32, requested_actions=requests)

    def observed(runtime, character, monster, deck, packets, stats):
        roster = roster_from_character(character)
        if roster is None or any(slot is not None for slot in roster.slots):
            raise ValueError("Actual fresh empty Symbiot constructor is required")
        result = inspector(runtime, character, monster, deck, packets, stats)
        result["fresh_empty_symbiot"] = roster.to_record()
        result[
            "fixture_policy"
        ] = "actual fresh constructor; no captured creature supplied"
        result["empty_capture_prerequisite_causality_verified"] = False
        requested = next(
            action
            for action in cases
            if (action["breed"], action["level"], action["passive"])
            == (
                character["breed"],
                character["level"],
                validate_deck(deck, character["breed"], character["level"])["passive"][
                    0
                ],
            )
        )
        action_rows = [
            row
            for row in result.get("actions", [])
            if row.get("reference") == requested["action"]
        ]
        result["empty_roster_action_classification"] = (
            "owned_action_missing"
            if not action_rows
            else "authority_unresolved"
            if any(
                row.get("target_selection", {}).get("status")
                == "eligibility_authority_unresolved"
                for row in action_rows
            )
            else "known_cast_rejection_with_empty_roster"
            if all(not row.get("attempts") for row in action_rows)
            else "actual_transaction_attempted"
        )
        return result

    result = ready.run(
        output,
        basics_only=True,
        turn_cycle=True,
        turn_steps=0,
        cases_override=triples,
        active_deck_provider=lambda breed, level, passive: decks[breed, level, passive],
        on_runtime=observed,
    )
    result.update(
        scope="Frozen17 Osa passive authority gaps replayed against actual fresh empty Symbiot",
        source_plan_sha256=hashlib.sha256(raw).hexdigest(),
        source_graph_sha256=graph_hash,
        requested_cases=cases,
        captured_creature_supplied=False,
        full_capture_semantics_verified=False,
        full_client_verified=False,
    )
    Path(output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
