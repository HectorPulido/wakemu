"""Filter an inactive NPC candidate to complete native execution passes."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(candidate, validation, output):
    manifest = json.loads((candidate / "manifest.json").read_text())
    audit = json.loads(validation.read_text())
    for name, checksum in manifest["changed_documents"].items():
        if digest(candidate / name) != checksum:
            raise ValueError("Candidate document changed after validation: " + name)
    if (
        audit.get("schema") != "native-npc-activation-validation-v1"
        or audit.get("candidate_manifest_sha256") != digest(candidate / "manifest.json")
        or audit.get("changed_document_hashes") != manifest["changed_documents"]
        or audit.get("base_revision") != manifest["base_revision"]
        or audit.get("overlay_applied") != "npc_candidate"
    ):
        raise ValueError("Execution validation does not attest this NPC candidate")
    tests = audit.get("class_tests")
    if (
        not tests
        or not tests.get("successful")
        or tests.get("failures")
        or tests.get("errors")
        or tests.get("skipped")
        or tests.get("run", 0) <= 0
    ):
        raise ValueError("Complete passing class regressions are required")
    if audit.get("sources_stable") is not True:
        raise ValueError("Execution validation requires stable tested runtime sources")
    if audit.get("preview_sources_match_current") is not True:
        raise ValueError(
            "NPC previews must attest the currently tested runtime sources"
        )
    root = Path(__file__).resolve().parents[2]
    for name, expected_hash in audit["runtime_code_sha256"].items():
        if digest(root / name) != expected_hash:
            raise ValueError("Tested runtime source changed: " + name)
    rows = audit["monsters"]
    by_ref = {row["ref"]: row for row in rows}
    if len(by_ref) != len(rows) or set(by_ref) != set(manifest["selected_references"]):
        raise ValueError("Execution validation does not cover the full selected cohort")
    inventory = json.loads((candidate / "monster-status.json").read_text())
    npc_name = "native-npc-spell-effect-trees.json"
    npc = json.loads((candidate / npc_name).read_text())
    base_hashes = audit.get("base_document_hashes", {})
    if (
        npc_name not in base_hashes
        or digest(candidate / ("base-" + npc_name)) != base_hashes[npc_name]
    ):
        raise ValueError(
            "Previous NPC policy differs from the validated native baseline"
        )
    if manifest.get("base_document_hashes", base_hashes) != base_hashes:
        raise ValueError("Native baseline document hashes differ from preparation")
    baseline = json.loads((candidate / ("base-" + npc_name)).read_text())
    if npc.get("baseline_effects") != baseline.get(
        "baseline_effects", baseline["effects"]
    ):
        raise ValueError(
            "Preserved NPC baseline effects differ from the native baseline"
        )
    previous = baseline.get("activation_policy", {})
    previous_enabled = previous.get("enabled_monsters", {})
    enabled = dict(previous_enabled)
    selected = set(manifest["selected_references"])
    inventory_refs = [monster["ref"] for monster in inventory["monsters"]]
    if len(set(inventory_refs)) != len(inventory_refs) or not selected.issubset(
        inventory_refs
    ):
        raise ValueError("Inventory must contain each selected reference exactly once")
    policy = npc["activation_policy"]["enabled_monsters"]
    for monster in inventory["monsters"]:
        if monster["ref"] not in selected:
            continue
        authority = policy.get(str(monster["ref"]))
        if authority is None or any(
            monster[key] != authority[key]
            for key in ("min_level", "max_level", "spell_ids")
        ):
            raise ValueError(
                "Inventory differs from the hashed native activation policy"
            )
    passed = set()
    for monster in inventory["monsters"]:
        ref = monster["ref"]
        if ref not in selected:
            continue
        row = by_ref[ref]
        commit = row.get("ai_commit", {})
        expected = {
            (level, spell)
            for level in range(monster["min_level"], monster["max_level"] + 1)
            for spell in monster["spell_ids"]
        }
        observed = {(case["level"], case["spell_id"]) for case in row["cases"]}
        from validate_monster_spell_activation import initialization_proven

        raw_triples = policy[str(ref)].get("initial_state_triples", [])
        constructor_valid = not raw_triples or (
            initialization_proven(
                ref,
                commit.get("level"),
                raw_triples,
                commit.get("native_initialization"),
            )
            and all(
                any(
                    target.get("effectful")
                    and initialization_proven(
                        ref,
                        case["level"],
                        raw_triples,
                        target.get("native_initialization"),
                    )
                    for target in case.get("successful_targets", [])
                )
                for case in row["cases"]
            )
        )
        valid = (
            constructor_valid
            and row["status"] == "validated"
            and not row.get("pending_initialization")
            and commit.get("status") == "validated"
            and commit.get("packets", 0) > 0
            and commit.get("forecast_source_unchanged") is True
            and commit.get("serializer_failure_rolled_back") is True
            and len(row["cases"]) == len(expected)
            and observed == expected
            and all(
                case["status"] == "validated"
                and any(
                    target.get("effectful")
                    for target in case.get("successful_targets", [])
                )
                for case in row["cases"]
            )
        )
        if valid:
            passed.add(ref)
            enabled[str(ref)] = npc["activation_policy"]["enabled_monsters"][str(ref)]
        monster["activation_status"] = (
            "validated_pending_deployment"
            if valid
            else "pending_execution_or_initialization"
        )
        monster["execution_validation"] = row
    if not passed:
        raise ValueError("No completely validated NPC references")
    output.mkdir(parents=True, exist_ok=False)
    for name in manifest["changed_documents"]:
        shutil.copyfile(candidate / name, output / name)
    npc["activation_policy"]["enabled_monsters"] = enabled
    (output / npc_name).write_text(
        json.dumps(npc, ensure_ascii=False, separators=(",", ":")) + "\n"
    )
    manifest.update(
        execution_validated=True,
        class_regressions_passed=True,
        selected_references=sorted(passed),
        evaluated_references=sorted(selected),
        execution_validation_sha256=digest(validation),
        tested_runtime_code_sha256=audit["runtime_code_sha256"],
        activated=False,
    )
    manifest["changed_documents"] = {
        name: digest(output / name) for name in manifest["changed_documents"]
    }
    inventory.update(
        activated=False,
        summary=dict(
            Counter(row["activation_status"] for row in inventory["monsters"])
        ),
        validation_sha256=digest(validation),
    )
    for name, document in (
        ("manifest.json", manifest),
        ("monster-status.json", inventory),
    ):
        (output / name).write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n"
        )
    shutil.copyfile(validation, output / "execution-validation.json")
    return dict(
        validated=len(passed),
        pending=len(selected - passed),
        total=len(inventory["monsters"]),
        activated=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("validation", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2] / ".runtime"
    if root not in args.output.resolve().parents:
        parser.error("Final candidates must remain under .runtime")
    print(json.dumps(finalize(args.candidate, args.validation, args.output)))


if __name__ == "__main__":
    main()
