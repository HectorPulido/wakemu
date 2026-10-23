#!/usr/bin/env python3
"""Compile disabled action3 profiles for explicitly evidenced destruction targets.

The known species derive from external quest evidence joined to native records;
no original user-group-template roster recovery is claimed. Requires source301.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

from build_environmental_group_profiles import (
    ROOT,
    SOURCE_KEY,
    REVISION,
    INVENTORY_SHA,
    INVENTORY,
    NATIVE_CELLS,
    GENERATED_REWARD_AUTHORITY,
    insert,
    scalar,
    fingerprint,
    native_bands,
    profile_variables,
)

POLICY = "wakemu.explicit-target-destroy-profiles.v1;native-action3;external-species;random2..5;ui301"
ROSTER_POLICY = "wakemu.environmental-exact-species-genesis-v1"
DESTROY_POLICY = "wakemu.explicit-public-target-native-destroy-v1"
RANKED = "wakemu.original-destroy-rank-bands-base-rewards.v1"
SIMPLE = "wakemu.original-destroy-single-primary-base-result.v1"
SPECS = (
    ROOT
    / ".runtime/parallel-readiness-20261021/environmental-destroy292-web-candidate-proof-specs.json"
)
CATALOG = (
    ROOT
    / ".runtime/parallel-readiness-20261021/destroy8-source/native-two-actor-records.json"
)
SEED = ROOT / "server/seeds/environmental_destroy_profiles.sql"
MANIFEST = (
    ROOT
    / "agents_docs/reports/parallel-readiness-20261021/environmental-destroy-profile-manifest.json"
)


def population_sql(specs, catalog):
    """Add only exact externally evidenced species to existing declared sizing."""
    lines = []
    documents = {row["path"]: row["sha256"] for row in catalog["documents"]}
    records = {
        int(row["record_key"]): row["payload"]
        for row in catalog["records"]
        if row["path"] == "monsters.json"
    }
    for template in specs["templates"]:
        if len(template["known_species"]) != 1:
            raise ValueError(
                "This qualified cohort has exactly one known target per template"
            )
        species = template["known_species"][0]
        reference = species["reference"]
        record = records[reference]
        if record["ref"] != reference or (record["min_level"], record["max_level"]) != (
            species["native_min_level"],
            species["native_max_level"],
        ):
            raise ValueError("Known target differs from the attested native record")
        insert(
            lines,
            "environmental_random_native_species",
            (
                "monster_reference",
                "native_min_level",
                "native_max_level",
                "catalog_revision",
                "monsters_sha256",
            ),
            [
                (
                    reference,
                    record["min_level"],
                    record["max_level"],
                    catalog["revision"],
                    documents["monsters.json"],
                )
            ],
        )
        for case in template["scenario_cases"]:
            identity = case["scenario_id"]
            guard = (
                f"SELECT 1 FROM environmental_destroy_sources WHERE source_key={scalar(SOURCE_KEY)} AND scenario_id={identity}"
                f' AND policy_version={scalar(DESTROY_POLICY)} AND template_reference={template["template_reference"]}'
                f' AND monster_reference={reference} AND action_id={species["world_action_id"]} AND catalog_revision={scalar(REVISION)}'
            )
            lines.append(
                "DO $$ BEGIN IF NOT EXISTS("
                + guard
                + ") THEN RAISE EXCEPTION 'Destruction target lacks qualified original action and external source'; END IF; END $$;"
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
                        ROSTER_POLICY,
                        5,
                        case["native_mode"],
                        template["template_reference"],
                        case["requested_group_quantity"],
                        case["group_target"],
                        case["mob_target"],
                        case["challenge_level_min"],
                        case["challenge_level_max"],
                        case["duration_seconds"] * 1000,
                        fingerprint(dict(template=template, case=case)),
                    )
                ],
            )
            insert(
                lines,
                "environmental_random_roster_species",
                ("source_key", "scenario_id", "policy_version", "monster_reference"),
                [(SOURCE_KEY, identity, ROSTER_POLICY, reference)],
            )
            scopes = sorted(
                {
                    (int(row["map_id"]), int(row["region_id"]))
                    for row in case["original_locations"]
                }
            )
            insert(
                lines,
                "environmental_random_roster_bindings",
                ("source_key", "scenario_id", "policy_version", "map_id", "region_id"),
                [(SOURCE_KEY, identity, ROSTER_POLICY, m, r) for m, r in scopes],
            )
    return lines


def compile_pipeline(
    *,
    native_cell_rows,
    specs,
    inventory,
    catalog,
    prior_schedule_profiles=(),
    geometry_source_sha256=None,
    intermission_ms=0,
    schedule_version=7,
):
    if fingerprint(specs) != fingerprint(json.loads(SPECS.read_text())):
        raise ValueError(
            "Explicit target evidence differs from the frozen source corpus"
        )
    if (
        catalog["revision"] != REVISION
        or fingerprint(catalog) != fingerprint(json.loads(CATALOG.read_text()))
        or len(specs["templates"]) != 2
    ):
        raise ValueError("Unexpected target corpus/catalog")
    if (
        type(intermission_ms) is not int
        or intermission_ms < 0
        or type(schedule_version) is not int
        or schedule_version < 1
    ):
        raise ValueError("Invalid declared regional schedule")
    original = {row["id"]: row for row in inventory["scenarios"]}
    if (
        len(original) != 1208
        or inventory != json.loads(INVENTORY.read_text())
        or hashlib.sha256(INVENTORY.read_bytes()).hexdigest() != INVENTORY_SHA
    ):
        raise ValueError("Original scenario inventory differs")
    surfaces = defaultdict(set)
    point_count = 0
    for row in native_cell_rows:
        values = tuple(row[key] for key in ("map_id", "region_id", "x", "y", "z"))
        if any(type(value) is not int for value in values):
            raise ValueError("Invalid native floor point")
        surfaces[values[:2]].add(values[2:])
        point_count += 1
    ready = []
    pending = []
    seen = set()
    for template in specs["templates"]:
        if (
            template["original_template_membership_recovered"] is not False
            or template["per_group_member_count_source"] is not None
            or template["random_composition_authority"]
            != "USER_AUTHORIZED_EXACT_KNOWN_SPECIES_ONLY"
        ):
            raise ValueError("Target reconstruction boundary differs")
        (species,) = template["known_species"]
        for case in template["scenario_cases"]:
            identity = case["scenario_id"]
            scenario = original[identity]
            if (
                identity in seen
                or scenario["type"] != 5
                or scenario["configuration"] != case["configuration"]
                or scenario["duration_raw"] != case["duration_seconds"]
            ):
                raise ValueError("Original destruction scenario configuration differs")
            seen.add(identity)
            config = scenario["configuration"]
            expected = {
                "usergrouptemplateid": template["template_reference"],
                "usergroupquantitytospawn": case["requested_group_quantity"],
                "nbmobforreward": case["mob_target"],
                "nbgroupforreward": 0,
                "monsteractiontypeid": 3,
                "challengeduration": case["duration_seconds"],
                "challengelevelmin": case["challenge_level_min"],
                "challengelevelmax": case["challenge_level_max"],
            }
            if (
                any(config.get(key) != str(value) for key, value in expected.items())
                or scenario["native_subtype_name"] != case["native_mode"]
            ):
                raise ValueError("Original objective/action/player bands changed")
            source = dict(
                native_type=5,
                native_nb_group_for_reward=0,
                native_nb_mob_for_reward=case["mob_target"],
                native_duration_seconds=case["duration_seconds"],
                challenge_level_min=case["challenge_level_min"],
                challenge_level_max=case["challenge_level_max"],
                template_reference_metadata_only=template["template_reference"],
                native_user_group_quantity_to_spawn=case["requested_group_quantity"],
            )
            scopes = defaultdict(list)
            for row in case["original_locations"]:
                scopes[(int(row["map_id"]), int(row["region_id"]))].append(row)
            for (map_id, region_id), locations in sorted(scopes.items()):
                if (
                    any(
                        row["native_criteria"] or row["native_cells_present"] != "True"
                        for row in locations
                    )
                    or len({row["protector_id"] for row in locations}) != 1
                ):
                    raise ValueError(
                        "Destruction scope needs an exact supported territory"
                    )
                if (
                    len(surfaces[(map_id, region_id)])
                    < case["requested_group_quantity"] * 5
                ):
                    raise ValueError(
                        "Original native surface cannot support declared maximum births"
                    )
                bands = native_bands(scenario) if scenario["subtype"] == 3 else None
                if bands is None and not (
                    len(scenario["rewards"]) == 1
                    and scenario["rewards"][0]["flag"]
                    and scenario["rewards"][0]["text"] == ""
                ):
                    raise ValueError("Destruction reward authority is unqualified")
                for reward in scenario["rewards"]:
                    if (
                        any(
                            type(reward[k]) is not int or reward[k] < 0
                            for k in (
                                "field_agO",
                                "field_aAi",
                                "field_aHj",
                                "field_aHk",
                            )
                        )
                        or reward["field_aHk"]
                    ):
                        raise ValueError("Unsupported original reward scalar")
                ready.append(
                    dict(
                        source=source,
                        scenario=scenario,
                        map_id=map_id,
                        region_id=region_id,
                        protector_id=int(locations[0]["protector_id"]),
                        bands=bands,
                        criterion="",
                        species=species,
                    )
                )
    if len(seen) != 8:
        raise ValueError("Known destruction cohort must preserve all eight scenarios")

    lines = [
        "-- Disabled sealed destruction profiles from explicitly identified targets; no DB import or activation.",
        "-- Requires original275/278, runtime274/282/284/288/289/290, source/action/population/UI301.",
        "-- Per-group member sizing2..5 is declared Wakemu; no original template composition is claimed.",
        "BEGIN;",
    ]
    profiles = []
    schedules = defaultdict(list)
    counters = Counter()
    for item in ready:
        source = item["source"]
        scenario = item["scenario"]
        identity = scenario["id"]
        map_id, region_id = item["map_id"], item["region_id"]
        key = f"destroy-native-{abs(identity)}-{map_id}-{region_id}"
        family = "monster_destroy"
        objective = "mob"
        mode = {1: "solo", 2: "race", 3: "competitive", 4: "collaborative"}[
            scenario["subtype"]
        ]
        threshold = source["native_nb_mob_for_reward"]
        if (
            threshold <= 0
            or int(scenario["duration_raw"]) != source["native_duration_seconds"]
        ):
            raise ValueError("Original type/threshold/duration contract differs")
        # Only an event's persisted298 draw can supply COLLAB's complete global
        # target. The immutable1 is a marker, never a claim that one destruction ends it.
        required = 1 if mode == "collaborative" else threshold
        duration = source["native_duration_seconds"] * 1000
        digest = fingerprint(
            dict(source=source, scope=[map_id, region_id], authority=POLICY, mode=mode)
        )
        location_guard = (
            f"SELECT 1 FROM environmental_native_scenario_locations WHERE source_key={scalar(SOURCE_KEY)}"
            f" AND scenario_id={identity} AND map_id={map_id} AND region_id={region_id}"
            " AND native_cells_present AND native_criteria="
            + ("''" if not item["criterion"] else scalar(item["criterion"]))
        )
        population_guard = (
            f"SELECT 1 FROM environmental_random_roster_bindings WHERE source_key={scalar(SOURCE_KEY)}"
            f" AND scenario_id={identity} AND policy_version={scalar(ROSTER_POLICY)}"
            f" AND map_id={map_id} AND region_id={region_id}"
        )
        lines.append(
            "DO $$ BEGIN IF NOT EXISTS("
            + location_guard
            + ") OR NOT EXISTS("
            + population_guard
            + ") THEN RAISE EXCEPTION 'Destruction profile lacks exact original territory/random pool'; END IF; END $$;"
        )
        insert(
            lines,
            "environmental_runtime_profiles",
            (
                "profile_key",
                "version",
                "native_scenario_id",
                "family",
                "mode",
                "map_id",
                "region_id",
                "duration_ms",
                "recurrence_period_ms",
                "anchor_ms",
                "level_min",
                "level_max",
                "minimum_contribution",
                "authority",
                "source_sha256",
                "catalog_revision",
                "enabled",
                "sealed",
            ),
            [
                (
                    key,
                    1,
                    identity,
                    family,
                    mode,
                    map_id,
                    region_id,
                    duration,
                    None,
                    0,
                    max(1, source["challenge_level_min"]),
                    source["challenge_level_max"],
                    threshold,
                    POLICY,
                    digest,
                    REVISION,
                    False,
                    False,
                )
            ],
        )
        insert(
            lines,
            "environmental_profile_objectives",
            (
                "profile_key",
                "version",
                "objective_key",
                "family",
                "target_reference",
                "action_id",
                "resource_step",
                "unit",
                "required_quantity",
            ),
            [
                (
                    key,
                    1,
                    objective,
                    family,
                    item["species"]["reference"],
                    item["species"]["world_action_id"],
                    None,
                    "interaction",
                    required,
                )
            ],
        )
        insert(
            lines,
            "environmental_profile_destroy_ui",
            ("profile_key", "version", "source_key", "native_scenario_id", "authority"),
            [(key, 1, SOURCE_KEY, identity, POLICY)],
        )
        insert(
            lines,
            "environmental_profile_destroy_policy",
            (
                "profile_key",
                "version",
                "source_key",
                "scenario_id",
                "policy_version",
                "monster_reference",
                "action_id",
            ),
            [
                (
                    key,
                    1,
                    SOURCE_KEY,
                    identity,
                    DESTROY_POLICY,
                    item["species"]["reference"],
                    item["species"]["world_action_id"],
                )
            ],
        )
        insert(
            lines,
            "environmental_profile_publication",
            (
                "profile_key",
                "version",
                "challenge_id",
                "secondary_id",
                "protector_id",
                "native_time",
                "time_mode",
                "source_authority",
            ),
            [
                (
                    key,
                    1,
                    identity,
                    0,
                    item["protector_id"],
                    0,
                    "constant",
                    "wakemu-native-publication-v1;original-scenario-protector;declared-secondary-time-zero",
                )
            ],
        )
        insert(
            lines,
            "environmental_profile_publication_states",
            ("profile_key", "version", "lifecycle_state", "state_ordinal"),
            [
                (key, 1, state, ordinal)
                for state, ordinal in [
                    ("proposed", 0),
                    ("active", 1),
                    ("completed", 2),
                    ("expired", 2),
                    ("cancelled", 3),
                ]
            ],
        )
        insert(
            lines,
            "environmental_profile_native_variable_policy",
            (
                "profile_key",
                "version",
                "source_key",
                "native_scenario_id",
                "policy_contract",
                "source_authority",
            ),
            [
                (
                    key,
                    1,
                    SOURCE_KEY,
                    identity,
                    "wakemu.durable-native-variable-projection.v1",
                    POLICY,
                )
            ],
        )
        variables = profile_variables(key, scenario, objective)
        insert(
            lines,
            "environmental_profile_native_variable_bindings",
            (
                "profile_key",
                "version",
                "source_key",
                "native_scenario_id",
                "variable_index",
                "native_name",
                "binding_kind",
                "objective_key",
                "configuration_key",
                "constant_value",
                "source_authority",
                "entity_kind",
            ),
            variables,
        )
        if mode in ("race", "competitive"):
            winners = (
                source["native_user_group_quantity_to_spawn"]
                if mode == "race"
                else max(
                    r["rank_max"] for r in item["bands"] if r["rank_max"] is not None
                )
            )
            insert(
                lines,
                "environmental_profile_evaluation",
                (
                    "profile_key",
                    "version",
                    "evaluator",
                    "winner_count",
                    "tie_policy",
                    "source_authority",
                ),
                [
                    (
                        key,
                        1,
                        "first_completion" if mode == "race" else "score_at_deadline",
                        winners,
                        "commit_order" if mode == "race" else "character_id",
                        "wakemu.character-race-original-destroy-group-capacity.v1;one-character-one-place;not-original-winner-limit"
                        if mode == "race"
                        else "wakemu.original-destroy-rank-conditions.v1;all-eligible-fallback;character-id-ties",
                    )
                ],
            )
        if mode in ("race", "competitive"):
            bands = item["bands"] if mode == "competitive" else native_bands(scenario)
            insert(
                lines,
                "environmental_profile_ranked_reward_policy",
                (
                    "profile_key",
                    "version",
                    "source_key",
                    "native_scenario_id",
                    "policy_contract",
                    "eligibility_contract",
                    "source_authority",
                    "grant_authority",
                    "result_parameter_mode",
                    "result_parameter",
                    "parameter_authority",
                ),
                [
                    (
                        key,
                        1,
                        SOURCE_KEY,
                        identity,
                        RANKED,
                        "all_eligible" if mode == "competitive" else "ranked_winners",
                        "original-primary-list-and-exact-rank-predicates",
                        GENERATED_REWARD_AUTHORITY,
                        "winner_score",
                        None,
                        "wakemu.result-parameter-winning-position-one-score.v1",
                    )
                ],
            )
            insert(
                lines,
                "environmental_profile_ranked_reward_bands",
                (
                    "profile_key",
                    "version",
                    "source_key",
                    "native_scenario_id",
                    "primary_reward_index",
                    "reward_id",
                    "rank_min",
                    "rank_max",
                ),
                [
                    (
                        key,
                        1,
                        SOURCE_KEY,
                        identity,
                        band["primary_reward_index"],
                        band["reward_id"],
                        band["rank_min"],
                        band["rank_max"],
                    )
                    for band in bands
                ],
            )
        if mode != "competitive":
            reward = scenario["rewards"][0]
            rewards = []
            for kind, reference, amount in [
                ("xp", None, reward["field_agO"]),
                ("item", reward["field_aAi"], reward["field_aHj"]),
            ]:
                if amount:
                    if kind == "item" and reference <= 0:
                        raise ValueError(
                            "Positive original item quantity has no item reference"
                        )
                    rewards.append(
                        (
                            key,
                            1,
                            len(rewards),
                            kind,
                            reference,
                            amount,
                            GENERATED_REWARD_AUTHORITY,
                        )
                    )
            insert(
                lines,
                "environmental_profile_rewards",
                (
                    "profile_key",
                    "version",
                    "ordinal",
                    "kind",
                    "reference",
                    "quantity",
                    "source_authority",
                ),
                rewards,
            )
        if mode in ("solo", "collaborative"):
            insert(
                lines,
                "environmental_profile_simple_result_policy",
                (
                    "profile_key",
                    "version",
                    "source_key",
                    "native_scenario_id",
                    "reward_id",
                    "policy_contract",
                    "primary_reward_index",
                    "parameter_mode",
                    "source_authority",
                    "mapping_authority",
                    "parameter_authority",
                ),
                [
                    (
                        key,
                        1,
                        SOURCE_KEY,
                        identity,
                        scenario["rewards"][0]["id"],
                        SIMPLE,
                        0,
                        "personal_progress" if mode == "solo" else "global_progress",
                        "original-single-unconditional-primary-base-reward",
                        "original-primary-list-index-zero",
                        "wakemu.result-parameter-personal-or-global-progress.v1",
                    )
                ],
            )
        schedules[(map_id, region_id)].append(key)
        profiles.append(
            dict(
                profile_key=key,
                scenario_id=identity,
                family=family,
                mode=mode,
                map_id=map_id,
                region_id=region_id,
                protector_id=item["protector_id"],
                native_variable_count=len(variables),
                original_group_count=source["native_user_group_quantity_to_spawn"],
                minimum_contribution=threshold,
                static_objective_quantity=required,
                global_goal="persisted298monster_births"
                if mode == "collaborative"
                else "original_personal_threshold",
                native_region_floor_points=len(surfaces[(map_id, region_id)]),
            )
        )
        counters[mode] += 1
    for row in prior_schedule_profiles:
        schedules[(row["map_id"], row["region_id"])].append(row["profile_key"])
    for (map_id, region_id), candidates in sorted(schedules.items()):
        candidates = sorted(set(candidates))
        key = f"wakemu-native-resources-{map_id}-{region_id}"
        insert(
            lines,
            "environmental_regional_schedule_policies",
            (
                "policy_key",
                "version",
                "map_id",
                "region_id",
                "selection_policy",
                "cadence_policy",
                "intermission_ms",
                "authority",
                "source_sha256",
                "sealed",
                "enabled",
            ),
            [
                (
                    key,
                    schedule_version,
                    map_id,
                    region_id,
                    "wakemu_round_robin",
                    "occupied_sequential_windows",
                    intermission_ms,
                    POLICY,
                    fingerprint(
                        dict(
                            scope=[map_id, region_id],
                            profiles=candidates,
                            intermission_ms=intermission_ms,
                        )
                    ),
                    False,
                    False,
                )
            ],
        )
        insert(
            lines,
            "environmental_regional_schedule_candidates",
            ("policy_key", "version", "ordinal", "profile_key", "profile_version"),
            [
                (key, schedule_version, index, candidate, 1)
                for index, candidate in enumerate(candidates)
            ],
        )
        lines.append(
            f"UPDATE environmental_regional_schedule_policies SET sealed=TRUE WHERE policy_key={scalar(key)} AND version={schedule_version};"
        )
    for row in profiles:
        lines.append(
            f"UPDATE environmental_runtime_profiles SET sealed=TRUE WHERE profile_key={scalar(row['profile_key'])} AND version=1;"
        )
    lines.extend(["SET CONSTRAINTS ALL IMMEDIATE;", "COMMIT;", ""])
    sql = "\n".join(lines)
    manifest = dict(
        source_scenarios=292,
        identified_species_scenarios=8,
        source_profiles=len(profiles),
        unique_scenarios=len({r["scenario_id"] for r in profiles}),
        profiles_by_mode=dict(counters),
        profiles=profiles,
        pending=pending,
        pending_reasons=dict(Counter(r["reason"] for r in pending)),
        schedule_version=schedule_version,
        regional_schedules=len(schedules),
        pending_unique_scenarios_by_reason={
            reason: len(
                {row["scenario_id"] for row in pending if row["reason"] == reason}
            )
            for reason in sorted({row["reason"] for row in pending})
        },
        native_variable_bindings=sum(row["native_variable_count"] for row in profiles),
        prior_candidate_profiles=len(prior_schedule_profiles),
        prior_resource_profiles=sum(
            row["profile_key"].startswith("resource-native-")
            for row in prior_schedule_profiles
        ),
        combined_schedule_candidates=sum(len(set(v)) for v in schedules.values()),
        original_geometry_points=point_count,
        geometry_source_sha256=geometry_source_sha256,
        source_inventory_sha256=INVENTORY_SHA,
        species_authority_sha256=fingerprint(specs),
        sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
        enabled=False,
        sealed=True,
    )
    return sql, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-cell-csv", type=Path, default=NATIVE_CELLS)
    parser.add_argument("--seed", type=Path, default=SEED)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    report = ROOT / "agents_docs/reports/parallel-readiness-20261021"
    prior = []
    for filename in (
        "environmental-group-profile-manifest.json",
        "environmental-group-criteria-profile-manifest.json",
    ):
        for row in json.loads((report / filename).read_text())["profiles"]:
            prior.append(
                dict(
                    profile_key=row["profile_key"],
                    map_id=row["map_id"],
                    region_id=row["region_id"],
                )
            )
    from build_environmental_group_profiles import prior_resource_profiles

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
            native_cell_rows=cells,
            specs=json.loads(SPECS.read_text()),
            inventory=json.loads(INVENTORY.read_text()),
            catalog=json.loads(CATALOG.read_text()),
            prior_schedule_profiles=prior,
            geometry_source_sha256=hashlib.sha256(
                args.native_cell_csv.read_bytes()
            ).hexdigest(),
        )
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
