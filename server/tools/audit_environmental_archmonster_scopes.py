#!/usr/bin/env python3
"""Audit original nonstandard archmonster scopes without creating quest profiles."""
import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re

from build_environmental_resource_actions import ROOT, SOURCE_KEY, INVENTORY_SHA

PROOF = (
    ROOT
    / ".runtime/parallel-readiness-20261021/environmental-nonstandard63-native-archmonster-proof-specs.json"
)
INVENTORY = (
    ROOT
    / "agents_docs/reports/recurring-missions/ENVIRONMENTAL-SCENARIOS-INVENTORY-20261011.json"
)
LOCATIONS = (
    ROOT
    / "agents_docs/reports/parallel-readiness-20261021/environmental-original-scenario-locations.csv"
)
OUT = (
    ROOT
    / "agents_docs/reports/parallel-readiness-20261021/environmental-archmonster63-scope-guard-inventory"
)
COUNT = re.compile(
    r"GetMonsterCountInZone\(([1-9][0-9]*)\)\s*<\s*4\s+and\s+GetNbMonstersInZone\(\1\)\s*<\s*4"
)


def audit(proof, inventory, locations):
    originals = {row["id"]: row for row in inventory["scenarios"]}
    by_id = {row["scenario_id"]: row for row in proof["rows"]}
    if len(originals) != 1208 or len(by_id) != 63 or len(proof["rows"]) != 63:
        raise ValueError("Original nonstandard source denominator differs")
    rows = []
    coverage = Counter()
    for location in locations:
        identity = int(location["scenario_id"])
        if identity not in by_id:
            continue
        source = by_id[identity]
        original = originals[identity]
        if (
            original["type"] != 4
            or source["native_type"] != 4
            or source["native_mode_name"] != "NONE"
            or source["configuration"] != original["configuration"]
            or source["original_scenario_rewards"]
            or original["rewards"]
        ):
            raise ValueError(
                "Nonstandard source is not the original reward-free notification"
            )
        config = {
            key.lower(): int(value) for key, value in original["configuration"].items()
        }
        if config["challengeduration"] != 10 or config["usergroupquantitytospawn"] != 1:
            raise ValueError("Original notification/group metadata changed")
        matches = [
            membership
            for membership in source["group_memberships"]
            if membership["group_id"] == int(location["group_id"])
            and membership["criteria"] == location["native_criteria"]
        ]
        if len(matches) != 1:
            raise ValueError("Original location/group predicate join differs")
        criterion = location["native_criteria"]
        species = source["explicit_count_predicate_breed"]
        native = source["native_monster"]
        match = COUNT.fullmatch(criterion)
        if match is not None:
            if (
                int(match[1]) != species
                or source["classification"] != "EXPLICIT_ARCHMONSTER_BREED_COUNT_GUARD"
            ):
                raise ValueError(
                    "Original count predicate does not name the attested species"
                )
            disposition = "positive_exact_breed_count_guard"
            limit = 4
        elif (
            re.search(r"\band\s+False\s*$", criterion)
            and source["classification"] == "ORIGINAL_FALSE_MEMBERSHIP_GUARD"
        ):
            disposition = "excluded_literal_false_membership"
            limit = None
        else:
            raise ValueError("Unqualified original nonstandard predicate")
        if (
            native["ref"] != species
            or not 0 < native["min_level"] <= native["max_level"]
        ):
            raise ValueError("Original archmonster scalar identity/levels differ")
        scoped = bool(
            location["map_id"]
            and location["region_id"]
            and location["native_cells_present"] == "True"
        )
        rows.append(
            dict(
                source_key=SOURCE_KEY,
                scenario_id=identity,
                native_type=4,
                native_mode="NONE",
                group_id=int(location["group_id"]),
                protector_id=int(location["protector_id"]),
                map_id=int(location["map_id"]) if location["map_id"] else None,
                region_id=int(location["region_id"]) if location["region_id"] else None,
                native_cells_present=location["native_cells_present"] == "True",
                source_membership_predicate=criterion,
                disposition=disposition,
                scope_source_available=scoped,
                monster_reference=species,
                native_min_level=native["min_level"],
                native_max_level=native["max_level"],
                original_template_reference_metadata=config["usergrouptemplateid"],
                original_group_quantity_metadata=1,
                original_notification_duration_metadata=10,
                original_client_requirement=source["text1"],
                count_upper_exclusive=limit,
                monster_ttl_authority=None,
                per_group_members_authority=None,
                scenario_reward_count=0,
                native_loot_rows=len(native["loot_definitions"]),
                runtime_enabled=False,
            )
        )
        coverage[identity] += 1
    if set(coverage) != set(by_id):
        raise ValueError("Some original nonstandard scenarios have no joined scope")
    positives = [
        row for row in rows if row["disposition"] == "positive_exact_breed_count_guard"
    ]
    return dict(
        source_scenarios=63,
        location_rows=len(rows),
        unique_native_scopes=len({(row["map_id"], row["region_id"]) for row in rows}),
        positive_count_guard_scenarios=len({row["scenario_id"] for row in positives}),
        positive_count_guard_locations=len(positives),
        positive_native_species=len({row["monster_reference"] for row in positives}),
        false_membership_scenarios=sorted(
            {
                row["scenario_id"]
                for row in rows
                if row["disposition"] == "excluded_literal_false_membership"
            }
        ),
        positive_scope_available=sum(
            row["scope_source_available"] for row in positives
        ),
        positive_scopes=len({(row["map_id"], row["region_id"]) for row in positives}),
        rows=rows,
        no_quest_profiles=True,
        no_duration_as_ttl=True,
        no_group_quantity_as_membercount=True,
        activation_qualified=False,
        source_inventory_sha256=INVENTORY_SHA,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-stem", type=Path, default=OUT)
    args = parser.parse_args()
    if hashlib.sha256(INVENTORY.read_bytes()).hexdigest() != INVENTORY_SHA:
        raise ValueError("Original inventory SHA differs")
    with LOCATIONS.open() as stream:
        result = audit(
            json.loads(PROOF.read_text()),
            json.loads(INVENTORY.read_text()),
            list(csv.DictReader(stream)),
        )
    args.output_stem.with_suffix(".json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    with args.output_stem.with_suffix(".csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(result["rows"][0]))
        writer.writeheader()
        writer.writerows(result["rows"])
    print(
        json.dumps(
            {key: value for key, value in result.items() if key != "rows"}, indent=2
        )
    )


if __name__ == "__main__":
    main()
