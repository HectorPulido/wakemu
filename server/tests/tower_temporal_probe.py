"""Native end/ACK progression and actual granted-spell casts; no stat mutation."""
import json
import os
import tempfile
import struct
import traceback
from pathlib import Path
from collections import Counter
from time import monotonic
from unittest.mock import patch
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.combat_spell_grant import granted_spells
from native_supreme_paid_component_runtime import PaidComponentRuntime


def cast_granted(case, identity, reference, target):
    from wakfu_server.combat_server_spell import prepare_server_spell
    from wakfu_server.combat_spell_commit import commit_spell_transaction
    from wakfu_server.combat_spell_grant_book import grant_record
    from wakfu_server.combat_los import authoritative_visible
    from wakfu_server.combat_obstacle_condition import footprint

    actor = case.fight.actors[identity]
    before = dict(ap=actor.ap, mp=actor.mp, wp=actor.effect_stats[4], hp=target.hp)
    before_stats = {i: dict(a.effect_stats) for i, a in case.fight.actors.items()}
    grant = grant_record(case.fight, identity, reference)
    tx = prepare_server_spell(
        struct.pack(">qqiih", identity, grant["uid"], *target.position),
        case.characters[identity],
        case.monsters,
        case.fight,
        actor.owner_id,
        case.decks[identity],
        action_id=case.runtime.action_id + 1,
        critical=None,
        line_of_sight=lambda source, destination, candidate: authoritative_visible(
            case.map_id,
            source,
            destination,
            candidate,
            blocking_footprints={
                other.id: footprint(other.position, other.physical_radius)
                for other in candidate.actors.values()
                if other.hp > 0
            },
        ),
        **case.common
    )
    commit_spell_transaction(case.runtime, tx, stats_serializer=case.stats)
    after = case.fight.actors[identity]
    assert before["ap"] - after.ap == tx.plan["costs"]["ap"]
    return dict(
        reference=reference,
        uid=grant["uid"],
        target=target.id,
        costs=tx.plan["costs"],
        before=before,
        after=dict(
            ap=after.ap,
            mp=after.mp,
            wp=after.effect_stats[4],
            hp=case.fight.actors[target.id].hp,
        ),
        stat_changes={
            str(i): {
                str(k): [before_stats[i].get(k), v]
                for k, v in a.effect_stats.items()
                if before_stats[i].get(k) != v
            }
            for i, a in case.fight.actors.items()
            if i in before_stats and before_stats[i] != a.effect_stats
        },
    )


