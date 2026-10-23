#!/usr/bin/env python3
"""Compile disabled group pipelines from exact original species and territories.

Uses source275/278, random population298 and native UI299. It never supplies a
roster, activates a profile, invents a species, or evaluates unsupported criteria.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

from build_environmental_resource_actions import (
    ROOT,
    SOURCE_KEY,
    REVISION,
    INVENTORY_SHA,
    insert,
    scalar,
)
from build_environmental_resource_profiles import GENERATED_REWARD_AUTHORITY

INVENTORY = (
    ROOT
    / "agents_docs/reports/recurring-missions/ENVIRONMENTAL-SCENARIOS-INVENTORY-20261011.json"
)
AUTHORITY = (
    ROOT
    / "agents_docs/reports/parallel-readiness-20261021/environmental810-original-species-authority.json"
)
NATIVE_CELLS = (
    ROOT
    / ".runtime/parallel-readiness-20261021/environmental-original-native-cells.csv"
)
SEED = ROOT / "server/seeds/environmental_group_profiles.sql"
ROSTER_POLICY = "wakemu.environmental-exact-species-genesis-v1"
POLICY = "wakemu.original-species-group-profiles.v1;native-levels-not-player-bands;random298;ui299"
RANKED = "wakemu.original-group-rank-bands-base-rewards.v1"
SIMPLE = "wakemu.original-group-single-primary-base-result.v1"
DEFAULT_MANIFEST = (
    ROOT
    / "agents_docs/reports/parallel-readiness-20261021/environmental-group-profile-manifest.json"
)
CRITERIA_SEED = ROOT / "server/seeds/environmental_group_criteria_profiles.sql"
CRITERIA_MANIFEST = (
    ROOT
    / "agents_docs/reports/parallel-readiness-20261021/environmental-group-criteria-profile-manifest.json"
)
LOCATION_CRITERIA = {
    "": "always",
    "GetSatisfactionLevel() >= 3": "all_wishes",
    "IsNeoServer()": "neo_server",
}


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def native_bands(scenario):
    if str(ROOT / "server") not in sys.path:
        sys.path.insert(0, str(ROOT / "server"))
    from wakfu_server.objectives.environmental_reward_bands import (
        compile_native_reward_bands,
    )

    rewards = sorted(
        scenario["rewards"], key=lambda row: (row["field_aHh"] + 128) % 256 - 128
    )
    return compile_native_reward_bands(
        [
            dict(
                reward_id=row["id"],
                primary_result_index=index,
                primary_reward_list=row["flag"],
                native_text=row["text"],
            )
            for index, row in enumerate(rewards)
        ],
        variable="nbMobPlayer",
    )


def profile_variables(key, scenario, objective):
    config = {
        k.lower(): (k, int(v))
        for k, v in scenario["configuration"].items()
        if re.fullmatch(r"-?[0-9]+", v)
    }
    rows = []
    for index, name in enumerate(scenario["variables"]):
        obj = configuration = value = authority = entity = None
        if name.lower() in config:
            kind = "configconstant"
            configuration, value = config[name.lower()]
        elif name == "nbMobMin":
            kind = "declared_threshold"
            configuration, value = config["nbmobforreward"]
            authority = POLICY
        elif name == "nbMobMax" and scenario["subtype"] == 3:
            kind = "leader_progress"
            obj = objective
            authority = "wakemu.group-leading-personal-monster-progress.v1"
        else:
            match = re.fullmatch(r"nb(Mob|Group)(Player|Global|Spawned|Left)", name)
            if match is None:
                raise ValueError("Unqualified original group variable: " + name)
            entity = {"Mob": "monster", "Group": "group"}[match[1]]
            kind = {
                "Player": "entity_personal_progress",
                "Global": "entity_global_progress",
                "Spawned": "spawned",
                "Left": "remaining",
            }[match[2]]
            if match[2] in ("Player", "Global"):
                obj = objective
                authority = "wakemu.authenticated-owned-entity-progress.v1;distinct-monster-group-receipts"
        rows.append(
            (
                key,
                1,
                SOURCE_KEY,
                scenario["id"],
                index,
                name,
                kind,
                obj,
                configuration,
                value,
                authority,
                entity,
            )
        )
    return rows


def prior_resource_profiles(seed_paths):
    """Read only generated public profile headers, never execute or interpret SQL."""
    found = {}
    pattern = re.compile(
        r"^\(E'(resource-native-([0-9]+)-([0-9]+)-([0-9]+))',1,-[0-9]+,E'resource_collect',",
        re.M,
    )
    for path in seed_paths:
        for match in pattern.finditer(Path(path).read_text()):
            key = match[1]
            row = dict(profile_key=key, map_id=int(match[3]), region_id=int(match[4]))
            if key in found:
                raise ValueError("Duplicate profile in prior resource seed inventory")
            found[key] = row
    return tuple(found.values())


def compile_pipeline(
    *,
    native_cell_rows,
    inventory_path=INVENTORY,
    authority_path=AUTHORITY,
    prior_schedule_profiles=(),
    intermission_ms=0,
    schedule_version=5,
    geometry_source_sha256=None,
    criterion_mode="blank",
):
    """Return complete profile/publication/objective/reward/variable/schedule SQL."""
    if (
        type(intermission_ms) is not int
        or intermission_ms < 0
        or type(schedule_version) is not int
        or schedule_version < 1
    ):
        raise ValueError("Invalid declared regional schedule policy")
    if criterion_mode not in ("blank", "qualified_nonempty"):
        raise ValueError("Unsupported group profile criterion cohort")
    if criterion_mode == "qualified_nonempty":
        if str(ROOT / "server") not in sys.path:
            sys.path.insert(0, str(ROOT / "server"))
        from wakfu_server.objectives.environmental_location_criteria import supports

        if not all(supports(criterion) for criterion in LOCATION_CRITERIA):
            raise ValueError(
                "Runtime location parser differs from source criterion policy"
            )
    inventory_bytes = Path(inventory_path).read_bytes()
    if hashlib.sha256(inventory_bytes).hexdigest() != INVENTORY_SHA:
        raise ValueError("Original1208 inventory hash differs")
    scenarios = {r["id"]: r for r in json.loads(inventory_bytes)["scenarios"]}
    source_document = json.loads(Path(authority_path).read_text())
    if (
        source_document["catalog_revision"] != REVISION
        or len(source_document["rows"]) != 810
    ):
        raise ValueError("Original810 source/catalog scope differs")
    surfaces = defaultdict(dict)
    point_count = 0
    for row in native_cell_rows:
        values = tuple(row[k] for k in ("map_id", "region_id", "x", "y", "z"))
        if (
            any(type(value) is not int for value in values)
            or min(values[:2]) <= 0
            or not -32768 <= values[4] < 32768
        ):
            raise ValueError("Invalid original native floor point")
        map_id, region_id, x, y, z = values
        point_count += 1
        surfaces[(map_id, region_id)][(x, y)] = max(
            z, surfaces[(map_id, region_id)].get((x, y), z)
        )
    ready = []
    pending = []
    for row in source_document["rows"]:
        identity = row["scenario_id"]
        scenario = scenarios[identity]
        if criterion_mode == "qualified_nonempty" and not any(
            location["native_criteria"] in LOCATION_CRITERIA
            and location["native_criteria"]
            for location in row["original_locations"]
        ):
            continue
        if not row["original_species_references"]:
            pending.append(
                dict(scenario_id=identity, reason="original_species_missing")
            )
            continue
        if row["native_type"] not in (6, 7, 8) or row["missing_native_species"]:
            raise ValueError("Unexpected native species family")
        if row["original_configuration"] != scenario["configuration"]:
            raise ValueError("Species audit configuration differs from original source")
        scopes = defaultdict(list)
        for location in row["original_locations"]:
            if location["map_id"] and location["region_id"]:
                scopes[(int(location["map_id"]), int(location["region_id"]))].append(
                    location
                )
        if not scopes:
            pending.append(
                dict(scenario_id=identity, reason="original_location_missing")
            )
            continue
        for (map_id, region_id), locations in sorted(scopes.items()):
            reason = None
            criteria = {x["native_criteria"] for x in locations}
            criterion = next(iter(criteria)) if len(criteria) == 1 else None
            if (criterion_mode == "blank" and criteria != {""}) or (
                criterion_mode == "qualified_nonempty"
                and (criterion not in LOCATION_CRITERIA or not criterion)
            ):
                reason = "original_location_criteria_unqualified"
            elif not all(x["native_cells_present"] == "True" for x in locations):
                reason = "original_native_floor_missing"
            elif len({int(x["protector_id"]) for x in locations}) != 1:
                reason = "original_protector_ambiguous"
            elif (
                len(surfaces.get((map_id, region_id), {}))
                < row["native_user_group_quantity_to_spawn"] * 5
            ):
                reason = "insufficient_original_floor_for_declared_max_members"
            if reason:
                pending.append(
                    dict(
                        scenario_id=identity,
                        map_id=map_id,
                        region_id=region_id,
                        reason=reason,
                    )
                )
                continue
            rewards = scenario["rewards"]
            if scenario["subtype"] == 3:
                bands = native_bands(scenario)
            elif len(rewards) == 1 and rewards[0]["flag"] and rewards[0]["text"] == "":
                bands = None
            else:
                pending.append(
                    dict(
                        scenario_id=identity,
                        map_id=map_id,
                        region_id=region_id,
                        reason="original_conditional_reward_unqualified",
                    )
                )
                continue
            for reward in rewards:
                if any(
                    type(reward[k]) is not int or not 0 <= reward[k] < 2**31
                    for k in ("field_agO", "field_aAi", "field_aHj", "field_aHk")
                ):
                    raise ValueError(
                        "Original reward exceeds normalized scalar grant shape"
                    )
                if reward["field_aHk"] != 0:
                    raise ValueError(
                        "Original group nonzero kamas authority unqualified"
                    )
            ready.append(
                dict(
                    source=row,
                    scenario=scenario,
                    map_id=map_id,
                    region_id=region_id,
                    protector_id=int(locations[0]["protector_id"]),
                    bands=bands,
                    criterion=criterion,
                )
            )
    lines = [
        "-- Disabled sealed group profiles from exact native species; no DB import or activation.",
        "-- Requires original275/278, runtime274/282/284/288/289/290, random298 and group UI299.",
        "-- Per-group member sizing2..5 is declared Wakemu; no original template composition is claimed.",
        "BEGIN;",
    ]
    profiles = []
    schedules = defaultdict(list)
    counters = Counter()
    if criterion_mode == "qualified_nonempty":
        lines.insert(
            -1,
            "-- Requires staged300 exact native location guards; no unsupported predicate is admitted.",
        )
    for item in ready:
        source = item["source"]
        scenario = item["scenario"]
        identity = scenario["id"]
        map_id, region_id = item["map_id"], item["region_id"]
        key = f"group-native-{abs(identity)}-{map_id}-{region_id}"
        family = "group_defeat" if source["native_type"] == 7 else "monster_defeat"
        objective = "group" if family == "group_defeat" else "mob"
        mode = {1: "solo", 2: "race", 3: "competitive", 4: "collaborative"}[
            scenario["subtype"]
        ]
        threshold = (
            source["native_nb_group_for_reward"]
            if family == "group_defeat"
            else source["native_nb_mob_for_reward"]
        )
        if (
            threshold <= 0
            or int(scenario["duration_raw"]) != source["native_duration_seconds"]
        ):
            raise ValueError("Original type/threshold/duration contract differs")
        # Only an event's persisted298 draw can supply COLLAB's complete global
        # target. The immutable1 is a marker, never a claim that one kill ends it.
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
            + ") THEN RAISE EXCEPTION 'Group profile lacks exact original territory/random pool'; END IF; END $$;"
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
                    source["template_reference_metadata_only"]
                    if family == "group_defeat"
                    else None,
                    None,
                    None,
                    "interaction",
                    required,
                )
            ],
        )
        insert(
            lines,
            "environmental_profile_group_ui",
            ("profile_key", "version", "source_key", "native_scenario_id", "authority"),
            [(key, 1, SOURCE_KEY, identity, POLICY)],
        )
        if criterion_mode == "qualified_nonempty":
            insert(
                lines,
                "environmental_profile_location_policy",
                (
                    "profile_key",
                    "version",
                    "source_key",
                    "native_scenario_id",
                    "protector_id",
                    "native_criteria",
                    "criterion_kind",
                    "source_authority",
                ),
                [
                    (
                        key,
                        1,
                        SOURCE_KEY,
                        identity,
                        item["protector_id"],
                        item["criterion"],
                        LOCATION_CRITERIA[item["criterion"]],
                        "original-exact-native-territory-criterion;native-location-policy300",
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
                        "wakemu.character-race-original-group-capacity.v1;one-character-one-place;not-original-winner-limit"
                        if mode == "race"
                        else "wakemu.original-group-rank-conditions.v1;all-eligible-fallback;character-id-ties",
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
                if mode == "collaborative" and family == "monster_defeat"
                else "persisted298group_births"
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
        source_scenarios=810,
        positive_species_scenarios=518,
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
        prior_resource_profiles=len(prior_schedule_profiles),
        combined_schedule_candidates=sum(len(set(v)) for v in schedules.values()),
        original_geometry_points=point_count,
        geometry_source_sha256=geometry_source_sha256,
        source_inventory_sha256=INVENTORY_SHA,
        species_authority_sha256=hashlib.sha256(
            Path(authority_path).read_bytes()
        ).hexdigest(),
        sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
        enabled=False,
        sealed=True,
    )
    if criterion_mode == "qualified_nonempty":
        manifest["criterion_mode"] = criterion_mode
        manifest["profiles_by_criterion"] = dict(
            Counter(item["criterion"] for item in ready)
        )
        manifest["scenarios_by_criterion"] = {
            criterion: sorted(
                {
                    item["scenario"]["id"]
                    for item in ready
                    if item["criterion"] == criterion
                }
            )
            for criterion in sorted({item["criterion"] for item in ready})
        }
        manifest["prior_candidate_profiles"] = len(prior_schedule_profiles)
        manifest["prior_resource_profiles"] = sum(
            row["profile_key"].startswith("resource-native-")
            for row in prior_schedule_profiles
        )
        manifest["prior_group_profiles"] = sum(
            row["profile_key"].startswith("group-native-")
            for row in prior_schedule_profiles
        )
        manifest["unassigned_group_scenarios_preserved"] = [
            row["scenario_id"]
            for row in source_document["rows"]
            if row["original_species_references"] and not row["original_locations"]
        ]
        manifest["unassigned_periodic_reward_scenarios_preserved"] = [
            identity
            for identity in manifest["unassigned_group_scenarios_preserved"]
            if len(scenarios[identity]["rewards"]) == 5
        ]
    return sql, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-cell-csv", type=Path, default=NATIVE_CELLS)
    parser.add_argument("--seed", type=Path, default=SEED)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument(
        "--criterion-delta",
        action="store_true",
        help="Separate staged300 delta; never overwrite the frozen438-profile seed",
    )
    args = parser.parse_args()
    seeds = [
        ROOT / "server/seeds" / name
        for name in (
            "environmental_resource_profiles.sql",
            "environmental_resource_races.sql",
            "environmental_resource_competitions.sql",
            "environmental_resource_level_criteria.sql",
        )
    ]
    prior = prior_resource_profiles(seeds)
    if args.criterion_delta:
        if args.seed.resolve() == SEED.resolve():
            args.seed = CRITERIA_SEED
        if args.manifest.resolve() == DEFAULT_MANIFEST.resolve():
            args.manifest = CRITERIA_MANIFEST
        original = json.loads(DEFAULT_MANIFEST.read_text())
        prior = (
            *prior,
            *(
                dict(
                    profile_key=row["profile_key"],
                    map_id=row["map_id"],
                    region_id=row["region_id"],
                )
                for row in original["profiles"]
            ),
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
            criterion_mode="qualified_nonempty" if args.criterion_delta else "blank",
            schedule_version=6 if args.criterion_delta else 5,
        )
    manifest["prior_resource_seed_sha256"] = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in seeds
    }
    args.seed.parent.mkdir(parents=True, exist_ok=True)
    args.seed.write_text(sql)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: value
                for key, value in manifest.items()
                if key
                not in (
                    "profiles",
                    "pending",
                    "prior_resource_seed_sha256",
                    "scenarios_by_criterion",
                    "unassigned_group_scenarios_preserved",
                    "unassigned_periodic_reward_scenarios_preserved",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
