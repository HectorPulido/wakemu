"""Opt-in earned Spirit encounter driver; never a discovered unit test.

The player strategy is a bounded witness attempt, not an optimal solver. Every
cast, turn and AI action uses the ordinary native transaction and ACK path.
"""
import struct
import time

from jondo_earned_scene_native_probe import build_scene, _drain, _oracle


def _facts(case):
    return {
        str(i): dict(
            hp=a.hp,
            maximum=a.max_hp,
            ap=a.ap,
            mp=a.mp,
            position=list(a.position),
            team=a.team,
            states=sorted(e.reference for e in a.state_ledger.entries),
        )
        for i, a in case.fight.actors.items()
    }


def _human_cast(scene, reference, target_id):
    from wakfu_server.combat_cast_delivery_source import connected_action_source
    from wakfu_server.combat_server_spell import prepare_server_spell
    from wakfu_server.combat_spell_commit import commit_spell_transaction
    from wakfu_server.combat_obstacle_condition import footprint
    from wakfu_ai.bridge.jondo_los import casting_visible

    case = scene.case
    actor = case.fight.current
    target = case.fight.actors[target_id]
    character, deck = connected_action_source(
        case.fight, case.characters, case.decks, scene.identity, scene.account, actor.id
    )
    if actor.controlled:
        from wakfu_server.combat_class_ai_spell import canonical_class_actions

        uid = canonical_class_actions(case.fight, actor, character, deck)[reference][
            "uid"
        ]
    else:
        uid = reference
    body = struct.pack(">qqiih", actor.id, uid, *target.position)
    source = _oracle(scene).state_identity(case.runtime)
    transaction = prepare_server_spell(
        body,
        character,
        case.monsters,
        case.fight,
        scene.account,
        deck,
        action_id=case.runtime.action_id + 1,
        critical=None,
        rng=case.rng,
        player_characters=case.characters,
        deck_blobs=case.decks,
        line_of_sight=lambda start, end, current: casting_visible(
            1134,
            start,
            end,
            current,
            blocking_footprints={
                a.id: footprint(a.position, a.physical_radius)
                for a in current.actors.values()
                if a.hp > 0
            },
        ),
    )
    assert _oracle(scene).state_identity(case.runtime) == source
    before = _facts(case)
    packets = commit_spell_transaction(
        case.runtime, transaction, stats_serializer=case.stats
    )
    _drain(case)
    return dict(
        type="cast",
        actorId=actor.id,
        spellId=reference,
        targetId=target_id,
        costs=transaction.plan["costs"],
        packets=len(packets),
        before=before,
        after=_facts(case),
    )


def _end_human(scene):
    from wakfu_server.combat_timeline_snapshot import current_wire_turn

    case = scene.case
    actor = case.fight.current
    case.runtime.end_turn(scene.account, actor.id, current_wire_turn(case.fight))
    _drain(case)


