"""Retain only surviving authentic phase-two Tal runtimes for source attribution."""
import gc, json, unittest
from pathlib import Path

retained_cases = []


def observe():
    output = []
    for current in gc.get_objects():
        if type(current).__name__ != "PaidComponentRuntime":
            continue
        fight = current.fight
        boss = fight.actors.get(-200)
        if boss is None or boss.hp != 80000 or boss.position != (0, -33, -22):
            continue
        states = [e for e in boss.state_ledger.entries if e.reference in (8231, 8243)]
        if not any(e.reference == 8231 and e.level == 2 for e in states):
            continue
        retained_cases.append(current)
        groups = {}
        for uid, row in getattr(fight, "native_owned_group_effects", {}).items():
            invocation = row.get("invocation", {})
            if isinstance(invocation, dict) and invocation.get("reference") in (
                379830,
                379920,
            ):
                groups[str(uid)] = {
                    "owned_group": row,
                    "retained_record": getattr(
                        fight, "native_retained_records", {}
                    ).get(uid),
                }
        output.append(
            dict(
                turn=fight.turn_id,
                table=getattr(fight, "native_table_turn", None),
                boss_hp=boss.hp,
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
                        )
                    }
                    for e in states
                ],
                groups=groups,
                event_deliveries=getattr(fight, "native_turn_event_deliveries", None),
            )
        )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/tal261-authentic-phase2-state-and-end-groups-readonly.json"
    ).write_text(json.dumps(output, indent=2, default=repr))
    return unittest.TestSuite()
