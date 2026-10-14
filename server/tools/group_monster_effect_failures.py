"""Incremental diagnostic triage by native semantic context, never unlock claims."""
import argparse
import hashlib
import json
from pathlib import Path


def stable_read(path, attempts=3, preserve_dir=None):
    for _ in range(attempts):
        before = path.read_bytes()
        try:
            document = json.loads(before)
        except json.JSONDecodeError:
            continue
        if before == path.read_bytes():
            digest = hashlib.sha256(before).hexdigest()
            if preserve_dir is not None:
                preserve_dir.mkdir(parents=True, exist_ok=True)
                target = preserve_dir / (digest + ".json")
                if target.exists() and target.read_bytes() != before:
                    raise ValueError("Immutable snapshot content conflict")
                if not target.exists():
                    target.write_bytes(before)
            return document, digest
    raise ValueError("Receipt changed or was incomplete during bounded snapshot read")


def diagnostic_signature(diagnostic):
    details = diagnostic.get("details", {})
    native = details.get("native_casting_diagnostic", {})
    failed = [entry for entry in native.get("trace", []) if entry.get("value") is False]
    stage = (
        failed[-1]["stage"] if failed else "execution_exception_without_native_stage"
    )
    # Exception codes remain attached evidence; they do not define causal groups.
    return {
        "stage": stage,
        "criterion": native.get("criterion"),
        "error_type": diagnostic.get("error_type"),
        "effect_id": details.get("effect_id"),
        "selector": details.get("selector"),
        "resource": details.get("resource"),
        "message_without_cast_code": None
        if details.get("native_casting_result")
        else diagnostic.get("message"),
    }


