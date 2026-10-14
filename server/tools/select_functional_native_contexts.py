"""Candidate-only whole-book native behavior: effectful execution or proven native rejection."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path


def proven_native_los_rejection(native):
    if not isinstance(native, dict):
        return False
    trace = native.get("trace")
    if not isinstance(trace, list) or not trace:
        return False

    def contains_error(value):
        if isinstance(value, dict):
            return any(
                isinstance(key, str)
                and any(
                    word in key.lower()
                    for word in ("error", "exception", "unsupported")
                )
                for key in value
            ) or any(contains_error(item) for item in value.values())
        if isinstance(value, list):
            return any(contains_error(item) for item in value)
        return False

    if contains_error(trace) or any(not isinstance(entry, dict) for entry in trace):
        return False
    if any(
        any(
            word in str(entry.get("stage", "")).lower()
            for word in ("error", "exception", "unsupported")
        )
        for entry in trace
    ):
        return False
    flags = native.get("selected_casting_flags")
    if not isinstance(flags, dict):
        return False
    los = [entry for entry in trace if entry.get("stage") == "native_los"]
    details = [entry for entry in trace if entry.get("stage") == "native_los_detail"]
    results = [entry for entry in trace if entry.get("stage") == "result"]
    return (
        flags.get("line_of_sight") is True
        and len(los) == len(details) == len(results) == 1
        and los[0].get("value") is False
        and isinstance(details[0].get("value"), dict)
        and details[0]["value"].get("result") is False
        and results[0].get("value") == "twG"
    )


def classify_guard(case):
    if case.get("status") == "validated":
        return {"mode": "original_validated", "effectful_claim_unchanged": True}
    if case.get("status") != "pending":
        return None
    errors = case.get("errors", {})
    allowed = {
        f"ValueError: Native spell casting eligibility rejected: {code}"
        for code in ("twI", "twE", "twV", "twG")
    }
    if not errors or not set(errors) <= allowed or not case.get("cast_diagnostics"):
        return None
    guards = []
    for diagnostic in case["cast_diagnostics"]:
        details = diagnostic.get("details", {})
        native = details.get("native_casting_diagnostic", {})
        code = details.get("native_casting_result")
        if code not in ("twI", "twE", "twV", "twG"):
            return None
        if code == "twG" and not proven_native_los_rejection(native):
            return None
        failures = [
            entry for entry in native.get("trace", []) if entry.get("value") is False
        ]
        if not failures:
            return None
        guards.append(
            {
                "native_result": code,
                "failed_stages": failures,
                "criterion": native.get("criterion"),
                "selected_casting_flags": native.get("selected_casting_flags"),
                "original_target": diagnostic.get("target"),
                "target_id": diagnostic.get("target_id"),
            }
        )
    return {
        "mode": "native_guarded_not_effectful",
        "effectful_claim_unchanged": False,
        "guards": guards,
        "dormancy_permanent_not_inferred": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, action="append", required=True)
    parser.add_argument("--exclude-ref", type=int, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("Output must be new")
    index = json.loads(args.index.read_text())
    native = {
        m["ref"]: m for m in json.load(gzip.open(args.inventory, "rt"))["monsters"]
    }
    contexts = {}
    sources = {}
    for path in args.receipt:
        raw = path.read_bytes()
        receipt = json.loads(raw)
        if raw != path.read_bytes():
            raise ValueError("Moving receipt must be snapshotted first")
        digest = hashlib.sha256(raw).hexdigest()
        sources[digest] = {
            "path": str(path.resolve()),
            "sha256": digest,
            "source_sha256_before": receipt.get("source_sha256_before"),
            "source_sha256_after": receipt.get("source_sha256_after"),
            "candidate_manifest_sha256": receipt.get("candidate_manifest_sha256"),
            "sources_stable": receipt.get("sources_stable"),
        }
        if receipt.get("sources_stable") is not True:
            continue
        for position, entry in enumerate(receipt.get("cases", [])):
            context = entry["context"]
            key = context["reference"], context["actor_level"]
            contexts.setdefault(key, {})[context["spell_id"]] = {
                "context": context,
                "raw_case": entry["raw_case"],
                "receipt_context": digest,
                "pointer": f"/cases/{position}",
            }
    missing = {row["spell_id"] for row in index["missing_source_nodes"]}
    candidates = []
    for (ref, level), cases in sorted(contexts.items()):
        if ref in args.exclude_ref or ref not in native:
            continue
        monster = native[ref]
        if not monster.get("actor_profile_present"):
            continue
        if ref in index.get("effective_minigame_references", []) or ref == 4559:
            continue
        book, rejected = [], False
        for ability in monster["abilities"]:
            spell = ability["spell_id"]
            metadata = index["spell_index"].get(str(spell))
            entry = cases.get(spell)
            if (
                not metadata
                or not entry
                or spell in missing
                or metadata["runtime_missing_families"]
            ):
                rejected = True
                break
            maximum = (metadata.get("casting") or {}).get("maximum_level")
            requested = (
                level
                if ability["level_parameter"] == -1
                else ability["level_parameter"]
            )
            if (
                type(maximum) is not int
                or not 1 <= maximum <= 32767
                or entry["context"]["spell_level"] != min(requested, maximum)
            ):
                rejected = True
                break
            result = classify_guard(entry["raw_case"])
            init = entry["raw_case"].get("initialization_receipts", [])
            if result is None or (
                monster["initial_states"]
                and not any(row.get("initialized") is True for row in init)
            ):
                rejected = True
                break
            book.append(dict(entry, behavior_classification=result))
        if not rejected and book:
            candidates.append(
                {
                    "reference": ref,
                    "actor_level": level,
                    "book": book,
                    "guarded_spell_ids": [
                        row["context"]["spell_id"]
                        for row in book
                        if row["behavior_classification"]["mode"]
                        == "native_guarded_not_effectful"
                    ],
                    "fullbook_effectful": False,
                    "functional_native_context_candidate": True,
                    "requires_actual_ai_damage_and_four_atomic_invariants": True,
                    "requires_ai_trace_no_unsupported_error": True,
                    "requires_parent_contract_review_before_publish": True,
                    "requires_reachable_effect_criteria_supported_review": True,
                    "source_compatibility_not_inferred": True,
                    "admission": False,
                }
            )
    result = {
        "schema": "functional-native-context-candidate-pool-v1",
        "candidates": candidates,
        "original_source_contexts": sources,
        "candidate_count": len(candidates),
        "strict_effectful_counts_unchanged": True,
        "admission": False,
        "visibility_not_overridden": True,
        "permanent_dormancy_not_inferred": True,
    }
    args.output.write_text(json.dumps(result, separators=(",", ":")) + "\n")
    print(
        json.dumps(
            {
                "candidate_count": len(candidates),
                "guarded_candidates": sum(
                    bool(c["guarded_spell_ids"]) for c in candidates
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
