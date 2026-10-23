"""Compile the entire original resource family into disabled runtime SQL.

No database connection or native runtime is loaded. Original scenario counts,
levels, resource stages and action IDs are preserved. A separate typed CSV must
provide unresolved server timing, objective-unit and reward authority before a
candidate can become even a disabled runtime profile. Raw reward display values
are evidence, not grant instructions. Output is private SQL, never auto-applied.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from build_environmental_resource_actions import (
    ROOT,
    SOURCE_KEY,
    REVISION,
    INVENTORY_SHA,
    build as source_actions,
    insert,
)

INVENTORY = (
    ROOT
    / "agents_docs/reports/recurring-missions/ENVIRONMENTAL-SCENARIOS-INVENTORY-20261011.json"
)
RECORDS = (
    ROOT
    / ".runtime/parallel-readiness-20261021/environmental-resource-source-join/original-resource-seed-records.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / ".runtime/parallel-readiness-20261021/environmental-resource-profile-compiler"
)
SEED_PATH = ROOT / "server/seeds/environmental_resource_profiles.sql"
RACE_SEED_PATH = ROOT / "server/seeds/environmental_resource_races.sql"
COMPETITIVE_SEED_PATH = ROOT / "server/seeds/environmental_resource_competitions.sql"
RESULT_SEED_PATH = ROOT / "server/seeds/environmental_resource_results.sql"
CRITERIA_SEED_PATH = ROOT / "server/seeds/environmental_resource_level_criteria.sql"
LOCATIONS = (
    ROOT
    / "agents_docs/reports/parallel-readiness-20261021/environmental-original-scenario-locations.csv"
)
GENERATED_AUTHORITY = "wakemu-resource-interaction-policy-v1;original-duration-seconds;regional-schedule282"
GENERATED_REWARD_AUTHORITY = (
    "wakemu-original-display-base-rewards-v1;no-booster;not-original-server-grant"
)
POLICY_COLUMNS = (
    "scenario_id",
    "map_id",
    "region_id",
    "duration_ms",
    "anchor_ms",
    "recurrence_period_ms",
    "unit",
    "authority",
    "reward_authority",
    "reward_item_reference",
    "reward_item_quantity",
    "reward_xp",
    "reward_kamas",
)


def positive(value, name, minimum=1):
    if type(value) is not int or not minimum <= value < 2**63:
        raise ValueError("Invalid resource policy " + name)
    return value


def validate_policy_rows(rows):
    """Validate CLI and programmatic callers through the same closed schema."""
    result, seen = [], set()
    for value in rows:
        if type(value) is not dict or set(value) != set(POLICY_COLUMNS):
            raise ValueError(
                "Resource policy fields differ from the closed typed schema"
            )
        row = dict(value)
        if (
            type(row["scenario_id"]) is not int
            or not -(2**31) <= row["scenario_id"] < 0
        ):
            raise ValueError("Invalid original resource scenario identity")
        for field in ("map_id", "region_id", "duration_ms"):
            positive(row[field], field)
        identity = (row["scenario_id"], row["map_id"], row["region_id"])
        if identity in seen:
            raise ValueError("Duplicate resource policy scope")
        seen.add(identity)
        positive(row["anchor_ms"], "anchor", 0)
        period = row["recurrence_period_ms"]
        if period is not None and positive(period, "period") < row["duration_ms"]:
            raise ValueError("Resource policy duration exceeds recurrence")
        if row["unit"] not in ("interaction", "quantity"):
            raise ValueError("Explicit resource objective unit required")
        for field in ("authority", "reward_authority"):
            if (
                type(row[field]) is not str
                or not row[field].strip()
                or "\0" in row[field]
            ):
                raise ValueError("Explicit runtime and reward authorities required")
        item, quantity = row["reward_item_reference"], row["reward_item_quantity"]
        if (item is None) != (quantity is None):
            raise ValueError("Resource item reward requires reference and quantity")
        for field in (
            "reward_item_reference",
            "reward_item_quantity",
            "reward_xp",
            "reward_kamas",
        ):
            if row[field] is not None:
                positive(row[field], field)
                if row[field] >= 2**31:
                    raise ValueError("Resource reward exceeds normalized runtime range")
        if item is None and row["reward_xp"] is None and row["reward_kamas"] is None:
            raise ValueError("Explicit resource reward policy required")
        result.append(row)
    return tuple(result)


def policies(path):
    """Read explicit policy rows; blank recurrence means no assumed cadence."""
    if path is None:
        return ()
    rows = []
    with Path(path).open(newline="") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != POLICY_COLUMNS:
            raise ValueError(
                "Resource policy CSV must use the exact documented columns"
            )
        for raw in reader:
            if set(raw) != set(POLICY_COLUMNS) or any(
                value is None for value in raw.values()
            ):
                raise ValueError("Malformed resource policy CSV row")
            row = dict(raw)
            for field in POLICY_COLUMNS:
                if field not in ("unit", "authority", "reward_authority"):
                    row[field] = None if not raw[field] else int(raw[field])
            rows.append(row)
    return validate_policy_rows(rows)


def _reward_bands(scenario):
    """Reuse the production strict parser without loading native catalogues."""
    import sys

    server_path = str(ROOT / "server")
    if server_path not in sys.path:
        sys.path.insert(0, server_path)
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
        ]
    )


def _criterion_minimum(text):
    """Use the real closed native criterion parser, never a CSV level bypass."""
    import sys

    server_path = str(ROOT / "server")
    if server_path not in sys.path:
        sys.path.insert(0, server_path)
    from wakfu_server.resource_action_criteria import minimum_effective_level

    return minimum_effective_level(text)


def compile_profiles(
    *,
    inventory_path=INVENTORY,
    records_path=RECORDS,
    policy_rows=(),
    declared_character_races=False,
    declared_resource_competitions=False,
    evaluated_resource_criteria=False,
):
    """Return SQL, full313-row diagnostic census and finite summary."""
    resources, actions, bindings = source_actions(inventory_path, records_path)
    inventory = json.loads(Path(inventory_path).read_text())
    scenarios = {r["id"]: r for r in inventory["scenarios"]}
    selected, census = {}, []
    for binding in bindings:
        scenario = scenarios[binding["scenario_id"]]
        config = {
            key.lower(): value for key, value in scenario["configuration"].items()
        }
        threshold = positive(int(config["nbresourceforreward"]), "original threshold")
        quantity = positive(
            int(config["ressourcequantitytospawn"]), "original spawn count"
        )
        minimum, maximum = int(config["challengelevelmin"]), int(
            config["challengelevelmax"]
        )
        positive(minimum, "original minimum level")
        positive(maximum, "original maximum level")
        if minimum > maximum:
            raise ValueError("Reversed original resource level bounds")
        action = actions.get(
            (binding["resource_reference"], binding["resource_step"], 0)
        )
        row = dict(
            binding,
            level_min=minimum,
            level_max=maximum,
            required_quantity=threshold,
            spawn_quantity=quantity,
            native_duration_raw=scenario["duration_raw"],
            native_subtype=scenario["subtype"],
            product_references=[] if action is None else action["product_references"],
            item_reference=None if action is None else action["item_reference"],
            native_criteria=None if action is None else action["criteria"],
            original_base_xp=[r["field_agO"] for r in scenario["rewards"]],
            original_display_items=[
                (r["field_aAi"], r["field_aHj"]) for r in scenario["rewards"]
            ],
            missing=[
                "explicit_runtime_policy",
                "original_final_xp_authority",
                "declared_placement_cells",
                "regional_schedule_policy",
            ],
        )
        if action is None:
            row["missing"].append("missing_original_stage")
        elif action["criteria"]:
            row["missing"].append("original_action_criteria_evaluator")
        if action is not None and (
            action["item_reference"] or action["product_references"]
        ):
            row["missing"].append("original_product_settlement_authority")
        if action is not None and not action["product_references"]:
            row["missing"].append("no_original_product_output")
        selected[row["scenario_id"]] = row
        census.append(row)
    policy_rows = validate_policy_rows(policy_rows)
    if any(row["scenario_id"] not in selected for row in policy_rows):
        raise ValueError("Policy outside original313 resource family")
    lines = [
        "-- Generated disabled profiles only; no activation or real DB mutation is performed by the compiler.",
        "-- Requires source275, original locations278, original actions280 and runtime274.",
        "-- Placement281 and regional scheduling282 must be supplied separately before activation.",
        "BEGIN;",
    ]
    counts = Counter()
    for policy in policy_rows:
        native = selected[policy["scenario_id"]]
        if native["action_id"] is None:
            counts["blocked_missing_stage"] += 1
            continue
        if native["native_criteria"]:
            if not evaluated_resource_criteria:
                counts["blocked_criteria"] += 1
                continue
            _criterion_minimum(native["native_criteria"])
        if native["item_reference"] or native["product_references"]:
            counts["blocked_product_settlement"] += 1
            continue
        if (native["native_subtype"] == 3 and not declared_resource_competitions) or (
            native["native_subtype"] == 2 and not declared_character_races
        ):
            # Native mode and display ranks do not prove winner admission or
            # rank-band reward settlement. Never flatten these into solo grants.
            counts["blocked_unsupported_mode"] += 1
            continue
        key = "resource-native-{}-{}-{}".format(
            abs(native["scenario_id"]), policy["map_id"], policy["region_id"]
        )
        fingerprint = hashlib.sha256(
            json.dumps(dict(policy=policy, source=native), sort_keys=True).encode()
        ).hexdigest()
        # The source-location guard is evaluated against normalized original SQL,
        # rather than trusting a caller-selected map merely because it exists.
        from build_environmental_resource_actions import scalar

        guard = (
            "SELECT 1 FROM environmental_native_scenario_locations WHERE source_key="
            + scalar(SOURCE_KEY)
            + " AND scenario_id="
            + str(native["scenario_id"])
            + " AND map_id="
            + str(policy["map_id"])
            + " AND region_id="
            + str(policy["region_id"])
            + " AND native_cells_present AND native_criteria=''"
        )
        lines.append(
            "DO $$ BEGIN IF NOT EXISTS("
            + guard
            + ") THEN RAISE EXCEPTION 'Resource profile lacks original scenario territory'; END IF; END $$;"
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
                    native["scenario_id"],
                    "resource_collect",
                    {1: "solo", 2: "race", 3: "competitive", 4: "collaborative"}[
                        native["native_subtype"]
                    ],
                    policy["map_id"],
                    policy["region_id"],
                    policy["duration_ms"],
                    policy["recurrence_period_ms"],
                    policy["anchor_ms"],
                    native["level_min"],
                    native["level_max"],
                    native["required_quantity"],
                    policy["authority"],
                    fingerprint,
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
                    native["resource_reference"],
                    native["action_id"],
                    native["resource_step"],
                    policy["unit"],
                    native["spawn_quantity"]
                    if native["native_subtype"] == 4
                    else native["required_quantity"],
                )
            ],
        )
        if native["native_subtype"] == 2:
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
                        "first_completion",
                        native["spawn_quantity"],
                        "commit_order",
                        "wakemu.character-race-capacity-from-original-physical-population.v1;each-hero-occupies-one-place;not-original-character-limit",
                    )
                ],
            )
        if native["native_subtype"] == 3:
            bands = _reward_bands(scenarios[native["scenario_id"]])
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
                        "score_at_deadline",
                        max(
                            band["rank_max"]
                            for band in bands
                            if band["rank_max"] is not None
                        ),
                        "character_id",
                        "wakemu.resource-competition-top-two-ranks.v1;original-rank-conditions;all-eligible-fallback;character-id-ties",
                    )
                ],
            )
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
                        native["scenario_id"],
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
                        native["scenario_id"],
                        band["primary_reward_index"],
                        band["reward_id"],
                        band["rank_min"],
                        band["rank_max"],
                    )
                    for band in bands
                ],
            )
            counts["ranked_reward_bands_emitted"] += len(bands)
        rewards = []
        for kind, reference, amount in (
            ("item", policy["reward_item_reference"], policy["reward_item_quantity"]),
            ("xp", None, policy["reward_xp"]),
            ("kamas", None, policy["reward_kamas"]),
        ):
            if amount is not None and native["native_subtype"] != 3:
                rewards.append(
                    (
                        key,
                        1,
                        len(rewards),
                        kind,
                        reference,
                        amount,
                        policy["reward_authority"],
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
        counts["disabled_profiles_emitted"] += 1
    lines.append("COMMIT;\n")
    summary = dict(
        native_scenarios=len(census),
        original_action_matched=sum(r["action_id"] is not None for r in census),
        missing_original_stages=[
            r["scenario_id"] for r in census if r["action_id"] is None
        ],
        product_output_missing=sum(
            not r["product_references"] for r in census if r["action_id"] is not None
        ),
        action_criteria_nonempty=sum(bool(r["native_criteria"]) for r in census),
        product_settlement_blocked=sum(
            bool(r["item_reference"] or r["product_references"]) for r in census
        ),
        current_producer_candidates=sum(
            r["action_id"] is not None
            and not r["native_criteria"]
            and not r["item_reference"]
            and not r["product_references"]
            for r in census
        ),
        policy_rows=len(policy_rows),
        activated_profiles=0,
        source_inventory_sha256=INVENTORY_SHA,
        **dict(counts),
    )
    return "\n".join(lines), census, summary


def generate_policies(
    *,
    inventory_path=INVENTORY,
    records_path=RECORDS,
    locations_path=LOCATIONS,
    include_competitive=False,
    evaluated_resource_criteria=False,
):
    """Build all eligible source-location policies with explicit Wakemu rewards.

    The returned CSV retains unsupported race/competitive candidates for review;
    compile_profiles refuses to emit their runtime rows. No rank or winner count
    is inferred from reward accessor Xk or the number of spawned resources.
    """
    _, census, _ = compile_profiles(
        inventory_path=inventory_path, records_path=records_path
    )
    scenarios = {
        row["id"]: row
        for row in json.loads(Path(inventory_path).read_text())["scenarios"]
    }
    scopes, scope_criteria = {}, {}
    with Path(locations_path).open(newline="") as stream:
        for row in csv.DictReader(stream):
            identity = int(row["scenario_id"])
            if (
                row["native_cells_present"] != "True"
                or not row["map_id"]
                or not row["region_id"]
            ):
                continue
            scope = (int(row["map_id"]), int(row["region_id"]))
            scopes.setdefault(identity, set()).add(scope)
            scope_criteria.setdefault((identity, *scope), set()).add(
                row["native_criteria"]
            )
    result, omissions = [], []
    for native in census:
        if (
            native["action_id"] is None
            or native["item_reference"]
            or native["product_references"]
        ):
            continue
        if native["native_criteria"]:
            if not evaluated_resource_criteria:
                continue
            _criterion_minimum(native["native_criteria"])
        identity = native["scenario_id"]
        scenario = scenarios[identity]
        config = {
            key.lower(): value for key, value in scenario["configuration"].items()
        }
        if int(config["challengeduration"]) != native["native_duration_raw"]:
            raise ValueError(
                "Original duration differs from its authenticated scenario field"
            )
        duration_ms = positive(native["native_duration_raw"], "original seconds") * 1000
        rewards = scenario["rewards"]
        # Only one unconditional primary display reward may define this local
        # grant policy. Multiple conditional ranks remain unsupported.
        eligible_reward = (
            len(rewards) == 1 and not rewards[0]["text"] and rewards[0]["flag"]
        )
        if include_competitive and scenario["subtype"] == 3:
            _reward_bands(scenario)
            eligible_reward = True
        for map_id, region_id in sorted(scopes.get(identity, ())):
            reason = None
            if scope_criteria[(identity, map_id, region_id)] != {""}:
                reason = "original_group_criteria_unqualified"
            elif not eligible_reward:
                reason = "conditional_or_ranked_reward_policy_unqualified"
            reward = (
                (
                    next(r for r in rewards if r["text"] == "")
                    if include_competitive and scenario["subtype"] == 3
                    else rewards[0]
                )
                if eligible_reward
                else None
            )
            if reason:
                omissions.append(
                    dict(
                        scenario_id=identity,
                        map_id=map_id,
                        region_id=region_id,
                        reason=reason,
                    )
                )
                continue
            item = reward["field_aAi"] if reward["field_aAi"] > 0 else None
            quantity = reward["field_aHj"] if item is not None else None
            row = dict(
                zip(
                    POLICY_COLUMNS,
                    (
                        identity,
                        map_id,
                        region_id,
                        duration_ms,
                        0,
                        None,
                        "interaction",
                        GENERATED_AUTHORITY,
                        GENERATED_REWARD_AUTHORITY,
                        item,
                        quantity,
                        reward["field_agO"] or None,
                        reward["field_aHk"] or None,
                    ),
                )
            )
            result.append(row)
        if not scopes.get(identity):
            omissions.append(
                dict(
                    scenario_id=identity,
                    map_id=None,
                    region_id=None,
                    reason="missing_original_floor_location",
                )
            )
    return validate_policy_rows(result), omissions


def compile_pipeline(
    *,
    native_cell_rows,
    inventory_path=INVENTORY,
    records_path=RECORDS,
    locations_path=LOCATIONS,
    intermission_ms=0,
    native_geometry_source_sha256=None,
    profile_modes=(1, 4),
    declared_character_races=False,
    schedule_version=1,
    prior_schedule_profiles=(),
    declared_resource_competitions=False,
    evaluated_resource_criteria=False,
    only_evaluated_criteria=False,
    schedule_all_prior_scopes=False,
):
    """Compile complete disabled pipelines using supplied authentic floor rows.

    ``native_cell_rows`` contains map_id,region_id,x,y,z from original geometry.
    No synthetic positions or client coordinates are accepted as substitutes.
    The caller must retain the original export provenance beside the manifest.
    Where original surfaces shareXY, declared placement selects their highest
    originalZ. It never synthesizes a height or claims original server policy.
    """
    positive(intermission_ms, "declared intermission", 0)
    policies_generated, omissions = generate_policies(
        inventory_path=inventory_path,
        records_path=records_path,
        locations_path=locations_path,
        include_competitive=declared_resource_competitions,
        evaluated_resource_criteria=evaluated_resource_criteria,
    )
    inventory = json.loads(Path(inventory_path).read_text())
    scenarios = {row["id"]: row for row in inventory["scenarios"]}
    cells = {}
    for row in native_cell_rows:
        scope = (
            positive(row["map_id"], "floor map"),
            positive(row["region_id"], "floor region"),
        )
        point = tuple(row[key] for key in ("x", "y", "z"))
        if (
            any(type(value) is not int for value in point)
            or not -(2**15) <= point[2] < 2**15
        ):
            raise ValueError("Invalid original environmental floor point")
        cells.setdefault(scope, set()).add(point)
    original_point_count = sum(len(points) for points in cells.values())
    surfaces = {}
    for scope, points in cells.items():
        selected_z = {}
        for x, y, z in points:
            selected_z[(x, y)] = max(z, selected_z.get((x, y), z))
        surfaces[scope] = {(x, y, z) for (x, y), z in selected_z.items()}
    cells = surfaces
    protectors = {}
    with Path(locations_path).open(newline="") as stream:
        for row in csv.DictReader(stream):
            if (
                row["native_cells_present"] == "True"
                and row["map_id"]
                and row["region_id"]
                and not row["native_criteria"]
            ):
                key = (
                    int(row["scenario_id"]),
                    int(row["map_id"]),
                    int(row["region_id"]),
                )
                protectors.setdefault(key, set()).add(int(row["protector_id"]))
    ready, blocked = [], list(omissions)
    criteria_sources = {}
    if only_evaluated_criteria:
        export = json.loads(Path(records_path).read_text())
        criteria_sources = {
            entry["payload"]["resource_reference"]: entry["payload"]
            for entry in export["plant-resources.json"]
        }
    for row in policies_generated:
        scenario = scenarios[row["scenario_id"]]
        if scenario["subtype"] not in profile_modes:
            continue
        if only_evaluated_criteria:
            normalized = {
                key.lower(): value for key, value in scenario["configuration"].items()
            }
            resource = criteria_sources[int(normalized["ressourcerefid"])]
            action = next(
                action
                for stage in resource["stage_definitions"]
                if stage["stage_id"] == int(normalized["ressourcestep"])
                for action in stage["actions"]
            )
            if not action["criteria"]:
                continue
            _criterion_minimum(action["criteria"])
        config = {
            key.lower(): value for key, value in scenario["configuration"].items()
        }
        scope = (row["map_id"], row["region_id"])
        ids = protectors.get((row["scenario_id"], *scope), set())
        reason = None
        if len(ids) != 1:
            reason = "ambiguous_original_protector"
        elif len(cells.get(scope, ())) < int(config["ressourcequantitytospawn"]):
            reason = "insufficient_original_region_floor_points"
        if reason:
            blocked.append(
                dict(
                    scenario_id=row["scenario_id"],
                    map_id=scope[0],
                    region_id=scope[1],
                    reason=reason,
                )
            )
            continue
        ready.append(row)
    sql, census, summary = compile_profiles(
        inventory_path=inventory_path,
        records_path=records_path,
        policy_rows=ready,
        declared_character_races=declared_character_races,
        declared_resource_competitions=declared_resource_competitions,
        evaluated_resource_criteria=evaluated_resource_criteria,
    )
    lines = [sql.removesuffix("COMMIT;\n")]
    schedules, profiles = {}, []
    for row in ready:
        identity, map_id, region_id = (
            row["scenario_id"],
            row["map_id"],
            row["region_id"],
        )
        scenario = scenarios[identity]
        config = {
            key.lower(): (key, int(value))
            for key, value in scenario["configuration"].items()
        }
        key = "resource-native-{}-{}-{}".format(abs(identity), map_id, region_id)
        protector = next(iter(protectors[(identity, map_id, region_id)]))
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
                (key, 1, state, ordinal)
                for state, ordinal in (
                    ("proposed", 0),
                    ("active", 1),
                    ("completed", 2),
                    ("expired", 2),
                    ("cancelled", 3),
                )
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
                    GENERATED_AUTHORITY,
                )
            ],
        )
        bindings = []
        for index, name in enumerate(scenario["variables"]):
            objective = configuration = value = entity = authority = None
            if name.lower() in config:
                kind = "configconstant"
                configuration, value = config[name.lower()]
            elif name == "nbResourceMin":
                kind = "declared_threshold"
                configuration, value = config["nbresourceforreward"]
                authority = GENERATED_AUTHORITY
            elif name in ("nbResourcePlayer", "nbResourceGlobal"):
                kind = (
                    "personal_progress"
                    if name.endswith("Player")
                    else "global_progress"
                )
                objective = "resource"
            elif name == "nbResourceMax" and declared_resource_competitions:
                kind = "leader_progress"
                objective = "resource"
                authority = "wakemu.resource-competition-leading-personal-progress.v1;max-not-stock-or-threshold"
            elif name in ("nbResourceSpawned", "nbResourceLeft"):
                kind = "spawned" if name.endswith("Spawned") else "remaining"
                entity = "resource"
            else:
                raise ValueError(
                    "Original resource variable has no qualified typed projection: "
                    + name
                )
            bindings.append(
                (
                    key,
                    1,
                    SOURCE_KEY,
                    identity,
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
            bindings,
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
            [
                (
                    key,
                    1,
                    SOURCE_KEY,
                    "declared_native_cells",
                    "catalog_cvF",
                    GENERATED_AUTHORITY,
                )
            ],
        )
        all_points = cells[(map_id, region_id)]
        # Explicit bounded Wakemu placement: retain a two-population margin
        # plus32 exact native candidates, rather than repeating every map tile
        # in each scenario. Runtime still checks live occupancy before birth.
        spawn_count = int(config["ressourcequantitytospawn"][1])
        points = sorted(all_points)[: min(spawn_count * 2 + 32, len(all_points))]
        insert(
            lines,
            "environmental_profile_resource_cells",
            ("profile_key", "version", "ordinal", "x", "y", "z"),
            [(key, 1, index, *point) for index, point in enumerate(points)],
        )
        schedules.setdefault((map_id, region_id), []).append(key)
        profiles.append(
            dict(
                profile_key=key,
                scenario_id=identity,
                map_id=map_id,
                region_id=region_id,
                protector_id=protector,
                native_variable_count=len(bindings),
                candidate_cells=len(points),
                original_region_cells=len(all_points),
                original_spawn_count=spawn_count,
            )
        )
    for row in prior_schedule_profiles:
        scope = (row["map_id"], row["region_id"])
        if scope in schedules or schedule_all_prior_scopes:
            schedules.setdefault(scope, []).append(row["profile_key"])
    for (map_id, region_id), candidates in sorted(schedules.items()):
        if schedule_version != 1:
            candidates = sorted(set(candidates))
        key = "wakemu-native-resources-{}-{}".format(map_id, region_id)
        fingerprint = hashlib.sha256(
            json.dumps(
                dict(
                    scope=[map_id, region_id],
                    candidates=candidates,
                    intermission_ms=intermission_ms,
                ),
                sort_keys=True,
            ).encode()
        ).hexdigest()
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
                    GENERATED_AUTHORITY,
                    fingerprint,
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
    lines.append("COMMIT;\n")
    result = "\n".join(lines)
    manifest = dict(
        summary,
        pipeline_profiles=len(profiles),
        regional_schedules=len(schedules),
        profiles=profiles,
        omissions=blocked,
        geometry_sha256=hashlib.sha256(
            json.dumps(
                [(scope, sorted(points)) for scope, points in sorted(cells.items())]
            ).encode()
        ).hexdigest(),
        native_geometry_source_sha256=native_geometry_source_sha256,
        original_geometry_points=original_point_count,
        placement_policy="wakemu.highest-original-z-per-xy.sorted.twice-population-plus32.v1",
        sql_sha256=hashlib.sha256(result.encode()).hexdigest(),
        enabled=False,
        sealed=False,
    )
    return result, census, manifest


def compile_declared_races(
    *,
    native_cell_rows,
    inventory_path=INVENTORY,
    records_path=RECORDS,
    locations_path=LOCATIONS,
    intermission_ms=0,
    native_geometry_source_sha256=None,
):
    """Opt-in per-character races; preserve the existing solo/collab seed.

    Original physical population bounds supply. Treating it as a character
    winner capacity is an explicit Wakemu rule, including each loaded hero.
    Schedule version2 references the prior profiles without rewriting them.
    """
    points = tuple(native_cell_rows)
    arguments = dict(
        native_cell_rows=points,
        inventory_path=inventory_path,
        records_path=records_path,
        locations_path=locations_path,
        intermission_ms=intermission_ms,
        native_geometry_source_sha256=native_geometry_source_sha256,
    )
    _, _, baseline = compile_pipeline(**arguments)
    sql, census, manifest = compile_pipeline(
        **arguments,
        profile_modes=(2,),
        declared_character_races=True,
        schedule_version=2,
        prior_schedule_profiles=baseline["profiles"],
    )
    manifest.update(
        declared_character_races=True,
        original_character_limit_proven=False,
        race_capacity_policy="one-place-per-character-from-original-physical-population",
        prior_seed_profiles=len(baseline["profiles"]),
        schedule_version=2,
        expected_combined_candidates=len(baseline["profiles"])
        + manifest["pipeline_profiles"],
    )
    return sql, census, manifest


def compile_declared_competitions(
    *,
    native_cell_rows,
    inventory_path=INVENTORY,
    records_path=RECORDS,
    locations_path=LOCATIONS,
    intermission_ms=0,
    native_geometry_source_sha256=None,
):
    """Separate exact original rank bands with declared all-eligible grants."""
    points = tuple(native_cell_rows)
    arguments = dict(
        native_cell_rows=points,
        inventory_path=inventory_path,
        records_path=records_path,
        locations_path=locations_path,
        intermission_ms=intermission_ms,
        native_geometry_source_sha256=native_geometry_source_sha256,
    )
    _, _, baseline = compile_pipeline(**arguments)
    _, _, races = compile_pipeline(
        **arguments,
        profile_modes=(2,),
        declared_character_races=True,
        schedule_version=2,
        prior_schedule_profiles=baseline["profiles"],
    )
    prior = baseline["profiles"] + races["profiles"]
    sql, census, manifest = compile_pipeline(
        **arguments,
        profile_modes=(3,),
        declared_resource_competitions=True,
        schedule_version=3,
        prior_schedule_profiles=prior,
    )
    manifest.update(
        declared_resource_competitions=True,
        reward_eligibility="all_eligible",
        tie_policy="character_id",
        prior_seed_profiles=len(prior),
        prior_profiles=prior,
        schedule_version=3,
        expected_combined_candidates=len(prior) + manifest["pipeline_profiles"],
    )
    return sql, census, manifest


def compile_result_policies(*, profile_rows, inventory_path=INVENTORY):
    """Supplement old unsealed resource profiles without rewriting their seeds.

    Insert these289/288 mappings before sealing; never unseal an existing policy.
    """
    scenarios = {
        row["id"]: row
        for row in json.loads(Path(inventory_path).read_text())["scenarios"]
    }
    lines = [
        "-- Explicit result mappings only. Import before sealing existing disabled profiles.",
        "BEGIN;",
    ]
    counts = Counter()
    seen = set()
    for row in profile_rows:
        key, identity = row["profile_key"], row["scenario_id"]
        if key in seen:
            raise ValueError("Duplicate resource result profile")
        seen.add(key)
        scenario = scenarios[identity]
        if scenario["subtype"] not in (1, 2, 4):
            raise ValueError(
                "Supplement requires original simple/race resource profiles"
            )
        rewards = scenario["rewards"]
        if len(rewards) != 1 or rewards[0]["text"] or not rewards[0]["flag"]:
            raise ValueError(
                "Supplement requires one original unconditional primary reward"
            )
        if scenario["subtype"] in (1, 4):
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
                        rewards[0]["id"],
                        "wakemu.original-resource-single-primary-base-result.v1",
                        0,
                        "personal_progress"
                        if scenario["subtype"] == 1
                        else "global_progress",
                        "original-single-unconditional-primary-list",
                        "original-primary-result-index-zero",
                        "wakemu.simple-resource-completed-objective-score.v1",
                    )
                ],
            )
            counts["simple_results"] += 1
        else:
            bands = _reward_bands(scenario)
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
                        "ranked_winners",
                        "original-single-unconditional-primary-list",
                        GENERATED_REWARD_AUTHORITY,
                        "winner_score",
                        None,
                        "wakemu.race-result-winning-position-one-score.v1",
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
            counts["race_results"] += 1
    lines.append("COMMIT;\n")
    sql = "\n".join(lines)
    return sql, dict(counts, sql_sha256=hashlib.sha256(sql.encode()).hexdigest())


def compile_evaluated_resource_criteria(
    *,
    native_cell_rows,
    inventory_path=INVENTORY,
    records_path=RECORDS,
    locations_path=LOCATIONS,
    intermission_ms=0,
    native_geometry_source_sha256=None,
):
    """Supplement only original nonempty criteria accepted by the real parser.

    Schema292 checks the existing original action/population relation. There is
    no new criterion child policy or lowered profile-level eligibility.
    """
    points = tuple(native_cell_rows)
    arguments = dict(
        native_cell_rows=points,
        inventory_path=inventory_path,
        records_path=records_path,
        locations_path=locations_path,
        intermission_ms=intermission_ms,
        native_geometry_source_sha256=native_geometry_source_sha256,
    )
    _, _, previous = compile_declared_competitions(**arguments)
    prior = previous["prior_profiles"] + previous["profiles"]
    sql, census, manifest = compile_pipeline(
        **arguments,
        profile_modes=(1, 2, 3, 4),
        declared_character_races=True,
        declared_resource_competitions=True,
        evaluated_resource_criteria=True,
        only_evaluated_criteria=True,
        schedule_version=4,
        prior_schedule_profiles=prior,
        schedule_all_prior_scopes=True,
    )
    modes = {
        row["id"]: row["subtype"]
        for row in json.loads(Path(inventory_path).read_text())["scenarios"]
    }
    result_rows = [
        row for row in manifest["profiles"] if modes[row["scenario_id"]] != 3
    ]
    results, result_manifest = compile_result_policies(
        profile_rows=result_rows, inventory_path=inventory_path
    )
    sql = sql.removesuffix("COMMIT;\n") + "\n" + results.replace("\nBEGIN;\n", "\n")
    manifest.update(
        evaluated_resource_criteria=True,
        criterion_authority="original280-action-sha;closed-parser;292-source-validator",
        prior_seed_profiles=len(prior),
        schedule_version=4,
        expected_combined_candidates=len(prior) + manifest["pipeline_profiles"],
        supplemental_results=result_manifest,
        sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
    )
    return sql, census, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-csv", type=Path)
    parser.add_argument(
        "--generate-source-policies",
        action="store_true",
        help="Declare versioned Wakemu base rewards and original seconds timing in bulk",
    )
    parser.add_argument(
        "--native-cell-csv",
        type=Path,
        help="Original map_id,region_id,x,y,z floor rows; enables complete disabled pipeline generation",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--declared-character-races",
        action="store_true",
        help="Opt in to separate Wakemu per-character race seed and schedule version2",
    )
    parser.add_argument(
        "--declared-resource-competitions",
        action="store_true",
        help="Opt in to separate original rank-band competitions and schedule version3",
    )
    parser.add_argument(
        "--evaluated-resource-level-criteria",
        action="store_true",
        help="Supplement only source criteria accepted by the closed current-effective-level parser",
    )
    parser.add_argument(
        "--seed-output",
        type=Path,
        nargs="?",
        const=SEED_PATH,
        help="Explicitly persist the complete disabled SQL seed; defaults to server/seeds/environmental_resource_profiles.sql",
    )
    args = parser.parse_args()
    if args.policy_csv and args.generate_source_policies:
        parser.error("Choose explicit CSV or generated source policy")
    if args.native_cell_csv and not args.generate_source_policies:
        parser.error("Native geometry requires generated source policies")
    if args.seed_output and not args.native_cell_csv:
        parser.error(
            "A persisted seed requires the complete original-geometry pipeline"
        )
    if (
        sum(
            (
                args.declared_character_races,
                args.declared_resource_competitions,
                args.evaluated_resource_level_criteria,
            )
        )
        > 1
    ):
        parser.error("Choose one separate declared mode cohort")
    if (
        args.declared_character_races
        or args.declared_resource_competitions
        or args.evaluated_resource_level_criteria
    ):
        if not args.native_cell_csv or not args.generate_source_policies:
            parser.error(
                "Declared races require generated source policies and complete original geometry"
            )
        if args.output_dir == DEFAULT_OUTPUT:
            args.output_dir = DEFAULT_OUTPUT.with_name(
                "environmental-resource-level-criteria-compiler"
                if args.evaluated_resource_level_criteria
                else "environmental-resource-race-compiler"
                if args.declared_character_races
                else "environmental-resource-competition-compiler"
            )
        if args.seed_output == SEED_PATH:
            args.seed_output = (
                CRITERIA_SEED_PATH
                if args.evaluated_resource_level_criteria
                else RACE_SEED_PATH
                if args.declared_character_races
                else COMPETITIVE_SEED_PATH
            )
    omissions = []
    rows = policies(args.policy_csv)
    if args.generate_source_policies:
        rows, omissions = generate_policies(
            include_competitive=args.declared_resource_competitions
            or args.evaluated_resource_level_criteria,
            evaluated_resource_criteria=args.evaluated_resource_level_criteria,
        )
        if args.declared_character_races or args.declared_resource_competitions:
            target_mode = 2 if args.declared_character_races else 3
            ids = {
                row["id"]
                for row in json.loads(INVENTORY.read_text())["scenarios"]
                if row["subtype"] == target_mode
            }
            rows = tuple(row for row in rows if row["scenario_id"] in ids)
        elif args.evaluated_resource_level_criteria:
            _, original_rows, _ = compile_profiles()
            ids = {
                row["scenario_id"] for row in original_rows if row["native_criteria"]
            }
            rows = tuple(row for row in rows if row["scenario_id"] in ids)
    sql, census, summary = compile_profiles(policy_rows=rows)
    pipeline_manifest = None
    if args.native_cell_csv:
        with args.native_cell_csv.open(newline="") as stream:
            cells = [
                {key: int(row[key]) for key in ("map_id", "region_id", "x", "y", "z")}
                for row in csv.DictReader(stream)
            ]
        pipeline = (
            compile_evaluated_resource_criteria
            if args.evaluated_resource_level_criteria
            else compile_declared_competitions
            if args.declared_resource_competitions
            else compile_declared_races
            if args.declared_character_races
            else compile_pipeline
        )
        sql, census, pipeline_manifest = pipeline(
            native_cell_rows=cells,
            native_geometry_source_sha256=hashlib.sha256(
                args.native_cell_csv.read_bytes()
            ).hexdigest(),
        )
        summary = {
            key: value
            for key, value in pipeline_manifest.items()
            if key not in ("profiles", "omissions", "prior_profiles")
        }
    if args.generate_source_policies:
        summary["generated_policy_scenarios"] = len(
            {row["scenario_id"] for row in rows}
        )
        summary["generated_policy_location_rows"] = len(rows)
        summary["omitted_location_rows"] = len(omissions)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "disabled-resource-profiles.sql").write_text(sql)
    if args.seed_output:
        args.seed_output.parent.mkdir(parents=True, exist_ok=True)
        args.seed_output.write_bytes(sql.encode("utf-8"))
        if args.declared_resource_competitions:
            result_sql, result_manifest = compile_result_policies(
                profile_rows=pipeline_manifest["prior_profiles"]
            )
            RESULT_SEED_PATH.write_bytes(result_sql.encode("utf-8"))
            (args.output_dir / "result-policy-manifest.json").write_text(
                json.dumps(result_manifest, indent=2) + "\n"
            )
    (args.output_dir / "resource-profile-census.json").write_text(
        json.dumps(census, indent=2) + "\n"
    )
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    if pipeline_manifest is not None:
        (args.output_dir / "pipeline-manifest.json").write_text(
            json.dumps(pipeline_manifest, indent=2) + "\n"
        )
    with (args.output_dir / "policy-template.csv").open("w", newline="") as stream:
        csv.writer(stream).writerow(POLICY_COLUMNS)
    if args.generate_source_policies:
        with (args.output_dir / "generated-resource-policies.csv").open(
            "w", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=POLICY_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        (args.output_dir / "policy-omissions.json").write_text(
            json.dumps(omissions, indent=2) + "\n"
        )
        with (args.output_dir / "resource-policy-candidate-census.csv").open(
            "w", newline=""
        ) as stream:
            fields = (
                "scenario_id",
                "native_subtype",
                "mode",
                "duration_ms",
                "resource_reference",
                "resource_step",
                "action_id",
                "personal_threshold",
                "global_spawn_count",
                "required_quantity",
                "minimum_contribution",
                "runtime_support",
            )
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            for row in census:
                if (
                    row["action_id"] is None
                    or row["native_criteria"]
                    or row["item_reference"]
                    or row["product_references"]
                ):
                    continue
                mode = {1: "solo", 2: "race", 3: "competitive", 4: "collaborative"}[
                    row["native_subtype"]
                ]
                writer.writerow(
                    dict(
                        scenario_id=row["scenario_id"],
                        native_subtype=row["native_subtype"],
                        mode=mode,
                        duration_ms=row["native_duration_raw"] * 1000,
                        resource_reference=row["resource_reference"],
                        resource_step=row["resource_step"],
                        action_id=row["action_id"],
                        personal_threshold=row["required_quantity"],
                        global_spawn_count=row["spawn_quantity"],
                        required_quantity=row["spawn_quantity"]
                        if mode == "collaborative"
                        else row["required_quantity"],
                        minimum_contribution=row["required_quantity"],
                        runtime_support="disabled_candidate"
                        if mode in ("solo", "collaborative")
                        else "unqualified_winner_limit"
                        if mode == "race"
                        else "unqualified_rank_band_rewards",
                    )
                )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
