"""Generate immutable205 updates for native outcome-bound consumables.

Migration198 remains the original bounded inventory. Read its emitted INSERT
rows via the checked-in initial catalog before applying this expansion once.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "server/protocol/native-consumable-actions.json"
OUTPUT = ROOT / "server/migrations/205_native_consumable_outcome_actions.sql"
FLASKS = {
    18351: (114177, 113041),
    18355: (114231, 114233),
    18401: (114497, 114499),
    18406: (114237, 114239),
}
ROOTS = {
    **{key: [value[0]] for key, value in FLASKS.items()},
    18357: [176028, 176030],
    22491: [205959],
}


def expand(payload):
    for row in payload["items"]:
        if row["item_ref"] not in ROOTS:
            continue
        state = row["plan"]["states"][0]
        metadata = state["metadata"]
        metadata["combat_only_effect_ids"] = ROOTS[row["item_ref"]]
        metadata[
            "outcome_event_policy"
        ] = "wakemu.owned-consumable-end1026-before-rewards-v1"
        if row["item_ref"] in FLASKS:
            _, control = FLASKS[row["item_ref"]]
            nodes = metadata["native_effects"]
            root = nodes[str(control)]
            assert root["generic"] == 330 and root["native_metadata"]["target_masks"][
                5
            ] == [1030]
            assert (
                root["criteria"].split()
                == "GetFightModel() == 2 or GetFightModel() == 24 or GetFightModel() == 73 or GetFightModel() == 76".split()
            )
            state.update(clock="event", duration_ms=0)
            metadata["counter"] = dict(
                decrement_event_ids=[1030],
                decrement=1,
                maximum_level=state["maximum_level"],
                criteria=root["criteria"],
                fight_models=[2, 24, 73, 76],
            )
            metadata["counter_control_effect_ids"] = [control, *root["children"]]
        row.update(available=True, unsupported_reason="")
    return payload


def main():
    payload = expand(json.loads(CATALOG.read_text()))
    qualified = [row for row in payload["items"] if row["item_ref"] in ROOTS]
    assert len(qualified) == 6
    digest = hashlib.sha256(json.dumps(qualified, sort_keys=True).encode()).hexdigest()
    lines = [
        "-- Native owned-consumable END1026 expansion; original migration198 remains immutable."
    ]
    for row in qualified:
        plan = json.dumps(
            row["plan"], ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).replace("'", "''")
        lines.append(
            "UPDATE native_consumable_actions SET available=true,unsupported_reason='',plan='"
            + plan
            + "'::jsonb,source_sha256='"
            + digest
            + "' WHERE item_ref="
            + str(row["item_ref"])
            + ";"
        )
    OUTPUT.write_text("\n".join(lines) + "\n")
    CATALOG.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    )
    print(
        json.dumps(
            dict(
                updated=len(qualified),
                available=sum(row["available"] for row in payload["items"]),
                patch_sha256=digest,
            )
        )
    )


if __name__ == "__main__":
    main()
