"""Opt-in cyclic arena projection; one immutable initial native door choice."""
from copy import deepcopy
import hashlib
import json


def validate(config):
    policy = config["topology"].get("rotation_choice")
    if (
        not isinstance(policy, dict)
        or policy.get("authority") != "reviewed_native_cycle_reconstruction"
    ):
        raise ValueError("Missing reviewed native rotation policy")
    cycle, terminal = policy.get("cycle_source_orders"), policy.get(
        "terminal_source_order"
    )
    if (
        not isinstance(cycle, list)
        or len(cycle) < 2
        or any(type(order) is not int or order <= 0 for order in cycle)
        or len(set(cycle)) != len(cycle)
        or type(terminal) is not int
        or terminal in cycle
    ):
        raise ValueError("Invalid distinct native cycle/terminal arenas")
    if config["topology"].get("branch_routes") or config["topology"].get("auto_edges"):
        raise ValueError("Rotation cannot mix implicit parallel/automatic traversal")
    source_orders = set(cycle) | {terminal}
    for document in (config["topology"], config["compiled_plan"]):
        rooms = {room["order"]: room for room in document["rooms"]}
        if not source_orders <= set(rooms):
            raise ValueError("Rotation arena is absent from frozen source")
    selectors = policy.get("selectors")
    if (
        not isinstance(selectors, list)
        or len(selectors) != len(cycle)
        or {s.get("source_order") for s in selectors} != set(cycle)
        or len({s.get("source_id") for s in selectors}) != len(cycle)
        or any(
            type(s.get("source_id")) is not int or s["source_id"] <= 0
            for s in selectors
        )
    ):
        raise ValueError("Every cycle arena needs exactly one native selector")
    gates = {g["source_id"]: g for g in config["topology"]["physical_doors"]}
    if any(
        s["source_id"] not in gates
        or gates[s["source_id"]].get(
            "native_destination_room", gates[s["source_id"]]["destination_room"]
        )
        != s["source_order"]
        for s in selectors
    ):
        raise ValueError("Native selector contradicts original gate arena")
    if policy.get("main_source_orders") != cycle + [terminal]:
        raise ValueError("Optional arenas cannot enter mandatory rotation")
    return policy


def source_order(config, selector):
    policy = validate(config)
    choices = [
        s["source_order"] for s in policy["selectors"] if s["source_id"] == selector
    ]
    if len(choices) != 1:
        raise ValueError("Native door is not an initial cycle choice")
    cycle = policy["cycle_source_orders"]
    first = cycle.index(choices[0])
    return cycle[first:] + cycle[:first] + [policy["terminal_source_order"]]


def project(config, selector):
    """Project geometry AND rosters; never change original pinned evidence/hash.

    Returned projection is ephemeral. Persist selector before spawning, and keep
    original catalog hash as the provenance identity. A caller must not install
    this derived document as an unrelated active configuration.
    """
    order = source_order(config, selector)
    mapping = {old: new for new, old in enumerate(order, 1)}
    for room in config["topology"]["rooms"]:
        mapping.setdefault(room["order"], room["order"])
    if len(set(mapping.values())) != len(mapping):
        raise ValueError("Optional logical order collides with rotation")
    output = deepcopy(config)
    for document in (output["topology"], output["compiled_plan"]):
        for room in document["rooms"]:
            room["native_source_order"] = room["order"]
            room["order"] = mapping[room["order"]]
        document["rooms"].sort(key=lambda room: room["order"])
    for gate in output["topology"]["physical_doors"]:
        native_order = gate["destination_room"]
        if native_order not in mapping:
            raise ValueError("Native gate targets an absent arena")
        gate["native_destination_room"] = native_order
        gate["destination_room"] = mapping[native_order]
        gate["source_room"] = max(1, gate["destination_room"] - 1)
    for binding in output["topology"].get("doors", []):
        for field in ("source_room", "destination_room"):
            binding[field] = mapping[binding[field]]
        if "progression_gate_room" in binding:
            binding["progression_gate_room"] = (
                max(binding["source_room"], binding["destination_room"]) - 1
            )
    for binding in output["topology"].get("physical_exit_objects", []):
        if binding.get("rotation_scope") != "shared_entry":
            raise ValueError("Native exterior exit needs explicit rotation scope")
        binding["room_order"] = 1
    output["projection_source_evidence_hashes"] = deepcopy(
        config.get("evidence_hashes", {})
    )
    output["evidence_hashes"] = deepcopy(config.get("evidence_hashes", {}))
    for key, document in (
        ("plan", output["compiled_plan"]),
        ("topology", output["topology"]),
    ):
        output["evidence_hashes"][key] = hashlib.sha256(
            json.dumps(
                document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
    output["topology"]["selected_rotation"] = selector
    output["topology"]["rotation_source_orders"] = order
    output["evidence_hashes"]["topology"] = hashlib.sha256(
        json.dumps(
            output["topology"],
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    return output


def shared_entry_room(topology, source):
    """Bind literal native exterior access in shared exploration lobby only."""
    bindings = [
        b
        for b in topology.get("physical_exit_objects", ())
        if b["source_id"] == source["id"] and b.get("rotation_scope") == "shared_entry"
    ]
    if not bindings:
        return None
    if len(bindings) != 1 or source.get("map_id") != topology["asset_map_id"]:
        raise ValueError("Ambiguous native shared-lobby exterior binding")
    binding = bindings[0]
    center = tuple(source[k] for k in ("x", "y", "z"))
    literal = {
        tuple(p[k] for k in ("x", "y", "z"))
        for p in source.get("approach_positions", ())
    }
    if source.get("approach_blocks_center") is False:
        literal.add(center)
    approaches = set(map(tuple, binding.get("native_approach_cells", ())))
    if (
        tuple(binding["source_position"]) != center
        or not approaches
        or not approaches <= literal
        or not approaches <= set(map(tuple, topology["shared_lobby_cells"]))
    ):
        raise ValueError("Exterior binding leaves its literal native lobby approaches")
    return 1
