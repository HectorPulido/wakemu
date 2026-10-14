"""Run selected spell/effect work in genuine owned native contexts, never whole books."""
import argparse
import ast
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def select_spells(index, blocks=(), spells=(), maximum=10):
    known = index["spell_index"]
    selected = set()
    for identity in blocks:
        rows = [row for row in index["blocks"] if row["block_id"] == identity]
        if len(rows) != 1:
            raise ValueError("Unknown or duplicate effect work block: " + identity)
        selected.update(rows[0]["spell_ids"])
    if spells:
        if blocks and not set(spells) <= selected:
            raise ValueError("Selected spell does not belong to selected block")
        selected = set(spells)
    if not blocks and not spells:
        selected = {
            int(spell)
            for spell, row in known.items()
            if not row.get("runtime_missing_families")
        }
    if any(str(spell) not in known for spell in selected):
        raise ValueError("Unknown selected native spell")
    if type(maximum) is not int or maximum <= 0:
        raise ValueError("Invalid spell budget")
    return sorted(selected)[:maximum]


def plan_contexts(row, abilities, minimum=None, maximum=None, limit=1):
    """Deduplicate exact native identities; never transfer proof between levels."""
    if limit <= 0 or (
        minimum is not None and maximum is not None and minimum > maximum
    ):
        raise ValueError("Invalid native context bounds")
    seen, result = set(), []
    for owner in row["resolved_native_level_contexts"]:
        for low, high in owner["native_actor_ranges"]:
            low = max(low, minimum) if minimum is not None else low
            high = min(high, maximum) if maximum is not None else high
            for level in range(low, high + 1):
                owned = [
                    a
                    for a in abilities(owner["ref"], level)
                    if a["spell_id"] == row["spell_id"]
                ]
                if len(owned) != 1:
                    raise ValueError("Native spell ownership missing or ambiguous")
                identity = (
                    owner["ref"],
                    level,
                    row["spell_id"],
                    owned[0]["spell_level"],
                )
                if identity in seen:
                    continue
                seen.add(identity)
                result.append(
                    dict(
                        reference=identity[0],
                        actor_level=identity[1],
                        spell_id=identity[2],
                        spell_level=identity[3],
                    )
                )
                if len(result) >= limit:
                    return result
    return result


def tool_dependency_paths(root, actual_ai=False):
    directory = root / "server/tools"
    available = {path.stem: path for path in directory.glob("*.py")}
    pending = ["validate_monster_spell_activation"]
    if actual_ai:
        pending.append("monster_actual_ai_acceptance")
    visited, result = set(), []
    while pending:
        name = pending.pop()
        if name in visited or name not in available:
            continue
        visited.add(name)
        path = available[name]
        result.append(path)
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module:
                pending.append(node.module.split(".")[0])
            elif isinstance(node, ast.Import):
                pending.extend(alias.name.split(".")[0] for alias in node.names)
    return result


def source_map(root, actual_ai=False):
    paths = list((root / "server/wakfu_server").rglob("*.py"))
    if not actual_ai:
        paths = [
            p
            for p in paths
            if p.name not in ("combat_tactical_ai.py", "combat_ai_capabilities.py")
        ]
    paths += [root / "server/protocol_codec.py"]
    paths += tool_dependency_paths(root, actual_ai)
    return {str(p.relative_to(root)): sha(p) for p in paths if p.exists()}


def pointer(document, path):
    for component in path.split("/")[1:]:
        key = component.replace("~1", "/").replace("~0", "~")
        document = document[int(key)] if isinstance(document, list) else document[key]
    return document


def reusable_case(index, context, sources, candidate_hash, loader):
    identity = (
        context["reference"],
        context["actor_level"],
        context["spell_id"],
        context["spell_level"],
    )
    for cached in index.get("actual_case_cache", []):
        if (
            cached["reference"],
            cached["actor_level"],
            cached["spell_id"],
            cached["spell_level"],
        ) != identity:
            continue
        receipt = index["receipt_contexts"][cached["context_ref"]]
        old = receipt.get("source_sha256")
        if not isinstance(old, dict) or not old:
            continue
        if receipt.get("candidate_manifest_sha256") != candidate_hash or any(
            old.get(k) != value for k, value in sources.items()
        ):
            continue
        document = loader(receipt["receipt"], receipt["sha256"])
        if document.get("sources_stable") is not True:
            continue
        row = pointer(document, cached["original_json_pointer"])
        case = row.get("raw_case", row)
        if (
            case.get("level"),
            case.get("spell_id"),
            case.get("spell_level"),
        ) != identity[1:]:
            raise ValueError("Original proof pointer identity differs")
        return deepcopy(case), dict(
            receipt=receipt["receipt"],
            sha256=receipt["sha256"],
            json_pointer=cached["original_json_pointer"],
            proof_key=cached["proof_key"],
        )
    return None


