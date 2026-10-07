#!/usr/bin/env python3
"""Synthetic forecast-graph load; excludes native preview generation costs."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import statistics
import time
from scripts.acceptance import fixture, successor, cast
from wakfu_ai.planning.planner import decide


def corpus(width, depth):
    data = fixture()
    data["actors"][1].update(hp=300, max_hp=300)
    data["states"][0]["actors"] = deepcopy(data["actors"])
    frontier = ["root"]
    for level in range(depth):
        following = []
        for key in frontier:
            before = next(s for s in data["states"] if s["key"] == key)
            for branch in range(width):
                next_key = key + ":" + str(branch)
                action = cast()
                action["spellId"] += branch
                successor(
                    data,
                    key,
                    next_key,
                    action,
                    hp={1: before["actors"][1]["hp"] - branch - 1},
                    ap=5 - level,
                )
                # Distinct native usage histories are part of the state key.
                data["states"][-1]["actors"][0]["usage"] = next_key
                following.append(next_key)
        frontier = following
    data["policy"] = dict(budgetMs=250)
    return data


def measure(data, count=40, workers=1):
    def run(_):
        started = time.perf_counter()
        result = decide(data)
        return (time.perf_counter() - started) * 1000, result["trace"]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        samples = list(pool.map(run, range(count)))
    times = sorted(t for t, _ in samples)
    return dict(
        samples=count,
        workers=workers,
        states=len(data["states"]),
        bytes=len(json.dumps(data).encode()),
        p50Ms=round(statistics.median(times), 3),
        p95Ms=round(times[int(0.95 * (count - 1))], 3),
        p99Ms=round(times[int(0.99 * (count - 1))], 3),
        maxExpanded=max(t["expanded"] for _, t in samples),
        timeouts=sum(t["timedOut"] for _, t in samples),
    )


def main():
    results = {
        name: measure(corpus(width, depth))
        for name, width, depth in (("small", 3, 2), ("medium", 4, 3), ("complex", 5, 4))
    }
    results["concurrent"] = measure(corpus(5, 4), workers=4)
    print(
        json.dumps(
            dict(
                scope="synthetic DTO validation and search; no native preview or HTTP",
                results=results,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
