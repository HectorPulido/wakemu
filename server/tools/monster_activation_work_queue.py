"""Persistent monster recovery queue; reuse evidence only for unchanged inputs.

Historical failures seed pattern work without rerunning fights. A worker provides
its actual per-reference dependency fingerprint when completing a new probe.
Publication is a separate batch of execution-approved jobs, never a status guess.
"""
import argparse
from collections import Counter
import hashlib
import gzip
import json
from pathlib import Path
import time


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(dependencies):
    if not isinstance(dependencies, dict) or not dependencies:
        raise ValueError("Actual dependency files are required")
    return {str(Path(name).resolve()): digest(name) for name in sorted(dependencies)}


def linked_evidence(link):
    if not isinstance(link, dict) or digest(link["path"]) != link["sha256"]:
        raise ValueError("Worker evidence changed")
    return json.loads(Path(link["path"]).read_text())


def reusable(job):
    expected = job.get("execution_dependencies")
    if not expected or job.get("state") not in ("execution_approved", "blocked"):
        return False
    try:
        linked_evidence(job["evidence"])
        return fingerprint(expected) == expected
    except (OSError, ValueError, KeyError):
        return False


def save(path, queue):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def load(path):
    queue = json.loads(Path(path).read_text())
    if queue.get("schema") != "monster-activation-work-queue-v1":
        raise ValueError("Unknown queue schema")
    # An interrupted worker does not erase its prior evidence or block the lane.
    for job in queue["jobs"]:
        if job["state"] == "running":
            job["state"] = "retryable"
    return queue


def build(inventory, cohorts, *, level_limit=50, native_profiles=None):
    if type(level_limit) is not int or level_limit <= 1:
        raise ValueError("Invalid exclusive level limit")
    patterns = {}
    for group in cohorts["groups"]:
        for ref in group["refs"]:
            if ref in patterns:
                raise ValueError("Causal groups must be disjoint")
            patterns[ref] = group
    jobs = []
    for row in inventory["remaining_monsters"]:
        low, high = row["min_level"], row["max_level"]
        if type(low) is not int or type(high) is not int or not 1 <= low <= high:
            raise ValueError("Invalid native level range")
        if low >= level_limit:
            continue
        group = patterns.get(row["ref"])
        positive = row["category"] in (
            "source_stable_positive_pending_admission",
            "private_source_native_positive_not_shared_admission",
        )
        jobs.append(
            dict(
                ref=row["ref"],
                name=row["name"],
                min_level=low,
                spell_ids=sorted(
                    {
                        ability["spell_id"]
                        for ability in (native_profiles or {})
                        .get(row["ref"], {})
                        .get("native_abilities", [])
                    }
                ),
                max_level=min(high, level_limit - 1),
                native_max_level=high,
                state="historical_positive" if positive else "pattern_pending",
                pattern=group["id"] if group else "outside-bulk:" + str(row["ref"]),
                signature=group["signature"] if group else None,
                historical_category=row["category"],
                historical_proof=row.get("latest_actual_proof"),
                execution_dependencies=None,
                attempts=[],
            )
        )
    if len({job["ref"] for job in jobs}) != len(jobs):
        raise ValueError("Duplicate monster reference")
    return dict(
        schema="monster-activation-work-queue-v1",
        started_at=time.time(),
        level_limit=level_limit,
        published_revision=inventory["revision"],
        baseline_enabled=inventory["enabled"],
        jobs=sorted(jobs, key=lambda j: j["ref"]),
    )


def representatives(queue):
    """One unfinished representative per causal pattern, largest fanout first."""
    groups = {}
    for job in queue["jobs"]:
        if job["state"] in ("enabled", "historical_positive") or reusable(job):
            continue
        groups.setdefault(job["pattern"], []).append(job)
    return [
        dict(
            pattern=key,
            representative=min(j["ref"] for j in jobs),
            affected_refs=sorted(j["ref"] for j in jobs),
            count=len(jobs),
        )
        for key, jobs in sorted(
            groups.items(), key=lambda item: (-len(item[1]), item[0])
        )
    ]


def invalidate(queue, changed_files):
    changed = {str(Path(name).resolve()) for name in changed_files}
    affected = []
    for job in queue["jobs"]:
        dependencies = job.get("execution_dependencies")
        if job["state"] == "enabled":
            continue
        if dependencies and changed.intersection(dependencies):
            job["state"] = "retryable"
            affected.append(job["ref"])
    return affected


