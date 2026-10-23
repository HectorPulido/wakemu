"""Read surviving exact Tal capped-fight carriers; never collect or replay."""
import gc, json, unittest
from pathlib import Path

retained_cases = []


def observe():
    rows = []
    for current in gc.get_objects():
        if type(current).__name__ != "PaidComponentRuntime":
            continue
        fight = current.fight
        boss = fight.actors.get(-200)
        if boss is None or boss.hp != 80000:
            continue
        receipt = getattr(fight, "native_npc_initialization_receipts", {}).get(-200, {})
        if receipt.get("ref") != 5500:
            continue
        retained_cases.append(current)
        references = (379874, 379883, 379885, 379887)
        markers = {
            str(uid): record
            for uid, record in getattr(fight, "native_retained_records", {}).items()
            if isinstance(record, dict)
            and (
                record.get("generic_effect") in references
                or record.get("effect_class") == 400
            )
        }
        rows.append(
            dict(
                turn=fight.turn_id,
                table=getattr(fight, "native_table_turn", None),
                boss_hp=boss.hp,
                actors=[
                    dict(
                        id=a.id,
                        hp=a.hp,
                        position=a.position,
                        states=[
                            {
                                k: getattr(e, k, None)
                                for k in (
                                    "uid",
                                    "reference",
                                    "level",
                                    "caster_id",
                                    "target_id",
                                    "effect_ids",
                                    "duration",
                                )
                            }
                            for e in a.state_ledger.entries
                        ],
                    )
                    for a in fight.actors.values()
                ],
                retained_markers=markers,
                owned_marker_groups={
                    str(uid): row
                    for uid, row in getattr(
                        fight, "native_owned_group_effects", {}
                    ).items()
                    if isinstance(row, dict)
                    and row.get("generic_effect", row.get("reference")) in references
                },
                group_population=getattr(
                    fight, "native_encounter_group_population", None
                ),
                area_activation=getattr(
                    fight, "native_encounter_area_activation", None
                ),
            )
        )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/tal-latest-capped-fight-marker-retention-readonly.json"
    ).write_text(json.dumps(rows, indent=2, default=repr))
    return unittest.TestSuite()
