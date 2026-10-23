"""Preserve the actual first fatality/auspice endpoint after cooperative stop."""
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
    from wakfu_server.fight_checkpoint_store import snapshot

    rows = {}
    for identity, a in f.actors.items():
        if True:
            rows[str(identity)] = dict(
                radius=getattr(a, "radius", None),
                native_obstacle_id=getattr(a, "native_obstacle_id", None),
                stats=dict(a.effect_stats),
                hp=a.hp,
                max_hp=a.max_hp,
                ap=a.ap,
                mp=a.mp,
                wp=a.effect_stats[4],
                position=a.position,
                distance_to_boss=abs(a.position[0] - b.position[0])
                + abs(a.position[1] - b.position[1]),
                marker9050=[
                    dict(
                        uid=e.uid,
                        reference=e.reference,
                        level=e.level,
                        caster=getattr(e, "caster_id", None),
                        effect_ids=getattr(e, "effect_ids", None),
                    )
                    for e in a.state_ledger.entries
                    if e.reference == 9050
                ],
            )
    events = getattr(f, "events", [])
    selected = [
        e
        for e in events
        if isinstance(e, dict)
        and any(
            e.get(k) in (8472, 408668, 408641, 401749, 401750, 9050)
            for k in (
                "reference",
                "reference_id",
                "state_id",
                "spell_id",
                "effect_reference",
            )
        )
    ]
    journals = {}
    for name in (
        "native_turn_event_deliveries",
        "native_encounter_post_start_deliveries",
        "native_npc_phase_deliveries",
    ):
        v = getattr(f, name, None)
        journals[name] = list(v.items())[-80:] if isinstance(v, dict) else v
    facts = dict(
        classification="Cooperative committed-boundary stop; no native victory",
        table=f.native_table_turn,
        turn=f.turn_id,
        current=getattr(f.current, "id", None),
        boss_position=b.position,
        boss_states=[
            (e.reference, e.level, getattr(e, "caster_id", None))
            for e in b.state_ledger.entries
        ],
        players=rows,
        auspice_events=selected[-100:],
        journal_tails=journals,
        native_qi_slots=getattr(f, "native_qi_slots", None),
        full_checkpoint=snapshot(f, runtime=c.runtime),
        rng_state=c.rng.getstate(),
        no_gameplay_actions=True,
        verification_before=before,
        verification_after=verify(r),
        rushu_verification=sys.modules[
            "test_rushu_dd230_eleven_slot_opening"
        ].RUSHU_ACTUAL_CHECKPOINT["authorized_service_transition_verifier"](),
    )
    Path(
        ".runtime/parallel-readiness-20261021/nox-v4-first-native-start9-full-geometry-checkpoint-readonly.json"
    ).write_text(json.dumps(facts, indent=2, default=str) + "\n")
    return unittest.TestSuite()