def complete(job, *, dependencies, receipt, elapsed_seconds, case_qualifier=None):
    """Record a completed original-validator result, with actual input files."""
    if receipt.get("ref") != job["ref"]:
        raise ValueError("Wrong reference in worker receipt")
    if receipt.get("status") not in ("execution_approved", "blocked", "retryable"):
        raise ValueError("Unknown worker disposition")
    observed = fingerprint(dependencies)
    if observed != dependencies:
        raise ValueError("Dependencies changed during execution")
    evidence = linked_evidence(receipt["evidence"])
    rows = evidence.get("monsters", [evidence])
    actual = next((row for row in rows if row.get("ref") == job["ref"]), None)
    if actual is None:
        raise ValueError("Raw worker evidence has no matching reference")
    if receipt["status"] == "execution_approved":
        if not all(
            receipt.get(key) is True
            for key in (
                "full_native_book",
                "native_initialization_proven",
                "actual_ai_commit",
                "forecast_source_unchanged",
                "serializer_failure_rolled_back",
                "committed_state_changed",
                "owned_object_identities_preserved",
            )
        ):
            raise ValueError("Incomplete native/AI approval")
        if receipt.get("level_range") != [job["min_level"], job["max_level"]]:
            raise ValueError("Approval does not cover the requested native levels")
        expected = {
            (level, spell)
            for level in range(job["min_level"], job["max_level"] + 1)
            for spell in job.get("spell_ids", [])
        }
        if not expected or actual.get("status") != "validated":
            raise ValueError(
                "Missing authoritative owned book or validated native result"
            )
        cases = {
            (case["level"], case["spell_id"]): case for case in actual.get("cases", [])
        }
        if len(cases) != len(actual.get("cases", [])):
            raise ValueError("Duplicate native case identities")

        def qualified(case):
            if case_qualifier is not None:
                return case_qualifier(case) is True
            return case.get("status") == "validated" and any(
                target.get("effectful") is True
                for target in case.get("successful_targets", [])
            )

        if not expected <= cases.keys() or any(
            not qualified(cases[key]) for key in expected
        ):
            raise ValueError(
                "Raw native evidence does not cover the full requested book"
            )
        ai = actual.get("ai_commit", {})
        if (
            ai.get("status") != "validated"
            or ai.get("packets", 0) <= 0
            or not all(
                ai.get(key) is True
                for key in (
                    "forecast_source_unchanged",
                    "serializer_failure_rolled_back",
                    "committed_state_changed",
                    "owned_object_identities_preserved",
                )
            )
        ):
            raise ValueError("Missing actual AI proof")
    job["execution_dependencies"] = observed
    job["evidence"] = receipt["evidence"]
    job["state"] = receipt["status"]
    job["attempts"].append(dict(receipt=receipt, elapsed_seconds=elapsed_seconds))


def status(queue):
    hours = max((time.time() - queue["started_at"]) / 3600, 1 / 3600)
    attempted = sum(bool(j["attempts"]) for j in queue["jobs"])
    enabled = sum(j["state"] == "enabled" for j in queue["jobs"])
    return dict(
        total=len(queue["jobs"]),
        states=dict(Counter(j["state"] for j in queue["jobs"])),
        pattern_count=len(representatives(queue)),
        newly_executed=attempted,
        newly_enabled=enabled,
        executed_per_hour=round(attempted / hours, 2),
        enabled_per_hour=round(enabled / hours, 2),
        heavy_test_runs=queue.get("heavy_test_runs", 0),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--cohorts", type=Path)
    parser.add_argument("--native-monsters", type=Path)
    parser.add_argument("--level-limit", type=int, default=50)
    parser.add_argument("--changed-file", action="append", default=[])
    args = parser.parse_args()
    if args.queue.exists():
        queue = load(args.queue)
    else:
        if not args.inventory or not args.cohorts:
            parser.error("A new queue requires inventory and causal cohorts")
        profiles = {}
        if args.native_monsters:
            raw = args.native_monsters.read_bytes()
            native = json.loads(
                gzip.decompress(raw) if args.native_monsters.suffix == ".gz" else raw
            )
            profiles = {row["ref"]: row for row in native["monsters"]}
        queue = build(
            json.loads(args.inventory.read_text()),
            json.loads(args.cohorts.read_text()),
            level_limit=args.level_limit,
            native_profiles=profiles,
        )
    affected = invalidate(queue, args.changed_file)
    save(args.queue, queue)
    print(
        json.dumps(
            dict(
                **status(queue),
                invalidated_refs=affected,
                next_patterns=representatives(queue)[:10]
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
