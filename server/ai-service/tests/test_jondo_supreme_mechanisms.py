"""Opt-in Jondo solvability checks reusing the native paid-player witnesses.

No boss spell or phase input is supplied by this adapter: Jondo controls the
boss over TCP; the existing player solver and native assertions stay intact.
"""
import inspect
import textwrap


def _jondo_boss_turn(
    case, characters, monsters, decks, targets, hammered, receipt, *, backend="jondo"
):
    import struct
    import time
    from wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_ai.native.native_stats import NativeStats
    from wakfu_ai.bridge.jondo_entry import run_prepared_turn
    from wakfu_ai.transport.framed import FramedClient
    from wakfu_ai.transport.endpoint import tcp_address

    first = next(iter(characters))
    runtime = case.runtime
    if not hasattr(runtime, "tactical_encounter_id"):
        import uuid

        runtime.tactical_encounter_id = uuid.uuid4().hex
    before = {identity: runtime.fight.actors[identity].hp for identity in targets}
    source_events = len(runtime.fight.events)
    oracle = NativeOracle(
        runtime,
        characters=characters,
        monsters=monsters,
        decks=decks,
        excluded_decks={i: frozenset() for i in characters},
        viewer_id=first,
        flags=dict(native_area_callbacks=True, native_start_events=True),
    )
    stats = NativeStats(
        characters=characters, monsters=monsters, fight_id=runtime.fight.id, map_id=1056
    )
    channel = FramedClient(*tcp_address("tcp://ai-jondo:8091"), timeout=20)
    actions = []
    began = time.monotonic()
    try:
        if backend == "current":
            from wakfu_ai.native.native_turn import run_turn
            from wakfu_ai.native.native_profiles import encounter_profiles
            from wakfu_ai.bridge.world_entry import native_exporter, context_transport
            from wakfu_server import native_catalog

            profiles = encounter_profiles(runtime, native_catalog._database(), monsters)
            profile = profiles.get(
                monsters[runtime.fight.current.id]["ref"], profiles[None]
            )
            channel.close()
            channel = context_transport(
                "tcp://ai:8090", first_turn=runtime.fight.current.turn_count == 1
            )
            deliveries = run_turn(
                runtime,
                characters=characters,
                monsters=monsters,
                decks=decks,
                excluded_decks={i: frozenset() for i in characters},
                viewer_id=first,
                flags=dict(native_area_callbacks=True, native_start_events=True),
                transport=channel,
                exporter=native_exporter(),
                policy=profile["policy"],
                policy_version=profile["identity"],
                stats_serializer=stats,
                max_actions=8,
                budget_seconds=20 if runtime.fight.current.turn_count == 1 else 10,
            )
        else:
            deliveries = run_prepared_turn(
                runtime,
                oracle,
                stats,
                channel,
                deadline=began + (20 if runtime.fight.current.turn_count == 1 else 10),
                max_actions=8,
            )
        for packets, diagnostic in deliveries:
            actions.append(
                dict(
                    action=diagnostic["action"],
                    packetCount=len(packets),
                    reason=diagnostic.get("reason"),
                    diagnostic=diagnostic,
                )
            )
    finally:
        channel.close()
    for action in actions:
        chosen = action["action"]
        if (
            chosen.get("type") == "cast"
            and chosen.get("spellId") == 5693
            and chosen.get("targetId") in targets
        ):
            hammered.add(chosen["targetId"])
            receipt["hammer_targets"].append(chosen["targetId"])
    receipt.setdefault("jondoTurns", []).append(
        dict(
            backend=backend,
            actions=actions,
            wallMs=(time.monotonic() - began) * 1000,
            beforeTotemHP=before,
            afterTotemHP={i: runtime.fight.actors[i].hp for i in targets},
            hammerTargets=list(hammered),
        )
    )
    receipt["threshold_sources"].extend(
        event
        for event in runtime.fight.events[source_events:]
        if event.get("kind") == "state_applied" and event.get("state_id") == 4227
    )
    for _ in range(32):
        if runtime.awaiting_ack is None:
            break
        runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
    if len(receipt["jondoTurns"]) >= 2 and not hammered:
        raise AssertionError(
            backend
            + " completed two native Moon turns without hammering any required original totem with5693; the existing four-totem player witness has not received its hammer premise"
        )


