"""Inventory installed dungeon rosters from read-only exports; prepare no DB writes."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def native_role(monster):
    values = monster.get("raw_visual_arrays", {}).get("csc")
    if not isinstance(values, list) or any(type(value) is not int for value in values):
        return "unknown"
    if 45 in values:
        return "archmonster"
    if 115 in values:
        return "dominant"
    return "boss" if 43 in values else "ordinary"


def audit(rows, native_monsters, groups=()):
    native = {monster["ref"]: monster for monster in native_monsters}
    configurations = {}
    records = []
    for row in rows:
        config = row["configuration"]
        configurations[row["route_key"]] = row
        plan = config["compiled_plan"]
        rooms = plan["rooms"]
        all_refs = {monster["ref_id"] for room in rooms for monster in room["monsters"]}
        early, forbidden, unknown = [], [], []
        provenance = {
            room["order"]: {
                field["monster_index"]: field for field in room.get("fields", [])
            }
            for room in plan.get("generated_fields", [])
        }
        for room in rooms:
            for index, monster in enumerate(room["monsters"]):
                role = native_role(native.get(monster["ref_id"], {}))
                entry = dict(
                    room=room["order"],
                    reference=monster["ref_id"],
                    count=monster["count"],
                )
                source = provenance.get(room["order"], {}).get(index)
                entry["identity_source"] = (
                    "generated_slot"
                    if source is not None and source.get("original_monster") is None
                    else "generated_unresolved_identity"
                    if source is not None and "ref_id" in source.get("fields", [])
                    else "preserved_known_identity"
                )
                if role == "boss" and room["order"] != rooms[-1]["order"]:
                    early.append(entry)
                if role in ("archmonster", "dominant"):
                    forbidden.append(dict(entry, native_role=role))
                if role == "unknown":
                    unknown.append(entry)
        records.append(
            dict(
                route_key=row["route_key"],
                policy_version=row["policy_version"],
                slug=plan["slug"],
                policy=plan.get("policy_mode"),
                room_count=len(rooms),
                early_native_bosses=early,
                optional_native_roles=forbidden,
                unknown_native_roles=unknown,
                first_room_covers_species_union=(
                    len(rooms) > 1
                    and {monster["ref_id"] for monster in rooms[0]["monsters"]}
                    == all_refs
                ),
                caveat="Species coverage alone does not prove publication of all room groups.",
            )
        )
    group_records = []
    for row in groups:
        selected = configurations.get(row["context_route_key"])
        reasons = []
        if (
            selected is None
            or selected["policy_version"] != row["context_policy_version"]
        ):
            reasons.append("pinned_configuration_not_in_export")
        elif row["members"] is None:
            reasons.append("receipt_group_missing")
        else:
            config = selected["configuration"]
            room = next(
                (
                    room
                    for room in config["compiled_plan"]["rooms"]
                    if room["order"] == row["room_order"]
                ),
                None,
            )
            topology = next(
                (
                    room
                    for room in config["topology"]["rooms"]
                    if room["order"] == row["room_order"]
                ),
                None,
            )
            if room is None or topology is None:
                reasons.append("receipt_room_absent")
            else:
                expected = Counter()
                for monster in room["monsters"]:
                    expected[monster["ref_id"]] += monster["count"]
                if expected != Counter(member["ref"] for member in row["members"]):
                    reasons.append("registered_roster_differs_from_pinned_room")
                cells = {tuple(cell) for cell in topology["cells"]}
                if any(
                    tuple(member[key] for key in ("x", "y", "z")) not in cells
                    for member in row["members"]
                ):
                    reasons.append("registered_member_outside_room_cells")
            if (
                row["room_order"] != row["current_room"]
                and row["group_status"] != "defeated"
            ):
                reasons.append("noncurrent_group_not_defeated")
        group_records.append(
            dict(
                instance_id=row["instance_id"],
                route_key=row["context_route_key"],
                room_order=row["room_order"],
                findings=reasons,
            )
        )
    return dict(
        configurations=records,
        active_instance_groups=group_records,
        summary=dict(
            active_configurations=len(records),
            generated_configurations=sum(
                record["policy"] == "generated_native_species_policy"
                for record in records
            ),
            early_boss_configurations=sum(
                bool(record["early_native_bosses"]) for record in records
            ),
            generated_early_boss_configurations=sum(
                record["policy"] == "generated_native_species_policy"
                and bool(record["early_native_bosses"])
                for record in records
            ),
            checked_active_groups=len(group_records),
            groups_with_findings=sum(
                bool(record["findings"]) for record in group_records
            ),
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configurations", type=Path, required=True)
    parser.add_argument("--native-monsters", type=Path, required=True)
    parser.add_argument("--groups", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    inventory = audit(
        json.loads(args.configurations.read_text()),
        json.loads(args.native_monsters.read_text())["monsters"],
        [] if args.groups is None else json.loads(args.groups.read_text()) or [],
    )
    inventory["evidence_sha256"] = {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (args.configurations, args.native_monsters)
        + (() if args.groups is None else (args.groups,))
    }
    with args.output.open("x") as destination:
        json.dump(inventory, destination, indent=2)
        destination.write("\n")
    print(json.dumps(inventory["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