def resume_cases(document, sources, candidate_hash):
    if (
        document.get("schema") != "monster-effect-work-qualification-v1"
        or document.get("sources_stable") is not True
        or document.get("candidate_unchanged") is not True
        or document.get("candidate_manifest_sha256") != candidate_hash
        or document.get("source_sha256_before") != sources
        or document.get("source_sha256_after") != sources
    ):
        raise ValueError("Resume source or candidate identity differs")
    result = {}
    for position, row in enumerate(document["cases"]):
        context, case = row["context"], row["raw_case"]
        identity = tuple(
            context[k] for k in ("reference", "actor_level", "spell_id", "spell_level")
        )
        if (
            identity in result
            or tuple(case.get(k) for k in ("level", "spell_id", "spell_level"))
            != identity[1:]
        ):
            raise ValueError("Resume native identity differs or duplicates")
        result[identity] = (deepcopy(case), position)
    return result


def qualify(contexts, *, run_case, cache_case, persist, maximum_cases):
    """A pending spell never prevents independent selected spells from running."""
    result, executed = [], 0
    for context in contexts:
        cached = cache_case(context)
        if cached is None:
            if executed >= maximum_cases:
                break
            case = run_case(context)
            record = dict(context=context, raw_case=case, reused=False)
            executed += 1
        else:
            case, receipt = cached
            record = dict(
                context=context, raw_case=case, reused=True, original_receipt=receipt
            )
        result.append(record)
        persist(result, executed)
    return result, executed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--fallback", type=Path, action="append", default=[])
    parser.add_argument("--native-inventory", type=Path, required=True)
    parser.add_argument("--block", action="append", default=[])
    parser.add_argument("--spell", type=int, action="append", default=[])
    parser.add_argument("--minimum-level", type=int)
    parser.add_argument("--maximum-level", type=int)
    parser.add_argument("--max-spells", type=int, default=10)
    parser.add_argument("--max-cases", type=int, default=20)
    parser.add_argument("--contexts-per-spell", type=int, default=1)
    parser.add_argument("--initial-subscription-audit", type=Path)
    parser.add_argument("--trigger-index", type=Path)
    parser.add_argument("--actual-ai", action="store_true")
    parser.add_argument("--new-contexts-only", action="store_true")
    parser.add_argument("--resume-report", type=Path)
    parser.add_argument("--resume-sha256")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.max_cases <= 0:
        raise ValueError("Use a new output and a positive case budget")
    root, candidate = args.root.resolve(), args.candidate.resolve()
    sys.path[:0] = [
        str(root / p) for p in ("server", "server/tools", "server/ai-service")
    ]
    index = json.loads(args.index.read_text())
    selected = select_spells(index, args.block, args.spell, args.max_spells)
    before, manifest_hash = source_map(root, args.actual_ai), sha(
        candidate / "manifest.json"
    )
    started = time.monotonic()
    report = dict(
        schema="monster-effect-work-qualification-v1",
        source_root=str(root),
        index_sha256=sha(args.index),
        candidate_manifest_sha256=manifest_hash,
        selected_blocks=args.block,
        selected_spell_ids=selected,
        source_sha256_before=before,
        worker_sha256=sha(Path(__file__)),
        cases=[],
        actual_ai_enabled=args.actual_ai,
        status="running",
        admission=False,
        proof_scope="Selected actual native spell contexts only; no whole-book or exhaustive native-level claim",
        signature_deduplication="Exact native reference/actor-level/spell/spell-level identities; no level or source rebinding",
    )
    trigger_document = None
    if args.trigger_index:
        from monster_native_trigger_witness import validate_source_index

        trigger_document = validate_source_index(
            json.loads(args.trigger_index.read_text()), root, manifest_hash
        )
        report["trigger_index"] = dict(
            path=str(args.trigger_index.resolve()), sha256=sha(args.trigger_index)
        )
    resumed = {}
    if args.resume_report:
        if sha(args.resume_report) != args.resume_sha256:
            raise ValueError("Resume receipt hash differs")
        resumed = resume_cases(
            json.loads(args.resume_report.read_text()), before, manifest_hash
        )
        report["resume_parent"] = dict(
            path=str(args.resume_report.resolve()), sha256=args.resume_sha256
        )
    documents = {}
    last_progress = -1

    def load_receipt(path, expected):
        if sha(path) != expected:
            raise ValueError("Original proof receipt hash differs")
        if path not in documents:
            documents[path] = json.loads(Path(path).read_text())
        return documents[path]

    def persist(rows, executed):
        nonlocal last_progress
        report["cases"] = rows
        report["executed_cases"] = executed
        report["reused_cases"] = sum(row["reused"] for row in rows)
        report["visited_spells"] = len({row["context"]["spell_id"] for row in rows})
        report["spell_results"] = []
        for spell in sorted({row["context"]["spell_id"] for row in rows}):
            matching = [
                (position, row)
                for position, row in enumerate(rows)
                if row["context"]["spell_id"] == spell
            ]
            report["spell_results"].append(
                dict(
                    spell_id=spell,
                    effect_families=index["spell_index"][str(spell)].get(
                        "effect_families", []
                    ),
                    case_json_pointers=[
                        "/cases/" + str(position) for position, row in matching
                    ],
                    statuses=[
                        row["raw_case"].get(
                            "native_execution_domain_status", row["raw_case"]["status"]
                        )
                        for position, row in matching
                    ],
                    causal_diagnostics=[
                        dict(
                            context=row["context"],
                            observed_native_rejections=row["raw_case"].get(
                                "errors", {}
                            ),
                            exact_native_guard_cause_inferred=False,
                        )
                        for position, row in matching
                    ],
                    original_receipts=[
                        row["original_receipt"]
                        for position, row in matching
                        if row.get("original_receipt")
                    ],
                )
            )
        report["elapsed_seconds"] = time.monotonic() - started
        report["actual_native_contexts_per_hour"] = (
            executed * 3600 / max(report["elapsed_seconds"], 0.001)
        )
        report["spells_per_hour"] = (
            report["visited_spells"] * 3600 / max(report["elapsed_seconds"], 0.001)
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2))
        if rows and len(rows) % 20 == 0 and len(rows) != last_progress:
            print(
                json.dumps(
                    dict(
                        visited_spells=report["visited_spells"],
                        executed_cases=executed,
                        spells_per_hour=report["spells_per_hour"],
                    )
                ),
                flush=True,
            )
            last_progress = len(rows)

    from offline_monster_catalog import OfflineMonsterCatalog

    catalog = OfflineMonsterCatalog(candidate, args.fallback)
    try:
        with catalog.install():
            import gc
            import validate_monster_spell_activation as validator

            validator.install_overlay(candidate)
            if args.initial_subscription_audit:
                from initial_subscription_preparation import configure_source_audit

                configure_source_audit(
                    json.loads(args.initial_subscription_audit.read_text())
                )
                report["initial_subscription_audit_sha256"] = sha(
                    args.initial_subscription_audit
                )
            manifest = json.loads((candidate / "manifest.json").read_text())
            expected = manifest["native_source_provenance"]["bundle_documents"][
                "monsters.json.gz"
            ]
            if sha(args.native_inventory) != expected:
                raise ValueError("Native inventory source differs")
            with gzip.open(args.native_inventory, "rt") as stream:
                validator.NATIVE_SOURCE_MONSTERS = {
                    row["ref"]: row for row in json.load(stream)["monsters"]
                }
            from wakfu_server.monsters import native_abilities
            from wakfu_server.combat_geometry import published_geometry

            contexts = []
            report["context_planning_errors"] = []
            report["source_scope_unavailable_contexts"] = []
            report["historical_contexts_not_replayed"] = []
            cached_identities = {
                (c["reference"], c["actor_level"], c["spell_id"], c["spell_level"]): c
                for c in index.get("actual_case_cache", [])
            }
            selected_references = set(manifest["selected_references"])
            for spell in selected:
                try:
                    planned = plan_contexts(
                        index["spell_index"][str(spell)],
                        native_abilities,
                        args.minimum_level,
                        args.maximum_level,
                        args.contexts_per_spell,
                    )
                except ValueError as error:
                    report["context_planning_errors"].append(
                        dict(spell_id=spell, error=str(error))
                    )
                    continue
                for context in planned:
                    identity = (
                        context["reference"],
                        context["actor_level"],
                        context["spell_id"],
                        context["spell_level"],
                    )
                    previous = cached_identities.get(identity)
                    if args.new_contexts_only and previous is not None:
                        report["historical_contexts_not_replayed"].append(
                            dict(
                                context=context,
                                original_proof=previous,
                                status="historical_context_not_rebound_or_replayed",
                            )
                        )
                        continue
                    if (
                        previous is not None
                        and previous.get("status") == "validated"
                        and reusable_case(
                            index, context, before, manifest_hash, load_receipt
                        )
                        is None
                    ):
                        report["historical_contexts_not_replayed"].append(
                            dict(
                                context=context,
                                original_proof=previous,
                                status="historical_context_needs_source_requalification_not_replayed",
                            )
                        )
                        continue
                    if context["reference"] not in selected_references:
                        report["source_scope_unavailable_contexts"].append(context)
                    else:
                        contexts.append(context)
            report["planned_context_count"] = len(contexts)
            cells = published_geometry(1134).cells
            fixture_cache = validator.ReferenceFixtureCache()
            gc.collect()
            gc.freeze()

            def run(context):
                case = validator.run_case(
                    context["reference"],
                    context["actor_level"],
                    context["spell_id"],
                    context["spell_level"],
                    cells,
                    12,
                    propagate_infrastructure=True,
                    fixture_cache=fixture_cache,
                    recovery_search=True,
                    recovery_attempt_cap=6,
                    recovery_scene_cap=4,
                )
                if trigger_document is not None:
                    from monster_native_trigger_witness import annotate_pending

                    case = annotate_pending(
                        case, context, trigger_document, report["trigger_index"]
                    )
                if args.actual_ai and validator.case_qualification_complete(case):
                    from monster_actual_ai_acceptance import prove_scene

                    targets = [
                        t
                        for t in case.get("successful_targets", [])
                        if t.get("effectful")
                        and t.get("target_id") == 7
                        and "damage" in t.get("event_kinds", [])
                    ]
                    case["optional_actual_ai"] = (
                        prove_scene(
                            context["reference"],
                            context["actor_level"],
                            targets[0]["enemy_cell"],
                            targets[0].get("scenario"),
                            validator,
                        )
                        if targets
                        else dict(
                            status="not_attempted",
                            reason="No actual damage witness for selected spell",
                        )
                    )
                fixture_cache.clear()
                return case

            def cached(context):
                identity = tuple(
                    context[k]
                    for k in ("reference", "actor_level", "spell_id", "spell_level")
                )
                if identity in resumed:
                    case, position = resumed[identity]
                    return deepcopy(case), dict(
                        receipt=str(args.resume_report.resolve()),
                        sha256=args.resume_sha256,
                        json_pointer="/cases/" + str(position),
                        same_source_and_native_identity=True,
                    )
                return reusable_case(
                    index, context, before, manifest_hash, load_receipt
                )

            qualify(
                contexts,
                run_case=run,
                cache_case=cached,
                persist=persist,
                maximum_cases=args.max_cases,
            )
            report["budget_exhausted"] = report.get(
                "executed_cases", 0
            ) >= args.max_cases and len(report["cases"]) < len(contexts)
            report["status"] = (
                "completed_budgeted_batch"
                if report["budget_exhausted"]
                else "completed_selected_contexts"
            )
    except Exception as error:
        report["status"] = "infrastructure_or_source_error"
        report["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        report["catalog"] = catalog.receipt()
        report["source_sha256_after"] = source_map(root, args.actual_ai)
        report["sources_stable"] = before == report["source_sha256_after"]
        report["candidate_unchanged"] = (
            sha(candidate / "manifest.json") == manifest_hash
        )
        persist(report["cases"], report.get("executed_cases", 0))


if __name__ == "__main__":
    main()
