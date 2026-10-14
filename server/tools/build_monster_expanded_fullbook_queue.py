"""Plan unproven whole native books at native minimum without a global-positive gate."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "index",
        "inventory",
        "previous-queue",
        "published-verification",
        "output",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=100)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output must be new")
    index = json.loads(args.index.read_text())
    previous = json.loads(args.previous_queue.read_text())
    published = json.loads(args.published_verification.read_text())
    native = {
        row["ref"]: row
        for row in json.load(gzip.open(args.inventory, "rt"))["monsters"]
    }
    reserved = {row["reference"] for row in previous["jobs"]}
    reserved |= {2780, 3146, 2967, 5418, 3077, 4559}
    reserved |= set(published["selected_references"])
    tails = {
        2830,
        2831,
        2833,
        3075,
        3081,
        3084,
        3575,
        3577,
        2829,
        3578,
        3925,
        5482,
        3071,
        5421,
    }
    refs = (
        {ref for spell in index["spell_index"].values() for ref in spell["refs"]}
        - reserved
        - tails
    )
    exact = {
        (case["reference"], case["actor_level"], case["spell_id"], case["spell_level"])
        for case in index["actual_case_cache"]
        if case["status"] == "validated"
    }
    for case in previous.get("targeted_known_source_proofs", []):
        if case["spell_level_observed"] and "callback" not in case["mode"]:
            exact.add(tuple(case["native_tuple"]))
    jobs, excluded = [], []
    for ref in sorted(refs):
        monster = native[ref]
        if 803 in monster.get("dependencies", {}).get("effect_families", []):
            excluded.append({"reference": ref, "reason": "source_gap803"})
            continue
        if any(state["state_id"] == 852 for state in monster.get("initial_states", [])):
            excluded.append(
                {"reference": ref, "reason": "initial852_native_producer_unresolved"}
            )
            continue
        level = monster["min_level"]
        identities, missing, unresolved = [], [], []
        for ability in monster["abilities"]:
            spell = index["spell_index"].get(str(ability["spell_id"]), {})
            maximum = (spell.get("casting") or {}).get("maximum_level")
            if type(maximum) is not int or not 1 <= maximum <= 32767:
                unresolved.append(ability["spell_id"])
                continue
            # Native bPD -> bPO.Fq, exactly maps.monsters.native_abilities.
            requested = (
                level
                if ability["level_parameter"] == -1
                else ability["level_parameter"]
            )
            identity = [ref, level, ability["spell_id"], min(requested, maximum)]
            identities.append(identity)
            if tuple(identity) not in exact:
                missing.append(identity)
        if unresolved:
            excluded.append(
                {
                    "reference": ref,
                    "reason": "native_casting_authority_missing",
                    "spell_ids": unresolved,
                }
            )
            continue
        if identities:
            jobs.append(
                {
                    "reference": ref,
                    "actor_level": level,
                    "owned_spell_ids": sorted(
                        ability["spell_id"] for ability in monster["abilities"]
                    ),
                    "exact_contexts": identities,
                    "new_exact_owner_cases_needed": missing,
                    "new_case_count": len(missing),
                    "unknown_conditions_require_actual_diagnosis": True,
                }
            )
    jobs.sort(
        key=lambda row: (
            row["new_case_count"],
            len(row["owned_spell_ids"]),
            row["reference"],
        )
    )
    selected = jobs[: args.batch_size]
    contexts = [
        dict(
            reference=ref,
            actor_level=level,
            spell_id=spell,
            spell_level=pl,
            book_reference=job["reference"],
        )
        for job in selected
        for ref, level, spell, pl in job["new_exact_owner_cases_needed"]
    ]
    result = {
        "schema": "exact-owner-fullbook-completion-worker-queue-v1",
        "live_revision": published["revision"],
        "published_refs": 1310,
        "jobs": selected,
        "contexts": contexts,
        "job_count": len(selected),
        "missing_context_count": len(contexts),
        "ranked_remaining_jobs": jobs[args.batch_size :],
        "all_remaining_eligible_job_count": len(jobs),
        "excluded_source_contexts": excluded,
        "no_global_positive_spell_prerequisite": True,
        "native_abilities_resolver_mandatory": True,
        "resolved_native_identity_must_equal_queue": True,
        "cached_known_source_case_proofs": index["actual_case_cache"],
        "cached_receipt_contexts": index["receipt_contexts"],
        "targeted_known_source_proofs": previous.get(
            "targeted_known_source_proofs", []
        ),
        "targeted_original_source_contexts": previous.get(
            "targeted_original_source_contexts", {}
        ),
        "reserved_previous_job_refs": sorted(reserved),
        "admission": False,
        "source_compatibility_not_assumed": True,
        "input_sha256": {
            str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [
                args.index,
                args.inventory,
                args.previous_queue,
                args.published_verification,
                Path(__file__),
            ]
        },
    }
    args.output.write_text(json.dumps(result, separators=(",", ":")) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "job_count",
                    "missing_context_count",
                    "all_remaining_eligible_job_count",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
