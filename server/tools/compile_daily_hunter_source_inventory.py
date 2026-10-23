#!/usr/bin/env python3
"""Grade original daily-hunter data; never infer gameplay from titles or flags.

Output is private audit evidence, not installed gameplay configuration. A literal
False criterion is preserved as a blocked predicate, not relabelled retirement.
"""
import argparse
from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
_DELIVERY = re.compile(
    r"GetItemQuantity\((\d+)\)>=(\d+)andIsAchievementRunning\((\d+)\)(andFalse)?"
)


def original_deliveries(nodes):
    result = {}
    for node in nodes:
        for choice in node.get("choices", ()):
            criterion = choice.get("criteria", "")
            matched = _DELIVERY.fullmatch(re.sub(r"\s+", "", criterion))
            if matched is None:
                continue
            identity = int(matched[3])
            if type(choice.get("type")) is not int or choice["type"] != 8:
                raise ValueError("Unexpected original item-delivery choice type")
            row = dict(
                node_id=node["id"],
                choice_id=choice["id"],
                definition_id=identity,
                item_reference=int(matched[1]),
                quantity=int(matched[2]),
                criterion=criterion,
                literal_false=matched[4] is not None,
            )
            if row["quantity"] <= 0 or row["item_reference"] <= 0:
                raise ValueError("Invalid original delivery quantity/reference")
            if identity in result and result[identity] != row:
                raise ValueError("Ambiguous original daily item-delivery source")
            result[identity] = row
    return result


def compile_inventory(definitions, classifications, nodes):
    families = {r["definition_id"]: r["family"] for r in classifications}
    if len(families) != len(classifications):
        raise ValueError("Duplicate classified source definition")
    deliveries = original_deliveries(nodes)
    result = []
    for native in definitions:
        if (
            families.get(native["definition_id"]) != "trade_hunt_contract_candidate"
            or native["calendar_period_seconds"] != "86400"
        ):
            continue
        identity = int(native["definition_id"])
        objective = json.loads(native["objectives"])
        if (
            len(objective) != 1
            or objective[0].get("native_class") != "aJN"
            or objective[0].get("ckf")
            or objective[0].get("ckd")
            or objective[0].get("ckc")
            or objective[0].get("cke")
        ):
            raise ValueError(
                "Daily source objective shape changed; requalify numeric target authority"
            )
        rewards = json.loads(native["rewards"])
        for reward in rewards:
            parameters = reward["parameters"]
            kind = reward["type_id"]
            if (
                type(kind) is not int
                or kind not in (5, 6)
                or type(parameters) is not list
                or len(parameters) != (2 if kind == 5 else 1)
                or any(type(v) is not int or v <= 0 for v in parameters)
                or type(reward["raw_flag_ckk"]) is not bool
            ):
                raise ValueError("Original daily reward requires another typed family")
        blocked = native["activation_criteria"].strip() == "False"
        delivery = deliveries.get(identity)
        result.append(
            dict(
                definition_id=identity,
                title=native["title_en"],
                category_id=int(native["category_id"]),
                objective_id=objective[0]["d"],
                objective_native_class=objective[0]["native_class"],
                activation_criterion=native["activation_criteria"],
                eligibility_criterion=native["eligibility_criteria"],
                literal_false_predicate=blocked,
                native_boss_reference=None,
                automatic_acceptance=False,
                gameplay_activation_proven=False,
                calendar_anchor_ms=int(native["calendar_anchor_ms"]),
                period_seconds=86400,
                native_rewards=rewards,
                original_delivery=delivery,
                status="DEFERRED_LITERAL_FALSE_PREDICATE"
                if blocked
                else "ORIGINAL_TARGET_AND_SELECTION_UNRECOVERED",
                importance="UNIMPORTANT_DEFERRED_BY_SCOPE"
                if blocked
                else "ACTIVE_WORK_SOURCE_AUTHORITY_PENDING",
                obsolete_proven=False,
            )
        )
    if len({r["definition_id"] for r in result}) != len(result):
        raise ValueError("Duplicate original daily hunter definition")
    return dict(
        scope="Daily source grading only; no acceptance, targets or rewards are installed",
        total=len(result),
        statuses=dict(Counter(r["status"] for r in result)),
        recovered_item_delivery_sources=sum(
            r["original_delivery"] is not None for r in result
        ),
        rows=result,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    base = ROOT / "agents_docs/reports/parallel-readiness-20261021"
    with (base / "recurring-native-definitions.csv").open() as stream:
        definitions = list(csv.DictReader(stream))
    with (base / "recurring-source-family-classification.csv").open() as stream:
        classifications = list(csv.DictReader(stream))
    with gzip.open(ROOT / "server/protocol/npc-dialogues.json.gz", "rt") as stream:
        nodes = json.load(stream)["nodes"]
    result = compile_inventory(definitions, classifications, nodes)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}))


if __name__ == "__main__":
    main()
