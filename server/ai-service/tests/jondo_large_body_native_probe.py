"""Bounded actual-native large-body diagnostics, separate from encounter wins."""
from random import Random
import time
from unittest.mock import patch


def _oracle(case):
    from wakfu_ai.native.native_oracle import NativeOracle

    return NativeOracle(
        case.runtime,
        characters=case.characters,
        monsters=case.monsters,
        decks=case.decks,
        excluded_decks={7: frozenset()},
        viewer_id=7,
        flags=dict(native_area_callbacks=True, native_start_events=True),
    )


def body_side_los():
    import importlib
    import test_jondo_brizlon_native as fixture

    importlib.reload(fixture)
    from wakfu_server.combat_casting_los import native_casting_los
    from wakfu_server.combat_los import authoritative_visible
    from wakfu_server.combat_obstacle_condition import footprint
    import wakfu_ai.bridge.jondo_los as los

    importlib.reload(los)
    case = fixture.build_fixture(4251, boss_position=(-4, -7, -1))
    fight = case.fight
    oracle = _oracle(case)
    before = oracle.state_identity(case.runtime)
    player, boss = fight.actors[7], fight.actors[-7]
    aim = (-5, -7, -1)
    _, adapter = oracle.factory(fight, case.runtime.action_id + 1, Random(17))
    diagnostic = {}
    native = native_casting_los(
        fight, adapter.actor_authority, player.id, aim, boss, diagnostic=diagnostic
    )
    footprints = {
        a.id: footprint(a.position, a.physical_radius)
        for a in fight.actors.values()
        if a.hp > 0
    }
    observed = []

    def visible(map_id, source, target, candidate, **kwargs):
        observed.append(
            [
                dict(id=a.id, position=list(a.position), height=a.native_los_height)
                for a in candidate.actors.values()
                if a.hp > 0 and tuple(a.position) == tuple(target)
            ]
        )
        return authoritative_visible(map_id, source, target, candidate, **kwargs)

    with patch("wakfu_server.combat_los.authoritative_visible", visible):
        advisory = los.casting_visible(
            1134, player.position, aim, fight, blocking_footprints=footprints
        )
    assert oracle.state_identity(case.runtime) == before
    assert observed and observed[0] == [
        dict(id=boss.id, position=list(aim), height=boss.native_los_height)
    ]
    assert advisory == native
    return dict(
        passed=True,
        source=list(player.position),
        targetCenter=list(boss.position),
        aimedSide=list(aim),
        actualTargetHeight=boss.native_los_height,
        native=native,
        advisory=advisory,
        observedTargetContexts=observed,
        nativeDiagnostic=diagnostic,
        sourceUnchanged=True,
        scope="Read-only actual casting LOS at a large target body side",
    )


def shin_turn(endpoint="tcp://wakemu-jondo-brizlon-final-qa:8091"):
    import importlib
    import test_jondo_brizlon_native as fixture

    importlib.reload(fixture)
    from wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_ai.native.native_stats import NativeStats
    import wakfu_ai.bridge.jondo_entry as entry
    import wakfu_ai.bridge.jondo_snapshot as snapshot
    import wakfu_ai.bridge.jondo_los as los

    importlib.reload(los)
    importlib.reload(snapshot)
    importlib.reload(entry)
    from wakfu_ai.transport.framed import FramedClient
    from wakfu_ai.transport.endpoint import tcp_address
    from wakfu_server.combat_obstacle_condition import footprint

    case = fixture.build_fixture(
        2157, boss_position=(-4, -7, -1), player_position=(-10, -7, -1)
    )
    for _ in range(64):
        if case.fight.current.id == -7:
            break
        case.advance()
    assert case.fight.current.id == -7
    actor = case.fight.actors[-7]
    assert actor.physical_radius == 1
    before = dict(
        position=list(actor.position),
        ap=actor.ap,
        mp=actor.mp,
        playerHp=case.fight.actors[7].hp,
        npcHp=actor.hp,
    )
    oracle = _oracle(case)
    stats = NativeStats(
        characters=case.characters,
        monsters=case.monsters,
        fight_id=case.fight.id,
        map_id=1134,
    )
    original = NativeOracle.commit
    commits = []

    def observe(current, action, **kwargs):
        traveler = current.runtime.fight.current
        others = set().union(
            *(
                set(footprint(a.position, a.physical_radius))
                for a in current.runtime.fight.actors.values()
                if a.hp > 0 and a.id != traveler.id
            )
        )
        if action.get("type") == "move":
            assert all(
                not (set(footprint(tuple(point), traveler.physical_radius)) & others)
                for point in action["path"]
            ), "Large body crossed a peer actor"
        result = original(current, action, **kwargs)
        commits.append(
            dict(
                action=action,
                playerHp=current.runtime.fight.actors[7].hp,
                position=list(current.runtime.fight.actors[-7].position),
            )
        )
        return result

    channel = FramedClient(*tcp_address(endpoint), timeout=20)
    diagnostics = []
    started = time.monotonic()
    try:
        with patch.object(NativeOracle, "commit", observe):
            for packets, diagnostic in entry.run_prepared_turn(
                case.runtime,
                oracle,
                stats,
                channel,
                deadline=started + 20,
                max_actions=4,
            ):
                diagnostics.append(
                    dict(
                        action=diagnostic["action"],
                        reason=diagnostic.get("reason"),
                        rejected=diagnostic.get("rejectedActions", []),
                        packets=len(packets),
                    )
                )
    finally:
        channel.close()
    fixture._drain(case)
    after = dict(
        position=list(case.fight.actors[-7].position),
        ap=case.fight.actors[-7].ap,
        mp=case.fight.actors[-7].mp,
        playerHp=case.fight.actors[7].hp,
    )
    moved = any(c["action"]["type"] == "move" for c in commits)
    damaged = after["playerHp"] < before["playerHp"]
    return dict(
        passed=moved and damaged,
        reference=2157,
        nativeLevel=23,
        physicalRadius=1,
        scope="One native generic-map opening, not the official Shin Larva encounter or a victory",
        endpoint=endpoint,
        before=before,
        after=after,
        moved=moved,
        actualDamage=before["playerHp"] - after["playerHp"],
        nativeCommits=commits,
        diagnostics=diagnostics,
        elapsedMs=(time.monotonic() - started) * 1000,
        awaitingAck=case.runtime.awaiting_ack,
        peerBodyCrossings=0,
    )
