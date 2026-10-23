#!/usr/bin/env python3
"""Compile disabled destruction profiles from normalized original-body proofs.

Only positive source302 rows are consumed. Template IDs never become species,
and source301's already frozen eight scenarios are excluded from this delta.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re

from build_environmental_destroy_profiles import (
    ROOT,
    INVENTORY,
    INVENTORY_SHA,
    NATIVE_CELLS,
    REVISION,
    SOURCE_KEY,
)
from build_environmental_group_profiles import (
    fingerprint,
    native_bands,
    prior_resource_profiles,
    insert,
    scalar,
)
from environmental_destroy_profile_sql import emit_profiles

SOURCE = ROOT / ".runtime/staging/environmental-destroy-302/destroy_named_sources.json"
AUTHORITY = (
    ROOT
    / "agents_docs/reports/parallel-readiness-20261021/environmental810-original-species-authority.json"
)
SEED = ROOT / "server/seeds/environmental_named_destroy_profiles.sql"
MANIFEST = (
    ROOT
    / "agents_docs/reports/parallel-readiness-20261021/environmental-named-destroy-profile-manifest.json"
)
POLICY = "wakemu.original-body-namedtype-compatible-variant-v1"
PROFILE_AUTHORITY = "wakemu.original-body-namedtype-destroy-profiles.v1;declared-compatible-variant;native-action3;ui301"
POPULATION = (
    ROOT / ".runtime/staging/environmental-destroy-302/destroy_named_population.sql"
)
FROZEN_301 = frozenset((-1328, -1327, -1326, -1325, -1225, -1223, -1222, -1221))


def compile_pipeline(
    *,
    source_document,
    inventory,
    authority_document,
    native_cell_rows,
    prior_schedule_profiles=(),
    geometry_source_sha256=None,
    schedule_version=8,
):
    """Join positive normalized sources to exact original configuration and floor."""
    if source_document.get("policy_version") != POLICY:
        raise ValueError("Unknown declared named-type source policy")
    if hashlib.sha256(
        INVENTORY.read_bytes()
    ).hexdigest() != INVENTORY_SHA or inventory != json.loads(INVENTORY.read_text()):
        raise ValueError("Original scenario inventory differs")
    scenarios = {row["id"]: row for row in inventory["scenarios"]}
    audit = {row["scenario_id"]: row for row in authority_document["rows"]}
    if (
        len(scenarios) != 1208
        or len(audit) != 810
        or authority_document["catalog_revision"] != REVISION
    ):
        raise ValueError("Source corpus/catalog boundary differs")
    surfaces = defaultdict(dict)
    point_count = 0
    for row in native_cell_rows:
        values = tuple(row[key] for key in ("map_id", "region_id", "x", "y", "z"))
        if (
            any(type(value) is not int for value in values)
            or min(values[:2]) <= 0
            or not -32768 <= values[4] < 32768
        ):
            raise ValueError("Invalid original native floor point")
        m, r, x, y, z = values
        surfaces[(m, r)][(x, y)] = max(z, surfaces[(m, r)].get((x, y), z))
        point_count += 1
    by_scenario = defaultdict(list)
    for row in source_document["rows"]:
        identity = row["scenario_id"]
        if identity in FROZEN_301:
            raise ValueError("Source302 must not duplicate the frozen301 cohort")
        if (
            row["source_key"] != SOURCE_KEY
            or row["policy_version"] != POLICY
            or row["catalog_revision"] != REVISION
            or row["public_proof"].get("kind")
            != "ORIGINAL_BODY_NAMEDTYPE_COMPATIBLE_VARIANT"
            or not re.fullmatch("[0-9a-f]{64}", row["source_sha256"])
            or fingerprint(row["action_descriptor"]) != row["descriptor_sha256"]
        ):
            raise ValueError("Named-type source authority differs")
        by_scenario[identity].append(row)
    ready = []
    pending = []
    for identity, source in sorted(audit.items()):
        if source["native_type"] != 5:
            continue
        if identity in FROZEN_301:
            continue
        rows = by_scenario.get(identity)
        if not rows:
            pending.append(
                dict(
                    scenario_id=identity,
                    reason="no_positive_normalized_namedtype_source",
                )
            )
            continue
        if len(rows) != 1:
            raise ValueError(
                "Named-type compiler requires one declared selected prototype per scenario"
            )
        row = rows[0]
        scenario = scenarios[identity]
        descriptor = row["action_descriptor"]
        if (
            scenario["type"] != 5
            or row["template_reference"] != source["template_reference_metadata_only"]
            or scenario["configuration"] != source["original_configuration"]
            or descriptor.get("native_class") != "aMg"
            or descriptor.get("d") != row["action_id"]
            or descriptor.get("aGJ") != 3
            or type(row["monster_reference"]) is not int
            or row["monster_reference"] <= 0
        ):
            raise ValueError("Selected native action/template/configuration differs")
        unsupported = None
        if descriptor.get("clT") != "":
            unsupported = "unsupported_native_action_criterion"
        elif (
            descriptor.get("getDuration") != 0
            or descriptor.get("cbH") != 0
            or descriptor.get("csI") is not False
            or descriptor.get("csJ") is not True
            or descriptor.get("csK") is not False
        ):
            unsupported = "unsupported_native_action_context"
        if unsupported:
            pending.append(dict(scenario_id=identity, reason=unsupported))
            continue
        if (
            source["native_nb_group_for_reward"] != 0
            or source["native_nb_mob_for_reward"] <= 0
            or source["native_user_group_quantity_to_spawn"] <= 0
            or scenario["duration_raw"] != source["native_duration_seconds"]
        ):
            raise ValueError("Original destruction objective/count/timer differs")
        rewards = scenario["rewards"]
        if scenario["subtype"] == 3:
            try:
                bands = native_bands(scenario)
            except ValueError:
                pending.append(
                    dict(
                        scenario_id=identity,
                        reason="unsupported_original_ranked_rewards",
                    )
                )
                continue
        elif len(rewards) == 1 and rewards[0]["flag"] and rewards[0]["text"] == "":
            bands = None
        else:
            pending.append(
                dict(
                    scenario_id=identity,
                    reason="unsupported_original_reward_predicates",
                )
            )
            continue
        if any(
            type(reward[key]) is not int or not 0 <= reward[key] < 2**31
            for reward in rewards
            for key in ("field_agO", "field_aAi", "field_aHj", "field_aHk")
        ) or any(reward["field_aHk"] for reward in rewards):
            pending.append(
                dict(scenario_id=identity, reason="unsupported_original_reward_scalars")
            )
            continue
        scopes = defaultdict(list)
        unresolved = {
            tuple(
                location.get(key, "") for key in ("map_id", "region_id", "protector_id")
            )
            for location in source["original_locations"]
            if not location["map_id"] or not location["region_id"]
        }
        for map_id, region_id, protector_id in sorted(unresolved):
            pending.append(
                dict(
                    scenario_id=identity,
                    map_id=map_id,
                    region_id=region_id,
                    protector_id=protector_id,
                    reason="unresolved_original_location_scope",
                )
            )
        for location in source["original_locations"]:
            if location["map_id"] and location["region_id"]:
                scopes[(int(location["map_id"]), int(location["region_id"]))].append(
                    location
                )
        if not scopes:
            pending.append(
                dict(scenario_id=identity, reason="original_location_missing")
            )
            continue
        for (m, r), locations in sorted(scopes.items()):
            reason = None
            if any(location["native_criteria"] for location in locations):
                reason = "original_location_criterion_pending"
            elif any(
                location["native_cells_present"] != "True" for location in locations
            ):
                reason = "original_native_floor_missing"
            elif len({int(location["protector_id"]) for location in locations}) != 1:
                reason = "original_protector_ambiguous"
            elif (
                len(surfaces[(m, r)])
                < source["native_user_group_quantity_to_spawn"] * 5
            ):
                reason = "insufficient_original_floor_for_maximum_births"
            if reason:
                pending.append(
                    dict(scenario_id=identity, map_id=m, region_id=r, reason=reason)
                )
                continue
            ready.append(
                dict(
                    source=source,
                    scenario=scenario,
                    map_id=m,
                    region_id=r,
                    protector_id=int(locations[0]["protector_id"]),
                    bands=bands,
                    criterion="",
                    species=dict(
                        reference=row["monster_reference"],
                        world_action_id=row["action_id"],
                    ),
                )
            )
    sql, manifest = emit_profiles(
        ready=ready,
        pending=pending,
        prior_schedule_profiles=prior_schedule_profiles,
        source_scenarios=len(by_scenario),
        source_sha256=fingerprint(source_document),
        source_policy_version=POLICY,
        profile_authority=PROFILE_AUTHORITY,
        schedule_version=schedule_version,
        geometry_source_sha256=geometry_source_sha256,
        point_count=point_count,
        surfaces=surfaces,
    )
    manifest["preserved301_scenarios"] = sorted(FROZEN_301)
    manifest["source_policy_version"] = POLICY
    manifest["source_normalization_counts"] = source_document.get("counts")
    manifest["new_regions"] = len(
        {(row["map_id"], row["region_id"]) for row in manifest["profiles"]}
    )
    return sql, manifest


def population_sql(source_document, authority_document):
    """Source302-owned population delta with equality-checked immutable species."""
    if (
        source_document["policy_version"] != POLICY
        or source_document["catalog_revision"] != REVISION
    ):
        raise ValueError("Named source catalog/policy differs")
    audit = {row["scenario_id"]: row for row in authority_document["rows"]}
    documents = source_document["catalog_documents"]
    if isinstance(documents, list):
        documents = {row["path"]: row["sha256"] for row in documents}
    monsters_sha = documents["monsters.json"]
    lines = [
        "-- Exact normalized source302 population; unchanged genesis v1 sizing and pointer."
    ]
    species = {}
    for row in source_document["rows"]:
        actor = row["public_proof"]["selected_species"]
        ref = row["monster_reference"]
        if (
            actor["ref"] != ref
            or not 0 < actor["min_level"] <= actor["max_level"] <= 32767
        ):
            raise ValueError("Selected named actor bounds differ")
        values = (ref, actor["min_level"], actor["max_level"], REVISION, monsters_sha)
        if ref in species and species[ref] != values:
            raise ValueError("Selected actor has conflicting native bounds")
        species[ref] = values
    for reference, values in sorted(species.items()):
        columns = (
            "monster_reference",
            "native_min_level",
            "native_max_level",
            "catalog_revision",
            "monsters_sha256",
        )
        differences = " OR ".join(
            column + " IS DISTINCT FROM " + scalar(value)
            for column, value in zip(columns[1:], values[1:])
        )
        lines.append(
            "DO $$ BEGIN IF EXISTS(SELECT 1 FROM environmental_random_native_species WHERE monster_reference="
            + str(reference)
            + " AND ("
            + differences
            + ")) THEN RAISE EXCEPTION 'Named destruction species conflicts with frozen native record'; END IF; END $$;"
        )
        statement = []
        insert(statement, "environmental_random_native_species", columns, [values])
        lines.extend(
            line[:-1] + " ON CONFLICT(monster_reference) DO NOTHING;"
            for line in statement
        )
    for row in source_document["rows"]:
        identity = row["scenario_id"]
        source = audit[identity]
        guard = (
            f"SELECT 1 FROM environmental_destroy_sources WHERE source_key={scalar(SOURCE_KEY)} AND scenario_id={identity}"
            f' AND policy_version={scalar(POLICY)} AND monster_reference={row["monster_reference"]} AND action_id={row["action_id"]}'
            f' AND descriptor_sha256={scalar(row["descriptor_sha256"])} AND source_sha256={scalar(row["source_sha256"])}'
        )
        lines.append(
            "DO $$ BEGIN IF NOT EXISTS("
            + guard
            + ") THEN RAISE EXCEPTION 'Named population lacks exact normalized body/action source'; END IF; END $$;"
        )
        insert(
            lines,
            "environmental_random_roster_policies",
            (
                "source_key",
                "scenario_id",
                "policy_version",
                "native_type",
                "native_mode",
                "group_reference",
                "group_count",
                "nb_group_for_reward",
                "nb_mob_for_reward",
                "challenge_level_min",
                "challenge_level_max",
                "duration_ms",
                "source_sha256",
            ),
            [
                (
                    SOURCE_KEY,
                    identity,
                    "wakemu.environmental-exact-species-genesis-v1",
                    5,
                    source["native_mode"],
                    row["template_reference"],
                    source["native_user_group_quantity_to_spawn"],
                    source["native_nb_group_for_reward"],
                    source["native_nb_mob_for_reward"],
                    source["challenge_level_min"],
                    source["challenge_level_max"],
                    source["native_duration_seconds"] * 1000,
                    row["source_sha256"],
                )
            ],
        )
        insert(
            lines,
            "environmental_random_roster_species",
            ("source_key", "scenario_id", "policy_version", "monster_reference"),
            [
                (
                    SOURCE_KEY,
                    identity,
                    "wakemu.environmental-exact-species-genesis-v1",
                    row["monster_reference"],
                )
            ],
        )
        scopes = sorted(
            {
                (int(location["map_id"]), int(location["region_id"]))
                for location in source["original_locations"]
                if location["map_id"] and location["region_id"]
            }
        )
        insert(
            lines,
            "environmental_random_roster_bindings",
            ("source_key", "scenario_id", "policy_version", "map_id", "region_id"),
            [
                (
                    SOURCE_KEY,
                    identity,
                    "wakemu.environmental-exact-species-genesis-v1",
                    m,
                    r,
                )
                for m, r in scopes
            ],
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, default=SOURCE)
    parser.add_argument("--native-cell-csv", type=Path, default=NATIVE_CELLS)
    parser.add_argument("--seed", type=Path, default=SEED)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--population-fragment", type=Path, default=POPULATION)
    args = parser.parse_args()
    report = ROOT / "agents_docs/reports/parallel-readiness-20261021"
    prior = []
    for filename in (
        "environmental-group-profile-manifest.json",
        "environmental-group-criteria-profile-manifest.json",
        "environmental-destroy-profile-manifest.json",
    ):
        prior.extend(
            dict(
                profile_key=row["profile_key"],
                map_id=row["map_id"],
                region_id=row["region_id"],
            )
            for row in json.loads((report / filename).read_text())["profiles"]
        )
    prior.extend(
        prior_resource_profiles(
            [
                ROOT / "server/seeds" / name
                for name in (
                    "environmental_resource_profiles.sql",
                    "environmental_resource_races.sql",
                    "environmental_resource_competitions.sql",
                    "environmental_resource_level_criteria.sql",
                )
            ]
        )
    )
    with args.native_cell_csv.open() as stream:
        cells = (
            {key: int(row[key]) for key in ("map_id", "region_id", "x", "y", "z")}
            for row in csv.DictReader(stream)
        )
        sql, manifest = compile_pipeline(
            source_document=json.loads(args.source_manifest.read_text()),
            inventory=json.loads(INVENTORY.read_text()),
            authority_document=json.loads(AUTHORITY.read_text()),
            native_cell_rows=cells,
            prior_schedule_profiles=prior,
            geometry_source_sha256=hashlib.sha256(
                args.native_cell_csv.read_bytes()
            ).hexdigest(),
        )
    population = population_sql(
        json.loads(args.source_manifest.read_text()), json.loads(AUTHORITY.read_text())
    )
    args.population_fragment.parent.mkdir(parents=True, exist_ok=True)
    args.population_fragment.write_text(population)
    manifest["population_fragment_sha256"] = hashlib.sha256(
        population.encode()
    ).hexdigest()
    args.seed.parent.mkdir(parents=True, exist_ok=True)
    args.seed.write_text(sql)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: value
                for key, value in manifest.items()
                if key not in ("profiles", "pending")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
