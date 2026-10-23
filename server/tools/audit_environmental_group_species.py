#!/usr/bin/env python3
"""Partition810 environmental monster scenarios by exact original species authority.

No zone, family, template identity or nearby population substitutes for an
original breed parameter. Outputs are evidence, never enabled gameplay policy.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_KEY = "installed-environmental-source-v1"
BREED_KEYS = ("specialbreedid", *(f"breedid{index}" for index in range(1, 7)))


def integer(value):
    if type(value) is not str or not value.lstrip("-").isdigit():
        raise ValueError("Malformed original integer parameter")
    return int(value)


def audit(scenarios, locations, native_records):
    """Pure disjoint audit; preserve raw count and level roles without reinterpretation."""
    native = {row["reference"]: row for row in native_records}
    if len(native) != len(native_records):
        raise ValueError("Duplicate native species record")
    by_scenario = defaultdict(list)
    for row in locations:
        by_scenario[int(row["scenario_id"])].append(row)
    rows = []
    for source in scenarios:
        config = {key.lower(): value for key, value in source["configuration"].items()}
        if len(config) != len(source["configuration"]):
            raise ValueError("Colliding original configuration key casing")
        destroy = "monsteractiontypeid" in config
        standard = (
            source["type"] in (6, 7, 8)
            and "usergrouptemplateid" in config
            and "nbportalgroupforbossspawn" not in config
        )
        if not (destroy or standard):
            continue
        species_parameters = {
            key: integer(config[key]) for key in BREED_KEYS if key in config
        }
        species = sorted({value for value in species_parameters.values() if value > 0})
        other_entities = {
            key: value
            for key, value in config.items()
            if "resource" in key or "creature" in key
        }
        if species:
            classification = "original_explicit_species_pool"
        elif other_entities:
            classification = "original_creature_or_resource_reference_only"
        elif species_parameters:
            classification = "original_species_parameters_nonpositive_only"
        else:
            classification = "missing_original_species_template_only"
        missing = sorted(set(species) - set(native))
        records = [native[ref] for ref in species if ref in native]
        lower, upper = integer(config["challengelevelmin"]), integer(
            config["challengelevelmax"]
        )
        level_gaps = [
            dict(
                reference=row["reference"],
                native_min=row["min_level"],
                native_max=row["max_level"],
            )
            for row in records
            if row["min_level"] is None
            or row["max_level"] is None
            or max(lower, row["min_level"]) > min(upper, row["max_level"])
        ]
        scoped = by_scenario[source["id"]]
        gaps = []
        if not species:
            gaps.append("original_species_pool_unrecovered")
        if missing:
            gaps.append("original_species_missing_current_catalog")
        if not scoped:
            gaps.append("no_original_protector_map_region_join")
        if level_gaps:
            gaps.append("native_species_level_and_challenge_band_not_interchangeable")
        # No scenario in this source corpus declares member-size bounds. Never
        # label the template spawn quantity as an original per-group size.
        gaps.append("original_per_group_member_count_not_recovered")
        if destroy:
            gaps.append("DESTROY_action3_is_not_ordinary_combat_kill")
        rows.append(
            dict(
                source_key=SOURCE_KEY,
                scenario_id=source["id"],
                family="destroy_monster_action"
                if destroy
                else "standard_group_template",
                native_type=source["type"],
                native_type_name=source["native_type_name"],
                native_subtype=source["subtype"],
                native_mode=source["native_subtype_name"],
                source_classification=classification,
                original_species_parameters=species_parameters,
                original_species_references=species,
                original_species_count=len(species),
                creature_resource_parameters=other_entities,
                template_reference_metadata_only=integer(config["usergrouptemplateid"]),
                family_compatibility_used=False,
                native_species_records=records,
                missing_native_species=missing,
                native_species_level_gaps=level_gaps,
                challenge_level_min=lower,
                challenge_level_max=upper,
                native_user_group_quantity_to_spawn=integer(
                    config["usergroupquantitytospawn"]
                ),
                native_nb_group_for_reward=integer(config["nbgroupforreward"]),
                native_nb_mob_for_reward=integer(config["nbmobforreward"]),
                native_duration_seconds=integer(config["challengeduration"]),
                native_monster_action_type=integer(config["monsteractiontypeid"])
                if destroy
                else None,
                original_member_count_min=None,
                original_member_count_max=None,
                assigned=bool(source["group_memberships"]),
                original_group_memberships=source["group_memberships"],
                map_ids=sorted({int(row["map_id"]) for row in scoped if row["map_id"]}),
                region_ids=sorted(
                    {int(row["region_id"]) for row in scoped if row["region_id"]}
                ),
                original_locations=scoped,
                gaps=gaps,
                original_configuration=source["configuration"],
                runtime_activation_authorized_by_audit=False,
            )
        )
    if len(rows) != 810 or len({row["scenario_id"] for row in rows}) != len(rows):
        raise ValueError("Expected810 distinct original standard monster scenarios")
    positive = [row for row in rows if row["original_species_references"]]
    return dict(
        scope="Exact original species authority; not roster or gameplay activation",
        rows=sorted(rows, key=lambda row: row["scenario_id"]),
        counts=dict(
            total=810,
            disjoint_classification=dict(
                Counter(row["source_classification"] for row in rows)
            ),
            native_types=dict(Counter(row["native_type_name"] for row in rows)),
            positive_species_scenarios=len(positive),
            distinct_original_species=len(
                {ref for row in positive for ref in row["original_species_references"]}
            ),
            positive_species_with_original_locations=sum(
                bool(row["original_locations"]) for row in positive
            ),
            positive_species_without_original_locations=sum(
                not row["original_locations"] for row in positive
            ),
            positive_pool_sizes=dict(
                Counter(row["original_species_count"] for row in positive)
            ),
            positive_pools_with_native_level_gaps=sum(
                bool(row["native_species_level_gaps"]) for row in positive
            ),
            positive_pools_with_no_native_level_overlap=sum(
                len(row["native_species_level_gaps"]) == row["original_species_count"]
                for row in positive
            ),
            missing_native_species_references=len(
                {ref for row in rows for ref in row["missing_native_species"]}
            ),
            family_compatibility_qualified_as_original_species=0,
            native_original_member_size_bounds=0,
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory",
        type=Path,
        default=ROOT
        / "agents_docs/reports/recurring-missions/ENVIRONMENTAL-SCENARIOS-INVENTORY-20261011.json",
    )
    parser.add_argument(
        "--locations",
        type=Path,
        default=ROOT
        / "agents_docs/reports/parallel-readiness-20261021/environmental-original-scenario-locations.csv",
    )
    parser.add_argument(
        "--native-records",
        type=Path,
        default=ROOT
        / ".runtime/parallel-readiness-20261021/environmental810-original-species-native-records.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "agents_docs/reports/parallel-readiness-20261021/environmental810-original-species-authority.json",
    )
    args = parser.parse_args()
    with args.locations.open() as stream:
        locations = list(csv.DictReader(stream))
    native = json.loads(args.native_records.read_text())
    result = audit(
        json.loads(args.inventory.read_text())["scenarios"],
        locations,
        native["records"],
    )
    result["catalog_revision"] = native["revision"]
    result["native_monsters_document"] = native["document"]
    result["source_sha256"] = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (args.inventory, args.locations, args.native_records)
    }
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    with args.output.with_suffix(".csv").open("w", newline="") as stream:
        fields = list(result["rows"][0])
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for row in result["rows"]:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
                    if isinstance(value, (list, dict))
                    else value
                    for key, value in row.items()
                }
            )
    print(json.dumps(result["counts"], indent=2))


if __name__ == "__main__":
    main()
