"""Opt-in, disposable-only profiling of genuine Spirit Ready and one AI turn.

The watchdog deliberately interrupts diagnostics, never production execution.
Its output is not an encounter acceptance or deadline qualification receipt.
"""
from contextlib import ExitStack
import cProfile
import faulthandler
from functools import wraps
import math
import pstats
import signal
import tempfile
import threading
import time
import traceback
from unittest.mock import patch


class NativeQAProfileInterrupted(BaseException):
    """Escape ordinary engine exception handlers in a disposable fixture."""


def _profile_rows(profile, limit=35):
    stats = pstats.Stats(profile).stats
    rows = []
    for (filename, line, name), (primitive, calls, own, cumulative, _) in stats.items():
        rows.append(
            dict(
                file=filename,
                line=line,
                function=name,
                calls=calls,
                primitiveCalls=primitive,
                ownSeconds=own,
                cumulativeSeconds=cumulative,
            )
        )
    return sorted(rows, key=lambda row: row["cumulativeSeconds"], reverse=True)[:limit]


def profile_once(
    url,
    *,
    setup_cap_seconds=120,
    ai_cap_seconds=60,
    target_cap_seconds=30,
    native_deadline_seconds=20,
    stack_interval_seconds=5
):
    """Leave fixture preparation unprofiled; profile actual target calls only."""
    for value in (
        setup_cap_seconds,
        ai_cap_seconds,
        native_deadline_seconds,
        stack_interval_seconds,
        target_cap_seconds,
    ):
        if type(value) not in (float, int) or not math.isfinite(value) or value <= 0:
            raise ValueError("Profiling budgets must be finite and positive")
    if threading.current_thread() is not threading.main_thread():
        raise ValueError("Private profiling watchdog requires the main thread")
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise ValueError("Refusing to replace an existing watchdog")

    spans, active, stages, diagnostics = {}, [], [], []
    scene = channel = None
    target_active = False
    previous_handler = signal.getsignal(signal.SIGALRM)
    result = dict(
        kind="disposable_spirit_atomic_profile",
        passed=False,
        qualification=False,
        debugInterrupted=False,
        diagnostics=diagnostics,
        stages=stages,
        spans=spans,
        limit="Diagnostic timings include profiler overhead; no encounter acceptance claim",
    )

    def wrap(owner, name, *, target=False):
        original = getattr(owner, name)
        label = original.__module__ + "." + original.__qualname__

        @wraps(original)
        def timed(*args, **kwargs):
            wall, cpu = time.monotonic(), time.process_time()
            active.append(label)
            try:
                if target and not target_active:
                    return target_stage(label, lambda: original(*args, **kwargs))
                return original(*args, **kwargs)
            finally:
                elapsed = time.monotonic() - wall
                row = spans.setdefault(
                    label,
                    dict(
                        calls=0, wallSeconds=0.0, cpuSeconds=0.0, maximumWallSeconds=0.0
                    ),
                )
                row["calls"] += 1
                row["wallSeconds"] += elapsed
                row["cpuSeconds"] += time.process_time() - cpu
                row["maximumWallSeconds"] = max(row["maximumWallSeconds"], elapsed)
                active.pop()

        return patch.object(owner, name, timed)

    with tempfile.TemporaryFile(mode="w+b") as stacks:

        def interrupt(signum, frame):
            result["interruptedSpans"] = list(active)
            faulthandler.dump_traceback(file=stacks, all_threads=True)
            raise NativeQAProfileInterrupted("Private diagnostic wall cap reached")

        def stage(name, cap, operation):
            row = dict(name=name, wallCapSeconds=cap, profiled=False)
            stages.append(row)
            started, cpu = time.monotonic(), time.process_time()
            signal.setitimer(signal.ITIMER_REAL, cap)
            try:
                return operation()
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                row.update(
                    wallSeconds=time.monotonic() - started,
                    cpuSeconds=time.process_time() - cpu,
                )

        def target_stage(name, operation):
            nonlocal target_active
            profile = cProfile.Profile()
            remaining, interval = signal.getitimer(signal.ITIMER_REAL)
            cap = (
                min(target_cap_seconds, remaining) if remaining else target_cap_seconds
            )
            row = dict(name=name, wallCapSeconds=cap, profiled=True)
            stages.append(row)
            started, cpu = time.monotonic(), time.process_time()
            target_active = True
            signal.setitimer(signal.ITIMER_REAL, cap)
            profile.enable()
            completed = False
            interrupted = False
            try:
                value = operation()
                completed = True
                return value
            except NativeQAProfileInterrupted:
                interrupted = True
                raise
            finally:
                profile.disable()
                signal.setitimer(signal.ITIMER_REAL, 0)
                elapsed = time.monotonic() - started
                target_active = False
                row.update(
                    wallSeconds=elapsed,
                    cpuSeconds=time.process_time() - cpu,
                    completed=completed,
                    topCumulative=_profile_rows(profile),
                )
                # Do not re-arm while an interrupt unwinds fixture cleanup.
                if not interrupted and remaining:
                    signal.setitimer(
                        signal.ITIMER_REAL, max(0.001, remaining - elapsed), interval
                    )

        signal.signal(signal.SIGALRM, interrupt)
        faulthandler.dump_traceback_later(
            stack_interval_seconds, repeat=True, file=stacks
        )
        try:
            with ExitStack() as patches:

                def imports():
                    from native_supreme_paid_component_runtime import (
                        PaidComponentRuntime,
                    )
                    from wakfu_server.combat_runtime_messages import RuntimeMessages
                    from wakfu_server import combat_server_spell
                    from wakfu_ai.native.native_oracle import NativeOracle
                    from jondo_earned_scene_native_probe import (
                        build_scene,
                        _drain,
                        _oracle,
                    )
                    from wakfu_ai.bridge.jondo_entry import run_prepared_turn
                    from wakfu_ai.native.native_stats import NativeStats
                    from wakfu_ai.transport.framed import FramedClient
                    from wakfu_ai.transport.endpoint import tcp_address

                    return locals()

                api = stage("profiling_imports", setup_cap_seconds, imports)
                for owner, names in (
                    (api["PaidComponentRuntime"], ("__init__",)),
                    (
                        api["RuntimeMessages"],
                        (
                            "__init__",
                            "__deepcopy__",
                            "turn_started",
                            "_expire_owned",
                            "_changed_stat_packets",
                            "prepare_delivery",
                            "prepare_fight_delivery",
                        ),
                    ),
                    (
                        api["combat_server_spell"],
                        ("server_runtime", "prepare_server_turn_start"),
                    ),
                    (
                        api["NativeOracle"],
                        ("__init__", "state_identity", "_commit", "preview", "cast"),
                    ),
                ):
                    for name in names:
                        is_target = (
                            (
                                owner is api["PaidComponentRuntime"]
                                and name == "__init__"
                            )
                            or (
                                owner is api["RuntimeMessages"]
                                and name == "turn_started"
                            )
                            or (
                                owner is api["NativeOracle"]
                                and name in ("__init__", "state_identity", "_commit")
                            )
                        )
                        patches.enter_context(wrap(owner, name, target=is_target))
                scene = stage(
                    "unprofiled_fixture_with_target_spans",
                    setup_cap_seconds,
                    lambda: api["build_scene"]("spirit"),
                )
                case = scene.case
                result["setupTimings"] = scene.setupTimings
                result["initialActorId"] = case.fight.current.id

                def one_turn():
                    nonlocal channel
                    from wakfu_server.combat_effective_control import (
                        effective_server_controlled,
                    )

                    if not effective_server_controlled(case.fight, case.fight.current):
                        raise AssertionError(
                            "Expected genuine initial NPC; no synthetic advancement"
                        )
                    oracle = api["_oracle"](scene)
                    stats = api["NativeStats"](
                        characters=case.characters,
                        monsters=case.monsters,
                        fight_id=case.fight.id,
                        map_id=1134,
                    )
                    channel = api["FramedClient"](
                        *api["tcp_address"](url), timeout=native_deadline_seconds
                    )
                    deadline = time.monotonic() + native_deadline_seconds
                    result["nativeDeadlineSeconds"] = native_deadline_seconds
                    for _, diagnostic in api["run_prepared_turn"](
                        case.runtime,
                        oracle,
                        stats,
                        channel,
                        deadline=deadline,
                        max_actions=8,
                    ):
                        diagnostics.append(diagnostic)
                    api["_drain"](case)
                    result["npcBoundaryCompleted"] = True

                stage("one_actual_jondo_npc_boundary", ai_cap_seconds, one_turn)
        except NativeQAProfileInterrupted as error:
            result["debugInterrupted"] = True
            result["nativeError"] = dict(type=type(error).__name__, detail=str(error))
        except Exception as error:
            result["nativeError"] = dict(
                type=type(error).__name__,
                detail=str(error),
                traceback=traceback.format_exc(),
            )
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            faulthandler.cancel_dump_traceback_later()
            signal.signal(signal.SIGALRM, previous_handler)
            if channel is not None:
                channel.close()
            if scene is not None:
                result["finalActors"] = {
                    str(i): dict(
                        hp=a.hp,
                        maxHp=a.max_hp,
                        ap=a.ap,
                        mp=a.mp,
                        position=list(a.position),
                    )
                    for i, a in scene.case.fight.actors.items()
                }
                scene.database.doCleanups()
            stacks.seek(0)
            result["sampledStacks"] = stacks.read(65536).decode(
                "utf-8", errors="replace"
            )
    return result
