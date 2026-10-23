#!/usr/bin/env python3
"""Compile an additive disabled cohort for explicitly mapped native stages.

Original scenario stage2 remains source metadata. Only the exact source303
mapping may authorize physical stage1 and its original cvF deletion action.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path

from build_environmental_resource_actions import (
    ROOT,
    SOURCE_KEY,
    REVISION,
    INVENTORY_SHA,
    build,
    insert,
    scalar,
    digest,
)
from build_environmental_resource_profiles import (
    INVENTORY,
    RECORDS,
    LOCATIONS,
    GENERATED_REWARD_AUTHORITY,
    _reward_bands,
    compile_result_policies,
)
from build_environmental_group_profiles import (
    NATIVE_CELLS,
    prior_resource_profiles,
    fingerprint,
)

IDS = frozenset((*range(-1880, -1876), *range(-1637, -1633)))
ACTIONS = {744: 2102, 730: 2091}
POLICY = "wakemu.original-resource-bomb-stage2-to-native-stage1.v1"
SEED = ROOT / "server/seeds/environmental_resource_stage_profiles.sql"
MANIFEST = (
    ROOT
    / "agents_docs/reports/parallel-readiness-20261021/environmental-resource-stage-profile-manifest.json"
)


def variables(profile_key, scenario):
    config = {
        key.lower(): (key, int(value))
        for key, value in scenario["configuration"].items()
    }
    result = []
    for index, name in enumerate(scenario["variables"]):
        objective = configuration = value = entity = authority = None
        if name.lower() in config:
            kind = "configconstant"
            configuration, value = config[name.lower()]
        elif name == "nbResourceMin":
            kind = "declared_threshold"
            configuration, value = config["nbresourceforreward"]
            authority = POLICY
        elif name in ("nbResourcePlayer", "nbResourceGlobal"):
            kind = "personal_progress" if name.endswith("Player") else "global_progress"
            objective = "resource"
        elif name == "nbResourceMax" and scenario["subtype"] == 3:
            kind = "leader_progress"
            objective = "resource"
            authority = "wakemu.resource-competition-leading-personal-progress.v1;max-not-stock-or-threshold"
        elif name in ("nbResourceSpawned", "nbResourceLeft"):
            kind = "spawned" if name.endswith("Spawned") else "remaining"
            entity = "resource"
        else:
            raise ValueError(
                "Unqualified original stage-mapped resource variable: " + name
            )
        result.append(
            (
                profile_key,
                1,
                SOURCE_KEY,
                scenario["id"],
                index,
                name,
                kind,
                objective,
                configuration,
                value,
                authority,
                entity,
            )
        )
    return result


def compile_pipeline(
    *,
    native_cell_rows,
    prior_schedule_profiles=(),
    schedule_version=9,
    geometry_source_sha256=None,
):
    resources, _, original_bindings = build(INVENTORY, RECORDS)
    resources = {row["resource_reference"]: row for row in resources}
    bindings = {row["scenario_id"]: row for row in original_bindings}
    inventory = json.loads(INVENTORY.read_text())
    scenarios = {row["id"]: row for row in inventory["scenarios"]}
    if len(IDS) != 8 or any(
        bindings[identity]["status"] != "missing_original_stage" for identity in IDS
    ):
        raise ValueError("Original eight missing-stage cohort changed")
    cells = defaultdict(dict)
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
        cells[(m, r)][(x, y)] = max(z, cells[(m, r)].get((x, y), z))
        point_count += 1
    locations = defaultdict(list)
    with LOCATIONS.open() as stream:
        for row in csv.DictReader(stream):
            if int(row["scenario_id"]) in IDS:
                locations[int(row["scenario_id"])].append(row)
    lines = [
        "-- Disabled source303 stage-mapped resource profiles; original stage2 metadata unchanged.",
        "BEGIN;",
    ]
    profiles = []
    schedules = defaultdict(list)
    counts = Counter()
    for identity in sorted(IDS):
        scenario = scenarios[identity]
        config = {
            key.lower(): int(value) for key, value in scenario["configuration"].items()
        }
        ref = config["ressourcerefid"]
        resource = resources[ref]
        if (
            ref not in ACTIONS
            or config["ressourcestep"] != 2
            or 2 in resource["stages"]
        ):
            raise ValueError(
                "Original resource stage mismatch no longer matches declared mapping"
            )
        (stage,) = tuple(
            row for row in resource["stage_definitions"] if row["stage_id"] == 1
        )
        (action,) = stage["actions"]
        if (
            action["action_id"] != ACTIONS[ref]
            or action["criteria"]
            or action["item_reference"]
            or action["product_references"]
            or action["raw_getters"]["cvF"] != 0
            or action["raw_getters"]["cvG"] != 1
        ):
            raise ValueError(
                "Mapped physical action is not the exact original product-free cvF0 action"
            )
        mode = {1: "solo", 2: "race", 3: "competitive", 4: "collaborative"}[
            scenario["subtype"]
        ]
        threshold = config["nbresourceforreward"]
        spawn = config["ressourcequantitytospawn"]
        if (
            min(threshold, spawn, config["challengelevelmin"]) <= 0
            or scenario["duration_raw"] != config["challengeduration"]
        ):
            raise ValueError("Original mapped resource count/level/duration differs")
        scopes = defaultdict(list)
        for location in locations[identity]:
            if (
                not location["map_id"]
                or not location["region_id"]
                or location["native_criteria"]
                or location["native_cells_present"] != "True"
            ):
                raise ValueError(
                    "Mapped source territory is not a qualified original scope"
                )
            scopes[(int(location["map_id"]), int(location["region_id"]))].append(
                location
            )
        if not scopes:
            raise ValueError("Mapped source has no original location")
        for (m, r), scope_rows in sorted(scopes.items()):
            (protector,) = {int(row["protector_id"]) for row in scope_rows}
            if len(cells[(m, r)]) < spawn:
                raise ValueError(
                    "Original native floor cannot hold source resource population"
                )
            key = f"resource-native-{abs(identity)}-{m}-{r}"
            source_guard = f"SELECT 1 FROM environmental_native_scenario_locations WHERE source_key={scalar(SOURCE_KEY)} AND scenario_id={identity} AND map_id={m} AND region_id={r} AND native_cells_present AND native_criteria=''"
            lines.append(
                "DO $$ BEGIN IF NOT EXISTS("
                + source_guard
                + ") THEN RAISE EXCEPTION 'Mapped resource lacks exact original territory'; END IF; END $$;"
            )
            action_guard = (
                f"SELECT 1 FROM environmental_resolved_resource_actions a JOIN environmental_resource_stage_actions x USING(source_key,resource_reference,native_step,action_ordinal,action_id,action_sha256)"
                f" WHERE a.source_key={scalar(SOURCE_KEY)} AND a.scenario_id={identity} AND a.resource_reference={ref}"
                f' AND a.source_native_step=2 AND a.native_step=1 AND a.action_ordinal=0 AND a.action_id={action["action_id"]}'
                f" AND a.action_sha256={scalar(digest(action))} AND x.record_sha256={scalar(digest(resource))}"
            )
            lines.append(
                "DO $$ BEGIN IF NOT EXISTS("
                + action_guard
                + ") THEN RAISE EXCEPTION 'Mapped resource lacks exact declared source303 native action'; END IF; END $$;"
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
                        "resource_collect",
                        mode,
                        m,
                        r,
                        scenario["duration_raw"] * 1000,
                        None,
                        0,
                        config["challengelevelmin"],
                        config["challengelevelmax"],
                        threshold,
                        POLICY,
                        fingerprint(
                            dict(
                                scenario=scenario,
                                resource_sha=digest(resource),
                                scope=[m, r],
                                authority=POLICY,
                            )
                        ),
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
                        "resource",
                        "resource_collect",
                        ref,
                        action["action_id"],
                        1,
                        "interaction",
                        spawn if mode == "collaborative" else threshold,
                    )
                ],
            )
            if mode in ("race", "competitive"):
                bands = _reward_bands(scenario)
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
                            "first_completion"
                            if mode == "race"
                            else "score_at_deadline",
                            spawn
                            if mode == "race"
                            else max(
                                band["rank_max"]
                                for band in bands
                                if band["rank_max"] is not None
                            ),
                            "commit_order" if mode == "race" else "character_id",
                            "wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit"
                            if mode == "race"
                            else "wakemu.resource-competition-top-two-ranks.v1;original-rank-conditions;all-eligible-fallback;character-id-ties",
                        )
                    ],
                )
                if mode == "competitive":
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
                                "wakemu.original-resource-rank-bands-base-rewards.v1",
                                "all_eligible",
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
                (reward,) = scenario["rewards"]
                if reward["text"] or not reward["flag"] or reward["field_aHk"]:
                    raise ValueError("Mapped resource primary reward is not qualified")
                rewards = []
                for kind, reference, quantity in (
                    ("item", reward["field_aAi"], reward["field_aHj"]),
                    ("xp", None, reward["field_agO"]),
                ):
                    if quantity:
                        if (
                            type(quantity) is not int
                            or quantity <= 0
                            or quantity >= 2**31
                            or (kind == "item" and reference <= 0)
                        ):
                            raise ValueError("Original reward scalar is invalid")
                        rewards.append(
                            (
                                key,
                                1,
                                len(rewards),
                                kind,
                                reference,
                                quantity,
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
                        protector,
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
                    (key, 1, state, index)
                    for state, index in [
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
            var_rows = variables(key, scenario)
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
                var_rows,
            )
            insert(
                lines,
                "environmental_profile_resource_population",
                (
                    "profile_key",
                    "version",
                    "source_key",
                    "placement_policy",
                    "transition_policy",
                    "source_authority",
                ),
                [(key, 1, SOURCE_KEY, "declared_native_cells", "catalog_cvF", POLICY)],
            )
            points = sorted((x, y, z) for (x, y), z in cells[(m, r)].items())[
                : min(spawn * 2 + 32, len(cells[(m, r)]))
            ]
            insert(
                lines,
                "environmental_profile_resource_cells",
                ("profile_key", "version", "ordinal", "x", "y", "z"),
                [(key, 1, index, *point) for index, point in enumerate(points)],
            )
            profiles.append(
                dict(
                    profile_key=key,
                    scenario_id=identity,
                    map_id=m,
                    region_id=r,
                    mode=mode,
                    protector_id=protector,
                    original_step=2,
                    effective_step=1,
                    resource_reference=ref,
                    action_id=action["action_id"],
                    personal_threshold=threshold,
                    original_spawn_count=spawn,
                    candidate_cells=len(points),
                    native_variable_count=len(var_rows),
                    resource_record_sha256=digest(resource),
                    action_sha256=digest(action),
                )
            )
            schedules[(m, r)].append(key)
            counts[mode] += 1
    result_sql, _ = compile_result_policies(
        profile_rows=[row for row in profiles if row["mode"] != "competitive"]
    )
    lines.append(
        result_sql.removeprefix(
            "-- Explicit result mappings only. Import before sealing existing disabled profiles.\nBEGIN;\n"
        ).removesuffix("COMMIT;\n")
    )
    for row in prior_schedule_profiles:
        schedules[(row["map_id"], row["region_id"])].append(row["profile_key"])
    for (m, r), candidates in sorted(schedules.items()):
        candidates = sorted(set(candidates))
        key = f"wakemu-native-resources-{m}-{r}"
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
                    m,
                    r,
                    "wakemu_round_robin",
                    "occupied_sequential_windows",
                    0,
                    POLICY,
                    fingerprint(dict(scope=[m, r], profiles=candidates)),
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
    return sql, dict(
        source_scenarios=8,
        source_profiles=len(profiles),
        profiles=profiles,
        profiles_by_mode=dict(counts),
        native_variable_bindings=sum(row["native_variable_count"] for row in profiles),
        candidate_cells=sum(row["candidate_cells"] for row in profiles),
        prior_candidate_profiles=len(prior_schedule_profiles),
        combined_schedule_candidates=sum(
            len(set(values)) for values in schedules.values()
        ),
        regional_schedules=len(schedules),
        schedule_version=schedule_version,
        original_geometry_points=point_count,
        geometry_source_sha256=geometry_source_sha256,
        sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
        source_inventory_sha256=INVENTORY_SHA,
        enabled=False,
        sealed=True,
        qualified=False,
    )


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
        "environmental-destroy-profile-manifest.json",
        "environmental-named-destroy-profile-manifest.json",
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
            native_cell_rows=cells,
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
            {key: value for key, value in manifest.items() if key != "profiles"},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
