"""Compare complete ordinary/summon authority queries in one certified read pass.

Run only after isolated candidate application and outside live endurance:
PYTHONPATH=server:server/tests python3 server/tools/rift_ordinary_topology_benchmark.py
No database, network or gameplay actions are issued. Requires the matching catalog.
"""
import argparse
from contextlib import nullcontext
from copy import deepcopy
import json
import time
from unittest.mock import patch


def benchmark(history, queries, repeats, *, instrumented_candidate=None):
    import test_combat_ordinary_population_read_pass as fixture
    from wakfu_server import combat_global_pv_collections as pv
    from wakfu_server import combat_ordinary_events as events
    from wakfu_server.combat_state_ledger import StateLedger

    fixture.OrdinaryPopulationReadPassTests.setUpClass()
    case = fixture.OrdinaryPopulationReadPassTests()
    case.setUp()
    fight = case.case.fight
    source_actor = fight.actors[-7]
    source = case.ordinary.monsters[-7]
    for offset in range(history):
        identity = -1000 - offset
        actor = deepcopy(source_actor)
        actor.id = identity
        actor.state_ledger = StateLedger(identity)
        fight.actors[identity] = actor
        case.ordinary.monsters[identity] = dict(source, id=identity)
        pv.register_global_fighter(fight, identity)
        pv.set_global_fighter_status(fight, identity, "OUT_OF_PLAY")
    rows, expected = [], None
    for mode in ("baseline", "candidate"):
        samples = []
        for _ in range(repeats):
            if instrumented_candidate is not None:
                scope = (
                    instrumented_candidate() if mode == "candidate" else nullcontext()
                )
            else:
                scope = (
                    patch.object(pv, "_ordinary_fighter_topology", return_value=None)
                    if mode == "baseline"
                    else nullcontext()
                )
            with scope, events._phase_read_pass(case.case.events, case.case.inv):
                started = time.perf_counter()
                values = [case.wrapper(fight, fight.actors[7])]
                facts = events._ordinary_phase_facts(fight)
                initial = None if facts is None else facts.get("fighter_topologies")
                initial_rows = dict(initial or {})
                for _ in range(queries - 1):
                    values.append(case.wrapper(fight, fight.actors[7]))
                elapsed = time.perf_counter() - started
                current = events._ordinary_phase_facts(fight)
                cached = (
                    {} if current is None else current.get("fighter_topologies", {})
                )
                if mode == "candidate":
                    if not initial_rows or not all(
                        cached.get(key) is row for key, row in initial_rows.items()
                    ):
                        raise ValueError(
                            "Candidate topology cache did not activate and retain its exact proof"
                        )
                elif cached:
                    raise ValueError(
                        "Baseline unexpectedly reused candidate topology facts"
                    )
            if expected is None:
                expected = values
            elif values != expected:
                raise ValueError(
                    "Topology candidate changed full actor authority results"
                )
            samples.append(elapsed)
        rows.append(
            dict(
                mode=mode,
                seconds=samples,
                queries_per_pass=queries,
                historical_actors=history,
                total_actors=len(fight.actors),
                topology_cache_verified=(mode == "candidate"),
            )
        )
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=int, default=180)
    parser.add_argument("--queries", type=int, default=60)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.history < 0 or min(args.queries, args.repeats) < 1:
        parser.error("history must be nonnegative and queries/repeats positive")
    print(json.dumps(benchmark(args.history, args.queries, args.repeats), indent=2))


if __name__ == "__main__":
    main()
