"""Optional one-shot process allocation comparison around two Rift turns.

The trace is intentionally process-global: Python tracemalloc does not provide
per-thread allocation snapshots. Keep the entire traced interval out of
normal latency measurements. The tool reports allocation sites only, never
combat payloads, packets, actor rows, or inventory values.
"""
import gc
import json
import os
from pathlib import Path
import resource
import sys
import threading
import time
import tracemalloc
from datetime import datetime, timezone


OPCODE_END_TURN = 12403
BASELINE_WAVE = 1
SAMPLE_WAVE = 2
MAX_TRACE_SECONDS = 1800
MAX_TRACEBACKS = 40


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _wave(fight):
    fields = object.__getattribute__(fight, "__dict__")
    state = fields.get("rift_wave_state")
    wave = state.get("wave") if type(state) is dict else None
    return wave if type(wave) is int else None


def _rss_bytes():
    """Return current resident bytes on Linux, or None when unavailable."""
    try:
        values = Path("/proc/self/statm").read_text(encoding="ascii").split()
        return {"current_bytes": int(values[1]) * int(os.sysconf("SC_PAGE_SIZE"))}
    except (OSError, ValueError, IndexError, AttributeError):
        try:
            # ru_maxrss is a process peak, not current RSS; report it separately.
            value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            return {
                "peak_bytes": int(value * (1024 if sys.platform != "darwin" else 1))
            }
        except (OSError, ValueError, AttributeError):
            return None