def adapted_fulmoon_case(*, backend="jondo"):
    """Keep the existing paid-player solver and every original gate assertion."""
    from test_fulmoon_paid_native_four_totems import FulMoonPaidNativeFourTotemsTests

    original = (
        FulMoonPaidNativeFourTotemsTests.test_four_living_original_totems_earn_4227_without_hp_or_state_gifts
    )
    source = textwrap.dedent(inspect.getsource(original))
    start = source.index("            if identity == -200:")
    end = source.index(
        "            elif identity in characters and len(hammered) == 4:", start
    )
    source = (
        source[:start]
        + """            if identity == -200:
                _jondo_boss_turn(case, characters, monsters, decks, targets, hammered, receipt)
                continue
"""
        + source[end:]
    )
    namespace = dict(
        original.__globals__,
        _jondo_boss_turn=lambda *args: _jondo_boss_turn(*args, backend=backend),
    )
    exec(
        compile(source, "<jondo-native-fulmoon-paid-player-adapter>", "exec"), namespace
    )
    method = namespace[original.__name__]
    return type(
        "JondoFulMoonSolvabilityTests",
        (FulMoonPaidNativeFourTotemsTests,),
        {"test_jondo_drives_boss_while_native_players_earn_all_four_totems": method},
    )


def run_fulmoon(*, control=False, scenario="moon", backend="jondo"):
    """Use only the explicitly separate test database and disposable schema."""
    if scenario not in ("moon", "ogrest", "ombrage"):
        raise ValueError("Unknown native mechanism scenario")
    import json
    import os
    from pathlib import Path
    from contextlib import contextmanager
    from io import StringIO
    from unittest.mock import patch
    import unittest
    from psycopg.conninfo import conninfo_to_dict
    from wakfu_server.postgres import Database

    root = Path(__file__).resolve().parents[3]
    import psycopg

    connect = psycopg.connect

    def guarded_connect(conninfo="", **kwargs):
        facts = conninfo_to_dict(
            conninfo, **{k: v for k, v in kwargs.items() if k == "dbname"}
        )
        if facts.get("dbname") != "wakemu_migration_test":
            kwargs["options"] = (
                kwargs.get("options", facts.get("options", ""))
                + " -c default_transaction_read_only=on"
            )
        return connect(conninfo, **kwargs)

    original = Database.connection

    @contextmanager
    def isolated_connections(database, *args, **kwargs):
        with original(database, *args, **kwargs) as db:
            if (
                conninfo_to_dict(database.conninfo).get("dbname")
                != "wakemu_migration_test"
            ):
                db.execute("SET TRANSACTION READ ONLY")
            yield db

    with patch.dict(
        os.environ,
        {
            "WAKFU_POSTGRES_TEST_URL": "host=postgres dbname=wakemu_migration_test user=wakemu",
            "PGOPTIONS": "-c default_transaction_read_only=off",
            "WAKFU_MIGRATIONS_TEST_DIR": "/app/migrations",
        },
    ), patch.object(Database, "connection", isolated_connections), patch.object(
        psycopg, "connect", guarded_connect
    ):
        if scenario == "ombrage":
            if control:
                from test_ombrage_native_paid_clock import OmbrageNativePaidClockTests

                cls = OmbrageNativePaidClockTests
            else:
                cls = adapted_ombrage_case()
            instance = cls(
                "test_paid_stabilization_opens_early_native_vulnerability_component"
            )
        elif scenario == "ogrest":
            if control:
                from test_ogrest_reconstructed_native_phase import (
                    OgrestReconstructedNativePhaseTests,
                )

                cls = OgrestReconstructedNativePhaseTests
            else:
                cls = adapted_ogrest_case()
            instance = cls("test_original_artifact_six_phases_and_owned_final_exit")
        elif control:
            from test_fulmoon_paid_native_four_totems import (
                FulMoonPaidNativeFourTotemsTests,
            )

            instance = FulMoonPaidNativeFourTotemsTests(
                "test_four_living_original_totems_earn_4227_without_hp_or_state_gifts"
            )
        else:
            instance = adapted_fulmoon_case(backend=backend)(
                "test_jondo_drives_boss_while_native_players_earn_all_four_totems"
            )
        suite = unittest.TestSuite([instance])
        output = StringIO()
        result = unittest.TextTestRunner(stream=output, verbosity=2).run(suite)
    receipt = root / (
        ".runtime/parallel-readiness-20261021/ogrest-real-six-phases-terminal-receipt.json"
        if scenario == "ogrest"
        else ".runtime/ultimate-scenes-20261021/fulmoon-four-native-totems-positive4227.json"
    )
    if scenario == "ombrage":
        choices = list(
            (root / ".runtime/ultimate-scenes-20261021").glob(
                "ombrage-paid-clock-*.json"
            )
        )
        receipt = (
            max(choices, key=lambda p: p.stat().st_mtime_ns)
            if choices
            else root / "missing-ombrage-receipt"
        )
    return dict(
        backend=backend,
        scenario=scenario,
        control=control,
        testsRun=result.testsRun,
        failures=[dict(id=t.id(), trace=s) for t, s in result.failures],
        errors=[dict(id=t.id(), trace=s) for t, s in result.errors],
        skipped=[dict(id=t.id(), reason=s) for t, s in result.skipped],
        log=output.getvalue(),
        nativeMechanism=json.loads(receipt.read_bytes()) if receipt.exists() else None,
        scope=(
            "Unchanged original native witness; no Jondo selection"
            if control
            else backend
            + " TCP controls NPC turns; unchanged native paid-player solver"
        )
        + "; disposable isolated schema only",
    )


