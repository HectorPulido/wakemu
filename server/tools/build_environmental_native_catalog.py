"""Build normalized source-only environmental SQL and finite classifications.

This offline importer never activates an event or interprets unqualified reward
accessors, template IDs, action steps, or scenario duration units as game rules.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "agents_docs/reports/parallel-readiness-20261021"
SOURCE = ROOT / "agents_docs/reports/recurring-missions"
GUILD_DAILIES = frozenset((1389, 1390, 1391))


def scenario_family(configuration):
    keys = {key.lower() for key in configuration}
    if "nbportalgroupforbossspawn" in keys:
        return "portal_boss_chain"
    if "ressourcerefid" in keys:
        return "resource_interaction"
    if "monsteractiontypeid" in keys:
        return "destroy_monster_action"
    if "usergrouptemplateid" in keys:
        return "group_template"
    raise ValueError("Unclassified native scenario configuration")


def recurring_family(row):
    identity = row["definition_id"]
    ancestors = set(row["category_ancestor_ids"])
    if identity in GUILD_DAILIES:
        return "implemented_guild_daily"
    if 98 in ancestors or "almanax" in row["title_en"].lower():
        return "excluded_almanax"
    for category, name in (
        (517, "trade_hunt_contract_candidate"),
        (513, "scoreboard_contract_candidate"),
        (325, "seasonal_contract_candidate"),
        (682, "training_contract_candidate"),
        (939, "environmental_meta_candidate"),
        (776, "boss_smasher_candidate"),
    ):
        if category in ancestors:
            return name
    return (
        "journal_producer_unresolved"
        if row["native_is_quest"]
        else "achievement_producer_unresolved"
    )


def quoted(value):
    if value is None:
        return "NULL"
    if type(value) is bool:
        return "TRUE" if value else "FALSE"
    if type(value) is int:
        return str(value)
    if not isinstance(value, str) or "\0" in value:
        raise ValueError("Invalid SQL source scalar")
    return "'" + value.replace("'", "''") + "'"


def insert(stream, table, columns, rows):
    rows = list(rows)
    for offset in range(0, len(rows), 500):
        stream.write(f"INSERT INTO {table} ({','.join(columns)}) VALUES\n")
        stream.write(
            ",\n".join(
                "(" + ",".join(map(quoted, row)) + ")"
                for row in rows[offset : offset + 500]
            )
        )
        stream.write(";\n")


def load_sources():
    environment_path = SOURCE / "ENVIRONMENTAL-SCENARIOS-INVENTORY-20261011.json"
    recurring_path = SOURCE / "NATIVE-RECURRING-MISSIONS-INVENTORY-20261011.json"
    environment = json.loads(environment_path.read_text())
    recurring = json.loads(recurring_path.read_text())["definitions"]
    scenarios = environment["scenarios"]
    ids = {row["id"] for row in scenarios}
    if len(ids) != len(scenarios) or len(ids) != 1208:
        raise ValueError("Native scenario census changed or contains duplicates")
    if (
        len({row["definition_id"] for row in recurring}) != len(recurring)
        or len(recurring) != 700
    ):
        raise ValueError("Native recurring census changed or contains duplicates")
    for group in environment["groups"]:
        if any(member["challenge_id"] not in ids for member in group["members"]):
            raise ValueError("Unresolved protector challenge membership")
    for row in scenarios:
        normalized = {}
        for key, value in row["configuration"].items():
            if key.lower() in normalized and normalized[key.lower()] != value:
                raise ValueError("Conflicting case-normalized native parameter")
            normalized[key.lower()] = value
        scenario_family(row["configuration"])
        if len(set(row["variables"])) != len(row["variables"]):
            raise ValueError("Duplicate native ordered variable identity")
    return (
        environment,
        recurring,
        {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (environment_path, recurring_path)
        },
    )


def write_classification(environment, recurring, output):
    scenarios = environment["scenarios"]
    fields = (
        "scenario_id",
        "native_type",
        "native_subtype",
        "family",
        "assigned",
        "source_adapter_ready",
        "activation_ready",
        "missing_authority",
    )
    with (output / "environmental-source-family-classification.csv").open(
        "w", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in scenarios:
            family = scenario_family(row["configuration"])
            missing = [
                "protector_region_binding",
                "duration_consumer",
                "participant_evaluator",
                "reward_settlement_semantics",
            ]
            if family in ("group_template", "destroy_monster_action"):
                missing.append("native_template_roster")
            elif family == "resource_interaction":
                missing.append("resource_step_action_consumer")
            else:
                missing.append("portal_stage_transition_consumers")
            if row["native_type_name"] == "NOT_A_CHALLENGE":
                missing.append("native_nonchallenge_applicability")
            if not row["group_memberships"]:
                missing.append("unassigned_definition")
            writer.writerow(
                dict(
                    scenario_id=row["id"],
                    native_type=row["native_type_name"],
                    native_subtype=row["native_subtype_name"],
                    family=family,
                    assigned=bool(row["group_memberships"]),
                    source_adapter_ready=True,
                    activation_ready=False,
                    missing_authority=";".join(missing),
                )
            )
    with (output / "recurring-source-family-classification.csv").open(
        "w", newline=""
    ) as stream:
        writer = csv.writer(stream)
        writer.writerow(
            (
                "definition_id",
                "title_en",
                "native_is_quest",
                "family",
                "automatic_activation",
                "reason",
            )
        )
        for row in recurring:
            family = recurring_family(row)
            implemented = family == "implemented_guild_daily"
            reason = (
                "existing_original_guild_producer"
                if implemented
                else "almanax_out_of_scope"
                if family == "excluded_almanax"
                else "recurrence_metadata_does_not_identify_original_activation_objective_producer"
            )
            writer.writerow(
                (
                    row["definition_id"],
                    row["title_en"],
                    row["native_is_quest"],
                    family,
                    implemented,
                    reason,
                )
            )


def build(output):
    environment, recurring, hashes = load_sources()
    output.mkdir(parents=True, exist_ok=True)
    write_classification(environment, recurring, output)
    summary = {
        "environmental_definitions": 1208,
        "environmental_assigned": sum(
            bool(row["group_memberships"]) for row in environment["scenarios"]
        ),
        "environmental_families": dict(
            collections.Counter(
                scenario_family(row["configuration"])
                for row in environment["scenarios"]
            )
        ),
        "environmental_activation_qualified_from_recovered_data": 0,
        "recurring_candidates": 700,
        "recurring_families": dict(
            collections.Counter(recurring_family(row) for row in recurring)
        ),
        "source_hashes": hashes,
    }
    (output / "environmental-bulk-source-summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )
    return environment, recurring, summary


SOURCE_DDL = """
CREATE TABLE environmental_native_source_versions (
 source_key text PRIMARY KEY, source_sha256 text NOT NULL CHECK(length(source_sha256)=64),
 scenario_count integer NOT NULL CHECK(scenario_count=1208),
 objective_count integer NOT NULL, reward_count integer NOT NULL
);
CREATE TABLE environmental_native_scenarios (
 source_key text NOT NULL REFERENCES environmental_native_source_versions,
 scenario_id integer NOT NULL, native_type smallint NOT NULL, native_subtype smallint NOT NULL,
 client_visible boolean NOT NULL, duration_raw bigint NOT NULL,
 family text NOT NULL CHECK(family IN ('group_template','resource_interaction','destroy_monster_action','portal_boss_chain')),
 assigned boolean NOT NULL, activation_qualified boolean NOT NULL DEFAULT FALSE CHECK(NOT activation_qualified),
 PRIMARY KEY(source_key,scenario_id)
);
CREATE TABLE environmental_native_configuration (
 source_key text NOT NULL, scenario_id integer NOT NULL, native_key text NOT NULL,
 normalized_key text NOT NULL, native_value text NOT NULL,
 PRIMARY KEY(source_key,scenario_id,native_key),
 FOREIGN KEY(source_key,scenario_id) REFERENCES environmental_native_scenarios
);
CREATE TABLE environmental_native_variables (
 source_key text NOT NULL, scenario_id integer NOT NULL, ordinal integer NOT NULL CHECK(ordinal>=0), native_name text NOT NULL,
 PRIMARY KEY(source_key,scenario_id,ordinal), UNIQUE(source_key,scenario_id,native_name),
 FOREIGN KEY(source_key,scenario_id) REFERENCES environmental_native_scenarios
);
CREATE TABLE environmental_native_objectives (
 source_key text NOT NULL, scenario_id integer NOT NULL, objective_id integer NOT NULL,
 native_target bigint NOT NULL, native_label text NOT NULL, native_expression text NOT NULL,
 client_visible boolean NOT NULL, native_flag boolean NOT NULL,
 PRIMARY KEY(source_key,scenario_id,objective_id),
 FOREIGN KEY(source_key,scenario_id) REFERENCES environmental_native_scenarios
);
CREATE TABLE environmental_native_rewards_raw (
 source_key text NOT NULL, scenario_id integer NOT NULL, reward_id integer NOT NULL,
 field_ahj bigint NOT NULL, field_ago bigint NOT NULL, field_ahk bigint NOT NULL,
 field_xk bigint NOT NULL, field_ahf bigint NOT NULL, field_ahh bigint NOT NULL,
 field_aai bigint NOT NULL, native_flag boolean NOT NULL, native_text text NOT NULL,
 PRIMARY KEY(source_key,scenario_id,reward_id),
 FOREIGN KEY(source_key,scenario_id) REFERENCES environmental_native_scenarios
);
CREATE TABLE environmental_native_challenge_groups (
 source_key text NOT NULL REFERENCES environmental_native_source_versions, group_id integer NOT NULL,
 PRIMARY KEY(source_key,group_id)
);
CREATE TABLE environmental_native_group_members (
 source_key text NOT NULL, group_id integer NOT NULL, ordinal integer NOT NULL CHECK(ordinal>=0),
 scenario_id integer NOT NULL, native_criteria text NOT NULL,
 PRIMARY KEY(source_key,group_id,ordinal),
 FOREIGN KEY(source_key,group_id) REFERENCES environmental_native_challenge_groups,
 FOREIGN KEY(source_key,scenario_id) REFERENCES environmental_native_scenarios
);
CREATE TABLE environmental_native_protector_groups (
 source_key text NOT NULL, protector_id integer NOT NULL, ordinal integer NOT NULL CHECK(ordinal>=0), group_id integer NOT NULL,
 PRIMARY KEY(source_key,protector_id,ordinal),
 FOREIGN KEY(source_key,group_id) REFERENCES environmental_native_challenge_groups
);
"""


def write_sql(environment, hashes, path):
    scenarios = environment["scenarios"]
    source_key = "installed-environmental-source-v1"
    source_hash = next(
        value for name, value in hashes.items() if "ENVIRONMENTAL-SCENARIOS" in name
    )

    def prefixed(rows):
        return ((source_key, *row) for row in rows)

    with path.open("w") as stream:
        stream.write(
            "-- Source inventory only; no event profile, activation, reward grant or recurring-story import.\n"
        )
        stream.write(SOURCE_DDL)
        insert(
            stream,
            "environmental_native_source_versions",
            (
                "source_key",
                "source_sha256",
                "scenario_count",
                "objective_count",
                "reward_count",
            ),
            [
                (
                    source_key,
                    source_hash,
                    len(scenarios),
                    sum(len(row["objectives"]) for row in scenarios),
                    sum(len(row["rewards"]) for row in scenarios),
                )
            ],
        )
        insert(
            stream,
            "environmental_native_scenarios",
            (
                "source_key",
                "scenario_id",
                "native_type",
                "native_subtype",
                "client_visible",
                "duration_raw",
                "family",
                "assigned",
            ),
            prefixed(
                (
                    row["id"],
                    row["type"],
                    row["subtype"],
                    row["client"],
                    row["duration_raw"],
                    scenario_family(row["configuration"]),
                    bool(row["group_memberships"]),
                )
                for row in scenarios
            ),
        )
        insert(
            stream,
            "environmental_native_configuration",
            (
                "source_key",
                "scenario_id",
                "native_key",
                "normalized_key",
                "native_value",
            ),
            prefixed(
                (row["id"], key, key.lower(), value)
                for row in scenarios
                for key, value in row["configuration"].items()
            ),
        )
        insert(
            stream,
            "environmental_native_variables",
            ("source_key", "scenario_id", "ordinal", "native_name"),
            prefixed(
                (row["id"], index, name)
                for row in scenarios
                for index, name in enumerate(row["variables"])
            ),
        )
        insert(
            stream,
            "environmental_native_objectives",
            (
                "source_key",
                "scenario_id",
                "objective_id",
                "native_target",
                "native_label",
                "native_expression",
                "client_visible",
                "native_flag",
            ),
            prefixed(
                (
                    row["id"],
                    obj["id"],
                    obj["target"],
                    obj["label"],
                    obj["expression"],
                    obj["client"],
                    obj["flag"],
                )
                for row in scenarios
                for obj in row["objectives"]
            ),
        )
        insert(
            stream,
            "environmental_native_rewards_raw",
            (
                "source_key",
                "scenario_id",
                "reward_id",
                "field_ahj",
                "field_ago",
                "field_ahk",
                "field_xk",
                "field_ahf",
                "field_ahh",
                "field_aai",
                "native_flag",
                "native_text",
            ),
            prefixed(
                (
                    row["id"],
                    obj["id"],
                    obj["field_aHj"],
                    obj["field_agO"],
                    obj["field_aHk"],
                    obj["field_Xk"],
                    obj["field_aHf"],
                    obj["field_aHh"],
                    obj["field_aAi"],
                    obj["flag"],
                    obj["text"],
                )
                for row in scenarios
                for obj in row["rewards"]
            ),
        )
        insert(
            stream,
            "environmental_native_challenge_groups",
            ("source_key", "group_id"),
            prefixed((row["group_id"],) for row in environment["groups"]),
        )
        insert(
            stream,
            "environmental_native_group_members",
            ("source_key", "group_id", "ordinal", "scenario_id", "native_criteria"),
            prefixed(
                (row["group_id"], index, member["challenge_id"], member["criteria"])
                for row in environment["groups"]
                for index, member in enumerate(row["members"])
            ),
        )
        insert(
            stream,
            "environmental_native_protector_groups",
            ("source_key", "protector_id", "ordinal", "group_id"),
            prefixed(
                (row["protector_id"], index, group)
                for row in environment["protector_assignments"]
                for index, group in enumerate(row["challenge_group_ids"])
            ),
        )

        stream.write(
            "CREATE FUNCTION reject_environmental_native_source_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Environmental native source is append-only'; END $$;\n"
        )
        for suffix in IMMUTABLE_TABLES:
            table = "environmental_native_" + suffix
            stream.write(
                f"CREATE TRIGGER immutable_source BEFORE UPDATE OR DELETE ON {table} FOR EACH ROW EXECUTE FUNCTION reject_environmental_native_source_mutation();\n"
            )
        stream.write(REWARD_DISPLAY_VIEW)


IMMUTABLE_TABLES = (
    "source_versions",
    "scenarios",
    "configuration",
    "variables",
    "objectives",
    "rewards_raw",
    "challenge_groups",
    "group_members",
    "protector_groups",
)


REWARD_DISPLAY_VIEW = """
-- Original bhO -> bhF -> bhS -> bhR display consumers. Never grants rewards.
CREATE VIEW environmental_native_reward_display AS
WITH ordered AS (
 SELECT r.*,count(*) OVER(PARTITION BY source_key,scenario_id,native_flag,field_ahh) AS order_population,
 row_number() OVER(PARTITION BY source_key,scenario_id,native_flag ORDER BY field_ahh) AS display_position
 FROM environmental_native_rewards_raw r
)
SELECT source_key,scenario_id,reward_id,field_aai AS item_reference,field_ahj AS item_quantity,
 field_ago AS base_xp,field_ahk AS kamas,field_ahh AS display_order,
 native_flag AS primary_reward_list,
 CASE WHEN native_flag AND order_population=1 THEN display_position-1 ELSE NULL END AS primary_result_index,
 false AS server_grant_authorized
FROM ordered;
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPORT)
    parser.add_argument("--sql", type=Path)
    args = parser.parse_args()
    environment, _, summary = build(args.output)
    if args.sql is not None:
        write_sql(environment, summary["source_hashes"], args.sql)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
