"""Source-bound native traversal and presentation after mandatory completion.

This projection reads the existing main-run completion. It never creates a
fight, advances a stage, issues rewards, or writes an additional completion.
"""
from functools import lru_cache
from pathlib import Path
import hashlib
import json
import struct

POLICY = "reviewed-native-main-completion-v1"


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


@lru_cache(maxsize=1)
def rules():
    document = json.loads(
        Path(__file__).with_name("dungeon_main_completion_rules.json").read_text()
    )
    if document.get("schema") != "reviewed-native-main-completion-rules-v1":
        raise ValueError("Invalid native main completion rule schema")
    return tuple(document["rules"])


@lru_cache(maxsize=16)
def _native_rule(key, source_hash, release):
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    matches = [r for r in rules() if r["key"] == key and digest(r) == source_hash]
    if len(matches) != 1 or release != matches[0]["qualified_native_release"]:
        raise ValueError("Main completion native source changed")
    rule = matches[0]
    for gate in rule["gates"]:
        source = native_catalog.record(
            DATA_ROOT / "native-map-objects.json", "$", str(gate["source_id"])
        )
        state = native_catalog.record(
            DATA_ROOT / "native-interactive-states.json",
            "objects",
            str(gate["source_id"]),
        )
        if (
            source is None
            or state is None
            or source.get("type") != "Door"
            or source.get("map_id") != rule["map_id"]
            or state.get("type") != "Door"
            or state.get("map_id") != rule["map_id"]
            or digest(source) != gate["native_object_sha256"]
            or digest(state) != gate["native_state_sha256"]
        ):
            raise ValueError("Main completion gate differs from original native source")
    return rule


def require_rule(topology):
    record = topology.get("main_completion")
    flags = [
        d.get("requires_completion")
        for d in topology.get("physical_doors", ())
        if "requires_completion" in d
    ]
    if any(type(flag) is not bool for flag in flags):
        raise ValueError("Malformed native completion gate flag")
    if record is None:
        if any(flags):
            raise ValueError("Completion gate requires a source-bound native contract")
        return None
    from wakfu_server import native_catalog

    if (
        type(record) is not dict
        or record.get("policy") != POLICY
        or set(record) != {"policy", "rule_key", "rule_sha256"}
    ):
        raise ValueError("Invalid native main completion contract")
    rule = _native_rule(
        record["rule_key"], record["rule_sha256"], native_catalog.release()
    )
    from wakfu_server.dungeon_optional_rooms import main_room_orders

    if (
        topology["asset_map_id"] != rule["map_id"]
        or main_room_orders(topology)[-1] != rule["main_room_order"]
    ):
        raise ValueError("Main completion belongs to another native encounter scope")
    gates = {
        d["source_id"]: d
        for d in topology.get("physical_doors", ())
        if d.get("requires_completion") is True
    }
    if set(gates) != {g["source_id"] for g in rule["gates"]}:
        raise ValueError("Main completion gate inventory changed")
    for gate in rule["gates"]:
        if (
            gates[gate["source_id"]]["position"] != gate["position"]
            or gates[gate["source_id"]]["destination_room"] != rule["main_room_order"]
        ):
            raise ValueError("Main completion gate position or owner changed")
    extra = set(map(tuple, rule["traversal_cells"]))
    native = set(map(tuple, topology["exploration_geometry"]["cells"]))
    encounter = {tuple(cell) for room in topology["rooms"] for cell in room["cells"]}
    if not extra or not extra.issubset(native) or extra & encounter:
        raise ValueError(
            "Main completion traversal must remain native noncombat terrain"
        )
    return rule


def blocked_cells(topology, *, completed):
    if type(completed) is not bool:
        raise ValueError("Main completion requires committed boolean progress")
    rule = require_rule(topology)
    return (
        frozenset()
        if rule is None or completed
        else frozenset(map(tuple, rule["traversal_cells"]))
    )


def object_room(topology, source):
    rule = require_rule(topology)
    if rule is None or source.get("map_id") != rule["map_id"]:
        return None
    binding = next(
        (
            e
            for e in topology.get("physical_exit_objects", ())
            if e["source_id"] == source["id"]
        ),
        None,
    )
    if binding is None:
        return None
    extra = set(map(tuple, rule["traversal_cells"]))
    if binding["room_order"] == rule["main_room_order"] and set(
        map(tuple, binding["native_approach_cells"])
    ).issubset(extra):
        return rule["main_room_order"]
    return None


def presentation_packet(presentation):
    values = presentation["parameters"]
    if (
        type(values) is not list
        or len(values) > 127
        or any(
            type(value) is not int or not -(1 << 63) <= value < (1 << 63)
            for value in values
        )
        or type(presentation["event_id"]) is not int
        or not 0 < presentation["event_id"] < (1 << 31)
        or type(presentation["scenario_id"]) is not int
        or not 0 < presentation["scenario_id"] < (1 << 31)
    ):
        raise ValueError("Invalid native scenario presentation parameters")
    # Original cAS.dp and cio->ahp.a consume positional signed long arguments.
    return 13411, struct.pack(
        ">BiiB", 0, presentation["event_id"], presentation["scenario_id"], len(values)
    ) + b"".join(struct.pack(">q", value) for value in values)


def packets(topology, *, completed):
    rule = require_rule(topology)
    if rule is None or completed is False:
        return ()
    if completed is not True:
        raise ValueError("Main completion requires committed boolean progress")
    return (presentation_packet(rule["presentation"]),)
