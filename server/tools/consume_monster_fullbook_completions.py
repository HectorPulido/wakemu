"""Complete exact-owner native books and consume them once through actual AI.

Original proof contexts remain explicit. No source/level rebinding, native replay,
integer-range expansion, service action or admission happens in this consumer.
"""
import argparse
from contextlib import contextmanager
import gzip
import gc
import hashlib
import json
from pathlib import Path
import signal
import sys
import time


def identity(context):
    return tuple(
        context[key] for key in ("reference", "actor_level", "spell_id", "spell_level")
    )


def completed_books(jobs, proofs, native, qualifier=None):
    """Require every exact tuple plus the original constructor, never spell ID alone."""
    result = []
    for job in jobs:
        keys = [tuple(row) for row in job["exact_contexts"]]
        if not keys or any(key not in proofs for key in keys):
            continue
        rows = [proofs[key] for key in keys]
        if any(
            not (
                qualifier(row["raw_case"])
                if qualifier is not None
                else row["raw_case"].get("status") == "validated"
            )
            for row in rows
        ):
            continue
        ref, level = job["reference"], job["actor_level"]
        triples = native[ref]["raw_native"]["cle"]
        constructor = not triples or any(
            receipt.get("ref") == ref
            and receipt.get("descriptor_level") == level
            and receipt.get("raw_triples") == triples
            and receipt.get("initialized") is True
            for row in rows
            for receipt in row["raw_case"].get("initialization_receipts", [])
        )
        if constructor:
            result.append((job, rows))
    return result


@contextmanager
def context_deadline(seconds):
    """Wall-clock budget only; never advance or replace native clocks."""
    if not 0 < seconds <= 60:
        raise ValueError("Actual AI context budget must be at most 60 seconds")

    def expired(_signum, _frame):
        raise TimeoutError("Actual AI context wall-clock budget exhausted")

    previous = signal.signal(signal.SIGALRM, expired)
    timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, *timer)
        signal.signal(signal.SIGALRM, previous)


def worker_completed(report):
    """Recognize the actual native completion schema without rewriting receipts."""
    return isinstance(report, dict) and report.get("status", "").startswith("completed")


