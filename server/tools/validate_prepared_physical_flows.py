"""Offline full exploration sequence checks against prepared native candidates."""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_native_door_flow import shortest_path


def movement(path):
    return dict(
        start_position=dict(zip(("x", "y", "z"), path[0])),
        end_position=dict(zip(("x", "y", "z"), path[-1])),
        steps=[
            dict(zip(("dx", "dy", "dz"), [b[i] - a[i] for i in range(3)]))
            for a, b in zip(path, path[1:])
        ],
    )


def validate(config, flow, placement):
    from wakfu_server import dungeon_physical_doors as gates
    from wakfu_server.dungeon_runtime_config import plan_from_configuration

    plan_from_configuration(config)
    topology = config["topology"]
    geometry = topology["exploration_geometry"]
    observations = []
    for room in placement["rooms"]:
        order = room["order"]
        monsters = set(map(tuple, room["monster_positions"]))
        blocked = gates.blocked_cells(topology, order)
        witness = None
        for target in sorted(monsters):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                approach = (target[0] + dx, target[1] + dy, target[2])
                path = shortest_path(
                    geometry["edges"],
                    flow["entry"],
                    approach,
                    set(map(tuple, blocked)) | monsters,
                )
                if path:
                    gates.validate_movement(
                        topology, movement(path), unlocked_room=order
                    )
                    witness = dict(
                        target=list(target),
                        approach=list(approach),
                        path=path,
                        steps=len(path) - 1,
                    )
                    break
            if witness:
                break
        if witness is None:
            raise ValueError(
                f"Room {order} cannot be engaged without crossing future gates or monster cells"
            )
        if order < len(topology["rooms"]):
            boundary = flow["stages"][order - 1]["directed_boundary_path"]
            try:
                gates.validate_movement(
                    topology, movement(boundary), unlocked_room=order
                )
            except ValueError:
                pass
            else:
                raise ValueError("Future physical gate does not reject native crossing")
            gates.validate_movement(
                topology, movement(boundary), unlocked_room=order + 1
            )
        observations.append(dict(order=order, engagement_witness=witness))
    exits = [
        e
        for e in topology["physical_exit_objects"]
        if e["room_order"] == len(observations)
    ]
    if len(exits) != 1:
        raise ValueError("No unique final exterior exit")
    witness = None
    for approach in exits[0]["native_approach_cells"]:
        path = shortest_path(geometry["edges"], flow["entry"], approach)
        if path:
            gates.validate_movement(
                topology, movement(path), unlocked_room=len(observations)
            )
            witness = path
            break
    if witness is None:
        raise ValueError(
            "Final exit native approach unreachable after all room victories"
        )
    return dict(
        status="offline_exploration_sequence_validated",
        rooms=observations,
        final_exit_path=witness,
        exterior_destination=exits[0]["destination"],
        limits="Geometry, encounter engagement and gate protocol semantics only; actual victories, rewards, multiplayer transport and boss mechanics require isolated runtime integration and acceptance",
    )


def main():
    candidates = json.loads(
        Path("docs/reports/dungeons/AUTOMATIC-COMPLETE-CANDIDATES.json").read_text()
    )["records"]
    compositions = json.loads(
        Path("docs/reports/dungeons/AUTOMATIC-COMPOSITION-COVERAGE.json").read_text()
    )["records"]
    flows = json.loads(
        Path(".runtime/local/all-native-dungeon-flows.json").read_text()
    )["records"]
    records = []
    for candidate in candidates:
        if candidate["status"] != "offline_configuration_prepared":
            continue
        row = dict(route=candidate["route"], name=candidate["name"])
        try:
            config = json.loads(Path(candidate["path"]).read_text())
            flow = next(r for r in flows if r["route"]["key"] == candidate["route"])[
                "directed_physical_flows"
            ][0]
            placement = next(
                r for r in compositions if r["route"] == candidate["route"]
            )["placement_validation"]
            row.update(validate(config, flow, placement))
        except ValueError as error:
            row.update(status="unsupported", reason=str(error))
        records.append(row)
    path = Path("docs/reports/dungeons/AUTOMATIC-FLOW-SEQUENCE-VALIDATION.json")
    path.write_text(
        json.dumps(
            dict(
                scope="Offline sequence validation; not full runtime acceptance",
                records=records,
            ),
            indent=2,
        )
        + "\n"
    )
    print([(r["name"], r["status"]) for r in records])


if __name__ == "__main__":
    main()
