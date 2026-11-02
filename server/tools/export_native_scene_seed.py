"""Export only sealed normalized scene authority for public clean installations.

No player, inventory, receipt, selection or runtime-instance data is read.
Legacy settings are not a fallback or a target for gameplay rule publication.
"""
import json
import re
from psycopg.sql import Literal

# Explicit public columns; created_at and all player data are deliberately absent.
COLUMNS = {
    "native_scene_policies": [
        ("policy_id", "text"),
        ("authority", "text"),
        ("policy_sha256", "text"),
        ("published", "boolean"),
        ("map_id", "integer"),
        ("definition_id", "integer"),
        ("template_id", "integer"),
        ("source_id", "bigint"),
        ("wire_action", "integer"),
        ("descriptor_id", "integer"),
        ("catalog_revision", "text"),
        ("native_group_id", "integer"),
        ("native_action_id", "integer"),
        ("native_script_reference", "integer"),
        ("native_criterion", "text"),
        ("price_item_id", "integer"),
        ("price_quantity", "integer"),
        ("maximum_members", "integer"),
        ("competitive_ceiling", "integer"),
        ("profile_mode", "text"),
        ("profile_provenance", "text"),
        ("compiled_plan_sha256", "text"),
        ("combat_anchor_x", "integer"),
        ("combat_anchor_y", "integer"),
        ("combat_anchor_z", "integer"),
        ("combat_area_provenance", "text"),
        ("scene_source_uri", "text"),
        ("native_border_reference", "integer"),
        ("environment_enabled", "boolean"),
        ("environment_reserve_spawn_slots", "boolean"),
        ("environment_area_reference", "integer"),
        ("environment_level", "integer"),
        ("environment_coordinate_authority", "text"),
        ("environment_map_graphics_sha256", "text"),
        ("environment_provenance", "text"),
        ("environment_source_uri", "text"),
        ("native_descriptor", "jsonb"),
        ("native_effects", "jsonb"),
        ("source_provenance", "jsonb"),
    ],
    "native_scene_policy_objects": [
        ("policy_id", "text"),
        ("object_role", "text"),
        ("ordinal", "integer"),
        ("object_id", "bigint"),
        ("native_type", "text"),
        ("x", "integer"),
        ("y", "integer"),
        ("z", "integer"),
        ("payload_hex", "text"),
    ],
    "native_scene_policy_approaches": [
        ("policy_id", "text"),
        ("ordinal", "integer"),
        ("x", "integer"),
        ("y", "integer"),
        ("z", "integer"),
    ],
    "native_scene_policy_combat_cells": [
        ("policy_id", "text"),
        ("ordinal", "integer"),
        ("x", "integer"),
        ("y", "integer"),
        ("z", "integer"),
    ],
    "native_scene_profile_states": [
        ("policy_id", "text"),
        ("ordinal", "integer"),
        ("state_id", "integer"),
        ("source_sha256", "text"),
    ],
    "native_scene_profile_state_levels": [
        ("policy_id", "text"),
        ("state_ordinal", "integer"),
        ("ordinal", "integer"),
        ("level", "integer"),
    ],
    "native_scene_profile_targets": [
        ("policy_id", "text"),
        ("ordinal", "integer"),
        ("reference_id", "integer"),
    ],
    "native_scene_environment_placements": [
        ("policy_id", "text"),
        ("ordinal", "integer"),
        ("x", "integer"),
        ("y", "integer"),
        ("z", "integer"),
        ("area_reference", "integer"),
        ("level", "integer"),
        ("original_graphic", "integer"),
    ],
    "native_scene_admission_policies": [
        ("policy_id", "text"),
        ("admission_policy_id", "text"),
        ("admission_sha256", "text"),
        ("route_key", "text"),
        ("authority", "text"),
        ("entry_map_id", "integer"),
        ("entry_object_id", "bigint"),
        ("destination_id", "integer"),
        ("minimum_configuration_version", "integer"),
        ("provenance", "text"),
    ],
}


def _schema(value):
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value) is None
    ):
        raise ValueError("Invalid installation target schema")
    return value


def _literal(value, kind):
    if kind == "jsonb":
        return (
            Literal(json.dumps(value, sort_keys=True, allow_nan=False)).as_string()
            + "::jsonb"
        )
    return Literal(value).as_string()


