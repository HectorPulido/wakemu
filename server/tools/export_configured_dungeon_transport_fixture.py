"""Export native transport cases read-only; redirect JSON to a private fixture.

Run with PYTHONPATH=server:server/tests and the normal read-only native catalog
connection environment. No player data, instance writes or schema changes.
"""
import json, os, struct
from wakfu_server.postgres import Database
from wakfu_server import (
    dungeon_runtime_config,
    dungeon_optional_rooms,
    dungeon_branches,
    generic_transports,
    dungeon_native_flow,
    dungeon_optional_votes,
)
from configured_dungeon_flow_fixture import variants, native_approaches

D = Database(
    os.environ["WAKFU_DATABASE_URL"],
    password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
)
with D.connection() as db:
    db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
    records = [
        dict(
            route=r["route_key"],
            version=r["policy_version"],
            configuration=dungeon_runtime_config.active_configuration(
                db, r["route_key"]
            ),
        )
        for r in db.execute(
            "SELECT route_key,policy_version FROM dungeon_runtime_active_configurations ORDER BY route_key"
        ).fetchall()
    ]
    mode = db.execute(
        "SELECT value FROM settings WHERE name='dungeon_server_mode'"
    ).fetchone()["value"]
cases = []
for record in records:
    for variant, config in variants(record):
        t = config["topology"]
        main = dungeon_optional_rooms.main_room_orders(t)
        other = {
            identity
            for name, b in dungeon_branches.validate(t).items()
            if name != t.get("selected_branch")
            for identity in b["source_ids"]
        }
        for binding in t.get("doors", []):
            source = generic_transports.source(t["asset_map_id"], binding["source_id"])
            destination = next(
                d
                for d in source["destinations"]
                if d["destination_id"] == binding["destination_id"]
            )
            approaches = set(
                map(tuple, binding.get("native_approach_cells", ()))
            ) or native_approaches(source)
            cells = sorted(
                tuple(c)
                for c in t["exploration_geometry"]["cells"]
                if all(type(v) is int for v in c) and tuple(c) in approaches
            )
            if not cells:
                raise ValueError("Binding lacks an exact native integral approach")
            transfer = binding.get("binding_kind") == "native_entry_transfer"
            src, dst = binding["source_room"], binding["destination_room"]
            kind = (
                "entry_transfer"
                if transfer
                else "same_stage"
                if src == dst
                else "hub_return"
                if src > dst
                else "forward_hub"
                if dst - src > 1
                else "forward"
            )
            for phase in (
                ("initial_free", "postboss_completed") if transfer else ("frontier",)
            ):
                cases.append(
                    dict(
                        route=record["route"],
                        version=record["version"],
                        variant=variant,
                        phase=phase,
                        kind=kind,
                        source_id=source["id"],
                        destination_id=destination["destination_id"],
                        source_room=src,
                        destination_room=dst,
                        minimum_frontier=1 if transfer else max(src, dst),
                        approach=list(cells[0]),
                        destination={
                            k: destination[k] for k in ("map_id", "x", "y", "z")
                        },
                        original_criterion=destination["criterion"],
                        selected_branch=t.get("selected_branch"),
                        unselected_branch=source["id"] in other,
                        main_rooms=len(main),
                        binding=binding,
                    )
                )
for record in records:
    config = record["configuration"]
    t = config["topology"]
    rule = dungeon_optional_votes.rule_for(config)
    if rule is None:
        continue
    for binding in rule["transports"]:
        source = generic_transports.source(t["asset_map_id"], binding["source_id"])
        destination = next(
            d
            for d in source["destinations"]
            if d["destination_id"] == binding["destination_id"]
        )
        points = sorted(
            tuple(c)
            for c in t["exploration_geometry"]["cells"]
            if all(type(v) is int for v in c) and tuple(c) in native_approaches(source)
        )
        if not points:
            raise ValueError("Optional native source has no original floor approach")
        cases.append(
            dict(
                route=record["route"],
                version=record["version"],
                variant="canonical",
                phase="checkpoint",
                kind="optional_checkpoint",
                source_id=source["id"],
                destination_id=destination["destination_id"],
                source_room=None,
                destination_room=None,
                minimum_frontier=rule["required_checkpoint"] + 1,
                approach=list(points[0]),
                destination={k: destination[k] for k in ("map_id", "x", "y", "z")},
                original_criterion=destination["criterion"],
                selected_branch=None,
                unselected_branch=False,
                main_rooms=len(dungeon_optional_rooms.main_room_orders(t)),
                binding=binding,
                authority=dict(
                    rule_key=rule["key"],
                    rule_sha256=dungeon_optional_votes.digest(rule),
                    checkpoint=rule["required_checkpoint"],
                ),
            )
        )
print(
    json.dumps(
        dict(
            read_only=True, canonical_routes=len(records), server_mode=mode, cases=cases
        )
    )
)
