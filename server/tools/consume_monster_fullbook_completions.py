"""Historical exact-owner receipt helpers; the Python planner consumer is retired.

No equivalent WakIA qualification has been established. Historical proofs are
not evidence of an actual WakIA decision and must not be promoted as such.
"""
import argparse
from contextlib import contextmanager
import gc
import hashlib
import json
from pathlib import Path
import signal


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
    parser.parse_known_args()
    parser.error(
        "This exact-owner consumer required the retired Python planner helper; "
        "no equivalent WakIA qualification has been established. "
        "Existing receipts remain historical and must not be promoted as WakIA evidence."
    )


if __name__ == "__main__":
    raise SystemExit(main())
