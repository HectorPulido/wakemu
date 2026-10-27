"""Opt-in initial Spirit turn spans; no profiler, signals, threads or AI loop."""
from contextlib import ExitStack, contextmanager
import copy
from functools import wraps
import sys
import time
import traceback
from unittest.mock import patch


@contextmanager
def _provider_top_copy(span):
    """Observe the provider's local import; recursive copy sees the original."""
    original = copy.deepcopy

    def top_copy(*args, **kwargs):
        caller = sys._getframe(1)
        target = (
            caller.f_code.co_name == "prepare_server_turn_start"
            and caller.f_code.co_filename.endswith("/combat_server_spell.py")
        )
        copy.deepcopy = original
        try:
            if target:
                return span(
                    "actual_provider_local_fight_deepcopy",
                    lambda: original(*args, **kwargs),
                )
            return original(*args, **kwargs)
        finally:
            copy.deepcopy = top_copy

    with patch.object(copy, "deepcopy", top_copy):
        yield


def measure_once(url=None):
    """Build the real disposable scene and measure actual initial-turn calls."""
    from jondo_earned_scene_native_probe import build_scene
    from native_supreme_paid_component_runtime import PaidComponentRuntime
    from wakfu_server import combat_area_boundary, combat_runtime_messages
    from wakfu_server import combat_server_spell, combat_characteristic_link
    from wakfu_server import (
        combat_characteristic_reconciliation,
        combat_pointer_qi_commit,
    )
    from wakfu_server.combat_owned_equipment_factory import OwnedEquipmentRuntimeFactory
    from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
    from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
    from wakfu_server import (
        combat_equipment_external_events,
        combat_periodic_aptitude,
        combat_turn_events,
    )
    from wakfu_server.combat_event_replay import NativeEventReplay
    from wakfu_server.combat_effect_dispatch import EffectDispatcher
    from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
    from wakfu_server import combat_casting_los, combat_native_los_ray

    RuntimeMessages = combat_runtime_messages.RuntimeMessages
    rows, summaries, nesting, runtime_fields = [], {}, [], []
    measuring = False
    scene = None
    original_static_ray = combat_native_los_ray.static_ray
    ray_cache_before = original_static_ray.cache_info()
    omitted_spans = 0

    def span(label, operation):
        nonlocal omitted_spans
        started, cpu = time.monotonic(), time.process_time()
        frame = dict(label=label, childrenWall=0.0, childrenCpu=0.0)
        parent = nesting[-1]["label"] if nesting else None
        nesting.append(frame)
        succeeded = False
        try:
            value = operation()
            succeeded = True
            return value
        finally:
            wall, cpu_elapsed = time.monotonic() - started, time.process_time() - cpu
            nesting.pop()
            if nesting:
                nesting[-1]["childrenWall"] += wall
                nesting[-1]["childrenCpu"] += cpu_elapsed
            row = dict(
                label=label,
                parent=parent,
                depth=len(nesting),
                succeeded=succeeded,
                wallSeconds=wall,
                cpuSeconds=cpu_elapsed,
                exclusiveWallSeconds=max(0.0, wall - frame["childrenWall"]),
                exclusiveCpuSeconds=max(0.0, cpu_elapsed - frame["childrenCpu"]),
            )
            if len(rows) < 512:
                rows.append(row)
            else:
                omitted_spans += 1
            total = summaries.setdefault(
                label,
                dict(
                    calls=0,
                    wallSeconds=0.0,
                    cpuSeconds=0.0,
                    exclusiveWallSeconds=0.0,
                    exclusiveCpuSeconds=0.0,
                    maximumWallSeconds=0.0,
                ),
            )
            total["calls"] += 1
            for key in (
                "wallSeconds",
                "cpuSeconds",
                "exclusiveWallSeconds",
                "exclusiveCpuSeconds",
            ):
                total[key] += row[key]
            total["maximumWallSeconds"] = max(total["maximumWallSeconds"], wall)

    def wrapper(
        owner, name, *, label=None, activate=False, fields=False, provider_copy=False
    ):
        original = getattr(owner, name)

        @wraps(original)
        def measured(*args, **kwargs):
            nonlocal measuring
            if not measuring and not activate:
                return original(*args, **kwargs)
            previous = measuring
            measuring = True
            if fields:
                runtime_fields.append({id(v): k for k, v in vars(args[0]).items()})
            try:
                selected = label(args, kwargs) if callable(label) else label or name
                if provider_copy:
                    with _provider_top_copy(span):
                        return span(selected, lambda: original(*args, **kwargs))
                return span(selected, lambda: original(*args, **kwargs))
            finally:
                if fields:
                    runtime_fields.pop()
                measuring = previous

        return patch.object(owner, name, measured)

    def copied_field(args, kwargs):
        field = (
            runtime_fields[-1].get(id(args[0]), "unmapped")
            if runtime_fields
            else "outside_runtime_fields"
        )
        return "runtime_field_deepcopy." + field

    result = dict(
        kind="actual_spirit_initial_turn_spans",
        qualification=False,
        limit="Diagnostic only: actual native initial turn; no AI turn or encounter acceptance",
        instrumentation="monotonic/process_time direct wrappers; no profiler/signals/threads/timeouts",
    )
    started = time.monotonic()
    try:
        with ExitStack() as patches:
            for args, options in (
                (
                    (PaidComponentRuntime, "__init__"),
                    dict(label="runtime_constructor", activate=True),
                ),
                (
                    (RuntimeMessages, "turn_started"),
                    dict(label="initial_turn_started", activate=True),
                ),
                (
                    (RuntimeMessages, "__deepcopy__"),
                    dict(label="top_runtime_deepcopy", fields=True),
                ),
                ((combat_runtime_messages, "deepcopy"), dict(label=copied_field)),
                (
                    (combat_area_boundary, "deepcopy"),
                    dict(label="atomic_area_top_deepcopy"),
                ),
                (
                    (combat_area_boundary, "adopt_fight"),
                    dict(label="adopt_fight.from_runtime_adoption"),
                ),
                (
                    (combat_runtime_messages, "adopt_fight"),
                    dict(label="adopt_fight.runtime_provider_result"),
                ),
                (
                    (RuntimeMessages, "_expire_owned"),
                    dict(
                        label=lambda a, k: "expire_owned."
                        + (
                            "round_cleanup"
                            if k.get("round_cleanup")
                            else k.get("phase", "unknown")
                        )
                    ),
                ),
                (
                    (RuntimeMessages, "_changed_stat_packets"),
                    dict(label="changed_stat_packets"),
                ),
                ((RuntimeMessages, "prepare_delivery"), dict(label="prepare_delivery")),
                (
                    (RuntimeMessages, "prepare_fight_delivery"),
                    dict(label="prepare_fight_delivery"),
                ),
                (
                    (combat_server_spell, "prepare_server_turn_start"),
                    dict(label="actual_turn_start_provider", provider_copy=True),
                ),
                (
                    (combat_server_spell, "server_runtime"),
                    dict(label="native_factory_constructor"),
                ),
                (
                    (OwnedEquipmentRuntimeFactory, "__call__"),
                    dict(label="owned_equipment_factory_call"),
                ),
                (
                    (NativeEffectRuntimeFactory, "__call__"),
                    dict(label="native_effect_factory_call"),
                ),
                (
                    (combat_equipment_external_events, "deliver_completed_round"),
                    dict(label="deliver_completed_round"),
                ),
                (
                    (combat_periodic_aptitude, "renew_periodic_aptitudes"),
                    dict(label="renew_periodic_aptitudes"),
                ),
                (
                    (combat_turn_events, "deliver_turn_start"),
                    dict(label="deliver_native_turn_start"),
                ),
                (
                    (NativeAreaEventRuntime, "turn_start"),
                    dict(label="native_area_turn_start"),
                ),
                (
                    (NativeEventReplay, "__call__"),
                    dict(
                        label=lambda a, k: "event_replay.manager=%s.channel=%s.events=%s"
                        % (
                            a[1].manager_actor_id,
                            a[1].channel,
                            ",".join(str(v) for v in a[1].event_ids),
                        )
                    ),
                ),
                (
                    (EffectDispatcher, "execute"),
                    dict(
                        label=lambda a, k: "dispatcher_execute.reference=%s"
                        % a[1].reference
                    ),
                ),
                (
                    (EffectDispatcher, "_execute_resolved"),
                    dict(
                        label=lambda a, k: "dispatcher_resolved.reference=%s.family=%s"
                        % (a[1].reference, k["effect"]["effect_class"])
                    ),
                ),
                ((NativeRetainedRuntime, "view"), dict(label="retention_view")),
                (
                    (NativeRetainedRuntime, "synchronize"),
                    dict(label="retention_synchronize"),
                ),
                (
                    (combat_casting_los, "native_casting_los"),
                    dict(label="native_casting_los"),
                ),
                (
                    (combat_casting_los, "native_casting_ray"),
                    dict(label="native_casting_ray"),
                ),
                ((combat_native_los_ray, "cast_rays"), dict(label="native_cast_rays")),
                (
                    (combat_native_los_ray, "static_ray"),
                    dict(label="static_ray_cached_call"),
                ),
                (
                    (PaidComponentRuntime, "stats"),
                    dict(label="actual_stats_serializer"),
                ),
                (
                    (combat_characteristic_reconciliation, "characteristic_signatures"),
                    dict(label="characteristic_signatures"),
                ),
                (
                    (combat_characteristic_link, "characteristic_adoption_bindings"),
                    dict(label="characteristic_adoption_bindings"),
                ),
                (
                    (combat_pointer_qi_commit, "prepare_pointer_commit"),
                    dict(label="prepare_pointer_commit"),
                ),
            ):
                patches.enter_context(wrapper(*args, **options))
            scene = build_scene("spirit")
            result.update(
                setupTimings=scene.setupTimings,
                initialTurnCompleted=True,
                initialActorId=scene.case.fight.current.id,
                readyPackets=scene.readyPackets,
            )
    except Exception as error:
        result["nativeError"] = dict(
            type=type(error).__name__,
            detail=str(error),
            traceback=traceback.format_exc(),
        )
    finally:
        result.update(
            elapsedBeforeCleanupSeconds=time.monotonic() - started,
            summaries=summaries,
            spans=rows,
            omittedSpans=omitted_spans,
        )
        ray_cache_after = original_static_ray.cache_info()
        result["staticRayCache"] = dict(
            before=ray_cache_before._asdict(),
            after=ray_cache_after._asdict(),
            hitsDelta=ray_cache_after.hits - ray_cache_before.hits,
            missesDelta=ray_cache_after.misses - ray_cache_before.misses,
        )
        if scene is not None:
            scene.database.doCleanups()
    return result
