#!/usr/bin/env python3
"""Audit a complete recovered recurring inventory using typed family compilers.

The JSON output is a private evidence artifact, never a gameplay configuration.
No database, catalog loader, server, reward grant or quest activation is opened.
"""
import argparse
import csv
import gzip
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
from wakfu_server.objectives.environmental_recurring_contracts import (
    compile_hunter_contract,
    UnresolvedRecurringContract,
)


def compile_inventory(definitions, families, offers=None):
    offers = {} if offers is None else offers
    if len({row["definition_id"] for row in definitions}) != len(definitions):
        raise ValueError("Duplicate original recurring definition")
    classified = {row["definition_id"]: row["family"] for row in families}
    if len(classified) != len(families) or set(classified) != {
        row["definition_id"] for row in definitions
    }:
        raise ValueError(
            "Recurring family classification does not cover the same inventory"
        )
    result = []
    for native in definitions:
        family = classified[native["definition_id"]]
        row = dict(
            definition_id=int(native["definition_id"]),
            family=family,
            title=native["title_en"],
            automatic_activation=False,
        )
        if family == "implemented_guild_daily":
            row.update(
                status="PRESERVE_IMPLEMENTED_GUILD_DAILY",
                reason="existing_native_owned_pipeline",
            )
        elif family == "excluded_almanax":
            row.update(status="OUT_OF_SCOPE", reason="almanax_excluded")
        elif family == "trade_hunt_contract_candidate":
            try:
                contract = compile_hunter_contract(
                    definition_id=int(native["definition_id"]),
                    objectives=json.loads(native["objectives"]),
                    rewards=json.loads(native["rewards"]),
                    anchor_ms=int(native["calendar_anchor_ms"]),
                    period_seconds=int(native["calendar_period_seconds"]),
                    cooldown_seconds=int(native["cooldown_seconds"]),
                    repeatable=native["repeatable"] == "True",
                    activation_criteria=native["activation_criteria"],
                    eligibility_criteria=native["eligibility_criteria"],
                    acceptance_criteria=(
                        offers[int(native["definition_id"])].criterion
                        if int(native["definition_id"]) in offers
                        else None
                    ),
                )
                row.update(
                    status="COMPILED_SOURCE_CONTRACT_NOT_ACTIVATED",
                    reason="hunter_distinct_boss_variable_sum",
                    contract=asdict(contract),
                    integration_pending=[
                        "owned_original_acceptance",
                        "durable_boss_victory_binding",
                        "native_reward_settlement_and_multiplier_policy",
                    ],
                )
            except UnresolvedRecurringContract as exc:
                row.update(status="PRODUCER_CONTRACT_UNRESOLVED", reason=str(exc))
        elif family == "seasonal_contract_candidate":
            row.update(
                status="PRODUCER_CONTRACT_UNRESOLVED",
                reason="calendar_dates_do_not_identify_objective_or_interaction_producer",
            )
        elif family == "boss_smasher_candidate":
            row.update(
                status="PRODUCER_CONTRACT_UNRESOLVED",
                reason="original_event_window_boss_and_stasis_constraints_require_versioned_binding",
            )
        elif family == "scoreboard_contract_candidate":
            row.update(
                status="PRODUCER_CONTRACT_UNRESOLVED",
                reason="scoreboard_server_selection_or_objective_producer_unrecovered",
            )
        else:
            row.update(
                status="OUTSIDE_SELECTED_FAMILY_COMPILER",
                reason="no_story_or_generic_journal_activation_inferred",
            )
        result.append(row)
    return dict(
        scope="700 source candidates; no automatic gameplay activation",
        total=len(result),
        statuses=dict(Counter(row["status"] for row in result)),
        family_statuses={
            family: dict(
                Counter(row["status"] for row in result if row["family"] == family)
            )
            for family in sorted(set(classified.values()))
        },
        rows=result,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    base = ROOT / "agents_docs/reports/parallel-readiness-20261021"
    parser.add_argument(
        "--definitions", type=Path, default=base / "recurring-native-definitions.csv"
    )
    parser.add_argument(
        "--families",
        type=Path,
        default=base / "recurring-source-family-classification.csv",
    )
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with args.definitions.open() as stream:
        definitions = list(csv.DictReader(stream))
    with args.families.open() as stream:
        families = list(csv.DictReader(stream))
    from wakfu_server.objectives.environmental_recurring_offers import (
        compile_hunter_offers,
    )

    weekly_ids = {
        int(r["definition_id"])
        for r in definitions
        if r["repeatable"] == "True"
        and r["calendar_period_seconds"] == "604800"
        and any(
            f["definition_id"] == r["definition_id"]
            and f["family"] == "trade_hunt_contract_candidate"
            for f in families
        )
    }
    with gzip.open(ROOT / "server/protocol/npc-dialogues.json.gz", "rt") as stream:
        offers = compile_hunter_offers(json.load(stream)["nodes"], weekly_ids)
    result = compile_inventory(definitions, families, offers)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "rows"}, indent=2
        )
    )


if __name__ == "__main__":
    main()