def run_scene(
    endpoint, *, strategy="earned_score", maximum_boundaries=96, maximum_wall_seconds=90
):
    """Run genuine Ready and at most thirteen completed rounds plus terminal.

    ``passive`` deliberately supplies no player attacks. A failed witness is
    reported as a failed witness, never as proof the encounter is unwinnable.
    """
    if strategy not in ("earned_score", "passive"):
        raise ValueError("Unknown bounded player witness")
    from wakfu_server.combat_effective_control import (
        effective_input_owner,
        effective_server_controlled,
    )
    from wakfu_server.monsters import native_abilities
    from wakfu_server.boss_score_runtime import staged_score
    from wakfu_ai.bridge.jondo_entry import run_prepared_turn
    from wakfu_ai.native.native_stats import NativeStats
    from wakfu_ai.transport.framed import FramedClient
    from wakfu_ai.transport.endpoint import tcp_address

    scene = build_scene("spirit")
    case = scene.case
    records, rejected = [], []
    channel = FramedClient(*tcp_address(endpoint), timeout=20)
    started = time.monotonic()
    error = None
    try:
        for boundary in range(maximum_boundaries):
            if time.monotonic() - started >= maximum_wall_seconds:
                break
            if case.fight.phase != "active":
                break
            actor = case.fight.current
            if actor is None:
                raise AssertionError("Active native timeline has no actor")
            row = dict(
                boundary=boundary,
                actorId=actor.id,
                turnId=case.fight.turn_id,
                round=case.fight.native_timeline_round,
                before=_facts(case),
                score=staged_score(case.fight),
            )
            records.append(row)
            if effective_server_controlled(case.fight, actor):
                oracle = _oracle(scene)
                stats = NativeStats(
                    characters=case.characters,
                    monsters=case.monsters,
                    fight_id=case.fight.id,
                    map_id=1134,
                )
                row["backend"] = "actual_jondo_tcp"
                row["diagnostics"] = []
                for _, diagnostic in run_prepared_turn(
                    case.runtime,
                    oracle,
                    stats,
                    channel,
                    deadline=time.monotonic() + 20,
                    max_actions=8,
                ):
                    row["diagnostics"].append(diagnostic)
                _drain(case)
            elif effective_input_owner(case.fight, actor) == scene.account:
                row["backend"] = "paid_player_witness"
                row["casts"] = []
                if strategy == "earned_score":
                    allies = [
                        a
                        for a in case.fight.actors.values()
                        if a.team == actor.team and a.hp > 0
                    ]
                    wounded = sorted(allies, key=lambda a: a.hp / max(1, a.max_hp))
                    if actor.id == scene.identity:
                        options = [
                            (8488, actor.id),
                            (8489, actor.id),
                            (8486, -7),
                            (8485, -7),
                            (8486, -7),
                        ]
                    else:
                        reference = case.monsters[actor.id]["ref"]
                        abilities = {
                            a["spell_id"]
                            for a in native_abilities(reference, actor.effective_level)
                        }
                        options = (
                            [(8492, wounded[0].id), (8491, -7), (8490, -7)]
                            if 8492 in abilities
                            else [
                                (8494, wounded[0].id),
                                (8493, -7),
                                (8495, scene.identity),
                                (8493, -7),
                            ]
                        )
                    for spell, target in options:
                        try:
                            row["casts"].append(_human_cast(scene, spell, target))
                        except ValueError as failure:
                            rejected.append(
                                dict(
                                    actor=actor.id,
                                    spell=spell,
                                    target=target,
                                    reason=str(failure),
                                )
                            )
                if case.fight.phase == "active" and case.fight.current.id == actor.id:
                    _end_human(scene)
            else:
                raise AssertionError("Native actor has no qualified control path")
            row["after"] = _facts(case)
            if case.fight.native_timeline_round > 14:
                break
    except Exception as failure:
        error = dict(type=type(failure).__name__, detail=str(failure))
    finally:
        channel.close()
    try:
        return dict(
            kind="source_earned_spirit_bounded_witness",
            strategy=strategy,
            passed=case.fight.phase == "finished" and case.fight.winner == 0,
            phase=case.fight.phase,
            winner=getattr(case.fight, "winner", None),
            rounds=case.fight.native_timeline_round,
            score=staged_score(case.fight),
            finalActors=_facts(case),
            nativeError=error,
            boundaries=records,
            rejectedPlayerPreflights=rejected,
            elapsedMs=(time.monotonic() - started) * 1000,
            setupTimings=scene.setupTimings,
            wallBudgetSeconds=maximum_wall_seconds,
            sourceAdmission="Disposable real account/session and native Ready; reconstructed map1134",
            limit="A bounded player witness; no optimality or universal defeatability claim",
        )
    finally:
        scene.database.doCleanups()


def run_one_npc_turn(endpoint):
    """Measure one ordinary genuine NPC boundary, without a victory assertion."""
    result = run_scene(
        endpoint, strategy="passive", maximum_boundaries=1, maximum_wall_seconds=60
    )
    rows = result["boundaries"]
    diagnostics = rows[0].get("diagnostics", []) if rows else []
    result["encounterWon"] = result["passed"]
    result["passed"] = (
        result["nativeError"] is None
        and len(rows) == 1
        and bool(diagnostics)
        and diagnostics[-1]["action"]["type"] == "end_turn"
    )
    result["kind"] = "genuine_spirit_single_npc_turn_timing"
    result[
        "limit"
    ] = "Exactly one native NPC boundary; no13-round/200k or encounter victory claim"
    return result
