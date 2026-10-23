"""Locate surviving authentic Nox offense objects without collection or replay."""
import gc, json, unittest
from pathlib import Path

retained_cases = []


def observe():
    output = []
    for value in gc.get_objects():
        if type(value).__name__ != "NativeNoxOffense":
            continue
        runtime = getattr(value, "runtime", None)
        fight = getattr(runtime, "fight", None)
        if fight is None or getattr(fight, "native_table_turn", None) != 4:
            continue
        actor = fight.actors.get(1)
        boss = fight.actors.get(-200)
        if (
            actor is None
            or boss is None
            or value.characters.get(1, {}).get("breed") != 1
        ):
            continue
        retained_cases.append(value)
        states = lambda a: [
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
            for e in a.state_ledger.entries
            if e.reference in (9027, 9028, 9029)
        ]
        records = {
            str(uid): record
            for uid, record in getattr(fight, "native_retained_records", {}).items()
            if isinstance(record, dict)
            and record.get("generic_effect") in (402183, 402211, 402212, 402213)
        }
        output.append(
            dict(
                turn=fight.turn_id,
                table=4,
                boss_hp=boss.hp,
                actor_ap=actor.ap,
                player_states=states(actor),
                boss_states=states(boss),
                retained_records=records,
            )
        )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/nox-latest-faille-live-gc-readonly.json"
    ).write_text(json.dumps(output, indent=2, default=repr))
    return unittest.TestSuite()
