"""Recover the authentic retained endpoint after a fixture-output-only interruption."""
import json, sys, unittest
from pathlib import Path


def recover():
    recipe = sys.modules["test_nox_full_party_early_score"]
    record = recipe.retained_components[0]
    verify = record["authorized_uid_transition_verifier"]
    before = verify(record)
    case = record["case"]
    runtime = case.runtime
    fight = case.fight
    boss = fight.actors[-200]
    from wakfu_server.fight_checkpoint_store import snapshot
    from wakfu_server.maps.boss_score_runtime import staged_score

    selected = []

    def ref(row):
        if isinstance(row, dict):
            value = row.get("generic_effect", row.get("reference"))
            invocation = row.get("invocation")
            return value or getattr(invocation, "reference", None)
        return getattr(row, "generic_effect", None)

    for name in ("native_owned_group_effects", "native_retained_records"):
        for uid, row in getattr(fight, name, {}).items():
            if ref(row) == 401563:
                selected.append(dict(namespace=name, uid=uid, row=row))
    journals = {}
    for name in (
        "native_turn_event_deliveries",
        "native_npc_phase_deliveries",
        "native_turn_callback_deliveries",
    ):
        value = getattr(fight, name, None)
        if isinstance(value, dict):
            value = list(value.items())[-100:]
        elif isinstance(value, (list, tuple, set)):
            value = list(value)[-100:]
        journals[name] = value
    events = getattr(fight, "events", [])
    eventtail = [
        row
        for row in events
        if isinstance(row, dict)
        and (row.get("actor_id") == -200 or row.get("event_id") == 1002)
    ][-100:]
    result = dict(
        classification="root-authorized interrupted observation, not native terminal or victory",
        phase=fight.phase,
        table=fight.native_table_turn,
        timeline_round=getattr(fight, "native_timeline_round", None),
        turn=fight.turn_id,
        current=getattr(fight.current, "id", None),
        order=fight.order,
        score=staged_score(fight),
        boss_hp=boss.hp,
        players={
            str(i): dict(
                hp=fight.actors[i].hp,
                ap=fight.actors[i].ap,
                mp=fight.actors[i].mp,
                wp=fight.actors[i].effect_stats[4],
                position=fight.actors[i].position,
            )
            for i in case.characters
        },
        selected_boss_states=[
            dict(
                uid=e.uid,
                reference=e.reference,
                level=e.level,
                caster_id=getattr(e, "caster_id", None),
                effect_ids=getattr(e, "effect_ids", None),
            )
            for e in boss.state_ledger.entries
            if e.reference in (8969, 8977, 8978, 8979, 8988, 9031)
        ],
        retained401563=selected,
        event_journals=journals,
        boss_event_tail=eventtail,
        effect_execution_outcomes_not_instrumented_in_v3=True,
        runtime_id=id(runtime),
        fight_id=id(fight),
        store_id=id(record["fixture"].store),
        rng_id=id(case.rng),
        final_checkpoint=snapshot(fight, runtime=runtime),
        rng_state=case.rng.getstate(),
        verification_before=before,
        verification_after=verify(record),
        no_gameplay_actions=True,
        original_tokens_replaced=False,
        unchanged_since_admission_claimed=False,
    )
    output = Path(
        ".runtime/parallel-readiness-20261021/nox-v3-observer-only-interruption-authentic-endpoint-recovery.json"
    )
    output.write_text(json.dumps(result, indent=2, default=str) + "\n")
    record["observer_only_interruption_recovery"] = result
    rushu = sys.modules["test_rushu_dd230_native_opening"].RUSHU_ACTUAL_CHECKPOINT
    assert rushu["authorized_uid_transition_verifier"]()["original_tokens_preserved"]
    return unittest.TestSuite()