def run_temporal(fight, characters, monsters, decks, profile):
    case = PaidComponentRuntime(
        fight, characters, monsters, decks, map_id=1159, seed=17
    )
    first = next(iter(characters))
    events = []
    steps = []
    casts = []
    interesting = {
        245113,
        251939,
        251940,
        251941,
        394916,
        394918,
        394920,
        394922,
        245358,
        245359,
        252200,
    }

    def sink(**row):
        if row.get("effect_reference") in interesting or row.get("status") == "failed":
            events.append(row)

    def facts():
        f = case.fight
        return dict(
            table=f.native_table_turn,
            round=f.native_timeline_round,
            phase=f.phase,
            current=None if f.current is None else f.current.id,
            actors={
                str(i): dict(
                    ref=monsters[i]["ref"]
                    if i in monsters
                    else getattr(a, "native_summon_source", {}).get("ref"),
                    hp=a.hp,
                    maximum=a.max_hp,
                    ap=a.ap,
                    mp=a.mp,
                    controlled=a.controlled,
                    position=list(a.position),
                    states=[
                        dict(id=s.reference, level=s.level)
                        for s in a.state_ledger.entries
                    ],
                )
                for i, a in f.actors.items()
            },
            areas={
                str(i): dict(reference=r.get("reference"), position=r.get("position"))
                for i, r in getattr(f, "native_effect_areas", {}).items()
            },
            grants={str(i): sorted(granted_spells(f, i)) for i in characters},
        )

    started = monotonic()
    baseline = facts()
    with combat_diagnostic_scope(sink, limit=20000):
        case.runtime.turn_started(arm_deadline=False)
    from wakfu_server.combat_native_spell_casting import catalog

    metadata = {str(s): catalog().get(str(s)) for s in (6363, 6364)}
    attempted = set()
    rollback = []
    for index in range(160):
        f = case.fight
        if f.phase != "active" or f.current is None or f.native_table_turn >= 8:
            break
        actor = f.current
        before = facts()
        beginning = len(events)
        # One legal attempt per original granted spell, against actual live
        # native-born crystals. Transaction guards retain all native criteria.
        if actor.id in characters:
            for spell in (6364, 6363):
                f = case.fight
                actor = f.current
                if spell in attempted or spell not in granted_spells(f, actor.id):
                    continue
                cost = metadata[str(spell)]["costs"][
                    granted_spells(f, actor.id)[spell]["level"] - 1
                ][0]
                if actor.ap < cost:
                    continue
                candidates = [
                    a
                    for i, a in f.actors.items()
                    if i not in monsters
                    and i not in characters
                    and a.hp > 0
                    and getattr(a, "native_summon_source", {}).get("ref")
                    in {4657, 4658, 4659, 4660}
                ]
                if not candidates:
                    continue
                target = (
                    actor
                    if spell == 6363
                    else min(
                        candidates,
                        key=lambda a: (
                            abs(a.position[0] - actor.position[0])
                            + abs(a.position[1] - actor.position[1]),
                            a.id,
                        ),
                    )
                )
                attempted.add(spell)
                try:
                    with combat_diagnostic_scope(sink, limit=20000):
                        result = cast_granted(case, actor.id, spell, target)
                    casts.append(
                        dict(table=f.native_table_turn, accepted=True, **result)
                    )
                except ValueError as error:
                    casts.append(
                        dict(
                            table=f.native_table_turn,
                            spell=spell,
                            target=target.id,
                            accepted=False,
                            error=str(error),
                        )
                    )
        try:
            with combat_diagnostic_scope(sink, limit=20000):
                if profile == 7 and not rollback:
                    from wakfu_server.combat_effect_area_events import (
                        NativeAreaEventRuntime,
                    )
                    from wakfu_server.fight_checkpoint_store import snapshot

                    original = NativeAreaEventRuntime.fake_fighter_death
                    before_snapshot = snapshot(case.fight)
                    before_rng = case.rng.getstate()

                    def fail_own_area(self, row, source_id, **kw):
                        if row.get("reference") == 1284:
                            assert row["native_faw_hp_current"] == 0
                            assert 65 in row["native_current_fight_properties"]
                            raise ValueError("QA HP-Qq post-setter rollback witness")
                        return original(self, row, source_id, **kw)

                    try:
                        with patch.object(
                            NativeAreaEventRuntime, "fake_fighter_death", fail_own_area
                        ):
                            case.advance()
                    except ValueError as error:
                        if str(error) != "QA HP-Qq post-setter rollback witness":
                            raise
                        assert snapshot(case.fight) == before_snapshot
                        assert case.rng.getstate() == before_rng
                        rollback.append(
                            dict(
                                status="PASS",
                                table=case.fight.native_table_turn,
                                scope="Actual owned end/ACK failed after preview HP0/FFE65; live full snapshot and RNG unchanged",
                            )
                        )
                        case.advance()
                else:
                    case.advance()
        except Exception as error:
            steps.append(
                dict(
                    before=before,
                    error=type(error).__name__ + ": " + str(error),
                    traceback=traceback.format_exc(),
                    events=events[beginning:],
                )
            )
            break
        steps.append(dict(before=before, after=facts(), events=events[beginning:]))
    result = dict(
        profile=profile,
        elapsed_seconds=monotonic() - started,
        baseline=baseline,
        final=facts(),
        spell_metadata=metadata,
        casts=casts,
        steps=steps,
        rollback=rollback,
        root_counts=dict(
            Counter(
                str(e["effect_reference"]) + ":" + str(e.get("status")) for e in events
            )
        ),
        scope="One-player native clock probe, all other turns passed through owned end/ACK; no NPC AI offense or victory claim. No HP/AP/state assignment. Initial level50, key and party are fixture premises.",
    )
    (
        Path(os.environ.get("WAKFU_TEST_TOWER_ARTIFACT_DIR", tempfile.gettempdir()))
        / ("profile" + str(profile) + ".json")
    ).write_text(json.dumps(result, indent=2, default=str) + "\n")
    print(
        "TEMPORAL",
        json.dumps(
            dict(
                profile=profile,
                steps=len(steps),
                table=result["final"]["table"],
                phase=result["final"]["phase"],
                casts=casts,
                roots=result["root_counts"],
            )
        ),
    )

    failed = [step for step in steps if step.get("error")]
    if failed:
        raise AssertionError(failed[0]["traceback"])
    assert result["final"]["table"] >= 8, "Temporal probe ended before completed table7"
    assert {6363, 6364} <= {
        row["reference"] for row in casts if row.get("accepted")
    }, "Both native grants must be paid successfully"
    if profile == 7:
        assert rollback, "HP-Qq death rollback boundary was not reached"
