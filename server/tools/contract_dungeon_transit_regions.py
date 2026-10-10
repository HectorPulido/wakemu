"""Contract singleton intermediate walking regions without inventing terrain.

This is an explicit local encounter policy. Every native gate is retained and
gates surrounding the transit cell open after the same preceding victory.
"""
import copy


def contract(topology):
    result = copy.deepcopy(topology)
    rooms = result["rooms"]
    removed = {room["order"] for room in rooms[1:-1] if len(room["cells"]) == 1}
    if not removed:
        return result
    for order in removed:
        incoming = [
            d for d in result["physical_doors"] if d["destination_room"] == order
        ]
        outgoing = [d for d in result["physical_doors"] if d["source_room"] == order]
        if len(incoming) != 1 or len(outgoing) != 1:
            raise ValueError("Singleton transit region is not an unambiguous chain")
    survivors = [r for r in rooms if r["order"] not in removed]
    mapping = {}
    for room in rooms:
        downstream = next(r for r in survivors if r["order"] >= room["order"])
        mapping[room["order"]] = survivors.index(downstream) + 1
    for order in sorted(removed):
        target = survivors[mapping[order] - 1]
        target["cells"].extend(rooms[order - 1]["cells"])
    for door in result["physical_doors"]:
        original_source = door["source_room"]
        door["destination_room"] = mapping[door["destination_room"]]
        door["source_room"] = mapping[original_source]
        if door["source_room"] == door["destination_room"]:
            door["source_room"] -= 1
    for exit_object in result.get("physical_exit_objects", []):
        exit_object["room_order"] = mapping[exit_object["room_order"]]
    for room in survivors:
        room["order"] = mapping[room["order"]]
        room["cells"] = sorted(room["cells"])
    result["rooms"] = survivors
    result["transit_region_policy"] = {
        "authority": "Explicit local policy; singleton native walking regions have no encounter",
        "contracted_original_orders": sorted(removed),
        "original_to_encounter_order": mapping,
        "native_gate_count_preserved": len(result["physical_doors"]),
    }
    return result
