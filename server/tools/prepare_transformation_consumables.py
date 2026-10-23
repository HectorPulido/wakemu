"""Prepare type-738 native plans separately from immutable food migrations.

Default preparation keeps every candidate unavailable. The explicit qualified
mode is used only after original visual lifecycle and inventory tests pass.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from build_consumable_actions import build, encoded


def prepare(source, food, *, qualified_visual_runtime=False):
    items = json.loads((source / "items.json").read_text())
    native = json.loads((source / "native-descriptors.json").read_text())
    closure = json.loads((food / "state-closure.json").read_text())
    states = json.loads((source / "state-metadata.json").read_text())
    # aNv.cxn reads esy; false is the existing verified connected-time clock.
    assert all(state.get("esy") is False for state in states)
    direct = [
        row
        for row in items
        if all(effect["generic"] != 330 for effect in row["effects"])
    ]
    plans = build(
        direct,
        native,
        closure,
        states,
        {},
        include_transformations=True,
        expected_count=32,
    )
    for row in plans:
        for state in row["plan"]["states"]:
            metadata = state["metadata"]
            visual = []
            for node in metadata["native_effects"].values():
                hmi = node["native_metadata"].get("native_hmi_actions", {})
                kinds = {action["type"] for phase in hmi.values() for action in phase}
                if kinds & {
                    "APPEARANCE_CHANGE",
                    "SKIN_COLOR_CHANGE",
                    "SKIN_PART_VISIBILITY",
                }:
                    if (
                        node["generic"] != 400
                        or node["runner"] != "eXE"
                        or node["subscription"]
                        or node["values"]
                        or kinds
                        - {
                            "APPEARANCE_CHANGE",
                            "SKIN_COLOR_CHANGE",
                            "SKIN_PART_VISIBILITY",
                            "PARTICLE_SYSTEM",
                        }
                    ):
                        raise ValueError("Unqualified native transformation HMI family")
                    visual.append(node["id"])
            if visual:
                metadata["native_visual_effect_ids"] = sorted(visual)
                metadata["native_visual_policy"] = "original-retained-hmi-appearance-v1"
        row["plan"]["consumable_scope"] = "native-transformation"
        row["available"] = False
        reasons = set(filter(None, row["unsupported_reason"].split(";")))
        if not qualified_visual_runtime:
            reasons.add("native_visual_runtime_qualification_pending")
        row["unsupported_reason"] = ";".join(sorted(reasons))
        row["available"] = not reasons
    for item in items:
        if any(effect["generic"] == 330 for effect in item["effects"]):
            source_item = native["items"][str(item["reference"])]
            (root_id,) = source_item["effects"]
            parent = native["effects"][f'{root_id}:{source_item["level"]}']
            children = [
                native["effects"][f'{child}:{source_item["level"]}']
                for child in parent["children"]
            ]
            # This is an exact native ordered-success group, not a lottery.
            # USE excludes the existing state, so the first child cannot
            # succeed. Preserve the original group as provenance below.
            assert parent["generic"] == 330 and parent["values"] == [1, 1]
            assert not parent["criteria"] and not parent["subscription"]
            assert len(children) == 2 and all(
                child["generic"] == 304 and not child["subscription"]
                for child in children
            )
            assert children[0]["values"] == children[1]["values"]
            state_id, level, duration = children[1]["values"]
            assert children[0]["criteria"] == f'HasState({state_id}, "target")'
            assert not children[1]["criteria"]
            matching = next(
                row
                for row in plans
                if any(
                    state["state_id"] == state_id and state["level"] == level
                    for state in row["plan"]["states"]
                )
            )
            group_plan = copy.deepcopy(matching["plan"])
            group_plan["criterion"] = source_item["use_criteria"].get("USE", "")
            group_plan["native_item_criteria"] = source_item["use_criteria"]
            group_plan["native_item_effects"] = {
                str(node["id"]): copy.deepcopy(node) for node in (parent, *children)
            }
            group_plan["native_item_group_policy"] = dict(
                kind="ordered-one-success-existing-state-excluded-v1",
                root_id=root_id,
                children=parent["children"],
                state_id=state_id,
                selected_child=children[1]["id"],
            )
            plans.append(
                dict(
                    item_ref=item["reference"],
                    name=item["name"],
                    native_type=738,
                    available=qualified_visual_runtime,
                    unsupported_reason=""
                    if qualified_visual_runtime
                    else "native_visual_runtime_qualification_pending",
                    plan=group_plan,
                )
            )
    plans.sort(key=lambda row: row["item_ref"])
    assert len(plans) == len({row["item_ref"] for row in plans}) == 36
    return dict(
        scope="native-type-738-qualified"
        if qualified_visual_runtime
        else "native-type-738-review-only",
        items=plans,
        source_sha256=hashlib.sha256(encoded(native).encode()).hexdigest(),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--food", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--catalog", type=Path)
    parser.add_argument("--migration", type=Path)
    parser.add_argument("--qualified-visual-runtime", action="store_true")
    args = parser.parse_args()
    result = prepare(
        args.source, args.food, qualified_visual_runtime=args.qualified_visual_runtime
    )
    args.output.write_text(encoded(result) + "\n")
    if args.catalog:
        payload = json.loads(args.catalog.read_text())
        additions = {row["item_ref"]: row for row in result["items"]}
        base = [row for row in payload["items"] if row["item_ref"] not in additions]
        assert len(base) == 239
        payload["items"] = sorted(
            base + result["items"], key=lambda row: row["item_ref"]
        )
        args.catalog.write_text(encoded(payload) + "\n")
    if args.migration:

        def literal(value):
            return "'" + value.replace("'", "''") + "'"

        rows = []
        for row in result["items"]:
            rows.append(
                "("
                + ",".join(
                    (
                        str(row["item_ref"]),
                        "true" if row["available"] else "false",
                        literal(row["unsupported_reason"]),
                        literal(encoded(row["plan"])),
                        literal(result["source_sha256"]),
                    )
                )
                + ")"
            )
        args.migration.write_text(
            (
                "-- Native type738 retained-HMI consumables; original visual and inventory lifecycle qualified.\n"
                if args.qualified_visual_runtime
                else "-- Native type738 inventory; visual runtime qualification pending, no consumption enabled.\n"
            )
            + "INSERT INTO native_consumable_actions(item_ref,available,unsupported_reason,plan,source_sha256) VALUES\n"
            + ",\n".join(rows)
            + ";\n"
        )
    print(
        encoded(
            dict(
                items=len(result["items"]),
                available=sum(row["available"] for row in result["items"]),
                source_sha256=result["source_sha256"],
            )
        )
    )


if __name__ == "__main__":
    main()
