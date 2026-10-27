"""Bounded diagnostic of the actual NativeOracle.fork(runtime=...) copy.

This tool changes neither the game nor its providers. The temporary copy-dict
observer uses the original deepcopy operation, memo and value-before-key order.
Times include instrumentation overhead; nested inclusive rows are not additive.
"""
import argparse
from collections import defaultdict
from contextlib import contextmanager
import copy
import cProfile
import hashlib
import json
from pathlib import Path
import struct
import sys
import time


def _type(value):
    return type(value).__module__ + "." + type(value).__qualname__


class CopyFields:
    def __init__(self, runtime):
        self.runtime = runtime
        self.dictionaries = {id(vars(runtime.fight)): "fight"}
        self.dictionaries[id(runtime.fight.actors)] = "actor_map"
        for identity, actor in runtime.fight.actors.items():
            self.dictionaries[id(vars(actor))] = "actor:" + str(identity)
            self.dictionaries[id(vars(actor.state_ledger))] = "states:" + str(identity)
        self.runtime_fields = defaultdict(list)
        for name, value in vars(runtime).items():
            self.runtime_fields[id(value)].append(name)
        self.rows = []
        self.stack = []
        self.nodes = {}

    def measure(self, label, value, memo, operation):
        node = self.nodes.setdefault(id(value), len(self.nodes) + 1)
        memo_hit = memo is not None and id(value) in memo
        depth = len(self.stack)
        frame = {"child_ns": 0}
        self.stack.append(frame)
        start = time.perf_counter_ns()
        try:
            result = operation()
        finally:
            elapsed = time.perf_counter_ns() - start
            self.stack.pop()
            if self.stack:
                self.stack[-1]["child_ns"] += elapsed
        self.rows.append(
            dict(
                field=label,
                source_type=_type(value),
                source_node=node,
                memo_hit_before=memo_hit,
                tracked_depth=depth,
                shallow_length=len(value)
                if isinstance(value, (dict, list, tuple, set, frozenset, bytes))
                else None,
                shared_identity=result is value,
                inclusive_ns=elapsed,
                exclusive_of_tracked_descendants_ns=max(0, elapsed - frame["child_ns"]),
            )
        )
        return result

    @contextmanager
    def installed(self):
        from wakfu_server import combat_runtime_messages

        dictionary_copy = copy._deepcopy_dispatch[dict]
        runtime_copy = combat_runtime_messages.deepcopy
        self.original_runtime_copy = runtime_copy

        def observed_dict(value, memo, deepcopy=copy.deepcopy):
            label = self.dictionaries.get(id(value))
            if label is None:
                return dictionary_copy(value, memo)
            result = {}
            memo[id(value)] = result
            for key, item in value.items():
                # This is precisely _deepcopy_dict's RHS-before-key evaluation.
                cloned = self.measure(
                    label + "." + str(key),
                    item,
                    memo,
                    lambda item=item: deepcopy(item, memo),
                )
                result[deepcopy(key, memo)] = cloned
            return result

        def observed_runtime(value, memo=None):
            names = self.runtime_fields.get(id(value))
            if names is None:
                return runtime_copy(value, memo)
            return self.measure(
                "runtime." + "|".join(sorted(names)),
                value,
                memo,
                lambda: runtime_copy(value, memo),
            )

        copy._deepcopy_dispatch[dict] = observed_dict
        combat_runtime_messages.deepcopy = observed_runtime
        try:
            yield
        finally:
            copy._deepcopy_dispatch[dict] = dictionary_copy
            combat_runtime_messages.deepcopy = runtime_copy