def group_failures(index, receipts, preserve_dir=None):
    groups = {}
    snapshots = {}
    total = validated = pending = 0
    raw_status_counts = {}
    source_witness_cases = []
    identities = {}
    receipt_entries = 0
    reused_entries = 0
    for path in receipts:
        document, digest = stable_read(path, preserve_dir=preserve_dir)
        snapshots[digest] = {
            "path": str(path.resolve()),
            "immutable_snapshot": str((preserve_dir / (digest + ".json")).resolve())
            if preserve_dir
            else None,
            "source_sha256_before": document.get("source_sha256_before"),
            "source_sha256_after": document.get("source_sha256_after"),
            "sources_stable": document.get("sources_stable"),
            "candidate_manifest_sha256": document.get("candidate_manifest_sha256"),
            "reported_new_executed_cases": document.get("executed_cases"),
            "reported_reused_cases": document.get("reused_cases"),
        }
        for position, item in enumerate(document.get("cases", [])):
            receipt_entries += 1
            reused_entries += bool(item.get("reused"))
            case = item["raw_case"]
            identity = json.dumps(
                [
                    item["context"],
                    document.get("candidate_manifest_sha256"),
                    document.get("source_sha256_before"),
                    case,
                ],
                sort_keys=True,
                separators=(",", ":"),
            )
            proof_key = hashlib.sha256(identity.encode()).hexdigest()
            alias = {
                "receipt_sha256": digest,
                "pointer": f"/cases/{position}",
                "reused": item.get("reused", False),
                "original_receipt": item.get("original_receipt"),
            }
            if proof_key in identities:
                identities[proof_key]["aliases"].append(alias)
                continue
            identities[proof_key] = {
                "proof_key": proof_key,
                "context": item["context"],
                "aliases": [alias],
            }
            total += 1
            status = case.get("status", "missing_status")
            raw_status_counts[status] = raw_status_counts.get(status, 0) + 1
            if status in (
                "native_passive_initialization",
                "native_zero_unavailable",
                "native_zero_amount_unavailable",
                "passive_initialization_only",
            ):
                source_witness_cases.append(
                    {
                        "proof_key": proof_key,
                        "context": item["context"],
                        "raw_status": status,
                        "qualifier_record": item.get(
                            "qualification", item.get("case_qualification")
                        ),
                        "effectful_execution_inferred": False,
                    }
                )
                continue
            if status == "validated":
                validated += 1
                continue
            pending += 1
            context = item["context"]
            diagnostics = case.get("cast_diagnostics") or [
                {"message": error} for error in case.get("errors", {})
            ]
            for diagnostic in diagnostics:
                signature = diagnostic_signature(diagnostic)
                encoded = json.dumps(signature, sort_keys=True)
                key = hashlib.sha256(encoded.encode()).hexdigest()
                group = groups.setdefault(
                    key,
                    {
                        "group_id": key,
                        "signature": signature,
                        "spell_ids": set(),
                        "references": set(),
                        "case_evidence": {},
                        "causal_fix_proven": False,
                        "single_fix_unlock_count": None,
                    },
                )
                group["spell_ids"].add(context["spell_id"])
                group["references"].add(context["reference"])
                pointer = f"/cases/{position}"
                group["case_evidence"][digest + pointer] = {
                    "receipt_sha256": digest,
                    "pointer": pointer,
                    "context": context,
                    "original_exception": diagnostic.get("message"),
                    "proof_key": proof_key,
                    "pointer_aliases": identities[proof_key]["aliases"],
                }
    ranked = []
    for group in groups.values():
        group["spell_ids"] = sorted(group["spell_ids"])
        group["references"] = sorted(group["references"])
        group["unique_spell_count"] = len(group["spell_ids"])
        group["case_evidence"] = list(group["case_evidence"].values())
        group["representative"] = group["case_evidence"][0]
        group["source_dependencies"] = {
            str(spell): index["spell_index"].get(str(spell), {})
            for spell in group["spell_ids"]
        }
        ranked.append(group)
    ranked.sort(
        key=lambda group: (
            group["signature"]["stage"] == "range_accepts",
            -group["unique_spell_count"],
            group["group_id"],
        )
    )
    return {
        "schema": "monster-effect-semantic-diagnostic-triage-v1",
        "receipt_snapshots": snapshots,
        "cases_observed": total,
        "receipt_case_entries": receipt_entries,
        "reused_receipt_entries": reused_entries,
        "duplicate_receipt_entries": receipt_entries - total,
        "unique_executed_proofs": sum(
            any(not alias["reused"] for alias in entry["aliases"])
            for entry in identities.values()
        ),
        "unique_cache_only_proofs": sum(
            all(alias["reused"] for alias in entry["aliases"])
            for entry in identities.values()
        ),
        "proof_aliases": list(identities.values()),
        "validated_cases": validated,
        "pending_cases": pending,
        "raw_status_counts": raw_status_counts,
        "source_witness_cases": source_witness_cases,
        "source_witness_case_count": len(source_witness_cases),
        "groups": ranked,
        "top10": [
            dict(group, source_dependencies=None, case_evidence=None)
            for group in ranked[:10]
        ],
        "same_diagnostic_not_proven_same_cause": True,
        "admission": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, action="append", required=True)
    parser.add_argument("--caller-index", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output must be new")
    index, digest = stable_read(args.index)
    result = group_failures(index, args.receipt, args.output.with_suffix(".inputs"))
    result["source_index_sha256"] = digest
    if args.caller_index:
        callers, caller_digest = stable_read(args.caller_index)
        by_ref = {row["ref"]: row for row in callers["rows"]}
        result["caller_ancestry_source"] = {
            "path": str(args.caller_index.resolve()),
            "sha256": caller_digest,
            "authority": callers["authority"],
            "source_sha256": callers.get("source_sha256"),
        }
        for group in result["groups"]:
            group["native_initial_and_owned_caller_ancestry"] = {
                str(ref): by_ref[ref] for ref in group["references"] if ref in by_ref
            }
            group["caller_ancestry_not_execution_proof"] = True
    args.output.write_text(json.dumps(result, separators=(",", ":")) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("cases_observed", "validated_cases", "pending_cases")
            }
        )
    )
    print(
        json.dumps(
            [
                (group["signature"], group["unique_spell_count"])
                for group in result["top10"]
            ]
        )
    )


if __name__ == "__main__":
    main()
