"""Validate automatic dungeon flow candidates and produce safe placement evidence.

Pure preparation: never activates configurations or writes runtime storage.
Native encounter quantities and explicit DEV quantities retain separate authority.
"""
from collections import deque
import copy


def reachable(geometry, start, blocked=()):
    start = tuple(start)
    blocked = set(map(tuple, blocked))
    cells = set(map(tuple, geometry["cells"])) - blocked
    if start not in cells:
        return set()
    adjacency = {}
    for a, b in geometry["edges"]:
        a, b = tuple(a), tuple(b)
        if a in cells and b in cells:
            adjacency.setdefault(a, set()).add(b)
    seen, queue = {start}, deque([start])
    while queue:
        for cell in adjacency.get(queue.popleft(), ()):
            if cell not in seen:
                seen.add(cell)
                queue.append(cell)
    return seen


def validate(
    configuration, exploration, combat, formation, *, entry=None, player_slots=6
):
    """Return candidates or explicit reasons; formation uses the existing engine."""
    config = copy.deepcopy(configuration)
    topology = config["topology"]
    plan = config["compiled_plan"]
    reasons = []
    if (
        exploration["map_id"] != topology["asset_map_id"]
        or combat["map_id"] != topology["asset_map_id"]
    ):
        return {
            "status": "unsupported",
            "reasons": ["asset_map_identity_mismatch"],
            "rooms": [],
        }
    rooms = topology["rooms"]
    rosters = plan["rooms"]
    orders = list(range(1, len(rooms) + 1))
    if [r["order"] for r in rooms] != orders or [r["order"] for r in rosters] != orders:
        return {
            "status": "unsupported",
            "reasons": ["flow_and_roster_room_count_or_order_mismatch"],
            "rooms": [],
        }
    if not rooms:
        return {
            "status": "unsupported",
            "reasons": ["missing_native_flow"],
            "rooms": [],
        }
    bosses = set(
        plan.get("roster_policy_evidence", {}).get(
            "boss_references", plan.get("boss_references", [])
        )
    )
    original_fields = {r["order"]: r for r in plan.get("generated_fields", [])}
    generated_policy = plan.get("official") is False
    output = []
    entry = tuple(entry if entry is not None else rooms[0]["anchor"])
    for room, roster in zip(rooms, rosters):
        order = room["order"]
        findings = []
        cells = set(map(tuple, room["cells"]))
        anchor = tuple(room["anchor"])
        blocked = [
            g["position"]
            for g in topology.get("physical_doors", [])
            if g["destination_room"] > order
        ]
        stage_entry = entry
        if topology.get("policy") == "native_teleport_victory_policy":
            stage_entry = tuple(room.get("native_arrival", ()))
            if order == 1 and stage_entry != entry:
                findings.append("first_native_arrival_differs_from_entry")
            if order > 1:
                incoming = [
                    d
                    for d in topology.get("doors", [])
                    if d["source_room"] == order - 1 and d["destination_room"] == order
                ]
                previous = rooms[order - 2]
                previous_access = reachable(exploration, previous["native_arrival"])
                if (
                    len(incoming) != 1
                    or tuple(incoming[0]["destination_position"]) != stage_entry
                ):
                    findings.append("native_teleport_arrival_not_bound_to_prior_room")
                elif not any(
                    tuple(c) in previous_access
                    and tuple(c) in set(map(tuple, previous["cells"]))
                    for c in incoming[0]["native_approach_cells"]
                ):
                    findings.append(
                        "native_teleport_approach_unreachable_in_prior_room"
                    )
        accessible = reachable(exploration, stage_entry, blocked)
        if anchor not in accessible or anchor not in cells:
            findings.append("room_anchor_not_reachable_from_native_entry_at_gate_stage")
        if not cells.issubset(set(map(tuple, exploration["cells"]))):
            findings.append("room_cells_not_native_exploration_cells")
        monsters = roster["monsters"]
        if any(type(m.get("ref_id")) is not int or m["ref_id"] <= 0 for m in monsters):
            findings.append("unresolved_native_monster_identity")
        valid_counts = all(
            type(m.get("count")) is int and m["count"] > 0 for m in monsters
        )
        quantity = sum(m["count"] for m in monsters) if valid_counts else 0
        if not valid_counts or not 1 <= quantity <= 121:
            findings.append("malformed_or_unsupported_roster_quantity")
        boss_count = (
            sum(
                m["count"]
                for m in monsters
                if m.get("ref_id") in bosses or m.get("role") == "boss"
            )
            if valid_counts
            else 0
        )
        # An explicitly identified boss group may contain one of each boss.
        # Generated encounters cannot duplicate a boss or introduce it early.
        generated_room = original_fields.get(order, {}).get(
            "policy_applied", generated_policy
        )
        if generated_room and boss_count and order != len(rooms):
            findings.append("generated_final_boss_in_early_room")
        if generated_room and boss_count > 1:
            boss_rows = [
                m
                for m in monsters
                if m.get("ref_id") in bosses or m.get("role") == "boss"
            ]
            distinct_identified = (
                len(bosses) > 1
                and len(boss_rows) == len(bosses)
                and {m.get("ref_id") for m in boss_rows} == bosses
                and all(m.get("count") == 1 for m in boss_rows)
            )
            if not distinct_identified:
                findings.append("duplicate_generated_boss")
        placement = []
        if not findings:
            combat_cells = set(map(tuple, combat["cells"]))
            section = dict(
                combat,
                cells=[list(c) for c in cells if c in combat_cells],
                edges=[
                    (a, b)
                    for a, b in combat["edges"]
                    if tuple(a) in cells and tuple(b) in cells
                ],
            )
            try:
                placement = list(
                    formation(section, anchor, quantity, player_slots=player_slots)
                )
                if (
                    len(placement) != quantity
                    or len(set(map(tuple, placement))) != quantity
                ):
                    findings.append("formation_does_not_assign_unique_monster_cells")
                elif any(
                    tuple(p) not in cells or tuple(p) not in accessible
                    for p in placement
                ):
                    findings.append("monster_formation_leaves_reachable_room")
            except ValueError as error:
                findings.append("native_combat_formation_unavailable: " + str(error))
        reasons.extend(f"room_{order}: {f}" for f in findings)
        output.append(
            {
                "order": order,
                "quantity": quantity,
                "boss_count": boss_count,
                "roster_authority": "explicit_dev_policy"
                if generated_room
                else "preserved_reviewed_composition",
                "anchor": list(anchor),
                "monster_positions": placement,
                "status": "unsupported" if findings else "placement_validated",
                "reasons": findings,
            }
        )
    return {
        "status": "unsupported" if reasons else "candidate_validated",
        "reasons": reasons,
        "rooms": output,
        "limits": "Native entry reachability and combat formation only; official encounter composition and special boss scripts require separate evidence.",
    }
