"""Pure production projections shared by exported configured-flow regressions."""
from copy import deepcopy


def variants(record):
    from wakfu_server import (
        dungeon_entry_paths,
        dungeon_rotation,
        dungeon_branches,
        dungeon_gate_presentation,
    )

    config = dungeon_gate_presentation.project_configuration(
        record["configuration"], validated_pin=True
    )
    topology = config["topology"]
    if topology.get("entry_path_policy"):
        for row in topology["entry_path_policy"]["paths"]:
            yield "entry:" + row["key"], dungeon_entry_paths.project_configuration(
                config, row["key"]
            )
    elif topology.get("rotation_choice"):
        for row in topology["rotation_choice"]["selectors"]:
            yield "rotation:" + str(row["source_id"]), dungeon_rotation.project(
                config, row["source_id"]
            )
    elif topology.get("branch_routes"):
        for row in topology["branch_routes"]:
            projected = deepcopy(config)
            projected["topology"]["selected_branch"] = row["key"]
            # Keep topology's union intact for its source validator. Consumers
            # resolve each room through the same selected_room adapter.
            yield "branch:" + row["key"], projected
    else:
        yield "canonical", config


def native_approaches(source):
    points = {
        tuple(point[k] for k in ("x", "y", "z"))
        for point in source.get("approach_positions", ())
    }
    if (
        not source.get("approach_mask", 0)
        or source.get("approach_blocks_center") is False
    ):
        points.add(tuple(source[k] for k in ("x", "y", "z")))
    return points


def declared_initial_open_scene(topology):
    """Recognize the existing source-declared open route, not an ID exception."""
    if (
        topology.get("policy") != "native_physical_door_victory_policy"
        or topology.get("source_kind_reconstruction", {}).get(
            "completion_terrain_is_noncombat"
        )
        is not True
        or not topology.get("main_completion")
        or not topology.get("physical_doors")
    ):
        return False
    from wakfu_server.dungeon_optional_rooms import main_room_orders

    last = main_room_orders(topology)[-1]
    return all(
        gate.get("source_kind") == "native_initial_hidden_open_at_entry"
        and gate["source_room"] == gate["destination_room"] == 1
        and not gate.get("requires_completion", False)
        or gate.get("source_kind") == "noncombat_native_completion_gate"
        and gate["source_room"] == gate["destination_room"] == last
        and gate.get("requires_completion") is True
        for gate in topology["physical_doors"]
    )
