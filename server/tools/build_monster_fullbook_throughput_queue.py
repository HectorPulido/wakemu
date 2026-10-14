"""Project full-book admission throughput without transferring actual execution proofs."""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path


def build_queue(index, targeted, native, active_tail_refs):
    positive = {
        row["spell_id"]
        for row in targeted["rows"]
        if row["frozen_status"] == "validated"
        or row["has_later_effectful_targeted_mode"]
    }
    exact = set()
    observed_levels = collections.defaultdict(set)
    for case in index["actual_case_cache"]:
        observed_levels[case["reference"]].add(case["actor_level"])
        if case["status"] == "validated":
            exact.add(
                (
                    case["reference"],
                    case["actor_level"],
                    case["spell_id"],
                    case["spell_level"],
                )
            )
    for evidence in targeted["effectful_targeted_evidence"]:
        if (
            evidence["spell_level_observed"]
            and evidence["spell_level"] is not None
            and "callback" not in evidence["mode"]
        ):
            identity = tuple(evidence["native_tuple"])
            exact.add(identity)
            observed_levels[identity[0]].add(identity[1])
    refs = {
        ref for spell in index["spell_index"].values() for ref in spell["refs"]
    } - set(active_tail_refs)
    candidates, excluded = [], []
    for ref in sorted(refs):
        monster = native[ref]
        book = monster["abilities"]
        spell_ids = {ability["spell_id"] for ability in book}
        missing = spell_ids - positive
        if missing or 803 in monster.get("dependencies", {}).get("effect_families", []):
            excluded.append(
                {
                    "reference": ref,
                    "globally_unproven_spell_ids": sorted(missing),
                    "hard_initial803": 803
                    in monster.get("dependencies", {}).get("effect_families", []),
                }
            )
            continue
        alternatives = []
        for level in sorted(observed_levels[ref] | {max(1, monster["min_level"])}):
            if not max(1, monster["min_level"]) <= level <= monster["max_level"]:
                continue
            needed, identities, unresolved = [], [], []
            for ability in book:
                low, high = ability["effective_level_range"]
                parameter = ability["level_parameter"]
                maximum = (
                    index["spell_index"]
                    .get(str(ability["spell_id"]), {})
                    .get("casting")
                    or {}
                ).get("maximum_level")
                requested = level if parameter == -1 else parameter
                # Same native bPD -> bPO Fq upper bound as maps.monsters.native_abilities.
                spell_level = (
                    min(requested, maximum)
                    if type(maximum) is int and 1 <= maximum <= 32767
                    else None
                )
                if spell_level is None:
                    unresolved.append(ability["spell_id"])
                    continue
                identity = (ref, level, ability["spell_id"], spell_level)
                identities.append(identity)
                if identity not in exact:
                    needed.append(identity)
            if not unresolved:
                alternatives.append((len(needed), level, needed, identities))
        if not alternatives:
            excluded.append(
                {"reference": ref, "native_level_resolution_required": True}
            )
            continue
        cost, level, needed, identities = min(alternatives)
        candidates.append(
            {
                "reference": ref,
                "actor_level": level,
                "owned_spell_ids": sorted(spell_ids),
                "exact_contexts": identities,
                "new_exact_owner_cases_needed": needed,
                "new_case_count": cost,
                "refs_per_new_case_projection": 1 / cost if cost else None,
                "constructor_source_compatibility_and_ai_review_required": True,
                "global_spell_positive_not_owner_execution_proof": True,
                "admission": False,
            }
        )
    candidates.sort(
        key=lambda row: (
            row["new_case_count"],
            len(row["owned_spell_ids"]),
            row["reference"],
        )
    )
    histogram = collections.Counter(row["new_case_count"] for row in candidates)
    return {
        "schema": "monster-fullbook-throughput-source-plan-v1",
        "global_positive_any_mode_spell_count": len(positive),
        "actionable_unpublished_refs": len(refs),
        "globally_spell_ready_refs": len(candidates),
        "exact_new_case_cost_histogram": dict(sorted(histogram.items())),
        "ranked_jobs": candidates,
        "excluded_not_globally_spell_ready": excluded,
        "selection_rule": "Lowest exact-owner new-case cost first; context sets of distinct owners are disjoint, so one executed case never completes another owner.",
        "native_level_resolution_authority": "server/wakfu_server/maps/monsters.py::native_abilities (native bPD/bPO.Fq upper bound; zero and negative never raised)",
        "constructor_and_ai_cost_not_estimated": True,
        "proof_transfer_allowed": False,
        "deployed": False,
        "admission": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--targeted-union", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--active-tail-ref", type=int, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output must be new")
    native = {
        row["ref"]: row
        for row in json.load(gzip.open(args.inventory, "rt"))["monsters"]
    }
    result = build_queue(
        json.loads(args.index.read_text()),
        json.loads(args.targeted_union.read_text()),
        native,
        args.active_tail_ref,
    )
    result["input_sha256"] = {
        str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [args.index, args.targeted_union, args.inventory, Path(__file__)]
    }
    args.output.write_text(json.dumps(result, separators=(",", ":")) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in [
                    "global_positive_any_mode_spell_count",
                    "actionable_unpublished_refs",
                    "globally_spell_ready_refs",
                    "exact_new_case_cost_histogram",
                ]
            }
        )
    )


if __name__ == "__main__":
    main()
