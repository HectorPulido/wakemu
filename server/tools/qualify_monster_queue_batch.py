"""Qualify only selected queue dependents, sharing one warm catalog context.

Uses the original native-book validator and original actual-AI commit checker.
Does not run class suites, publish catalogs, or change services. Descriptor proof
bounds restrict the policy proposal, never the native actor or spell levels.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--asset-root", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only-ref", type=int, action="append", required=True)
    parser.add_argument("--max-attempts", type=int, default=12)
    parser.add_argument("--native-monsters", type=Path)
    args = parser.parse_args()
    if Path.cwd().resolve() != Path(__file__).resolve().parents[2]:
        parser.error("Run from the repository root")
    started = time.monotonic()
    from monster_activation_work_queue import complete, fingerprint, load, save
    from offline_monster_catalog import OfflineMonsterCatalog

    queue = load(args.queue)
    selected = set(args.only_ref)
    jobs = {job["ref"]: job for job in queue["jobs"]}
    if not selected <= jobs.keys() or any(
        jobs[ref]["state"] == "enabled" for ref in selected
    ):
        parser.error("Only existing, unfinished queue references may be qualified")
    if args.output.exists():
        parser.error("Preserve original evidence: output already exists")
    native_output = args.output.with_name(args.output.stem + "-native.json")
    if native_output.exists():
        parser.error("Preserve original native evidence: output already exists")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    snapshot = OfflineMonsterCatalog(args.candidate, args.asset_root)
    native_args = [
        "validate_monster_spell_activation",
        "--candidate",
        str(args.candidate),
        "--output",
        str(native_output),
        "--max-descriptor-level",
        str(queue["level_limit"] - 1),
        "--skip-class-tests",
        "--fail-fast-reference",
        "--recovery-search",
        "--max-attempts",
        str(args.max_attempts),
    ]
    if args.native_monsters is not None:
        native_args.extend(("--native-monsters", str(args.native_monsters)))
    for reference in sorted(selected):
        native_args.extend(("--only-ref", str(reference)))
    original_argv = sys.argv
    try:
        with snapshot.install():
            import validate_monster_spell_activation as validator

            sys.argv = native_args
            validator.main()
            native = json.loads(native_output.read_text())
            observed = {row["ref"] for row in native["monsters"]}
            if observed != selected:
                raise ValueError(
                    "Original validator omitted requested queue references"
                )
            # Reinstalling the overlay would compare its already overlaid caches
            # to base bytes. Call the original AI checker directly instead.
            result = native
            result["schema"] = "native-npc-bounded-native-ai-queue-validation-v1"
            result["original_native_proof"] = dict(
                path=str(native_output.resolve()),
                sha256=hashlib.sha256(native_output.read_bytes()).hexdigest(),
            )
            for row in result["monsters"]:
                if row["status"] == "validated":
                    row["ai_commit"] = validator.commit_smoke(row)
                    if row["ai_commit"]["status"] != "validated":
                        row["status"] = "pending"
                args.output.write_text(json.dumps(result, indent=2) + "\n")
            result["native_elapsed_seconds"] = native["elapsed_seconds"]
            result["elapsed_seconds"] = time.monotonic() - started
            result["summary"] = dict(
                Counter(row["status"] for row in result["monsters"])
            )
            result["ai_runtime_code_sha256_after"] = validator.source_hashes()
            result["ai_validator_sha256_after"] = validator.digest(
                Path(validator.__file__)
            )
            args.output.write_text(json.dumps(result, indent=2) + "\n")
            # Only original validator-qualified native/passive cases can advance
            # the queue; the original actual-AI checker still gates approval.
            if (
                not all(
                    result.get(key) is True
                    for key in (
                        "validator_stable",
                        "native_monsters_stable",
                    )
                )
                or result["ai_validator_sha256_after"] != result["validator_sha256"]
            ):
                raise ValueError("Executed source context changed")
            # Imported local modules are conservative dependencies. Unrelated
            # admin/ecology source files outside that execution graph cannot
            # invalidate a combat receipt merely by changing on disk.
            imported = {
                str(Path(module.__file__).resolve())
                for module in tuple(sys.modules.values())
                if getattr(module, "__file__", None)
                and str(module.__file__).endswith(".py")
            }
            dependency_files = {
                name: value
                for name, value in result["runtime_code_sha256"].items()
                if str(Path(name).resolve()) in imported
            }
            dependency_files[str(Path(validator.__file__).resolve())] = result[
                "validator_sha256"
            ]
            dependency_files[
                str(Path(result["native_monsters_path"]).resolve())
            ] = result["native_monsters_sha256"]
            manifest_path = args.candidate / "manifest.json"
            dependency_files[str(manifest_path.resolve())] = result[
                "candidate_manifest_sha256"
            ]
            dependencies = {
                str(Path(name).resolve()): value
                for name, value in dependency_files.items()
            }
            if fingerprint(dependencies) != dependencies:
                raise ValueError("Executed dependency fingerprints no longer match")
            result[
                "execution_dependency_scope"
            ] = "actual_imported_local_modules_not_dynamic_call_trace"
            result["execution_dependencies"] = dependencies
            args.output.write_text(json.dumps(result, indent=2) + "\n")
            link = dict(
                path=str(args.output.resolve()),
                sha256=hashlib.sha256(args.output.read_bytes()).hexdigest(),
            )
            latest = load(args.queue)
            latest_jobs = {job["ref"]: job for job in latest["jobs"]}
            for row in result["monsters"]:
                ai = row.get("ai_commit", {})
                approved = (
                    row["status"] == "validated" and ai.get("status") == "validated"
                )
                receipt = dict(
                    ref=row["ref"],
                    status="execution_approved" if approved else "blocked",
                    evidence=link,
                    level_range=[
                        latest_jobs[row["ref"]]["min_level"],
                        latest_jobs[row["ref"]]["max_level"],
                    ],
                    full_native_book=approved,
                    native_initialization_proven=not row.get(
                        "pending_initialization", True
                    ),
                    actual_ai_commit=ai.get("status") == "validated",
                    **{
                        key: ai.get(key)
                        for key in (
                            "forecast_source_unchanged",
                            "serializer_failure_rolled_back",
                            "committed_state_changed",
                            "owned_object_identities_preserved",
                        )
                    },
                )
                complete(
                    latest_jobs[row["ref"]],
                    dependencies=dependencies,
                    receipt=receipt,
                    elapsed_seconds=result["elapsed_seconds"],
                    case_qualifier=validator.case_qualification_complete,
                )
            save(args.queue, latest)
    finally:
        sys.argv = original_argv
        receipt_path = args.output.with_name(args.output.stem + "-catalog-receipt.json")
        receipt_path.write_text(json.dumps(snapshot.receipt(), indent=2) + "\n")


if __name__ == "__main__":
    main()