def checksum(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(path)


def pointer_value(report, pointer):
    for component in pointer.strip("/").split("/"):
        report = (
            report[int(component)] if isinstance(report, list) else report[component]
        )
    return report


def original_owner(report, pointer):
    """Read actual enclosing execution authority instead of trusting cache labels."""
    ancestry = [report]
    for component in pointer.strip("/").split("/"):
        report = (
            report[int(component)] if isinstance(report, list) else report[component]
        )
        ancestry.append(report)
    for node in reversed(ancestry):
        if not isinstance(node, dict):
            continue
        context = node.get("context")
        if isinstance(context, dict) and "reference" in context:
            return context["reference"]
        if "cases" in node:
            owner = node.get("ref", node.get("reference"))
            if type(owner) is int:
                return owner
    return None


def original_proof(path, digest, pointer, context):
    path = Path(path)
    if checksum(path) != digest:
        raise ValueError("Original native proof changed")
    report = json.loads(path.read_text())
    value = pointer_value(report, pointer)
    if "original_receipt" in value:
        if (
            value.get("source_equivalence_verified") is not True
            or identity(value["context"]) != context
        ):
            raise ValueError("Unverified historical source equivalence")
        ancestor = value["original_receipt"]
        leaf = original_proof(
            ancestor["receipt"], ancestor["sha256"], ancestor["json_pointer"], context
        )
        leaf.setdefault("source_equivalence_ancestry", []).append(
            dict(path=str(path.resolve()), sha256=digest, pointer=pointer)
        )
        return leaf
    raw = value.get("raw_case", value)
    if original_owner(report, pointer) != context[0]:
        raise ValueError("Original enclosing owner missing or differs")
    if (raw.get("level"), raw.get("spell_id"), raw.get("spell_level")) != context[1:]:
        raise ValueError("Original native tuple differs")
    if value.get("context") and identity(value["context"]) != context:
        raise ValueError("Original owner differs")
    return dict(
        context=context,
        raw_case=raw,
        path=str(path.resolve()),
        sha256=digest,
        pointer=pointer,
        source_root=report.get("source_root"),
        source_context_preserved=True,
    )


def freeze_warm_catalogs(loaders=None):
    """Keep long-lived native catalogs out of repeated cyclic GC traversals."""
    if loaders is None:
        from wakfu_server.combat_npc_attack import npc_runtime_catalog
        from wakfu_server.combat_native_spell_casting import catalog
        from wakfu_server.combat_geometry import published_geometry

        loaders = (npc_runtime_catalog, catalog, lambda: published_geometry(1134))
    enabled = gc.isenabled()
    gc.disable()
    try:
        for load in loaders:
            load()
        gc.collect()
        gc.freeze()
    finally:
        if enabled:
            gc.enable()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--seed-receipt", type=Path, action="append", default=[])
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, action="append", required=True)
    parser.add_argument("--native-inventory", type=Path, required=True)
    parser.add_argument("--native-monsters", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ready-output", type=Path, required=True)
    parser.add_argument("--helper-root", type=Path, required=True)
    parser.add_argument("--budget-seconds", type=float, default=60)
    parser.add_argument("--poll-seconds", type=float, default=2)
    args = parser.parse_args()
    root = args.root.resolve()
    sys.path[:0] = [
        str(root / "server"),
        str(root / "server/tools"),
        str(root / "server/ai-service"),
        str(args.helper_root.resolve()),
    ]
    queue = json.loads(args.queue.read_text())
    jobs = queue.get("zero_case_candidates_separate", []) + queue["jobs"]
    wanted = {tuple(row) for job in jobs for row in job["exact_contexts"]}
    with gzip.open(args.native_inventory, "rt") as stream:
        native = {row["ref"]: row for row in json.load(stream)["monsters"]}
    proofs = {}
    index = json.loads(args.index.read_text())
    for cached in index["actual_case_cache"]:
        key = identity(cached)
        if key not in wanted:
            continue
        context = index["receipt_contexts"][cached["context_ref"]]
        try:
            proofs[key] = original_proof(
                context["receipt"],
                context["sha256"],
                cached["original_json_pointer"],
                key,
            )
        except (ValueError, KeyError):
            continue
    for row in queue["targeted_known_source_proofs"]:
        key = identity(row)
        context = queue["targeted_original_source_contexts"][row["context_ref"]]
        if context.get("sources_stable") is True:
            proofs[key] = original_proof(
                context["original_report"],
                context["original_report_sha256"],
                context["original_json_pointer"],
                key,
            )
    for path in args.seed_receipt:
        report = json.loads(path.read_text())
        if report.get("sources_stable") is not True:
            raise ValueError("Seed source context is unstable")
        for number, row in enumerate(report["cases"]):
            key = identity(row["context"])
            if key in wanted:
                proofs[key] = original_proof(
                    path, checksum(path), f"/cases/{number}", key
                )
    from offline_monster_catalog import OfflineMonsterCatalog
    from actual_ai import prove
    from wakfu_server.monster_minigame_policy import exclusion_reason

    state = (
        json.loads(args.output.read_text())
        if args.output.exists()
        else dict(
            schema="automatic-exact-fullbook-ai-consumer-v1",
            status="running",
            rows=[],
            admission=False,
            native_cases_repeated=0,
            queue_sha256=checksum(args.queue),
            source_root=str(root),
            original_source_contexts_not_rebound=True,
        )
    )
    if state["queue_sha256"] != checksum(args.queue):
        raise ValueError("Continuation queue changed")
    seen = {(row["reference"], row["actor_level"]) for row in state["rows"]}
    held = set(
        queue.get("excluded_unchanged_ai_pending_refs", [2780, 3146, 2967, 5418])
    )
    catalog = OfflineMonsterCatalog(args.candidate, args.catalog_root)
    start = time.monotonic()
    with catalog.install():
        import validate_monster_spell_activation as validator

        validator.install_overlay(args.candidate)
        with gzip.open(args.native_monsters, "rt") as stream:
            validator.NATIVE_SOURCE_MONSTERS = {
                m["ref"]: m for m in json.load(stream)["monsters"]
            }
        from wakfu_server.monsters import native_abilities

        before = validator.source_hashes()
        state["tested_runtime_code_sha256"] = before
        freeze_warm_catalogs()
        while True:
            worker = None
            if args.worker.exists():
                try:
                    worker = json.loads(args.worker.read_text())
                except json.JSONDecodeError:
                    pass
            if worker:
                # A frozen physical source is checked even before the final seal.
                source = Path(worker["source_root"])
                pins = worker["source_sha256_before"]
                if any(
                    checksum(source / name) != digest for name, digest in pins.items()
                ):
                    raise ValueError("Native worker physical source drift")
                snapshot = (
                    args.output.parent
                    / "native-worker-snapshots"
                    / (checksum(args.worker) + ".json")
                )
                if not snapshot.exists():
                    atomic_json(snapshot, worker)
                digest = checksum(snapshot)
                for number, row in enumerate(worker["cases"]):
                    key = identity(row["context"])
                    if key in wanted:
                        proofs[key] = original_proof(
                            snapshot, digest, f"/cases/{number}", key
                        )
            for job, rows in completed_books(
                jobs, proofs, native, validator.case_qualification_complete
            ):
                ref, level = job["reference"], job["actor_level"]
                if (ref, level) in seen or ref in held:
                    continue
                seen.add((ref, level))
                row = dict(
                    reference=ref,
                    actor_level=level,
                    status="running",
                    proof_range=[level, level],
                    original_native_proofs=[
                        {k: v for k, v in proof.items() if k != "raw_case"}
                        for proof in rows
                    ],
                    admission=False,
                )
                state["rows"].append(row)
                tick = time.monotonic()
                try:
                    reason = exclusion_reason(ref)
                    if reason:
                        raise ValueError("Held ordinary policy: " + reason)
                    actual = sorted(
                        (ref, level, a["spell_id"], a["spell_level"])
                        for a in native_abilities(ref, level)
                    )
                    if actual != sorted(tuple(item) for item in job["exact_contexts"]):
                        raise ValueError(
                            "Actual native ownership/PL differs from complete book"
                        )
                    with context_deadline(args.budget_seconds):
                        ai = prove(
                            ref, [proof["raw_case"] for proof in rows], validator
                        )
                    row.update(status=ai["status"], actual_ai=ai)
                except Exception as error:
                    row.update(
                        status="pending", error=type(error).__name__ + ": " + str(error)
                    )
                row["elapsed_seconds"] = round(time.monotonic() - tick, 3)
                state["sources_stable"] = validator.source_hashes() == before
                if not state["sources_stable"]:
                    raise ValueError("Actual AI physical source changed")
                immutable = args.output.parent / "ai-proofs" / f"{ref}-{level}.json"
                atomic_json(
                    immutable,
                    dict(
                        schema="exact-owner-actual-ai-context-v1",
                        row=row,
                        tested_runtime_code_sha256=before,
                        sources_stable=True,
                        admission=False,
                    ),
                )
                row["immutable_ai_receipt"] = str(immutable.resolve())
                row["immutable_ai_sha256"] = checksum(immutable)
                atomic_json(args.output, state)
                ready = dict(
                    schema="approved-monster-policy-ranges-v1",
                    base_revision=queue["live_revision"],
                    expected_base_policy_count=queue["published_refs"],
                    expected_document_count=7486,
                    approvals=[],
                    deployed=False,
                )
                for accepted in state["rows"]:
                    if accepted["status"] != "validated_ordinary_ai":
                        continue
                    evidence = {
                        p["path"]: p["sha256"]
                        for p in accepted["original_native_proofs"]
                    }
                    if accepted.get("immutable_ai_receipt"):
                        evidence[accepted["immutable_ai_receipt"]] = accepted[
                            "immutable_ai_sha256"
                        ]
                    ready["approvals"].append(
                        dict(
                            ref=accepted["reference"],
                            min_level=accepted["actor_level"],
                            max_level=accepted["actor_level"],
                            proof_kind="same_owner_exact_native_level_fullbook_actual_ai",
                            original_evidence=[
                                dict(path=path, sha256=digest)
                                for path, digest in evidence.items()
                            ],
                            actual_ai_receipt=str(args.output.resolve()),
                            admission=False,
                        )
                    )
                atomic_json(args.ready_output, ready)
                print(
                    json.dumps(
                        dict(
                            reference=ref,
                            status=row["status"],
                            completed=len(state["rows"]),
                            ready=len(ready["approvals"]),
                        )
                    ),
                    flush=True,
                )
            if worker_completed(worker):
                break
            time.sleep(args.poll_seconds)
        for accepted in state["rows"]:
            if not accepted.get("immutable_ai_receipt"):
                immutable = (
                    args.output.parent
                    / "ai-proofs"
                    / f"{accepted['reference']}-{accepted['actor_level']}.json"
                )
                atomic_json(
                    immutable,
                    dict(
                        schema="exact-owner-actual-ai-context-v1",
                        row=accepted,
                        tested_runtime_code_sha256=before,
                        sources_stable=state.get("sources_stable"),
                        admission=False,
                    ),
                )
                accepted["immutable_ai_receipt"] = str(immutable.resolve())
                accepted["immutable_ai_sha256"] = checksum(immutable)
        ready = json.loads(args.ready_output.read_text())
        for approval in ready["approvals"]:
            accepted = next(
                row for row in state["rows"] if row["reference"] == approval["ref"]
            )
            evidence = dict(
                path=accepted["immutable_ai_receipt"],
                sha256=accepted["immutable_ai_sha256"],
            )
            if evidence not in approval["original_evidence"]:
                approval["original_evidence"].append(evidence)
        atomic_json(args.ready_output, ready)
        state.update(
            status="completed",
            elapsed_seconds=round(time.monotonic() - start, 3),
            sources_stable=validator.source_hashes() == before,
            catalog=catalog.receipt(),
            native_worker_terminal_source_stable=worker.get("sources_stable"),
        )
        atomic_json(args.output, state)
    return 0 if state["sources_stable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
