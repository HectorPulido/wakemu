"""Reconcile offline evidence into a new ledger, without publishing or DB access.

A completed runner is not qualification. Screening passes never substitute for
finalizer admission or the deferred class regression gate.
"""
import argparse
from collections import Counter
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def context_reasons(report, wrapper, manifest, manifest_hash, current_sources):
    reasons = []
    if (
        report.get("schema") != "native-npc-activation-validation-v1"
        or report.get("candidate_manifest_sha256") != manifest_hash
        or report.get("base_revision") != manifest["base_revision"]
        or report.get("changed_document_hashes") != manifest["changed_documents"]
        or report.get("base_document_hashes") != manifest["base_document_hashes"]
        or report.get("overlay_applied") != "npc_candidate"
    ):
        reasons.append("candidate_context_mismatch")
    if (
        not current_sources
        or report.get("runtime_code_sha256") != current_sources
        or report.get("sources_stable") is not True
        or report.get("preview_sources_match_current") is not True
        or report.get("native_monsters_stable") is not True
        or not report.get("native_monsters_sha256")
    ):
        reasons.append("missing_or_stale_runtime_source_proof")
    catalog = wrapper.get("catalog", {})
    if (
        wrapper.get("status") != "validator_completed"
        or catalog.get("schema") != "offline-monster-catalog-consumption-v1"
        or catalog.get("manifest_sha256") != manifest_hash
        or catalog.get("base_revision") != manifest["base_revision"]
        or catalog.get("authority")
        != "declared_offline_candidate_base_not_active_database"
        or catalog.get("failed_reads")
        or not catalog.get("verified_documents")
    ):
        reasons.append("missing_or_failed_offline_catalog_context")
    expected = dict(manifest["unchanged_documents"], **manifest["base_document_hashes"])
    if any(
        expected.get(name) != row.get("sha256")
        for name, row in catalog.get("verified_documents", {}).items()
    ):
        reasons.append("offline_catalog_seal_mismatch")
    return reasons


def classify_row(row, authority, initialization_proven, passive_proven):
    expected = {
        (level, spell)
        for level in range(authority["min_level"], authority["max_level"] + 1)
        for spell in authority["spell_ids"]
    }
    cases = row.get("cases", [])
    observed = [(case.get("level"), case.get("spell_id")) for case in cases]
    failures = [
        case
        for case in cases
        if case.get("status") not in ("validated", "passive_initialization_only")
        and (
            case.get("errors")
            or case.get("attempts", 0) > 0
            or case.get("status") in ("failed", "blocked")
        )
    ]
    if failures:
        return "blocked_local_execution", [
            dict(
                level=case.get("level"),
                spell_id=case.get("spell_id"),
                status=case.get("status"),
                errors=case.get("errors", {}),
            )
            for case in failures
        ]
    reasons = []
    if len(observed) != len(expected) or set(observed) != expected:
        reasons.append("incomplete_full_native_owned_spell_cases")
    if any(
        case.get("status") not in ("validated", "passive_initialization_only")
        for case in cases
    ):
        reasons.append("missing_case_execution_receipt")
    ordinary = [case for case in cases if case.get("status") == "validated"]
    effectful = lambda case: any(
        target.get("effectful") is True for target in case.get("successful_targets", [])
    )
    if not ordinary or not all(effectful(case) for case in ordinary):
        reasons.append("missing_effectful_ordinary_execution")
    if any(
        not passive_proven(case)
        for case in cases
        if case.get("status") == "passive_initialization_only"
    ):
        reasons.append("passive_source_proof_missing")
    commit = row.get("ai_commit", {})
    if (
        commit.get("status") != "validated"
        or commit.get("packets", 0) <= 0
        or commit.get("forecast_source_unchanged") is not True
        or commit.get("serializer_failure_rolled_back") is not True
    ):
        reasons.append("missing_ai_commit_delivery_proof")
    triples = authority.get("initial_state_triples", [])
    if triples:
        init = lambda level, receipt: initialization_proven(
            row["ref"], level, triples, receipt
        )
        if not init(commit.get("level"), commit.get("native_initialization")) or any(
            not any(
                target.get("effectful") is True
                and init(case["level"], target.get("native_initialization"))
                for target in case.get("successful_targets", [])
            )
            for case in ordinary
        ):
            reasons.append("missing_native_constructor_proof")
    if row.get("pending_initialization") or row.get("status") != "validated":
        reasons.append("validator_row_pending")
    return (
        ("pending_local_validation", reasons)
        if reasons
        else ("screening_pass_pending_final_gates", [])
    )


