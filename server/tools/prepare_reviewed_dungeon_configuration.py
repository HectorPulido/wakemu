"""Build versioned dungeon data from explicit reviewed guide/native evidence."""
import copy

from wakfu_server.combat_geometry import encounter_component, prepare_geometry
from wakfu_server.dungeon_runtime_config import canonical_hash, prepare_configuration


def prepare(original, proposal, native_monsters, geometry, *, version):
    if type(version) is not int or version <= original["version"]:
        raise ValueError("Reviewed configuration must advance its source version")
    if proposal["route_key"] != original["route"]["key"]:
        raise ValueError("Reviewed proposal belongs to another route")
    if geometry["map_id"] != original["route"]["start_map_id"]:
        raise ValueError("Reviewed geometry is not the native dungeon start map")
    topology = copy.deepcopy(original["topology"])
    if proposal["room_scope"] == "native_entry_component":
        if topology.get("doors"):
            raise ValueError(
                "Cannot collapse a native door flow through a roster review"
            )
        cells, ambiguous = encounter_component(
            prepare_geometry(geometry), tuple(proposal["native_entry"])
        )
        if ambiguous or cells != {
            tuple(cell) for cell in topology["rooms"][0]["cells"]
        }:
            raise ValueError("Reviewed single room differs from native entry component")
        topology["rooms"] = [topology["rooms"][0]]
        topology["auto_edges"] = []
        topology[
            "room_count_source"
        ] = "reviewed_guide_one_room_and_native_entry_component"
    elif proposal["room_scope"] != "preserve_existing_native_rooms":
        raise ValueError("Unsupported reviewed native room scope")
    if [room["order"] for room in proposal["rooms"]] != [
        room["order"] for room in topology["rooms"]
    ]:
        raise ValueError("Reviewed composition differs from its native room order")
    native_cells = {tuple(cell) for cell in geometry["cells"]}
    if any(
        not {tuple(cell) for cell in room["cells"]} <= native_cells
        for room in topology["rooms"]
    ):
        raise ValueError("Reviewed room contains cells absent from native geometry")
    native = {monster["ref"]: monster for monster in native_monsters}
    plan = copy.deepcopy(original["compiled_plan"])
    plan["rooms"] = []
    for room in proposal["rooms"]:
        monsters = []
        for slot in room["monsters"]:
            reference, count = slot["reference"], slot["count"]
            if (
                type(reference) is not int
                or reference not in native
                or type(count) is not int
                or count <= 0
            ):
                raise ValueError("Reviewed native identity/count is invalid")
            actor = native[reference]
            name = proposal["native_names_fr"].get(str(reference))
            if not isinstance(name, str) or not name:
                raise ValueError("Reviewed native French identity evidence is absent")
            properties = actor["raw_visual_arrays"]["csc"]
            monsters.append(
                dict(
                    name=name,
                    ref_id=reference,
                    count=count,
                    role="boss" if 43 in properties else "monster",
                    native_min_level=actor["min_level"],
                    native_max_level=actor["max_level"],
                    guide_min_level=None,
                    guide_max_level=None,
                )
            )
        plan["rooms"].append(
            dict(order=room["order"], monsters=monsters, diagnostics=[])
        )
    plan["policy_mode"] = "explicit_reviewed_guide_reference_rooms"
    plan["generated_fields"] = [
        dict(order=room["order"], policy_applied=False, fields=[])
        for room in plan["rooms"]
    ]
    plan["reviewed_data_policy"] = copy.deepcopy(proposal)
    plan["document_sha256"] = canonical_hash(proposal)
    plan[
        "local_policy"
    ] = "Reviewed native guide identities; quantities retain explicit candidate authority; no generated species padding."
    candidate = prepare_configuration(
        plan,
        topology,
        original["route"],
        version=version,
        provenance=original["provenance"],
    )
    if {
        key: value
        for key, value in candidate["context_policy"].items()
        if key != "policy_version"
    } != {
        key: value
        for key, value in original["context_policy"].items()
        if key != "policy_version"
    } or candidate[
        "level_policy"
    ] != original[
        "level_policy"
    ]:
        raise ValueError(
            "Reviewed data cannot change entry context or native level policy"
        )
    return candidate
