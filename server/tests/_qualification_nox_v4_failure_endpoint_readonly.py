"""Preserve the authentic paid endpoint after native summon preview failure."""
import json
from pathlib import Path
import sys
import unittest


def qualify():
    m = sys.modules["test_nox_full_party_victory_v4"]
    r = m.retained_components[0]
    before = m.verify_retained_component(r)
    case = r["case"]
    f = case.fight
    b = f.actors[-200]
    from wakfu_server.fight_checkpoint_store import snapshot
    from wakfu_server.maps.boss_score_runtime import staged_score

    result = dict(
        classification="Native summon preview error; no terminal, victory or external-stop claim",
        phase=f.phase,
        table=f.native_table_turn,
        turn=f.turn_id,
        current=getattr(f.current, "id", None),
        score=staged_score(f),
        boss_hp=b.hp,
        boss_states=[
            dict(
                reference=e.reference,
                uid=e.uid,
                level=e.level,
                caster_id=getattr(e, "caster_id", None),
            )
            for e in b.state_ledger.entries
        ],
        snapshot=snapshot(f, runtime=case.runtime),
        rng_state=case.rng.getstate(),
        receipt=r["receipt"],
        no_actions=True,
        verification_before=before,
        verification_after=m.verify_retained_component(r),
        rushu_verification=sys.modules[
            "test_rushu_dd230_eleven_slot_opening"
        ].RUSHU_ACTUAL_CHECKPOINT["authorized_service_transition_verifier"](),
    )
    p = Path(
        ".runtime/parallel-readiness-20261021/nox-v4-native-summon-environment-authority-error-authentic-endpoint.json"
    )
    p.write_text(json.dumps(result, indent=2, default=str) + "\n")
    r["final_error_endpoint_readonly"] = str(p)
    return unittest.TestSuite()