def _write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_suffix(path.suffix + ".tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.chmod(temporary, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _frame_rows(traceback):
    return [
        {"file": Path(frame.filename).name, "line": frame.lineno} for frame in traceback
    ]


def _delta_rows(snapshot, baseline):
    entries = snapshot.compare_to(baseline, "traceback")
    files = {}
    rows = []
    for entry in entries[:MAX_TRACEBACKS]:
        frames = _frame_rows(entry.traceback)
        rows.append(
            {
                "size_diff_bytes": entry.size_diff,
                "count_diff": entry.count_diff,
                "traceback": frames,
            }
        )
    for entry in entries:
        frames = _frame_rows(entry.traceback)
        if frames:
            frame = frames[-1]
            item = files.setdefault(
                frame["file"], {"size_diff_bytes": 0, "count_diff": 0}
            )
            item["size_diff_bytes"] += entry.size_diff
            item["count_diff"] += entry.count_diff
    file_rows = sorted(
        ({"file": name, **values} for name, values in files.items()),
        key=lambda row: (abs(row["size_diff_bytes"]), abs(row["count_diff"])),
        reverse=True,
    )[:MAX_TRACEBACKS]
    return rows, file_rows


def _snapshot_delta(label, current, baseline, traced_memory):
    traced_current, traced_peak = traced_memory
    rss = _rss_bytes()
    rows, files = _delta_rows(current, baseline)
    return {
        "label": label,
        "traced_current_bytes": traced_current,
        "traced_peak_bytes": traced_peak,
        "rss": rss,
        "top_tracebacks": rows,
        "top_files": files,
    }


def _sample(state, before_wave, after_wave):
    started = _utc()
    traced_before = tracemalloc.get_traced_memory()
    rss_before = _rss_bytes()
    before_gc = tracemalloc.take_snapshot()
    collected = gc.collect()
    after_gc = tracemalloc.take_snapshot()
    traced_after = tracemalloc.get_traced_memory()
    before_delta = _snapshot_delta(
        "before_gc_vs_wave1", before_gc, state["baseline"], traced_before
    )
    after_delta = _snapshot_delta(
        "after_gc_vs_wave1", after_gc, state["baseline"], traced_after
    )
    initial_rows, initial_files = _delta_rows(
        state["baseline"], state["trace_start_snapshot"]
    )
    freed_rows, freed_files = _delta_rows(after_gc, before_gc)
    payload = {
        "status": "completed",
        "fight_id": state["fight_id"],
        "baseline_wave": BASELINE_WAVE,
        "sample_wave": before_wave,
        "post_operation_wave": after_wave,
        "opcode": OPCODE_END_TURN,
        "baseline_started_utc": state["baseline_started_utc"],
        "baseline_completed_utc": state["baseline_completed_utc"],
        "baseline_trace_count": state["baseline_trace_count"],
        "wave1_post_operation_delta": {
            "top_tracebacks": initial_rows,
            "top_files": initial_files,
        },
        "sample_started_utc": started,
        "sample_completed_utc": _utc(),
        "traced_interval_excluded_from_performance_claims": True,
        "process_global_tracemalloc": True,
        "traceback_depth": 1,
        "collected_objects": collected,
        "rss_before_gc_bytes": rss_before,
        "rss_after_gc_bytes": _rss_bytes(),
        "traced_before_gc_bytes": traced_before[0],
        "traced_peak_before_gc_bytes": traced_before[1],
        "traced_after_gc_bytes": traced_after[0],
        "traced_peak_after_gc_bytes": traced_after[1],
        "before_gc_delta": before_delta,
        "after_gc_delta": after_delta,
        "gc_delta_tracebacks": freed_rows,
        "gc_delta_files": freed_files,
    }
    _write_json(state["output_path"], payload)
    state["finished"] = True
    state["baseline"] = None
    state["trace_start_snapshot"] = None
    try:
        tracemalloc.stop()
    except BaseException:
        pass
    timer = state.get("timer")
    if timer is not None:
        timer.cancel()


def _finish_without_sample(state, status):
    lock = state["finish_lock"]
    with lock:
        if state["finished"]:
            return
        state["finished"] = True
        try:
            if tracemalloc.is_tracing():
                traced_current, traced_peak = tracemalloc.get_traced_memory()
                tracemalloc.stop()
            else:
                traced_current = traced_peak = None
            _write_json(
                state["output_path"],
                {
                    "status": status,
                    "fight_id": state["fight_id"],
                    "baseline_wave": BASELINE_WAVE,
                    "sample_wave": SAMPLE_WAVE,
                    "opcode": OPCODE_END_TURN,
                    "baseline_started_utc": state["baseline_started_utc"],
                    "baseline_trace_count": state["baseline_trace_count"],
                    "diagnostic_finished_utc": _utc(),
                    "process_global_tracemalloc": True,
                    "traced_interval_excluded_from_performance_claims": True,
                    "traced_current_bytes_at_stop": traced_current,
                    "traced_peak_bytes_at_stop": traced_peak,
                    "rss_bytes_at_stop": _rss_bytes(),
                },
            )
        except BaseException:
            pass
        state["baseline"] = None
        state["trace_start_snapshot"] = None
        timer = state.get("timer")
        if timer is not None:
            timer.cancel()
        try:
            state["restore"]()
        except BaseException:
            pass


def install(
    registry_type,
    fight_type,
    *,
    fight_id,
    output_path,
    cprofile_tool_path=None,
    arm_cprofile_after_sample=False,
):
    """Capture post-success wave-1 baseline and post-success wave-2 deltas."""
    if type(fight_id) is not int:
        raise ValueError("Exact fight ID selector is required")
    original = registry_type.__dict__.get("execute")
    if type(original) is not type(lambda: None):
        raise ValueError("Registry.execute must be an exact Python method")
    state = {
        "fight_id": fight_id,
        "output_path": output_path,
        "original": original,
        "wrapper": None,
        "baseline": None,
        "trace_start_snapshot": None,
        "baseline_trace_count": None,
        "baseline_started_utc": None,
        "baseline_completed_utc": None,
        "trace_started": None,
        "finished": False,
        "finish_lock": threading.RLock(),
        "timer": None,
        "registry_type": registry_type,
        "fight_type": fight_type,
        "cprofile_tool_path": cprofile_tool_path,
        "arm_cprofile_after_sample": arm_cprofile_after_sample,
    }

    def restore():
        if registry_type.__dict__.get("execute") is state["wrapper"]:
            registry_type.execute = original

    state["restore"] = restore

    def wrapped(
        self,
        fight_id_arg,
        session,
        actor_id,
        operation,
        *,
        expected_sequence=None,
        require_turn=True,
        incident_request=None,
    ):
        if state["finished"]:
            return original(
                self,
                fight_id_arg,
                session,
                actor_id,
                operation,
                expected_sequence=expected_sequence,
                require_turn=require_turn,
                incident_request=incident_request,
            )
        if (
            type(fight_id_arg) is not int
            or fight_id_arg != state["fight_id"]
            or type(incident_request) is not dict
            or type(incident_request.get("opcode")) is not int
            or incident_request.get("opcode") != OPCODE_END_TURN
        ):
            return original(
                self,
                fight_id_arg,
                session,
                actor_id,
                operation,
                expected_sequence=expected_sequence,
                require_turn=require_turn,
                incident_request=incident_request,
            )
        sampled = False
        try:
            shared = self.lookup(fight_id_arg)
            with shared.lock:
                fight = shared.fight
                if (
                    type(fight) is not fight_type
                    or object.__getattribute__(fight, "id") != state["fight_id"]
                ):
                    return original(
                        self,
                        fight_id_arg,
                        session,
                        actor_id,
                        operation,
                        expected_sequence=expected_sequence,
                        require_turn=require_turn,
                        incident_request=incident_request,
                    )
                wave_before = _wave(fight)
                if state["baseline"] is None and wave_before == BASELINE_WAVE:
                    if tracemalloc.is_tracing():
                        restore()
                        state["finished"] = True
                        return original(
                            self,
                            fight_id_arg,
                            session,
                            actor_id,
                            operation,
                            expected_sequence=expected_sequence,
                            require_turn=require_turn,
                            incident_request=incident_request,
                        )
                    state["baseline_started_utc"] = _utc()
                    try:
                        tracemalloc.start(1)
                        state["trace_start_snapshot"] = tracemalloc.take_snapshot()
                        state["trace_started"] = time.monotonic()
                    except BaseException:
                        restore()
                        state["finished"] = True
                        if tracemalloc.is_tracing():
                            tracemalloc.stop()
                        return original(
                            self,
                            fight_id_arg,
                            session,
                            actor_id,
                            operation,
                            expected_sequence=expected_sequence,
                            require_turn=require_turn,
                            incident_request=incident_request,
                        )
                    try:
                        result = original(
                            self,
                            fight_id_arg,
                            session,
                            actor_id,
                            operation,
                            expected_sequence=expected_sequence,
                            require_turn=require_turn,
                            incident_request=incident_request,
                        )
                    except BaseException:
                        _finish_without_sample(state, "wave1_action_raised")
                        raise
                    if not tracemalloc.is_tracing():
                        _finish_without_sample(
                            state, "trace_stopped_during_wave1_action"
                        )
                        return result
                    post_fight = shared.fight
                    phase = getattr(post_fight, "phase", None)
                    del post_fight, fight
                    if phase != "active":
                        _finish_without_sample(state, "fight_closed_before_sample")
                        return result
                    try:
                        state["baseline"] = tracemalloc.take_snapshot()
                        state["baseline_trace_count"] = len(state["baseline"].traces)
                        state["baseline_completed_utc"] = _utc()
                        timer = threading.Timer(
                            MAX_TRACE_SECONDS,
                            _finish_without_sample,
                            args=(state, "timeout_before_sample"),
                        )
                        timer.daemon = True
                        state["timer"] = timer
                        timer.start()
                    except BaseException:
                        _finish_without_sample(state, "baseline_failed")
                    return result
                if state["baseline"] is not None and wave_before == SAMPLE_WAVE:
                    try:
                        result = original(
                            self,
                            fight_id_arg,
                            session,
                            actor_id,
                            operation,
                            expected_sequence=expected_sequence,
                            require_turn=require_turn,
                            incident_request=incident_request,
                        )
                    except BaseException:
                        _finish_without_sample(state, "selected_wave2_action_raised")
                        raise
                    post_fight = shared.fight
                    wave_after = _wave(post_fight)
                    del post_fight, fight
                    with state["finish_lock"]:
                        if not state["finished"]:
                            try:
                                _sample(state, wave_before, wave_after)
                                restore()
                                sampled = True
                            except BaseException:
                                _finish_without_sample(state, "snapshot_failed")
                                return result
                else:
                    try:
                        result = original(
                            self,
                            fight_id_arg,
                            session,
                            actor_id,
                            operation,
                            expected_sequence=expected_sequence,
                            require_turn=require_turn,
                            incident_request=incident_request,
                        )
                    except BaseException:
                        if state["baseline"] is not None:
                            _finish_without_sample(
                                state, "selected_action_raised_before_sample"
                            )
                        raise
                    if (
                        state["baseline"] is not None
                        and state["trace_started"] is not None
                    ):
                        post_fight = shared.fight
                        phase = getattr(post_fight, "phase", None)
                        del post_fight, fight
                        if phase != "active":
                            _finish_without_sample(state, "fight_closed_before_sample")
                    return result
            if sampled and state["arm_cprofile_after_sample"]:
                try:
                    armed = _arm_cprofile_after_sample(state)
                    arm_result = {
                        "status": "armed" if armed else "not_armed",
                        "completed_utc": _utc(),
                    }
                except BaseException as error:
                    arm_result = {
                        "status": "failed",
                        "completed_utc": _utc(),
                        "error_type": type(error).__name__,
                    }
                try:
                    output_base = Path(state["output_path"]).with_suffix("")
                    _write_json(
                        output_base.with_name(output_base.name + "-wave16-arm.json"),
                        arm_result,
                    )
                except BaseException:
                    pass
            return result
        except BaseException:
            raise

    state["wrapper"] = wrapped
    registry_type.execute = wrapped
    return state


def _arm_cprofile_after_sample(state):
    if not state["arm_cprofile_after_sample"] or state["cprofile_tool_path"] is None:
        return False
    from runpy import run_path

    tool = run_path(str(state["cprofile_tool_path"]))
    output_base = Path(state["output_path"]).with_suffix("")
    tool["install"](
        state["registry_type"],
        state["fight_type"],
        fight_id=state["fight_id"],
        wave=16,
        opcode=OPCODE_END_TURN,
        profile_path=output_base.with_name(output_base.name + "-wave16.prof"),
        metadata_path=output_base.with_name(output_base.name + "-wave16.json"),
    )
    return True


def install_from_environment(*, runtime_root):
    if os.environ.get("WAKFU_REGISTRY_EXECUTE_ALLOCATION_TRACE") != "1":
        return False
    if tracemalloc.is_tracing():
        return False
    if os.environ.get("WAKFU_REGISTRY_EXECUTE_CPROFILE") == "1":
        return False
    arm_cprofile = (
        os.environ.get("WAKFU_REGISTRY_EXECUTE_ALLOCATION_TRACE_THEN_CPROFILE") == "1"
    )
    cprofile_tool_path = os.environ.get("WAKFU_REGISTRY_EXECUTE_CPROFILE_TOOL")
    if arm_cprofile and not cprofile_tool_path:
        return False
    monitoring = getattr(sys, "monitoring", None)
    if (
        monitoring is not None
        and monitoring.get_tool(monitoring.PROFILER_ID) is not None
    ):
        return False
    combat_shared = sys.modules.get("wakfu_server.combat_shared")
    state_module = sys.modules.get("wakfu_server.combat_state")
    if combat_shared is None or state_module is None:
        raise RuntimeError("Combat transaction modules are not loaded at startup")
    registry_type = combat_shared.__dict__.get("Registry")
    fight_type = state_module.__dict__.get("Fight")
    if not isinstance(registry_type, type) or not isinstance(fight_type, type):
        raise RuntimeError("Combat Registry/Fight classes are not loaded at startup")
    fight_id = int(os.environ["WAKFU_REGISTRY_EXECUTE_ALLOCATION_TRACE_FIGHT_ID"])
    output_path = Path(
        os.environ.get(
            "WAKFU_REGISTRY_EXECUTE_ALLOCATION_TRACE_PATH",
            Path(runtime_root)
            / "logs"
            / "profiles"
            / f"registry-alloc-f{fight_id}-w1-w2.json",
        )
    )
    return install(
        registry_type,
        fight_type,
        fight_id=fight_id,
        output_path=output_path,
        cprofile_tool_path=cprofile_tool_path,
        arm_cprofile_after_sample=arm_cprofile,
    )
