"""One warm native worker: exact uncovered books, functional guards and real AI.

Every level remains explicit. Original native case statuses are never upgraded.
"""
import argparse
from pathlib import Path
import gzip
import hashlib
import json
import os
import sys
import time


def selected_jobs(queue, selected, excluded, first_level):
    jobs = []
    for row in queue["jobs"]:
        ref = row["reference"]
        if (
            row.get("state") != "no_published_low50_overlap"
            or row.get("exception") is not None
            or ref in excluded
            or (selected and ref not in selected)
        ):
            continue
        levels = sorted(
            {
                level
                for lo, hi in row["uncovered_intervals"]
                for level in range(lo, hi + 1)
            }
        )
        if not levels or any(
            type(level) is not int or not 1 <= level <= 50 for level in levels
        ):
            raise ValueError("Invalid exact uncovered low-level interval")
        jobs.append(dict(row, execution_levels=levels[:1] if first_level else levels))
    if len({r["reference"] for r in jobs}) != len(jobs):
        raise ValueError("Duplicate native owner job")
    return sorted(
        jobs,
        key=lambda r: (
            len(r["owned_spell_ids"]) * len(r["execution_levels"]),
            r["reference"],
        ),
    )


def exact_book_complete(cases, owned, level, qualify):
    expected = {(level, row["spell_id"], row["spell_level"]) for row in owned}
    observed = [(row["level"], row["spell_id"], row["spell_level"]) for row in cases]
    return (
        bool(expected)
        and len(observed) == len(set(observed))
        and set(observed) == expected
        and all(qualify(c) for c in cases)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "root",
        "candidate",
        "queue",
        "output",
        "index",
        "lifecycle",
        "aliases",
    ):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--fallback-root", type=Path, action="append", default=[])
    parser.add_argument("--criterion-source", type=Path, action="append", required=True)
    parser.add_argument("--only-ref", type=int, action="append", default=[])
    parser.add_argument("--exclude-ref", type=int, action="append", default=[])
    parser.add_argument("--first-level-pass", action="store_true")
    parser.add_argument("--resume", type=Path, action="append", default=[])
    args = parser.parse_args()
    root = args.root.resolve()
    if not args.first_level_pass:
        raise ValueError(
            "Current user scope requires one base-level probe for never-published references"
        )
    if args.output.exists():
        raise ValueError("Use a fresh immutable run output")
    sys.path[:0] = [
        str(root / f)
        for f in ("server", "server/tools", "server/tests", "server/ai-service")
    ]
    os.environ["WAKFU_NATIVE_GRANTED_CAST"] = "1"
    os.environ["WAKFU_NATIVE_AREA_CALLBACKS"] = "1"
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    from offline_monster_catalog import OfflineMonsterCatalog
    from select_functional_native_contexts import classify_guard
    from consume_monster_fullbook_completions import freeze_warm_catalogs
    from build_monster_effect_work_queue import records

    queue = json.loads(args.queue.read_text())
    jobs = selected_jobs(
        queue, set(args.only_ref), set(args.exclude_ref), args.first_level_pass
    )
    index = json.loads(args.index.read_text())
    lifecycle = json.loads(args.lifecycle.read_text())
    aliases = json.loads(args.aliases.read_text())["aliases"]
    expressions = {}
    for path in args.criterion_source:
        for section, identity, row in records(path, {"effects", "baseline_effects"}):
            variants = row if isinstance(row, list) else [row]
            for variant in variants:
                expressions.setdefault(identity, set()).add(variant.get("criteria", ""))
    initial = {}
    for row in lifecycle["rows"]:
        initial.setdefault(row["reference"], []).append(row)
    native_path = root / ".runtime/monster-combat-extraction-20261010/monsters.json.gz"
    native = {r["ref"]: r for r in json.load(gzip.open(native_path, "rt"))["monsters"]}
    inputs = [
        args.queue,
        args.candidate / "manifest.json",
        args.index,
        args.lifecycle,
        args.aliases,
        native_path,
        *args.criterion_source,
    ]
    input_hashes = {str(p.resolve()): sha(p) for p in inputs}
    catalog = OfflineMonsterCatalog(args.candidate, args.fallback_root)
    output = dict(
        schema="actual-low50-native-book-worker-v1",
        status="running",
        source_root=str(root),
        candidate_manifest_sha256=sha(args.candidate / "manifest.json"),
        worker_sha256=sha(Path(__file__)),
        input_sha256=input_hashes,
        selected_references=[r["reference"] for r in jobs],
        first_level_pass=args.first_level_pass,
        rows=[],
        policy_excluded=[],
        admission=False,
        full_native_book_effectful=False,
    )

    def save():
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_suffix(".tmp")
        temporary.write_text(json.dumps(output, indent=2) + "\n")
        temporary.replace(args.output)

    started = time.monotonic()
    with catalog.install():
        import validate_monster_spell_activation as v
        from wakfu_server.monsters import native_abilities
        from wakfu_server.combat_geometry import published_geometry
        from wakfu_server.monster_minigame_policy import exclusion_reason
        from filter_functional_native_criteria import syntax_only_context
        from wakfu_server.combat import (
            combat_characteristic_conditions as characteristic,
        )
        from wakfu_server.combat.combat_conditions import evaluate_condition

        v.NATIVE_SOURCE_MONSTERS = native
        v.install_overlay(args.candidate)
        output["runtime_code_before"] = v.source_hashes()
        output["validator_sha256"] = sha(Path(v.__file__))
        qualified = (
            lambda c: v.case_qualification_complete(c) or classify_guard(c) is not None
        )
        checked = {}

        def criteria_ready(ref, owned):
            wanted = set()
            missing = []
            for row in owned:
                metadata = index["spell_index"].get(str(row["spell_id"]))
                if metadata is None or metadata["runtime_missing_families"]:
                    missing.append(["spell_or_family", row["spell_id"]])
                    continue
                wanted.add((metadata.get("casting") or {}).get("criterion", ""))
                for effect in metadata["effect_ids"]:
                    if str(effect) not in expressions:
                        missing.append(["effect", effect])
                    else:
                        wanted.update(expressions[str(effect)])
            for row in initial.get(ref, []):
                if row.get("missing_source_node"):
                    missing.append(row["missing_source_node"])
                wanted.add(row.get("criterion", ""))
            previous = characteristic.native_aliases
            characteristic.native_aliases = lambda: aliases
            failures = {}
            try:
                for raw in wanted:
                    if not raw.strip():
                        continue
                    if raw not in checked:
                        try:
                            assert (
                                evaluate_condition(
                                    "false and (" + raw + ")", syntax_only_context()
                                )
                                is False
                            )
                            checked[raw] = None
                        except Exception as error:
                            checked[raw] = type(error).__name__ + ": " + str(error)
                    if checked[raw] is not None:
                        failures[raw] = checked[raw]
            finally:
                characteristic.native_aliases = previous
            return dict(
                complete=not missing and not failures,
                missing_source_nodes=missing,
                unsupported_criteria=failures,
                syntax_only_not_runtime_authority=True,
                nonempty_criteria_count=sum(bool(s.strip()) for s in wanted),
            )

        freeze_warm_catalogs()
        resume = {}
        for path in args.resume:
            old = json.loads(path.read_text())
            if (
                old.get("status") != "completed"
                or old.get("runtime_code_before") != output["runtime_code_before"]
                or old.get("candidate_manifest_sha256")
                != output["candidate_manifest_sha256"]
                or old.get("worker_sha256") != output["worker_sha256"]
                or not old.get("sources_stable")
            ):
                raise ValueError("Resume source/candidate/worker context differs")
            for row in old["rows"]:
                key = row["reference"], row["actor_level"]
                if key in resume:
                    raise ValueError("Duplicate resume exact owner level")
                resume[key] = dict(
                    row, resumed_from=dict(path=str(path.resolve()), sha256=sha(path))
                )
        for job in jobs:
            ref = job["reference"]
            reason = exclusion_reason(ref)
            if reason:
                output["policy_excluded"].append(
                    dict(reference=ref, reason=reason, context="ordinary_wild")
                )
                save()
                continue
            if ref not in set(
                json.loads((args.candidate / "manifest.json").read_text())[
                    "selected_references"
                ]
            ):
                output["policy_excluded"].append(
                    dict(reference=ref, reason="outside_candidate_no_execution")
                )
                save()
                continue
            for level in job["execution_levels"]:
                if (ref, level) in resume:
                    output["rows"].append(resume[(ref, level)])
                    save()
                    continue
                owned = native_abilities(ref, level)
                cases = []
                source_before = v.source_hashes()
                for ability in owned:
                    cases.append(
                        v.run_case(
                            ref,
                            level,
                            ability["spell_id"],
                            ability["spell_level"],
                            published_geometry(1134).cells,
                            12,
                            recovery_search=True,
                            recovery_attempt_cap=6,
                            recovery_scene_cap=4,
                        )
                    )
                constructor = not native[ref]["initial_state_triples"] or any(
                    v.initialization_proven(
                        ref, level, native[ref]["initial_state_triples"], r
                    )
                    for c in cases
                    for r in c.get("initialization_receipts", [])
                )
                criteria = criteria_ready(ref, owned)
                complete = (
                    exact_book_complete(cases, owned, level, qualified)
                    and constructor
                    and criteria["complete"]
                )
                row = dict(
                    reference=ref,
                    actor_level=level,
                    cases=cases,
                    native_constructor_proven=constructor,
                    functional_complete_book=complete,
                    reachable_criterion_proof=criteria,
                    actual_ai=None,
                )
                if constructor and any(
                    c["status"] == "validated"
                    and any(
                        t.get("effectful") is True
                        for t in c.get("successful_targets", [])
                    )
                    for c in cases
                ):
                    row["actual_ai"] = v.commit_smoke(dict(ref=ref, cases=cases))
                source_after = v.source_hashes()
                row["source_context_sha256"] = hashlib.sha256(
                    json.dumps(source_before, sort_keys=True).encode()
                ).hexdigest()
                row["sources_stable"] = (
                    source_before == source_after == output["runtime_code_before"]
                )
                output["rows"].append(row)
                save()
                print(
                    json.dumps(
                        dict(
                            ref=ref,
                            level=level,
                            functional_book=complete,
                            ai=(row["actual_ai"] or {}).get("status"),
                        )
                    ),
                    flush=True,
                )
        output["runtime_code_after"] = v.source_hashes()
        output["catalog_receipt"] = catalog.receipt()
        output["sources_stable"] = (
            output["runtime_code_before"] == output["runtime_code_after"]
        )
    output.update(
        status="completed",
        elapsed_seconds=time.monotonic() - started,
        worker_stable=sha(Path(__file__)) == output["worker_sha256"],
        inputs_stable=all(sha(p) == h for p, h in input_hashes.items()),
    )
    save()


if __name__ == "__main__":
    main()
