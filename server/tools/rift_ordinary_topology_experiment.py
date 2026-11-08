"""Instrumented isolated experiment; NOT release validation or fingerprint bypass.

Uses the installed package/catalog unchanged. Candidate source is loaded under
private module names, and only its consumer functions are temporarily selected
inside this process. No provider identity, source guard or catalog fingerprint
is overwritten. Run only when the parent permits local measurement.
"""
import argparse
from contextlib import ExitStack, contextmanager
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch


def load_candidate(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate_scope(directory):
    from wakfu_server import combat_global_pv_collections as installed_pv
    from wakfu_server import combat_summon_count as installed_counts

    candidate_pv = load_candidate(
        directory / "combat_global_pv_collections.py",
        "wakfu_server._instrumented_global_pv_collections",
    )
    candidate_counts = load_candidate(
        directory / "combat_summon_count.py", "wakfu_server._instrumented_summon_count"
    )

    @contextmanager
    def selected():
        with ExitStack() as stack:
            for name in (
                "global_fighter_guards",
                "global_fighter_registered",
                "global_fighter_participates",
                "ordinary_fighter_order",
                "_ordinary_topology_consumer_scope",
            ):
                stack.enter_context(
                    patch.object(
                        installed_pv, name, getattr(candidate_pv, name), create=True
                    )
                )
            stack.enter_context(
                patch.object(
                    installed_counts,
                    "registered_summon_counts",
                    candidate_counts.registered_summon_counts,
                )
            )
            yield

    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate-directory",
        type=Path,
        default=Path(".runtime/rift-followup-20261106/performance-topology-next"),
    )
    parser.add_argument("--history", type=int, default=180)
    parser.add_argument("--queries", type=int, default=60)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.history < 0 or min(args.queries, args.repeats) < 1:
        parser.error("history must be nonnegative and queries/repeats positive")
    from rift_ordinary_topology_benchmark import benchmark

    results = benchmark(
        args.history,
        args.queries,
        args.repeats,
        instrumented_candidate=candidate_scope(args.candidate_directory),
    )
    print(
        json.dumps(
            dict(
                kind="instrumented_component_experiment",
                release_validation=False,
                catalog_policy="installed matching catalog; no fingerprint overrides",
                full_authority_equal=True,
                results=results,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
