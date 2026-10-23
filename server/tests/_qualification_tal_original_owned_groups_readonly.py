"""Read five requested groups from the explicitly retained authentic Tal case."""
import json, unittest
from pathlib import Path


def observe():
    import _qualification_tal_latest_actual_retained_markers as saved

    result = []
    for current in saved.retained_cases:
        fight = current.fight
        groups = {}
        for uid, row in getattr(fight, "native_owned_group_effects", {}).items():
            invocation = row.get("invocation", {})
            ref = (
                invocation.get("reference")
                if isinstance(invocation, dict)
                else getattr(invocation, "reference", None)
            )
            if ref in (378827, 378829, 378831, 378833, 379875):
                groups[str(uid)] = {
                    "owned_group": row,
                    "retained_record": getattr(
                        fight, "native_retained_records", {}
                    ).get(uid),
                }
        result.append(
            dict(
                turn=fight.turn_id,
                table=getattr(fight, "native_table_turn", None),
                boss_hp=fight.actors[-200].hp,
                groups=groups,
            )
        )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/tal-five-original-owned-groups-readonly.json"
    ).write_text(json.dumps(result, indent=2, default=repr))
    return unittest.TestSuite()
