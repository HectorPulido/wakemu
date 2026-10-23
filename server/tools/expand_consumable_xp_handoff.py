"""Generate208 for the native4872 to6874 START handoff, without editing198/205."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    catalog_path = ROOT / "server/protocol/native-consumable-actions.json"
    payload = json.loads(catalog_path.read_text())
    row = next(row for row in payload["items"] if row["item_ref"] == 22146)
    source = row["plan"]["states"][0]
    source["metadata"].pop("native_handoff_target", None)
    source["metadata"].pop("handoff_contract", None)
    evidence = (
        ROOT
        / ".runtime/item-action-readiness-20261020/remaining/xp-descriptor/effects-native.json"
    )
    native = json.loads(evidence.read_text())["effects"]
    target = copy.deepcopy(source)
    target.update(
        state_id=6874,
        level=100,
        maximum_level=100,
        effect_ids=[316696, 316698],
        removes=[],
    )
    target["metadata"].update(
        native_effects={
            str(identity): native[str(identity) + ":100"]
            for identity in target["effect_ids"]
        },
        combat_only_effect_ids=[],
        application_control_effect_ids=[],
        removal_event_ids=[],
    )
    source["metadata"].update(
        combat_only_effect_ids=[203486],
        native_handoff_target=target,
        handoff_contract="eWu.D fresh6874/eZk.a7200000ms;316701 under owned4872;checkpoint-atomic-v1",
    )
    row.update(available=True, unsupported_reason="")
    encoded = json.dumps(
        row["plan"], ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    sql = "-- Attested native START4872 to fresh6874 online-clock handoff.198/205 remain immutable.\n"
    sql += (
        "UPDATE native_consumable_actions SET available=true,unsupported_reason='',plan='"
        + encoded.replace("'", "''")
        + "'::jsonb,source_sha256='"
        + digest
        + "' WHERE item_ref=22146;\n"
    )
    (ROOT / "server/migrations/208_native_consumable_xp_handoff.sql").write_text(sql)
    catalog_path.write_text(
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
