"""Export native committed death evidence without advancing the encounter."""
import json
from pathlib import Path
import sys
import unittest


def qualify():
    m = sys.modules["test_nox_full_party_victory_v4"]
    r = m.retained_components[0]
    verify = r["authorized_scoped_policy_transition_verifier"]
    before = verify(r)
    c = r["case"]
    f = c.fight
    b = f.actors[-200]
    result = dict(
        table=f.native_table_turn,
        turn=f.turn_id,
        current=getattr(f.current, "id", None),
        events_tail=getattr(f, "events", [])[-250:],
        runtime_last_native_delivery=getattr(c.runtime, "last_native_delivery", None),
        boss8979=[
            dict(
                uid=e.uid,
                reference=e.reference,
                level=e.level,
                caster=getattr(e, "caster_id", None),
                effect_ids=getattr(e, "effect_ids", None),
            )
            for e in b.state_ledger.entries
            if e.reference == 8979
        ],
        state_entries_4_5={
            str(i): [
                vars(e) if hasattr(e, "__dict__") else str(e)
                for e in f.actors[i].state_ledger.entries
            ]
            for i in (4, 5)
        },
        no_actions=True,
        verification_before=before,
    )
    for name, value in vars(f).items():
        if "death" in name:
            result[name] = value
    chosen = []
    for name in ("native_owned_group_effects", "native_retained_records"):
        for uid, row in getattr(f, name, {}).items():
            inv = (
                row.get("invocation")
                if isinstance(row, dict)
                else getattr(row, "invocation", None)
            )
            ref = (
                row.get("generic_effect", row.get("reference"))
                if isinstance(row, dict)
                else getattr(row, "generic_effect", None)
            ) or getattr(inv, "reference", None)
            if ref in (401749, 401750, 8472, 408668, 408641):
                chosen.append(dict(namespace=name, uid=uid, row=row))
    result["retained_phase_rows"] = chosen
    result["verification_after"] = verify(r)
    result["rushu_verification"] = sys.modules[
        "test_rushu_dd230_eleven_slot_opening"
    ].RUSHU_ACTUAL_CHECKPOINT["authorized_service_transition_verifier"]()
    Path(
        ".runtime/parallel-readiness-20261021/nox-v4-first-start9-committed-native-death-source-readonly.json"
    ).write_text(json.dumps(result, indent=2, default=str) + "\n")
    return unittest.TestSuite()