def reconcile(
    scope,
    ledger,
    manifest,
    manifest_hash,
    policy,
    evidence,
    current_sources,
    initialization_proven,
    passive_proven=lambda reference, case: False,
):
    scope_by_ref = {row["ref"]: row for row in scope["monsters"]}
    ledger_by_ref = {row["ref"]: row for row in ledger["monsters"]}
    if (
        len(scope_by_ref) != 1817
        or len(ledger_by_ref) != 1817
        or set(scope_by_ref) != set(ledger_by_ref)
    ):
        raise ValueError("Reconciliation requires exact unique frozen 1817 scope")
    selected = set(manifest["selected_references"])
    exceptions = {3174, 3976, 3980, 3981, 3982, 3983, 3984}
    expected_selected = {
        ref
        for ref, row in scope_by_ref.items()
        if row["min_level"] > 0 and ref not in exceptions
    }
    if selected != expected_selected:
        raise ValueError(
            "Candidate differs from exact positive nonexception frozen scope"
        )
    if (
        len(selected) != 1768
        or set(map(int, policy)) != selected
        or not selected.issubset(scope_by_ref)
    ):
        raise ValueError("Candidate must cover exact 1768 positive nonexception scope")
    evidence_by_ref = {}
    for report, wrapper, receipt in evidence:
        context = context_reasons(
            report, wrapper, manifest, manifest_hash, current_sources
        )
        refs = [row["ref"] for row in report.get("monsters", [])]
        if len(refs) != len(set(refs)) or not set(refs).issubset(selected):
            raise ValueError("Duplicate or outside-scope validation reference")
        for row in report.get("monsters", []):
            if row["ref"] in evidence_by_ref:
                raise ValueError(
                    "Conflicting duplicate report reference; select one explicit receipt"
                )
            evidence_by_ref[row["ref"]] = row, context, receipt
    result = deepcopy(ledger)
    for row in result["monsters"]:
        ref = row["ref"]
        row["qualification_verified"] = False
        row["local_enabled"] = False
        if ref not in selected:
            continue  # Preserve all 49 exclusions and their original reasons.
        authority = policy[str(ref)]
        if any(
            authority[key] != scope_by_ref[ref][key]
            for key in ("min_level", "max_level", "spell_ids")
        ):
            raise ValueError("Policy descriptor differs from frozen scope")
        row.update(
            status="pending_local_validation", blocker="missing_validation_receipt"
        )
        if ref not in evidence_by_ref:
            continue
        actual, context, receipt = evidence_by_ref[ref]
        status, reasons = (
            ("pending_local_validation", context)
            if context
            else classify_row(
                actual,
                authority,
                initialization_proven,
                lambda case: passive_proven(ref, case),
            )
        )
        row.update(
            status=status,
            blocker=reasons or None,
            validation_receipt=receipt,
            final_class_gate="deferred",
            finalizer_admission="pending",
        )
    result.update(
        schema="monster-offline-activation-ledger-v1",
        deployed=False,
        active_catalog_modified=False,
        summary=dict(Counter(row["status"] for row in result["monsters"])),
        candidate_manifest_sha256=manifest_hash,
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("scope", "ledger", "candidate", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--report", type=Path, action="append", default=[])
    parser.add_argument("--catalog-root", type=Path, action="append", default=[])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    if (root / ".runtime").resolve() not in args.output.resolve().parents:
        parser.error("Reconciled ledgers must stay beneath .runtime")
    load = lambda path: json.loads(path.read_text())
    manifest_path = args.candidate / "manifest.json"
    manifest = load(manifest_path)
    for name, checksum in manifest["changed_documents"].items():
        if digest(args.candidate / name) != checksum:
            raise ValueError("Candidate document changed: " + name)
    npc = load(args.candidate / "native-npc-spell-effect-trees.json")
    evidence = []
    current_sources = None
    for path in sorted(args.report):
        report = load(path)
        wrapper_path = path.with_name(path.stem + "-catalog-receipt.json")
        wrapper = load(wrapper_path) if wrapper_path.exists() else {}
        # Actual source reads are checked; declared receipt hashes alone cannot qualify.
        for record in wrapper.get("catalog", {}).get("verified_documents", {}).values():
            source = Path(record["source"])
            raw = (
                gzip.decompress(source.read_bytes())
                if record.get("gzip")
                else source.read_bytes()
            )
            if hashlib.sha256(raw).hexdigest() != record["sha256"]:
                raise ValueError(
                    "Offline consumed catalog source changed: " + str(source)
                )
        native_path = report.get("native_monsters_path")
        if native_path and digest(Path(native_path)) != report.get(
            "native_monsters_sha256"
        ):
            raise ValueError("Native monster authority changed")
        actual = {
            name: digest(root / name) for name in report.get("runtime_code_sha256", {})
        }
        if current_sources is not None and current_sources != actual:
            raise ValueError("Reports attest different runtime source contexts")
        current_sources = actual
        evidence.append(
            (
                report,
                wrapper,
                dict(
                    report=str(path),
                    report_sha256=digest(path),
                    catalog_receipt=str(wrapper_path),
                    catalog_receipt_sha256=digest(wrapper_path)
                    if wrapper_path.exists()
                    else None,
                ),
            )
        )
    from offline_monster_catalog import OfflineMonsterCatalog
    from validate_monster_spell_activation import install_overlay, initialization_proven
    from finalize_monster_spell_activation import (
        load_passive_source_authorities,
        final_passive_case_proven,
    )

    snapshot = OfflineMonsterCatalog(args.candidate, args.catalog_root)
    with snapshot.install():
        install_overlay(args.candidate)

        def passive(reference, case):
            for report, _, _ in evidence:
                try:
                    sources = load_passive_source_authorities(manifest, report)
                    return final_passive_case_proven(
                        case,
                        reference,
                        npc["activation_policy"]["enabled_monsters"],
                        npc,
                        sources,
                    )
                except (KeyError, OSError, ValueError, TypeError):
                    continue
            return False

        result = reconcile(
            load(args.scope),
            load(args.ledger),
            manifest,
            digest(manifest_path),
            npc["activation_policy"]["enabled_monsters"],
            evidence,
            current_sources or {},
            initialization_proven,
            passive,
        )
    result["reconciliation_inputs"] = {
        str(path): digest(path)
        for path in (args.scope, args.ledger, manifest_path, Path(__file__))
    }
    result["reconciler_catalog_receipt"] = snapshot.receipt()
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(result["summary"]))


if __name__ == "__main__":
    main()
