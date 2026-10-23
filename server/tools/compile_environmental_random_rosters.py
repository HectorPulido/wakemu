#!/usr/bin/env python3
"""Normalize exact native environmental species and declared random sizing."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICY = "wakemu.environmental-exact-species-genesis-v1"
CONTRACT = "wakemu.exact-species-random-roster.v1"


def literal(value):
    if type(value) is bool:
        return str(value).lower()
    if type(value) is int:
        return str(value)
    return "'" + value.replace("'", "''") + "'"


def compile_source(document, sizing):
    settings = {r["name"]: r["value"] for r in sizing}
    genesis = settings["monster_genesis"]
    reproduction = settings["monster_reproduction"]
    if (
        set(genesis) != {"groups_per_region", "min_members", "max_members"}
        or any(type(genesis[k]) is not int for k in genesis)
        or not 2 <= genesis["min_members"] <= genesis["max_members"] <= 8
        or type(reproduction["max_members"]) is not int
        or not 1 <= reproduction["max_members"] <= 8
    ):
        raise ValueError("Invalid existing native ecology sizing snapshot")
    minimum = genesis["min_members"]
    maximum = min(genesis["max_members"], reproduction["max_members"])
    if maximum < minimum:
        raise ValueError("Existing ecology sizing capacities conflict")
    qualified = []
    pending = []
    species = {}
    locations = set()
    for row in document["rows"]:
        refs = row["original_species_references"]
        if not refs:
            pending.append(
                dict(scenario_id=row["scenario_id"], reason="original_species_missing")
            )
            continue
        if (
            row["native_type"] not in (6, 7, 8)
            or row["missing_native_species"]
            or len(set(refs)) != len(refs)
        ):
            raise ValueError("Invalid exact native environmental pool")
        fields = (
            "native_user_group_quantity_to_spawn",
            "native_nb_group_for_reward",
            "native_nb_mob_for_reward",
            "native_duration_seconds",
            "challenge_level_min",
            "challenge_level_max",
            "template_reference_metadata_only",
        )
        if (
            any(type(row[k]) is not int for k in fields)
            or row["native_user_group_quantity_to_spawn"] <= 0
            or row["native_duration_seconds"] <= 0
        ):
            raise ValueError(
                "Missing native population/threshold/eligibility authority"
            )
        group_threshold = row["native_nb_group_for_reward"]
        mob_threshold = row["native_nb_mob_for_reward"]
        if not (
            (row["native_type"] == 7 and group_threshold > 0 and mob_threshold == 0)
            or (
                row["native_type"] in (6, 8)
                and mob_threshold > 0
                and group_threshold == 0
            )
        ):
            raise ValueError("Native objective count semantics conflict")
        records = {r["reference"]: r for r in row["native_species_records"]}
        if set(records) != set(refs):
            raise ValueError("Original pool record set differs")
        for reference, record in records.items():
            if (
                record["record_key"] != str(reference)
                or not 0 < record["min_level"] <= record["max_level"] <= 32767
            ):
                raise ValueError("Invalid native species level range")
            values = (record["min_level"], record["max_level"])
            if reference in species and species[reference] != values:
                raise ValueError("Conflicting native species record")
            species[reference] = values
        qualified.append(row)
        for location in row["original_locations"]:
            if location["native_cells_present"] != "True":
                continue
            locations.add(
                (
                    row["source_key"],
                    row["scenario_id"],
                    int(location["map_id"]),
                    int(location["region_id"]),
                )
            )
    return dict(
        policies=qualified,
        species=species,
        locations=sorted(locations),
        pending=pending,
        sizing=dict(
            min_members=minimum,
            max_members=maximum,
            max_zone_members=reproduction["max_zone_members"],
            max_zone_groups=reproduction["max_zone_groups"],
        ),
        counts=dict(
            source_scenarios=len(document["rows"]),
            policies=len(qualified),
            species=len(species),
            located_scenarios=len({r[1] for r in locations}),
            location_bindings=len(locations),
            pending_no_species=len(pending),
        ),
    )


def sql_seed(result, document, schema, source_sha, sizing_sha):
    out = [schema]
    put = lambda table, values: out.append(
        "INSERT INTO "
        + table
        + " VALUES("
        + ",".join(literal(v) for v in values)
        + ");"
    )
    sizing = result["sizing"]
    put(
        "environmental_random_roster_versions",
        (
            POLICY,
            CONTRACT,
            sizing["min_members"],
            sizing["max_members"],
            sizing["max_zone_members"],
            sizing["max_zone_groups"],
            "Wakemu policy: reuse existing ordinary ecology genesis sizing/caps; exact original species only; independent random proportions; native species minimum levels unchanged",
            sizing_sha,
        ),
    )
    put("environmental_random_roster_active", (True, POLICY, False))
    for reference, (minimum, maximum) in sorted(result["species"].items()):
        put(
            "environmental_random_native_species",
            (
                reference,
                minimum,
                maximum,
                document["catalog_revision"],
                document["native_monsters_document"]["sha256"],
            ),
        )
    for row in sorted(result["policies"], key=lambda r: r["scenario_id"]):
        put(
            "environmental_random_roster_policies",
            (
                row["source_key"],
                row["scenario_id"],
                POLICY,
                row["native_type"],
                row["native_mode"],
                row["template_reference_metadata_only"],
                row["native_user_group_quantity_to_spawn"],
                row["native_nb_group_for_reward"],
                row["native_nb_mob_for_reward"],
                row["challenge_level_min"],
                row["challenge_level_max"],
                row["native_duration_seconds"] * 1000,
                source_sha,
            ),
        )
        for reference in sorted(row["original_species_references"]):
            put(
                "environmental_random_roster_species",
                (row["source_key"], row["scenario_id"], POLICY, reference),
            )
    for source, scenario, map_id, region_id in result["locations"]:
        put(
            "environmental_random_roster_bindings",
            (source, scenario, POLICY, map_id, region_id),
        )
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sql", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    args = parser.parse_args()
    source = (
        ROOT
        / "agents_docs/reports/parallel-readiness-20261021/environmental810-original-species-authority.json"
    )
    sizing = (
        ROOT
        / ".runtime/parallel-readiness-20261021/environmental-current-group-size-policy.json"
    )
    document = json.loads(source.read_text())
    result = compile_source(document, json.loads(sizing.read_text()))
    if (
        result["counts"]["policies"],
        result["counts"]["species"],
        result["counts"]["located_scenarios"],
        result["counts"]["pending_no_species"],
    ) != (518, 407, 501, 292):
        raise ValueError("Exact environmental cohort changed")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    sizing_sha = hashlib.sha256(sizing.read_bytes()).hexdigest()
    args.sql.write_text(
        sql_seed(result, document, args.schema.read_text(), source_sha, sizing_sha)
    )
    args.report.write_text(
        json.dumps(
            dict(
                counts=result["counts"],
                sizing=result["sizing"],
                policy_version=POLICY,
                source_sha256=source_sha,
                sizing_sha256=sizing_sha,
                runtime_enabled=False,
            ),
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
