"""Generate209 for the native2786 outcome-healing charge owner."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    catalog = ROOT / "server/protocol/native-consumable-actions.json"
    payload = json.loads(catalog.read_text())
    row = next(row for row in payload["items"] if row["item_ref"] == 18422)
    state = row["plan"]["states"][0]
    assert (state["state_id"], state["level"], state["maximum_level"]) == (2786, 5, 300)
    metadata = state["metadata"]
    root = metadata["native_effects"]["114509"]
    assert root["native_metadata"]["target_masks"][5] == [1026]
    assert root["criteria"] == "(not IsBattleground())"
    child = metadata["native_effects"]["114510"]
    assert child["generic"] == 321 and child["values"] == [2786, 1]
    state.update(clock="event", duration_ms=0)
    metadata.update(
        combat_only_effect_ids=[114509],
        native_self_counter_effect_id=114510,
        counter=dict(
            decrement_event_ids=[1026],
            decrement=1,
            maximum_level=300,
            criteria=root["criteria"],
            executor="native_combat",
        ),
        outcome_event_policy="wakemu.owned-consumable-end1026-before-rewards-v1",
    )
    row.update(available=True, unsupported_reason="")
    encoded = json.dumps(
        row["plan"], ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    sql = "-- Native2786 END charge. Actual native321 changes carrier UID; durable1030 never decrements this family.\n"
    sql += (
        "UPDATE native_consumable_actions SET available=true,unsupported_reason='',plan='"
        + encoded.replace("'", "''")
        + "'::jsonb,source_sha256='"
        + digest
        + "' WHERE item_ref=18422;\n"
    )
    (ROOT / "server/migrations/209_native_consumable_vital_energy.sql").write_text(sql)
    catalog.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        + "\n"
    )
    print(
        json.dumps(
            dict(
                available=sum(row["available"] for row in payload["items"]),
                source_sha256=digest,
            )
        )
    )


if __name__ == "__main__":
    main()
