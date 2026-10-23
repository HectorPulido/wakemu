"""Generate221 for the four native one-level Man Co removers."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFERENCES = {10657, 15980, 20471, 24265}
ORIGIN_SQL = """ALTER TABLE character_consumable_buffs ALTER COLUMN source_item_ref DROP NOT NULL;
ALTER TABLE character_consumable_buffs ALTER COLUMN source_item_uid DROP NOT NULL;
ALTER TABLE character_consumable_buffs ADD COLUMN native_origin jsonb;
ALTER TABLE character_consumable_buffs ADD CONSTRAINT consumable_native_origin CHECK (COALESCE((
    (source_item_ref IS NOT NULL AND source_item_uid IS NOT NULL AND native_origin IS NULL)
    OR (source_item_ref IS NULL AND source_item_uid IS NULL AND state_id=981
        AND clock='online' AND duration_ms=240000 AND level<=100
        AND native_origin IS NOT NULL AND jsonb_typeof(native_origin)='object'
        AND native_origin->>'kind'='native-state'
        AND native_origin->>'effect_id'='45980'
        AND native_origin->>'parent_state_id'='987'
        AND native_origin->>'character_id'=character_id::text
        AND (native_origin->>'parent_uid')::bigint>0
        AND (native_origin->>'source_uid')::bigint>0
        AND (native_origin->>'combat_uid')::bigint>0
        AND (native_origin->>'fight_id')::bigint>0)),false));
"""


def main():
    native_path = (
        ROOT / ".runtime/item-action-readiness-20261020/anti-ko/native981.json"
    )
    native = json.loads(native_path.read_text())
    assert (native["state_id"], native["maximum_level"], native["duration_ms"]) == (
        981,
        100,
        240000,
    )
    model = dict(
        state_id=981,
        maximum_level=100,
        duration_ms=240000,
        effect_ids_by_level=native["effect_ids_by_level"],
        native_effects={str(row["id"]): row for row in native["effects"].values()},
        native_state_flags={
            key: value for key, value in native["raw"].items() if key.startswith("es")
        },
    )
    assert model["effect_ids_by_level"]["9"] == [254573, 254574, 254576]
    assert model["effect_ids_by_level"]["10"] == [282494, 254574, 254576]
    catalog = ROOT / "server/protocol/native-consumable-actions.json"
    payload = json.loads(catalog.read_text())
    sql = [
        ORIGIN_SQL,
        "-- Native instant989 executes eZi45983: subtract ONE level of retained981, preserving its existing deadline.",
    ]
    found = set()
    for row in payload["items"]:
        if row["item_ref"] not in REFERENCES:
            continue
        found.add(row["item_ref"])
        plan = row["plan"]
        instant = plan.get("native_instant_states", plan["states"])
        assert (
            len(instant) == 1
            and instant[0]["state_id"] == 989
            and instant[0]["level"] == 1
        )
        assert instant[0]["metadata"]["native_state_flags"]["esr"] is True
        assert instant[0]["effect_ids"] == [45983]
        effect = instant[0]["metadata"]["native_effects"]["45983"]
        assert effect["generic"] == 321 and effect["values"] == [981, 1]
        assert not effect["criteria"] and effect["subscription"] is False
        assert plan["criterion"] == "HasState(981)"
        plan.update(
            native_instant_states=instant,
            states=[],
            remove_states=[],
            reduce_states=[
                dict(state_id=981, levels=1, effect=effect, native_state=model)
            ],
        )
        row.update(available=True, unsupported_reason="")
        encoded = json.dumps(
            plan, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        sql.append(
            "UPDATE native_consumable_actions SET available=true,unsupported_reason='',plan='"
            + encoded.replace("'", "''")
            + "'::jsonb,source_sha256='"
            + digest
            + "' WHERE item_ref="
            + str(row["item_ref"])
            + ";"
        )
    assert found == REFERENCES
    (ROOT / "server/migrations/221_native_consumable_anti_ko.sql").write_text(
        "\n".join(sql) + "\n"
    )
    catalog.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    )
    (
        ROOT / ".runtime/item-action-readiness-20261020/anti-ko/normalized981.json"
    ).write_text(json.dumps(model, sort_keys=True, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                rows=len(payload["items"]),
                available=sum(row["available"] for row in payload["items"]),
            )
        )
    )


if __name__ == "__main__":
    main()
