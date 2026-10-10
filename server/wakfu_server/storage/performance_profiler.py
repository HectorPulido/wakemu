"""Bounded feature timings and opt-in Python stack sampling.

Wall-only observations have unknown CPU and are excluded from wait estimates.
Wall timings include waiting; thread CPU measures only the calling thread. Nested
spans overlap and must not be summed as exclusive CPU. Stack samples show Python
thread occupancy, not CPU attribution, and cannot sample while another thread
holds the GIL in native code. The native checkpoint watchdog covers that case.
"""
from collections import Counter
from contextlib import contextmanager
from functools import wraps
import json
import math
import os
import resource
from pathlib import Path
import re
import sys
import threading
import time

_BUCKETS = (
    0.0001,
    0.0005,
    0.001,
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    30.0,
    float("inf"),
)
_NAME = re.compile(r"^[a-zA-Z][a-zA-Z0-9_.:-]{0,95}$")


class PerformanceProfiler:
    def __init__(self, *, max_features=128, max_stacks=2048, retention=8):
        self.max_features = max(1, min(int(max_features), 512))
        self.max_stacks = max(1, min(int(max_stacks), 8192))
        self.retention = max(1, min(int(retention), 32))
        self._lock = threading.Lock()
        self._features = {}
        self._dropped = 0
        self._started = time.time()
        self._sampling = None
        self._last_sample = None

    def observe(self, name, wall_seconds, cpu_seconds=None, *, error=False):
        """Call only with fixed feature labels, never player or packet contents."""
        try:
            if not isinstance(name, str) or not _NAME.fullmatch(name):
                return
            wall = float(wall_seconds)
            cpu = 0.0 if cpu_seconds is None else float(cpu_seconds)
            if not math.isfinite(wall) or not math.isfinite(cpu) or wall < 0 or cpu < 0:
                return
            bucket = next(i for i, edge in enumerate(_BUCKETS) if wall <= edge)
            with self._lock:
                row = self._features.get(name)
                if row is None:
                    if len(self._features) >= self.max_features:
                        self._dropped += 1
                        return
                    row = [0, 0.0, 0.0, 0.0, 0, [0] * len(_BUCKETS), 0, 0.0]
                    self._features[name] = row
                row[0] += 1
                row[1] += wall
                row[2] += cpu
                row[3] = max(row[3], wall)
                row[4] += bool(error)
                row[5][bucket] += 1
                if cpu_seconds is not None:
                    row[6] += 1
                    row[7] += wall
        except Exception:
            pass  # Diagnostics must never change gameplay outcomes.

    @contextmanager
    def span(self, name):
        wall, cpu = time.perf_counter(), time.thread_time()
        failed = False
        try:
            yield
        except BaseException:
            failed = True
            raise
        finally:
            self.observe(
                name, time.perf_counter() - wall, time.thread_time() - cpu, error=failed
            )

    def profile(self, name):
        def decorate(function):
            @wraps(function)
            def measured(*args, **kwargs):
                with self.span(name):
                    return function(*args, **kwargs)

            return measured

        return decorate

    def reset(self):
        with self._lock:
            self._features.clear()
            self._dropped = 0
            self._started = time.time()

    def snapshot(self, *, reset=False):
        with self._lock:
            rows = [
                (name, row[:5] + [row[5][:]] + row[6:])
                for name, row in self._features.items()
            ]
            started, dropped = self._started, self._dropped
            if reset:
                self._features.clear()
                self._dropped = 0
                self._started = time.time()
        result = []
        for name, (
            count,
            wall,
            cpu,
            maximum,
            errors,
            buckets,
            measured_calls,
            known_wall,
        ) in rows:
            target, seen, percentile = math.ceil(count * 0.95), 0, maximum
            for edge, frequency in zip(_BUCKETS, buckets):
                seen += frequency
                if seen >= target:
                    percentile = min(edge, maximum)
                    break
            result.append(
                dict(
                    name=name,
                    count=count,
                    total_wall_seconds=wall,
                    total_cpu_seconds=cpu,
                    mean_wall_seconds=wall / count,
                    max_wall_seconds=maximum,
                    p95_wall_seconds=percentile,
                    errors=errors,
                    total_ms=wall * 1000,
                    cpu_ms=cpu * 1000,
                    wait_ms=max(0, known_wall - cpu) * 1000,
                    max_ms=maximum * 1000,
                    cpu_measured_calls=measured_calls,
                    known_wall_seconds=known_wall,
                    cpu_coverage_percent=100.0 * measured_calls / count,
                    unknown_cpu_calls=count - measured_calls,
                    p95_ms=percentile * 1000,
                )
            )
        result.sort(key=lambda row: row["total_wall_seconds"], reverse=True)
        return dict(
            started_at=started,
            elapsed_seconds=max(0, time.time() - started),
            dropped_features=dropped,
            features=result,
            sampling=self.status(),
        )

    def status(self):
        with self._lock:
            active = self._sampling
            return dict(
                sampling=active is not None,
                process_cpu_seconds=time.process_time(),
                rss_max_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                * (1 if sys.platform == "darwin" else 1024),
                threads=threading.active_count(),
                duration=active["duration"] if active else None,
                interval=active["interval"] if active else None,
                last_sample=dict(self._last_sample) if self._last_sample else None,
            )

    def start_sampling(self, *, duration=30, interval=0.05, output_dir):
        duration, interval = float(duration), float(interval)
        if not math.isfinite(duration) or not 5 <= duration <= 120:
            raise ValueError("Sampling duration must be between 5 and 120 seconds")
        if not math.isfinite(interval) or not 0.02 <= interval <= 1:
            raise ValueError("Sampling interval must be between 0.02 and 1 seconds")
        state = dict(
            duration=duration,
            interval=interval,
            stop=threading.Event(),
            output_dir=Path(output_dir),
            started_at=time.time(),
        )
        with self._lock:
            if self._sampling is not None:
                return False
            self._sampling = state
        thread = threading.Thread(
            target=self._sample,
            args=(state,),
            name="performance-stack-sampler",
            daemon=True,
        )
        try:
            thread.start()
        except Exception:
            with self._lock:
                self._sampling = None
            return False
        return True

    def stop_sampling(self):
        with self._lock:
            if self._sampling is None:
                return False
            self._sampling["stop"].set()
        return True

    def _sample(self, state):
        counts, dropped, rounds = Counter(), 0, 0
        started = time.monotonic()
        outcome = dict(started_at=state["started_at"], path=None, error=None)
        try:
            while (
                time.monotonic() - started < state["duration"]
                and not state["stop"].is_set()
            ):
                frames = sys._current_frames()
                own = threading.get_ident()
                for ident, frame in frames.items():
                    if ident == own:
                        continue
                    stack = []
                    while frame is not None and len(stack) < 32:
                        code = frame.f_code
                        # Basenames only: no locals, arguments, source text or absolute paths.
                        stack.append(
                            f"{Path(code.co_filename).name}:{code.co_name}:{frame.f_lineno}"
                        )
                        frame = frame.f_back
                    key = tuple(reversed(stack))
                    if key in counts or len(counts) < self.max_stacks:
                        counts[key] += 1
                    else:
                        dropped += 1
                frames.clear()
                rounds += 1
                state["stop"].wait(state["interval"])
            directory = state["output_dir"]
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            path = directory / f"performance-profile-{time.time_ns()}.json"
            payload = dict(
                schema_version=1,
                duration_seconds=time.monotonic() - started,
                interval_seconds=state["interval"],
                rounds=rounds,
                dropped_stacks=dropped,
                features=self.snapshot(),
                stacks=[
                    dict(frames=list(key), samples=count)
                    for key, count in counts.most_common()
                ],
                limitations="Python thread occupancy, not CPU attribution; nested spans overlap; native GIL stalls require watchdog",
            )
            # Disk work is confined to this background thread; private exclusive file.
            with os.fdopen(
                os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600),
                "w",
                encoding="utf-8",
            ) as stream:
                json.dump(payload, stream, separators=(",", ":"))
            outcome["path"] = str(path)
            old = sorted(
                directory.glob("performance-profile-*.json"), key=lambda item: item.name
            )
            for item in old[: -self.retention]:
                item.unlink(missing_ok=True)
        except Exception as exc:
            outcome["error"] = type(exc).__name__
        finally:
            outcome["duration_seconds"] = time.monotonic() - started
            with self._lock:
                self._last_sample = outcome
                if self._sampling is state:
                    self._sampling = None


PROFILER = PerformanceProfiler()
