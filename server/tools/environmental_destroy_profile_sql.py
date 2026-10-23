"""Pure SQL emitter shared by versioned destruction profile compilers.

No source rows or population policy definitions are emitted here. Those belong to
source normalization migrations; profiles are sealed and disabled.
"""
from collections import Counter, defaultdict
import hashlib
from build_environmental_destroy_profiles import (
    SOURCE_KEY,
    REVISION,
    INVENTORY_SHA,
    ROSTER_POLICY,
    RANKED,
    SIMPLE,
    GENERATED_REWARD_AUTHORITY,
    insert,
    scalar,
    fingerprint,
    native_bands,
    profile_variables,
)


def emit_profiles(
    *,
    ready,
    pending,
    prior_schedule_profiles,
    source_scenarios,
    source_sha256,
    source_policy_version,
    profile_authority,
    schedule_version,
    geometry_source_sha256,
    point_count,
    surfaces,
    intermission_ms=0,
):
    lines = [
        "-- Disabled sealed destruction profiles from explicitly identified targets; no DB import or activation.",
        "-- Requires normalized named-target source302, exact population bindings and native UI301.",
        "-- Per-group member sizing2..5 is declared Wakemu; no original template composition is claimed.",
        "BEGIN;",
    ]
    lines.insert(-1, "-- Source policy: " + source_policy_version)
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
            dict(
                source=source,
                scope=[map_id, region_id],
                authority=profile_authority,
                mode=mode,
            )
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
                    profile_authority,
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
            [(key, 1, SOURCE_KEY, identity, profile_authority)],
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
                    source_policy_version,
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
                    profile_authority,
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
                    profile_authority,
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
        identified_species_scenarios=source_scenarios,
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
        species_authority_sha256=source_sha256,
        sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
        enabled=False,
        sealed=True,
        qualified=False,
    )
    return sql, manifest