def _jondo_npc_turn(runtime, characters, monsters, decks, receipt, *, map_id):
    """Run actual server-controlled actors; retain native event-only endings."""
    import struct
    import time
    import uuid
    from wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_ai.native.native_stats import NativeStats
    from wakfu_ai.native.native_control import effective_server_controlled
    from wakfu_ai.bridge.jondo_entry import run_prepared_turn
    from wakfu_ai.transport.framed import FramedClient
    from wakfu_ai.transport.endpoint import tcp_address
    from tools.combat_audit_turns import advance_actual_turn
    from wakfu_server.combat_automatic_npc_turn import requires_automatic_npc_turn_end

    actor = runtime.fight.current
    identity, turn = actor.id, runtime.fight.turn_id
    if not hasattr(runtime, "tactical_encounter_id"):
        runtime.tactical_encounter_id = uuid.uuid4().hex
    actions = []
    started = time.monotonic()
    if requires_automatic_npc_turn_end(runtime.fight, actor):
        packets = runtime.end_automatic_npc_turn(identity, turn)
        actions.append(
            dict(
                action={"type": "end_turn"},
                packetCount=len(packets),
                reason="native_event_only_controller",
            )
        )
    elif not effective_server_controlled(runtime.fight, actor):
        advance_actual_turn(runtime)
        actions.append(
            dict(
                action={"type": "end_turn"}, reason="native_actor_not_server_controlled"
            )
        )
    else:
        first = next(iter(characters))
        oracle = NativeOracle(
            runtime,
            characters=characters,
            monsters=monsters,
            decks=decks,
            excluded_decks={i: frozenset() for i in characters},
            viewer_id=first,
            flags=dict(native_area_callbacks=True, native_start_events=True),
        )
        stats = NativeStats(
            characters=characters,
            monsters=monsters,
            fight_id=runtime.fight.id,
            map_id=map_id,
        )
        channel = FramedClient(*tcp_address("tcp://ai-jondo:8091"), timeout=20)
        try:
            for packets, diagnostic in run_prepared_turn(
                runtime,
                oracle,
                stats,
                channel,
                deadline=started + (20 if actor.turn_count == 1 else 10),
                max_actions=12,
            ):
                actions.append(
                    dict(action=diagnostic["action"], packetCount=len(packets))
                )
        finally:
            channel.close()
    for _ in range(32):
        if runtime.awaiting_ack is None:
            break
        runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
    receipt.setdefault("jondoTurns", []).append(
        dict(
            actor=identity,
            turn=turn,
            actions=actions,
            wallMs=(time.monotonic() - started) * 1000,
            phaseAfter=runtime.fight.phase,
        )
    )
    print(
        "JONDO_MECHANISM_NATIVE_TURN",
        identity,
        turn,
        len(actions),
        runtime.fight.phase,
        flush=True,
    )


