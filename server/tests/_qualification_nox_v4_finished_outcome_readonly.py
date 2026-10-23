"""Export native final calendar, cleanup and death evidence without replay."""
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
    from wakfu_server.fight_checkpoint_store import snapshot

    facts = dict(
        phase=f.phase,
        winner=f.winner,
        table=f.native_table_turn,
        turn=f.turn_id,
        current=getattr(f.current, "id", None),
        events_tail=getattr(f, "events", [])[-180:],
        runtime_last_native_delivery=getattr(c.runtime, "last_native_delivery", None),
        players={
            str(i): dict(
                hp=f.actors[i].hp,
                position=f.actors[i].position,
                marker9050=[
                    (e.uid, e.reference, e.level, getattr(e, "caster_id", None))
                    for e in f.actors[i].state_ledger.entries
                    if e.reference == 9050
                ],
            )
            for i in c.characters
        },
        npc_actors={
            str(i): dict(
                hp=a.hp,
                position=a.position,
                source=getattr(a, "native_summon_source", None),
                states=[(e.uid, e.reference, e.level) for e in a.state_ledger.entries],
            )
            for i, a in f.actors.items()
            if i not in c.characters
        },
        checkpoint=snapshot(f, runtime=c.runtime),
        rng_state=c.rng.getstate(),
        no_actions=True,
        verification_before=before,
    )
    for name in (
        "native_turn_event_deliveries",
        "native_encounter_post_start_deliveries",
        "native_npc_phase_deliveries",
        "native_death_event_deliveries",
    ):
        value = getattr(f, name, None)
        facts[name] = list(value.items())[-100:] if isinstance(value, dict) else value
    facts["verification_after"] = verify(r)
    facts["rushu_verification"] = sys.modules[
        "test_rushu_dd230_eleven_slot_opening"
    ].RUSHU_ACTUAL_CHECKPOINT["authorized_service_transition_verifier"]()
    Path(
        ".runtime/parallel-readiness-20261021/nox-v4-finished-native-outcome-and-calendar-cleanup-readonly.json"
    ).write_text(json.dumps(facts, indent=2, default=str) + "\n")
    return unittest.TestSuite()
