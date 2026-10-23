"""Finite synthetic tactical corpus exercising the real query-search coroutine.

This measures planner decisions and Python search overhead, NOT native-engine
correctness, HTTP overhead, production combat latency, or actual spell balance.
The preview seam is explicitly a FakeNativeSession subclass with tiny rules.
Comparison workers import baseline/current code in separate processes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time
from unittest.mock import patch


def worker(source, repeats):
    sys.path[:0] = [str(source / "tests"), str(source)]
    from test_query_search import FakeNativeSession, actor, make_graph, run_search
    from wakfu_ai.context.native_context import encode
    from wakfu_ai.planning import query_threat  # Load before timing the search.

    class ScenarioSession(FakeNativeSession):
        def __init__(self, config):
            super().__init__(
                spells=[],
                cells=config.get("cells", [(0, 0, 0), (3, 0, 0), (4, 0, 0), (0, 0, 1)]),
                edges=config.get("edges", []),
            )
            self.config = config
            self.rules = {row["id"]: row for row in config["spells"]}
            self.operations = Counter()
            self.root_state["actors"] = [
                actor(1, 1, (0, 0, 0), ap=config.get("ap", 6), mp=config.get("mp", 0)),
                actor(2, 1, (0, 0, 1), hp=config.get("ally_hp", 30)),
                actor(9, 0, (3, 0, 0), hp=config.get("enemy_hp", 30)),
            ]
            if config.get("second_enemy"):
                self.root_state["actors"].append(
                    dict(actor(10, 0, (4, 0, 0)), controlled=False)
                )
            self.root_state["labFlags"] = []
            self.root_state["labUses"] = []
            if config.get("features"):
                self.root_state["outcomeFeatures"] = {"owned_state_progress": 0}
            self.envelope["policy"]["limits"].update(config.get("limits", {}))
            if config.get("risk"):
                self.envelope["operations"] = ["project_turn"]

        def request(self, query):
            self.operations[query["operation"]] += 1
            previous = self.states[query["state"]]["public"]
            if query["operation"] == "repertoire":
                available = [
                    dict(spellId=row["id"], level=1)
                    for row in self.rules.values()
                    if row["id"] not in previous["labUses"]
                    and (
                        not row.get("requires")
                        or row["requires"] in previous["labFlags"]
                    )
                ]
                metadata = self.store.put_json(encode({"spells": available}))
                return dict(
                    id=query["id"], supported=True, result=dict(nativeMetadata=metadata)
                )
            action = query["action"]
            self.preview_actions.append(deepcopy(action))
            result = deepcopy(previous)
            rows = {row["id"]: row for row in result["actors"]}
            caster = rows[1]

            def reject(reason):
                return dict(
                    id=query["id"],
                    supported=False,
                    unknownDependencies=["synthetic_" + reason],
                )

            if action["type"] == "move":
                path = action["path"]
                occupied = {
                    tuple(row["position"])
                    for row in rows.values()
                    if row["id"] != 1 and row["hp"] > 0
                }
                if len(path) > caster["mp"] or any(
                    tuple(cell) in occupied for cell in path
                ):
                    return reject("blocked_movement")
                if any(
                    (tuple(a), tuple(b)) not in self.edges
                    for a, b in zip([caster["position"]] + path, path)
                ):
                    return reject("invalid_edge")
                caster["position"] = list(path[-1])
                caster["mp"] -= len(path)
            elif action["type"] == "cast":
                rule = self.rules[action["spellId"]]
                kind = rule["kind"]
                target = rows.get(action.get("targetId"))
                if self.config.get("reject_all"):
                    return reject("rule_unavailable")
                if caster["ap"] < rule["cost"]:
                    return reject("insufficient_ap")
                if rule.get("at") and caster["position"] != list(rule["at"]):
                    return reject("line_of_sight_or_range")
                if target is None or target["hp"] <= 0:
                    return reject("invalid_target")
                expected_team = (
                    1 if kind in ("heal", "buff", "ap", "unlock", "summon") else 0
                )
                if target["team"] != expected_team or (
                    kind in ("buff", "ap", "unlock", "summon") and target["id"] != 1
                ):
                    return reject("wrong_target")
                caster["ap"] -= rule["cost"]
                result["labUses"].append(rule["id"])
                if kind in ("damage", "aoe"):
                    damage = rule["value"] + (
                        rule.get("buff_bonus", 0) if "buff" in result["labFlags"] else 0
                    )
                    target["hp"] = max(0, target["hp"] - damage)
                    if kind == "aoe":
                        rows[2]["hp"] = max(0, rows[2]["hp"] - rule.get("friendly", 0))
                elif kind == "heal":
                    target["hp"] = min(target["max_hp"], target["hp"] + rule["value"])
                elif kind == "ap":
                    caster["ap"] += rule["value"]
                elif kind in ("buff", "unlock"):
                    result["labFlags"].append("buff" if kind == "buff" else "unlocked")
                    if self.config.get("features"):
                        result["outcomeFeatures"]["owned_state_progress"] += 1
                elif kind == "summon":
                    result["actors"].append(actor(100, 1, (1, 0, 1), hp=5))
            else:
                return reject("unknown_action")
            result["key"] = f"state-{len(self.states)}"
            result["stateRevision"] += 1
            result["nativeContext"] = self.store.put_json(
                make_graph(self.cells, self.edges)
            )
            self.states[result["key"]] = dict(public=result, used=False)
            return dict(id=query["id"], supported=True, result=result)

    def spec(identity, kind="damage", cost=2, value=5, **kw):
        return dict(id=identity, kind=kind, cost=cost, value=value, **kw)

    cells = [(x, 0, 0) for x in range(4)] + [(0, 0, 1)]
    cases = [
        dict(
            name="cheap_vs_ap_combo",
            ap=4,
            spells=[spec(11, cost=2, value=4), spec(12, cost=4, value=15)],
            expected=12,
        ),
        dict(
            name="gain_ap_then_strike",
            ap=3,
            spells=[spec(20, "ap", cost=1, value=3), spec(21, cost=5, value=20)],
            expected=20,
        ),
        dict(
            name="buff_then_strike",
            ap=4,
            features=True,
            spells=[spec(30, "buff"), spec(31, value=3, buff_bonus=20)],
            expected=30,
        ),
        dict(
            name="state_unlock",
            ap=4,
            features=True,
            spells=[spec(40, "unlock"), spec(41, value=20, requires="unlocked")],
            expected=40,
        ),
        dict(
            name="aoe_friendly_fire",
            ap=2,
            ally_hp=10,
            spells=[spec(50, "aoe", value=9, friendly=10), spec(51, value=6)],
            expected=51,
        ),
        dict(
            name="effective_heal",
            ap=2,
            ally_hp=5,
            spells=[spec(60, "heal", value=20), spec(61, value=5)],
            expected=60,
        ),
        dict(
            name="full_health_no_heal",
            ap=2,
            spells=[spec(60, "heal", value=20), spec(61, value=5)],
            expected=61,
        ),
        dict(
            name="finish_vs_summon",
            ap=2,
            enemy_hp=5,
            spells=[spec(70, "summon"), spec(71, value=5)],
            expected=71,
        ),
        dict(
            name="move_then_strike",
            ap=2,
            mp=1,
            cells=cells,
            edges=[((0, 0, 0), (1, 0, 0))],
            spells=[spec(80, value=15, at=(1, 0, 0))],
            expected="move",
        ),
        dict(
            name="los_detour",
            ap=2,
            mp=2,
            cells=cells + [(1, 0, 1)],
            edges=[((0, 0, 0), (1, 0, 0)), ((1, 0, 0), (1, 0, 1))],
            spells=[spec(81, value=15, at=(1, 0, 1))],
            expected="move",
        ),
        dict(
            name="multiple_targets_finish",
            ap=2,
            enemy_hp=4,
            second_enemy=True,
            spells=[spec(90, value=5)],
            expected=90,
            expected_target=9,
        ),
        dict(
            name="native_rejection",
            reject_all=True,
            spells=[spec(91)],
            expected="end_turn",
        ),
        dict(
            name="preparation_crowded_beam",
            ap=4,
            features=True,
            second_enemy=True,
            limits=dict(beam=2, depth=2, nodes=96, probeQuantum=64),
            spells=[
                spec(101, value=2),
                spec(102, value=3),
                spec(103, value=4),
                spec(104, "buff"),
                spec(105, value=1, buff_bonus=25),
            ],
            expected=104,
        ),
        dict(
            name="attack_then_safe_position",
            ap=2,
            mp=1,
            risk=True,
            cells=cells + [(-1, 0, 0)],
            edges=[((0, 0, 0), (-1, 0, 0))],
            spells=[spec(110, value=10)],
            expected=110,
            expect_move=True,
        ),
    ]

    def forecast(state, actor_id, store, weights, **kwargs):
        # Explicit synthetic risk seam: two independently reported adversaries.
        if False:
            yield None
        safe = next(row for row in state["actors"] if row["id"] == 1)["position"][0] < 0
        risk = 0 if safe else 8
        return dict(
            risk=risk * 2,
            knownLowerBound=risk * 2,
            complete=True,
            rivals=[
                dict(
                    actorId=identity,
                    risk=risk,
                    knownLowerBound=risk,
                    complete=True,
                    unknownDependencies=[],
                )
                for identity in (9, 10)
            ],
            unknownDependencies=[],
        )

    results = []
    for config in cases:
        times, samples = [], []
        for iteration in range(repeats + 1):
            session = ScenarioSession(config)
            start = time.perf_counter()
            with patch("wakfu_ai.planning.query_threat.forecast", forecast):
                decision = run_search(session)
            elapsed_ms = (time.perf_counter() - start) * 1000
            if iteration == 0:
                continue
            times.append(elapsed_ms)
            action = decision["action"]
            correct = action.get("spellId", action["type"]) == config["expected"]
            if config.get("expected_target"):
                correct &= action.get("targetId") == config["expected_target"]
            if config.get("expect_move"):
                # Both orderings are acceptable because only the first action is committed.
                correct = {step["type"] for step in decision["plan"]} == {
                    "move",
                    "cast",
                }
            samples.append(
                dict(
                    action=action,
                    plan=decision["plan"],
                    passed=correct,
                    score=decision["score"],
                    utility=decision["components"],
                    queries=dict(session.operations),
                    expanded=decision["expanded"],
                )
            )
        results.append(
            dict(
                name=config["name"],
                passed=all(row["passed"] for row in samples),
                median_ms=statistics.median(times),
                p95_ms=sorted(times)[math.ceil(0.95 * len(times)) - 1],
                deterministic=all(row == samples[0] for row in samples),
                sample=samples[0],
            )
        )
    return dict(
        kind="synthetic-search-corpus",
        source=str(source),
        repeats=repeats,
        warmups_per_case=1,
        passed=sum(row["passed"] for row in results),
        total=len(results),
        cases=results,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--compare", type=Path, help="Baseline ai-service directory")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("repeats must be positive")
    if args.compare:
        import os

        env = dict(os.environ)
        env.pop("PYTHONPATH", None)

        def isolated(path):
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(Path(__file__).resolve()),
                    "--source",
                    str(path.resolve()),
                    "--repeats",
                    str(args.repeats),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            return json.loads(result.stdout)

        result = dict(baseline=isolated(args.compare), current=isolated(args.source))
    else:
        result = worker(args.source.resolve(), args.repeats)
    payload = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n")
    print(payload)


if __name__ == "__main__":
    main()