def adapted_ogrest_case():
    from test_ogrest_reconstructed_native_phase import (
        OgrestReconstructedNativePhaseTests,
    )

    original = OgrestReconstructedNativePhaseTests.exercise_native_phases
    source = textwrap.dedent(inspect.getsource(original))
    old = "        advance_actual_turn(runtime)"
    if source.count(old) != 1:
        raise AssertionError("Original Ogrest native boundary source drift")
    source = source.replace(
        old,
        """        if runtime.fight.current is not None and runtime.fight.current.id not in characters:
            _jondo_npc_turn(runtime, characters, monsters, decks, receipt, map_id=1156)
        else:
            advance_actual_turn(runtime)""",
    )
    namespace = dict(original.__globals__, _jondo_npc_turn=_jondo_npc_turn)
    exec(compile(source, "<jondo-ogrest-native-npc-turn-adapter>", "exec"), namespace)
    return type(
        "JondoOgrestTerminalTests",
        (OgrestReconstructedNativePhaseTests,),
        {"exercise_native_phases": namespace[original.__name__]},
    )


def _advance_with_jondo(runtime, characters, monsters, decks, receipt, *, map_id):
    if runtime.fight.current is not None and runtime.fight.current.id not in characters:
        return _jondo_npc_turn(
            runtime, characters, monsters, decks, receipt, map_id=map_id
        )
    from tools.combat_audit_turns import advance_actual_turn

    return advance_actual_turn(runtime)


def adapted_ombrage_case():
    from test_ombrage_native_paid_clock import OmbrageNativePaidClockTests

    original = OmbrageNativePaidClockTests._run_strategy
    source = textwrap.dedent(inspect.getsource(original))
    old = "advance_actual_turn(runtime)"
    if source.count(old) != 6:
        raise AssertionError("Original Ombrage native boundary source drift")
    source = source.replace(
        old,
        "_advance_with_jondo(runtime, characters, monsters, decks, receipt, map_id=1229)",
    )
    namespace = dict(original.__globals__, _advance_with_jondo=_advance_with_jondo)
    exec(compile(source, "<jondo-ombrage-native-npc-turn-adapter>", "exec"), namespace)
    return type(
        "JondoOmbrageVulnerabilityTests",
        (OmbrageNativePaidClockTests,),
        {"_run_strategy": namespace[original.__name__]},
    )


def warm_current_catalog():
    """Administrative context provisioning only; no fight or native decision."""
    import time
    from wakfu_ai.bridge.world_entry import native_exporter, context_transport

    began = time.monotonic()
    channel = context_transport("tcp://ai:8090", first_turn=True, timeout=120)
    try:
        manifest = channel.catalog(native_exporter())
        return dict(
            manifest=manifest,
            wallMs=(time.monotonic() - began) * 1000,
            metrics=channel.metrics,
            qualification="Outside native turn budget; no fight/decision/commit",
        )
    finally:
        channel.close()


if __name__ == "__main__":
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario", choices=("moon", "ogrest", "ombrage"), default="moon"
    )
    parser.add_argument("--backend", choices=("jondo", "current"), default="jondo")
    parser.add_argument(
        "--control",
        action="store_true",
        help="Use the unchanged original native witness",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_fulmoon(
        scenario=args.scenario, control=args.control, backend=args.backend
    )
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    else:
        print(text)
    raise SystemExit(bool(result["failures"] or result["errors"] or result["skipped"]))
