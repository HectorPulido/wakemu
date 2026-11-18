"""Compile reviewed quest supplies against original chest/state/physical sources.

This publisher never opens a chest, grants an item, or changes player progress.
The caller owns the existing local bundle transaction and rollback policy.
"""

from psycopg.types.json import Jsonb

from wakfu_server import native_catalog, quest_chest_supplies as supplies
from wakfu_server.combat_geometry import published_geometry
from wakfu_server.combat_sn_path import NativeSnColumns
from wakfu_server.native_interaction_approaches import native_interaction_approaches
from wakfu_server.native_interactive_components import components, parameter_bounds
from wakfu_server.paths import DATA_ROOT


def compile_rule(db, rule):
    supplies.validate(rule)
    supplies._source(db, rule)
    if rule["scene_scope"] == "owned_story":
        from wakfu_server import generic_transports

        entry = rule["owned_entry"]
        source = generic_transports.source(entry["map_id"], entry["object_id"])
        targets = (
            []
            if source is None
            else [
                row
                for row in source["destinations"]
                if row["destination_id"] == entry["destination_id"]
                and row["map_id"] == rule["map_id"]
            ]
        )
        if len(targets) != 1:
            raise ValueError(
                "Quest supply private entry is not an original native branch"
            )
    from wakfu_server import quest_inventory
    from wakfu_server.achievements import counter_missions, mission_toolkit

    if rule["output_reference"] not in quest_inventory.REFERENCES:
        raise ValueError("Quest chest supply output is not an actual native quest item")
    definitions = mission_toolkit.definitions(
        db, dict(bindings=[dict(quest_id=rule["quest_id"])], links=[], activations=[])
    )
    bindings = counter_missions.bindings(list(definitions.values()))
    if (
        rule["quest_id"],
        rule["objective_id"],
        rule["variable_id"],
        rule["threshold"],
    ) not in bindings.get(rule["variable_id"], ()):
        raise ValueError(
            "Quest chest counter differs from its original native objective"
        )
    original = native_catalog.record(
        DATA_ROOT / "native-map-objects.json", "$", str(rule["object_id"])
    )
    body = components(bytes.fromhex(original["payload_hex"]))[1]
    _, start, end = parameter_bounds(body)
    if body[start:end].decode("utf-8") != str(rule["native_definition"]):
        raise ValueError("Quest chest definition differs from the real bEH parameter")
    # Original bEH fields precede its footprint and parameter. Preserve the
    # serialized orientation/QV bits and VA.a's ordered native floor selection.
    import struct

    direction, mask = body[16], struct.unpack_from(">h", body, 17)[0]
    physical = NativeSnColumns.from_published(rule["map_id"])
    expected = native_interaction_approaches(
        published_geometry(rule["map_id"]),
        rule["position"],
        direction=direction,
        approach_mask=mask,
        physical_columns=physical,
        center_allowed=False if mask & 256 else None,
    )
    if physical.source_sha256 != rule["physical_sha256"] or {
        tuple(p) for p in rule["approaches"]
    } != set(expected):
        raise ValueError("Quest chest approaches differ from original QV/VA.a surfaces")
    if db.execute(
        "SELECT 1 FROM paid_container_locations WHERE map_id=%s AND object_id=%s "
        "UNION ALL SELECT 1 FROM treasure_chest_rules WHERE map_id=%s AND object_id=%s "
        "UNION ALL SELECT 1 FROM declared_treasure_locations WHERE map_id=%s AND object_id=%s "
        "UNION ALL SELECT 1 FROM achievement_chest_bindings WHERE map_id=%s AND object_id=%s",
        (rule["map_id"], rule["object_id"]) * 4,
    ).fetchone():
        raise ValueError("Quest chest overlaps an ordinary treasure/payment producer")
    return rule


def install(db, document):
    if (
        not isinstance(document, dict)
        or set(document) != {"schema", "id", "rules"}
        or document["schema"] != "quest-chest-supply-batch-v1"
        or not isinstance(document["id"], str)
        or not document["id"]
        or not isinstance(document["rules"], list)
        or not document["rules"]
    ):
        raise ValueError("Malformed reviewed quest chest supply batch")
    seen = set()
    prepared = []
    for candidate in document["rules"]:
        rule = compile_rule(db, candidate)
        key = rule["map_id"], rule["object_id"]
        if key in seen:
            raise ValueError("Duplicate quest chest source")
        seen.add(key)
        prepared.append(rule)
    for rule in prepared:
        checksum = supplies.digest(rule)
        db.execute(
            "INSERT INTO quest_chest_supply_rules(map_id,object_id,rule,sha256,sealed) "
            "VALUES(%s,%s,%s,%s,true) ON CONFLICT DO NOTHING",
            (rule["map_id"], rule["object_id"], Jsonb(rule), checksum),
        )
        current = db.execute(
            "SELECT rule,sha256,sealed FROM quest_chest_supply_rules "
            "WHERE map_id=%s AND object_id=%s",
            (rule["map_id"], rule["object_id"]),
        ).fetchone()
        if (
            current is None
            or not current["sealed"]
            or current["sha256"] != checksum
            or current["rule"] != rule
        ):
            raise ValueError(
                "An immutable quest chest source is already published differently"
            )
    return dict(rules=len(prepared), id=document["id"])