def observe_fork(oracle, runtime):
    """Observe one existing source-owned fork, without extra graph clones."""
    observer = CopyFields(runtime)
    profile = cProfile.Profile()
    with observer.installed():
        start = time.perf_counter_ns()
        profile.enable()
        try:
            candidate = oracle.fork(runtime=runtime)
        finally:
            profile.disable()
        elapsed = time.perf_counter_ns() - start
    return (
        candidate,
        profile,
        dict(
            fork_wall_ns=elapsed,
            field_observations=observer.rows,
            exclusive_tracked_sum_ns=sum(
                row["exclusive_of_tracked_descendants_ns"] for row in observer.rows
            ),
            field_time_method="same operation/memo/order; instrumented wall time",
            exclusive_definition="excludes tracked descendant field times, not all child calls",
            summation="inclusive nested fields overlap; never sum them",
            source_value_policy="names/types/lengths/identity only; no source bodies",
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    for path in (root / "server", root / "server" / "ai-service"):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from tools.sublimation_semantic_fixture import build_fixture

    fixture = build_fixture(27159, arguments.manifest)
    # The source-pinned metadata backend is installed before AI/runtime imports.
    from wakfu_ai.native.native_oracle import NativeOracle
    from wakfu_server.combat_characteristic_link import bind_characteristic_stats
    from wakfu_server.combat_runtime_messages import RuntimeMessages
    from wakfu_server.fight_checkpoint_store import snapshot

    bind_characteristic_stats(fixture.fight)
    runtime = RuntimeMessages(fixture.fight)
    oracle = NativeOracle(
        runtime,
        characters={7: fixture.character},
        monsters=fixture.monster_sources,
        decks={7: frozenset()},
        excluded_decks={7: frozenset()},
        viewer_id=7,
        flags={"native_start_events": True, "native_area_callbacks": True},
    )
    # Genuine service callbacks, not a provider returning a fabricated decision.
    runtime.turn_start_provider = oracle.start_boundary
    runtime.turn_end_provider = oracle.end_boundary
    # Declared pending transport state, not an executed END/ACK qualification.
    runtime.awaiting_ack = runtime.fight.turn_id
    runtime.pending = [(13078, struct.pack(">qI", 7, 0))]
    shared = {"values": [1]}
    runtime.future_runtime_probe = shared
    runtime.fight.future_fight_probe = shared
    runtime.fight.actors[7].future_actor_probe = shared
    runtime.future_fight_alias = runtime.fight
    source_before = snapshot(runtime.fight, runtime=runtime)
    rng_before = fixture.factory.transaction_rng.getstate()
    candidate, profile, report = observe_fork(oracle, runtime)
    assert candidate is not runtime and candidate.fight is not runtime.fight
    assert candidate.future_fight_alias is candidate.fight
    assert (
        candidate.future_runtime_probe
        is candidate.fight.future_fight_probe
        is candidate.fight.actors[7].future_actor_probe
    )
    assert candidate.future_runtime_probe is not shared
    assert candidate.awaiting_ack == runtime.awaiting_ack
    assert (
        candidate.pending == runtime.pending
        and candidate.pending is not runtime.pending
    )
    assert candidate.turn_start_provider.__self__ is oracle
    assert candidate.turn_end_provider.__self__ is oracle
    for identity, actor in candidate.fight.actors.items():
        assert actor is not runtime.fight.actors[identity]
        assert actor.effect_stats._fight is candidate.fight
    candidate.future_runtime_probe["values"].append(2)
    candidate.pending.clear()
    candidate.awaiting_ack = None
    candidate.fight.actors[7].effect_stats[48] += 1
    assert shared == {"values": [1]}
    assert snapshot(runtime.fight, runtime=runtime) == source_before
    assert fixture.factory.transaction_rng.getstate() == rng_before
    assert copy._deepcopy_dispatch[dict].__module__ == "copy"
    report.update(
        status="one_actual_bounded_fork_observed_isolation_verified",
        manifest_sha256=hashlib.sha256(arguments.manifest.read_bytes()).hexdigest(),
        full_class_ready_qualified=fixture.full_class_ready_qualified,
        declared_transport_premise=True,
        assertions="source snapshot/RNG, aliases, independent actors/PA, pending ACK, callback ownership",
        overhead="observer plus cProfile; no calibrated uninstrumented latency or speedup",
        scope="one actual NativeOracle.fork(runtime=...) on one bounded native fixture; not World",
        source_files={
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (
                root / "server/ai-service/wakfu_ai/native/native_oracle.py",
                root / "server/wakfu_server/combat/combat_runtime_messages.py",
                Path(__file__).resolve(),
            )
        },
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    profile.dump_stats(str(arguments.output.with_suffix(".pstats")))
    print(
        json.dumps(
            dict(
                status=report["status"],
                fork_wall_ns=report["fork_wall_ns"],
                fields=len(report["field_observations"]),
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
