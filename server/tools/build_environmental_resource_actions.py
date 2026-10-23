"""Join original scenario resource stages to original actions, without activation.

Consumes a small read-only indexed export, not the combat runtime or full native
catalog. Mission eligibility, reward, XP, spawn and depletion rules are not
inferred from resource metadata.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_KEY = "installed-environmental-source-v1"
REVISION = "b3963fc05f1d8ec1eb9afc268fab0350f4de120144d67f7eee470747750b2450"
INVENTORY_SHA = "af1118a14c193f7b63683cf360d887a38cdcedc415e5ec70a492ed6460b752d1"
RESOURCE_SHA = "2397948397dbd0ed9b30d3d7905f4b3e726bf384dd0766436f0fa02f5637a4e2"
SEED_SHA = "a7fcc2399caeb4cd006de74d273f1d23bd8bfc9245b2000455c6212ff43cd4f0"
SUBSET_SHA = "20b48759ba4b57dd161f8583f1abcdba25d92e9750f9702de40230f83db7c07c"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError("Invalid original resource integer")
    return value


def scalar(value):
    if value is None:
        return "NULL"
    if type(value) is bool:
        return "TRUE" if value else "FALSE"
    if type(value) is int:
        return str(value)
    if not isinstance(value, str) or "\0" in value:
        raise ValueError("Invalid source SQL scalar")
    return "E'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def insert(lines, table, columns, rows):
    rows = list(rows)
    if rows:
        lines.append(
            f"INSERT INTO {table} ({','.join(columns)}) VALUES\n"
            + ",\n".join("(" + ",".join(map(scalar, row)) + ")" for row in rows)
            + ";"
        )


def build(inventory_path, records_path):
    raw = Path(inventory_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != INVENTORY_SHA:
        raise ValueError("Original environmental source hash changed")
    inventory = json.loads(raw)
    export = json.loads(Path(records_path).read_text())
    resources = sorted(
        (r["payload"] for r in export["plant-resources.json"]),
        key=lambda r: r["resource_reference"],
    )
    seeds = [r["payload"] for r in export["seed-actions.json"]]
    if digest(dict(resources=resources, seeds=seeds)) != SUBSET_SHA:
        raise ValueError("Original resource/seed subset differs from reviewed source")
    by_ref = {integer(r["resource_reference"], 1): r for r in resources}
    if len(resources) != 80 or len(by_ref) != 80 or seeds:
        raise ValueError("Native resource universe changed")
    bindings, actions = [], {}
    for scenario in inventory["scenarios"]:
        config = {}
        for key, value in scenario["configuration"].items():
            if key.lower() in config and config[key.lower()] != value:
                raise ValueError("Ambiguous original configuration key")
            config[key.lower()] = value
        if "ressourcerefid" not in config:
            continue
        ref, step = int(config["ressourcerefid"]), int(config["ressourcestep"])
        resource = by_ref[ref]
        stage_rows = [s for s in resource["stage_definitions"] if s["stage_id"] == step]
        if len(stage_rows) > 1:
            raise ValueError("Duplicate original resource stage")
        native_actions = stage_rows[0]["actions"] if stage_rows else []
        if len(native_actions) > 1:
            raise ValueError("Resource stage no longer has a unique original action")
        action = native_actions[0] if native_actions else None
        if action is not None:
            for field in (
                "action_id",
                "profession_id",
                "minimum_level",
                "duration_ms",
                "item_reference",
            ):
                integer(action[field])
            actions[(ref, step, 0)] = action
        bindings.append(
            dict(
                scenario_id=scenario["id"],
                resource_reference=ref,
                resource_step=step,
                action_ordinal=0 if action else None,
                action_id=action["action_id"] if action else None,
                status="matched_original_action"
                if action
                else "missing_original_stage",
                native_record_sha256=digest(resource),
                available_stages=resource["stages"],
            )
        )
    bindings.sort(key=lambda r: r["scenario_id"])
    if (
        len(bindings),
        len(actions),
        sum(b["action_id"] is not None for b in bindings),
    ) != (313, 78, 305):
        raise ValueError("Reviewed313/78/305 source denominator changed")
    if {b["resource_reference"] for b in bindings} != set(by_ref):
        raise ValueError("Export includes missing or unrelated resource definitions")
    return resources, actions, bindings


DDL = """-- Original source evidence only: no profiles, activation, XP or depletion policy.
CREATE TABLE environmental_resource_action_source_versions (
 source_key text PRIMARY KEY REFERENCES environmental_native_source_versions,
 catalog_revision text NOT NULL CHECK(length(catalog_revision)=64),
 inventory_sha256 text NOT NULL CHECK(length(inventory_sha256)=64),
 resource_document_sha256 text NOT NULL CHECK(length(resource_document_sha256)=64),
 seed_document_sha256 text NOT NULL CHECK(length(seed_document_sha256)=64),
 reviewed_subset_sha256 text NOT NULL CHECK(length(reviewed_subset_sha256)=64),
 resource_count integer NOT NULL CHECK(resource_count=80),
 scenario_count integer NOT NULL CHECK(scenario_count=313),
 matched_scenario_count integer NOT NULL CHECK(matched_scenario_count=305),
 missing_stage_count integer NOT NULL CHECK(missing_stage_count=8),
 action_count integer NOT NULL CHECK(action_count=78),
 server_activation_authorized boolean NOT NULL DEFAULT FALSE CHECK(NOT server_activation_authorized)
);
CREATE TABLE environmental_original_resources (
 source_key text NOT NULL REFERENCES environmental_resource_action_source_versions,
 resource_reference integer NOT NULL CHECK(resource_reference>0),
 record_sha256 text NOT NULL CHECK(length(record_sha256)=64),
 original_record jsonb NOT NULL CHECK(jsonb_typeof(original_record)='object'),
 PRIMARY KEY(source_key,resource_reference),
 CHECK((original_record->>'resource_reference')::integer=resource_reference)
);
CREATE TABLE environmental_original_resource_actions (
 source_key text NOT NULL,resource_reference integer NOT NULL,native_step integer NOT NULL,
 action_ordinal integer NOT NULL CHECK(action_ordinal>=0), action_id integer NOT NULL CHECK(action_id>0),
 profession_id integer NOT NULL CHECK(profession_id>=0),minimum_level integer NOT NULL CHECK(minimum_level>=0),
 duration_ms bigint NOT NULL CHECK(duration_ms>=0),native_criteria text NOT NULL,
 item_reference integer NOT NULL CHECK(item_reference>=0),
 product_references jsonb NOT NULL CHECK(jsonb_typeof(product_references)='array'),
 raw_getters jsonb NOT NULL CHECK(jsonb_typeof(raw_getters)='object'),
 original_action jsonb NOT NULL CHECK(jsonb_typeof(original_action)='object'),
 action_sha256 text NOT NULL CHECK(length(action_sha256)=64),
 PRIMARY KEY(source_key,resource_reference,native_step,action_ordinal),
 FOREIGN KEY(source_key,resource_reference) REFERENCES environmental_original_resources,
 CHECK((original_action->>'action_id')::integer=action_id)
);
CREATE TABLE environmental_scenario_resource_actions (
 source_key text NOT NULL,scenario_id integer NOT NULL,resource_reference integer NOT NULL,
 native_step integer NOT NULL,action_ordinal integer,
 status text NOT NULL CHECK(status IN ('matched_original_action','missing_original_stage')),
 PRIMARY KEY(source_key,scenario_id),
 FOREIGN KEY(source_key,scenario_id) REFERENCES environmental_native_scenarios,
 FOREIGN KEY(source_key,resource_reference) REFERENCES environmental_original_resources,
 FOREIGN KEY(source_key,resource_reference,native_step,action_ordinal)
 REFERENCES environmental_original_resource_actions,
 CHECK((status='matched_original_action' AND action_ordinal IS NOT NULL)
    OR (status='missing_original_stage' AND action_ordinal IS NULL))
);
"""


def render_sql(resources, actions, bindings):
    lines = [DDL]
    insert(
        lines,
        "environmental_resource_action_source_versions",
        (
            "source_key",
            "catalog_revision",
            "inventory_sha256",
            "resource_document_sha256",
            "seed_document_sha256",
            "reviewed_subset_sha256",
            "resource_count",
            "scenario_count",
            "matched_scenario_count",
            "missing_stage_count",
            "action_count",
        ),
        [
            (
                SOURCE_KEY,
                REVISION,
                INVENTORY_SHA,
                RESOURCE_SHA,
                SEED_SHA,
                SUBSET_SHA,
                80,
                313,
                305,
                8,
                78,
            )
        ],
    )
    insert(
        lines,
        "environmental_original_resources",
        ("source_key", "resource_reference", "record_sha256", "original_record"),
        [
            (SOURCE_KEY, r["resource_reference"], digest(r), canonical(r))
            for r in resources
        ],
    )
    insert(
        lines,
        "environmental_original_resource_actions",
        (
            "source_key",
            "resource_reference",
            "native_step",
            "action_ordinal",
            "action_id",
            "profession_id",
            "minimum_level",
            "duration_ms",
            "native_criteria",
            "item_reference",
            "product_references",
            "raw_getters",
            "original_action",
            "action_sha256",
        ),
        [
            (
                SOURCE_KEY,
                ref,
                step,
                ordinal,
                a["action_id"],
                a["profession_id"],
                a["minimum_level"],
                a["duration_ms"],
                a["criteria"],
                a["item_reference"],
                canonical(a["product_references"]),
                canonical(a["raw_getters"]),
                canonical(a),
                digest(a),
            )
            for (ref, step, ordinal), a in sorted(actions.items())
        ],
    )
    insert(
        lines,
        "environmental_scenario_resource_actions",
        (
            "source_key",
            "scenario_id",
            "resource_reference",
            "native_step",
            "action_ordinal",
            "status",
        ),
        [
            (
                SOURCE_KEY,
                b["scenario_id"],
                b["resource_reference"],
                b["resource_step"],
                b["action_ordinal"],
                b["status"],
            )
            for b in bindings
        ],
    )
    for table in (
        "environmental_resource_action_source_versions",
        "environmental_original_resources",
        "environmental_original_resource_actions",
        "environmental_scenario_resource_actions",
    ):
        lines.append(
            f"CREATE TRIGGER immutable_source BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION reject_environmental_native_source_mutation();"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--inventory",
        type=Path,
        default=ROOT
        / "agents_docs/reports/recurring-missions/ENVIRONMENTAL-SCENARIOS-INVENTORY-20261011.json",
    )
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--sql", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    args = parser.parse_args()
    resources, actions, bindings = build(args.inventory, args.records)
    args.sql.write_text(render_sql(resources, actions, bindings))
    with args.csv.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=tuple(bindings[0]))
        writer.writeheader()
        writer.writerows(
            {**b, "available_stages": canonical(b["available_stages"])}
            for b in bindings
        )
    print(
        f"Source only: {len(resources)} resources, {len(actions)} actions, "
        f"{sum(b['action_id'] is not None for b in bindings)} matched / {len(bindings)} scenarios"
    )


if __name__ == "__main__":
    main()