def scene_rows(db, configurations):
    """Read the policies pinned by every exported immutable configuration."""
    required = {}
    for row in configurations:
        config = row["configuration"]
        binding = config["topology"].get("native_scene_start")
        if binding is not None:
            if not isinstance(binding, dict) or not isinstance(
                binding.get("policy_id"), str
            ):
                raise ValueError(
                    "Dungeon configuration has an invalid paid-scene binding"
                )
            required.setdefault(binding["policy_id"], set()).add(row["route_key"])
    if not required:
        return {}
    present = db.execute(
        "SELECT to_regclass('native_scene_policies') AS relation"
    ).fetchone()
    if present is None or present["relation"] is None:
        raise ValueError(
            "Normalize paid-scene authority before exporting its dungeon configurations"
        )
    from wakfu_server import native_scene_policy_authority

    for identity, route_keys in required.items():
        # Published authority is immutable; export transactions are READ ONLY.
        native_scene_policy_authority.read_policy(db, identity, lock=False)
        for key in route_keys:
            native_scene_policy_authority.admission_policy(
                db, key, policy_id=identity, lock=False
            )
    result = {}
    for table, fields in COLUMNS.items():
        order = ["policy_id"] + [
            name
            for name in ("object_role", "state_ordinal", "ordinal")
            if name in dict(fields)
        ]
        result[table] = db.execute(
            "SELECT "
            + ",".join(name for name, _ in fields)
            + " FROM "
            + table
            + " WHERE policy_id=ANY(%s) ORDER BY "
            + ",".join(order),
            (sorted(required),),
        ).fetchall()
    if {row["policy_id"] for row in result["native_scene_policies"]} != set(required):
        raise ValueError(
            "Exported configurations lack their complete paid-scene authority"
        )
    return result


def scene_sql(tables, *, schema="public"):
    """Insert unpublished parents/children then seal, or verify existing identities.

    Existing published rows never receive INSERT/UPDATE attempts: immutable
    triggers remain active even during an idempotent import. Extra/conflicting
    child rows abort the enclosing installation transaction.
    """
    _schema(schema)
    if not any(table in tables for table in COLUMNS):
        return []
    if not set(COLUMNS) <= set(tables):
        raise ValueError("Incomplete normalized scene export")
    parents = tables["native_scene_policies"]
    identities = {row["policy_id"] for row in parents}
    if len(identities) != len(parents) or any(
        row["published"] is not True for row in parents
    ):
        raise ValueError("Only unique published scene identities can be exported")
    for table, fields in COLUMNS.items():
        for row in tables[table]:
            if (
                set(row) != {name for name, _ in fields}
                or row["policy_id"] not in identities
            ):
                raise ValueError("Unknown, incomplete or orphaned normalized scene row")
    result = []
    for parent in sorted(parents, key=lambda row: row["policy_id"]):
        identity = parent["policy_id"]
        key = Literal(identity).as_string()
        body = [
            "BEGIN",
            "PERFORM pg_advisory_xact_lock(hashtextextended('native_scene_policy:'||"
            + key
            + ",0));",
            f"IF NOT EXISTS (SELECT 1 FROM {schema}.native_scene_policies WHERE policy_id={key}) THEN",
        ]
        for table, fields in COLUMNS.items():
            columns = ",".join(name for name, _ in fields)
            for row in tables[table]:
                if row["policy_id"] != identity:
                    continue
                insert = dict(row)
                if table == "native_scene_policies":
                    insert["published"] = False
                values = ",".join(_literal(insert[name], kind) for name, kind in fields)
                body.append(
                    f"INSERT INTO {schema}.{table} ({columns}) VALUES ({values});"
                )
        body += [
            f"UPDATE {schema}.native_scene_policies SET published=true WHERE policy_id={key};",
            "END IF;",
        ]
        for table, fields in COLUMNS.items():
            rows = [row for row in tables[table] if row["policy_id"] == identity]
            tests = [
                f"(SELECT count(*) FROM {schema}.{table} WHERE policy_id={key}) <> {len(rows)}"
            ]
            for row in rows:
                condition = " AND ".join(
                    name + " IS NOT DISTINCT FROM " + _literal(row[name], kind)
                    for name, kind in fields
                )
                tests.append(
                    f"NOT EXISTS (SELECT 1 FROM {schema}.{table} WHERE {condition})"
                )
            body.append(
                "IF "
                + " OR ".join(tests)
                + " THEN RAISE EXCEPTION 'Conflicting normalized paid-scene installation authority'; END IF;"
            )
        body.append("END;")
        result.append("DO " + Literal("\n".join(body)).as_string() + ";")
    return result
