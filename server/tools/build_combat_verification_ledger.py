#!/usr/bin/env python3
"""Build an offline evidence ledger; catalog import is never gameplay proof.

Explicit contract evidence uses contract_checks entries with contract, authority
(semantic/client), evidence_id, passed, expected and actual. Historical review
flags, aggregate unit results and Ready success do not satisfy these checks.
"""
import gzip
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = (
    "range",
    "resources",
    "targets",
    "effects",
    "states",
    "turn_events",
    "summon_lifecycle",
    "delivery",
)
EXECUTED = {"actor_state_changed", "effect_executed", "executed"}
NO_EFFECT = {
    "no_effect",
    "no_effect_observed",
    "no_effect_requires_review",
    "accepted_no_effect",
    "cost_only",
    "skipped_condition",
}


def read_json(path):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf-8"))


def read_report(path):
    path = Path(path)
    if path.suffix == ".md":
        text = path.read_text(encoding="utf-8")
        return {
            "scope": "Aggregate unit report; no individual spell accreditation",
            "rows": [],
            "summary_text": text[:2000],
        }
    return read_json(path)


def source(path):
    path = Path(path)
    try:
        label = str(path.resolve().relative_to(ROOT))
    except ValueError:
        label = str(path.resolve())
    return {"path": label, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Evidence timestamps require a timezone")
    return parsed.astimezone(timezone.utc)


def report_sources(report):
    merged = {}
    for name in ("provenance", "sources_sha256", "source_before", "sources_before"):
        value = report.get(name, {})
        if isinstance(value, dict):
            merged.update(value)
    return merged


def resolve_report_source(key, root=ROOT):
    """Resolve a repo-owned source; never guess among colliding basenames."""
    root = Path(root).resolve()
    path = Path(key)
    if path.is_absolute() or len(path.parts) > 1:
        candidate = path if path.is_absolute() else root / path
        candidate = candidate.resolve()
        return (
            candidate
            if candidate.is_relative_to(root) and candidate.is_file()
            else None
        )
    candidates = {
        p.resolve()
        for directory in (
            "server/protocol",
            "server/wakfu_server/combat",
            "server/wakfu_server",
            "server/tools",
        )
        if (p := root / directory / key).is_file()
    }
    candidates = {p for p in candidates if p.is_relative_to(root)}
    return next(iter(candidates)) if len(candidates) == 1 else None


def current_report_hashes(reports, root=ROOT):
    hashes, resolved = {}, []
    keys = sorted({key for _, report in reports for key in report_sources(report)})
    for key in keys:
        path = resolve_report_source(key, root)
        if path is not None:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            hashes[key] = digest
            resolved.append(
                {
                    "report_key": key,
                    "path": str(path.relative_to(Path(root).resolve())),
                    "sha256": digest,
                }
            )
    return hashes, resolved


def report_freshness(report, hashes, reference_time, max_age_hours=None):
    """Require stable, compatible provenance; report age is informational by default."""
    reasons = []
    generated = report.get("generated_at")
    try:
        age = (timestamp(reference_time) - timestamp(generated)).total_seconds() / 3600
        if age < 0:
            reasons.append("future_report")
        elif max_age_hours is not None and age > max_age_hours:
            reasons.append("stale_report")
    except (TypeError, ValueError, AttributeError):
        age = None
        reasons.append("missing_or_invalid_timestamp")
    before = report.get("sources_before", report.get("source_before", {}))
    after = report.get("sources_after", report.get("source_after", {}))
    stable = report.get("sources_stable", report.get("source_stable"))
    if stable is False or (stable is not True and not (before and before == after)):
        reasons.append("source_stability_unverified")
    if before and after and before != after:
        reasons.append("sources_changed_during_report")
    provenance = report_sources(report)
    known = dict(hashes)
    basenames = {}
    for key, value in hashes.items():
        basenames.setdefault(Path(key).name, []).append(value)
    for key, values in basenames.items():
        if len(values) == 1:
            known.setdefault(key, values[0])
    matched, unknown, mismatches = [], [], []
    if not isinstance(provenance, dict) or not provenance:
        reasons.append("missing_source_hashes")
        provenance = {}
    for key, value in sorted(provenance.items()):
        if key not in known:
            unknown.append(key)
        elif value != known[key]:
            mismatches.append(key)
        else:
            matched.append(key)
    if mismatches:
        reasons.append("source_hash_mismatch")
    if unknown:
        reasons.append("source_hashes_outside_inventory")
    if not matched:
        reasons.append("no_matching_source_hash")
    return {
        "eligible": not reasons,
        "reasons": reasons,
        "age_hours": age,
        "matched_sources": matched,
        "unknown_sources": unknown,
        "mismatched_sources": mismatches,
    }


def applicability(spell, contract):
    families = set(spell.get("families", ()))
    if contract in {"range", "resources"} and spell.get("kind") == "passive":
        return "unknown"
    if contract in {"range", "resources", "targets", "effects", "delivery"}:
        return "required"
    if contract == "states" and (spell.get("states") or 304 in families):
        return "required"
    if contract == "summon_lifecycle" and 307 in families:
        return "required"
    if contract == "turn_events" and (
        spell.get("states")
        or families.intersection({304, 307, 315})
        or spell.get("kind") == "passive"
    ):
        return "required"
    # Absence from a partial catalog does not prove non-applicability.
    return "unknown"


def planned_cases(spell):
    legal = spell.get("unlock_level")
    levels = (
        sorted({200, legal}) if isinstance(legal, int) and 1 <= legal <= 200 else [200]
    )
    cases = []
    for breed in spell["breeds"]:
        for level in levels:
            if spell.get("kind") == "passive":
                for event in ("installation", "activation", "removal", "turn_boundary"):
                    cases.append(
                        {
                            "breed": breed,
                            "level": level,
                            "branch": "event",
                            "target": event,
                            "status": "pending",
                            "legal_scenario": "requires_validation",
                        }
                    )
                continue
            for branch in ("normal", "critical"):
                for target in ("self", "enemy", "empty_cell"):
                    cases.append(
                        {
                            "breed": breed,
                            "level": level,
                            "branch": branch,
                            "target": target,
                            "status": "pending",
                            "legal_scenario": "requires_validation",
                        }
                    )
    return cases


def evidence_outcome(row):
    status = str(row.get("status", row.get("verdict", "unknown"))).lower()
    if status in NO_EFFECT or "no_effect" in status or "cost_only" in status:
        return "no_effect"
    if "reject" in status or status in {
        "failed",
        "error",
        "lifecycle_failed",
        "blocked",
    }:
        return "rejected"
    if status == "cycle_observed":
        return "passive_cycle_observed"
    if status in EXECUTED:
        return "executed"
    if (
        status == "pass"
        and row.get("evidence_scope")
        == "actual client GUI, no simulation or packet injection"
    ):
        return "client_observed"
    return "unclassified"


def client_chain_present(row):
    expected = row.get("expected", {})
    requests = row.get("requests", ())
    server = row.get("server_finished", row.get("server", {})) or {}
    if (
        not row.get("received_client_update", row.get("delivery_seen", False))
        or len(requests) != 1
        or server.get("status") != "completed"
        or server.get("rejections")
    ):
        return False
    request = requests[0]
    return (
        expected.get("spell_id") == row.get("spell_id")
        and request.get("spell_id") == expected.get("spell_id")
        and request.get("actor_id") == expected.get("actor_id")
        and request.get("target") == expected.get("target")
        and request.get("opcode") == 13260
    )


def accredited_checks(row, fresh, outcome):
    if not fresh or outcome not in {"executed", "client_observed"}:
        return []
    result = []
    for check in row.get("contract_checks", ()):
        if not isinstance(check, dict):
            continue
        if (
            check.get("contract") in CONTRACTS
            and check.get("authority") in {"semantic", "client"}
            and check.get("evidence_id")
            and check.get("passed") is True
            and "expected" in check
            and "actual" in check
            and check["expected"] == check["actual"]
        ):
            if check["authority"] == "client" and (
                outcome != "client_observed" or not client_chain_present(row)
            ):
                continue
            result.append(check)
    return result


def shared_cause(row):
    reason = str(row.get("reason", row.get("error", "unknown_failure")))
    family = re.search(r"No handler for native effect class (\d+)", reason)
    if family:
        return "No handler for native effect class " + family.group(1)
    reason = re.sub(r"\b\d+\b", "<id>", reason)
    if "Unsupported native criterion" in reason:
        predicate = re.search(r"\b([A-Za-z_][A-Za-z_0-9]*)\(", reason)
        if predicate:
            return "Unsupported native criterion: " + predicate.group(1)
    if reason.startswith("Unsupported native predicate:"):
        return reason.splitlines()[0][:180]
    for prefix in ("Missing native", "Unsupported native", "No handler", "Native area"):
        if reason.startswith(prefix):
            return re.split(r"[:;\n]", reason, maxsplit=1)[0][:180]
    return re.sub(
        r"\b\d+\b", "<id>", reason.splitlines()[0] if reason else "unknown_failure"
    )[:180]


def build_ledger(
    inventory,
    reports=(),
    extras=None,
    *,
    reference_time,
    max_age_hours=None,
    known_hashes=None,
):
    hashes = dict(inventory.get("sources_sha256", {}))
    hashes.update(known_hashes or {})
    spells = {}
    for raw in inventory.get("spells", ()):
        sid = int(raw["id"])
        breeds = {int(raw["breed"])} if raw.get("breed") is not None else set()
        if sid in spells:
            spells[sid]["breeds"] = sorted(set(spells[sid]["breeds"]) | breeds)
            continue
        spells[sid] = dict(raw, breeds=sorted(breeds), origin="class_catalog")
    extra_rows = list(inventory.get("extra_spells", ()))
    extra_rows.extend((extras or {}).get("extras", ()))
    for raw in extra_rows:
        sid = int(raw["id"])
        breeds = set(map(int, raw.get("breeds", ())))
        breeds.update(
            int(link["breed"])
            for link in raw.get("links", raw.get("grant_paths", ()))
            if link.get("breed") is not None
        )
        if raw.get("breed") is not None:
            breeds.add(int(raw["breed"]))
        if sid in spells:
            spells[sid]["breeds"] = sorted(set(spells[sid]["breeds"]) | breeds)
            continue
        spells[sid] = dict(
            raw,
            breeds=sorted(breeds),
            origin="class_linked_extra",
            kind=raw.get("kind", "granted"),
        )
    metadata, observations = [], {}
    for label, report in sorted(reports, key=lambda pair: pair[0]):
        freshness = report_freshness(report, hashes, reference_time, max_age_hours)
        metadata.append(
            {
                "source": label,
                "freshness": freshness,
                "scope": report.get("scope", report.get("evidence_scope", "unknown")),
            }
        )
        rows = report.get("rows", report.get("cases", ()))
        if isinstance(rows, dict):
            rows = list(rows.values())
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            identity = row.get("spell_id", row.get("passive_id"))
            if identity is None:
                continue
            sid = int(identity)
            observations.setdefault(sid, []).append((label, index, row, freshness))
    output, causes = [], {}
    for sid, spell in sorted(spells.items()):
        contracts = {
            name: {
                "applicability": applicability(spell, name),
                "status": "pending",
                "evidence": [],
            }
            for name in CONTRACTS
        }
        scenarios, semantic, client, executions = [], set(), set(), 0
        passive = {
            "installed": False,
            "cycle_observed": False,
            "activation_observed": False,
            "start_activation_observed": False,
        }
        planned = planned_cases(spell)
        semantic_cases, client_cases = set(), set()
        for label, index, row, fresh in observations.get(sid, ()):
            outcome = evidence_outcome(row)
            branch = (
                "event"
                if spell.get("kind") == "passive"
                else ("critical" if row.get("critical") is True else "normal")
            )
            scenario = {
                "source": label,
                "row_index": index,
                "breed": row.get("breed"),
                "level": row.get("level"),
                "branch": branch,
                "target": row.get("variant", row.get("scenario", "unknown")),
                "outcome": outcome,
                "fresh": fresh["eligible"],
                "status": "pending",
                "reason": row.get("reason", row.get("error")),
            }
            if spell.get("kind") == "passive":
                scenario["passive_observations"] = {
                    "installed": row.get("installed") is True,
                    "cycle_observed": outcome == "passive_cycle_observed",
                    "activation_observed": row.get("activation_observed") is True,
                    "start_activation_observed": row.get("start_activation_observed")
                    is True,
                    "trace_complete": row.get("trace_complete") is True,
                }
                scenario["event_stages"] = [
                    {
                        "stage": stage.get("stage", "unknown"),
                        "status": stage.get("status", "unknown"),
                        "reason": stage.get("reason"),
                        "trace_complete": stage.get("trace_complete") is True,
                        "passive_activation_observed": stage.get(
                            "passive_activation_observed"
                        )
                        is True,
                        "activated_effects": [
                            {
                                "effect_reference": item.get("effect_reference"),
                                "effect_class": item.get("effect_class"),
                            }
                            for item in stage.get("activated_effects", ())
                        ],
                        "removed_retained_count": len(
                            stage.get("removed_retained_uids", ())
                        ),
                    }
                    for stage in row.get("stages", ())
                    if isinstance(stage, dict)
                ]
                if fresh["eligible"]:
                    for name in passive:
                        passive[name] |= scenario["passive_observations"][name]
            if (
                fresh["eligible"]
                and outcome == "executed"
                and spell.get("kind") != "passive"
            ):
                executions += 1
            checks = accredited_checks(row, fresh["eligible"], outcome)
            for check in checks:
                name = check["contract"]
                collection = semantic if check["authority"] == "semantic" else client
                collection.add(name)
                contracts[name]["evidence"].append(
                    {
                        "source": label,
                        "row_index": index,
                        "evidence_id": check["evidence_id"],
                        "authority": check["authority"],
                    }
                )
            identity = (row.get("breed"), row.get("level"), branch, scenario["target"])
            for authority, verified in (
                ("semantic", semantic_cases),
                ("client", client_cases),
            ):
                if {
                    c["contract"] for c in checks if c["authority"] == authority
                } == set(CONTRACTS):
                    verified.add(identity)
                    scenario[authority + "_verified"] = True
            if outcome in {"rejected", "no_effect"}:
                key = (
                    shared_cause(row)
                    if outcome == "rejected"
                    else "no_effect_requires_semantic_review"
                )
                group = causes.setdefault(
                    key,
                    {
                        "cause": key,
                        "affected_spell_ids": set(),
                        "breeds": set(),
                        "observations": 0,
                        "fresh_observations": 0,
                    },
                )
                group["affected_spell_ids"].add(sid)
                group["breeds"].update(spell["breeds"])
                group["observations"] += 1
                group["fresh_observations"] += int(fresh["eligible"])
            scenarios.append(scenario)
        for name in semantic | client:
            contracts[name]["status"] = "passed"
        imported = not spell.get("missing_definitions") and (
            spell["origin"] == "class_catalog" or spell.get("tree_exported") is True
        )
        identities = {
            (p["breed"], p["level"], p["branch"], p["target"]) for p in planned
        }
        semantic_complete = bool(identities) and identities <= semantic_cases
        client_complete = bool(identities) and identities <= client_cases
        for p in planned:
            key = (p["breed"], p["level"], p["branch"], p["target"])
            if key in client_cases:
                p["status"] = "client_verified"
            elif key in semantic_cases:
                p["status"] = "semantic_verified"
        output.append(
            {
                "spell_id": sid,
                "name": spell.get("name", ""),
                "breeds": spell["breeds"],
                "kind": spell.get("kind", "unknown"),
                "origin": spell["origin"],
                "catalog_imported": imported,
                "historical_review_claim": {
                    "game_verified": spell.get("game_verified", False),
                    "status": spell.get("review_status", "unknown"),
                    "accredited_by_this_ledger": False,
                },
                "offline_execution": executions > 0,
                "passive_observations": passive
                if spell.get("kind") == "passive"
                else None,
                "semantic_verified": semantic_complete,
                "client_verified": client_complete,
                "status": "passed" if client_complete else "pending",
                "contracts": contracts,
                "planned_cases": planned,
                "observed_cases": scenarios,
                "missing_scenarios": not scenarios,
            }
        )
    breeds = sorted({b for row in output for b in row["breeds"]})
    backlog = []
    for group in causes.values():
        group["affected_spell_ids"] = sorted(group["affected_spell_ids"])
        group["breeds"] = sorted(group["breeds"])
        group["affected_spell_count"] = len(group["affected_spell_ids"])
        backlog.append(group)
    backlog.sort(
        key=lambda g: (-g["affected_spell_count"], -len(g["breeds"]), g["cause"])
    )
    return {
        "schema": 1,
        "reference_time": reference_time,
        "max_age_hours": max_age_hours,
        "scope": "Offline evidence ledger; planned scenarios are not exhaustive dynamic gameplay coverage",
        "inventory_sources_sha256": inventory.get("sources_sha256", {}),
        "reports": metadata,
        "summary": {
            "spells": len(output),
            "class_spells": sum(r["origin"] == "class_catalog" for r in output),
            "extra_spells": sum(r["origin"] == "class_linked_extra" for r in output),
            "breeds": breeds,
            "breed_count": len(breeds),
            "offline_execution": sum(r["offline_execution"] for r in output),
            "passive_installed_observed": sum(
                bool(
                    r["passive_observations"] and r["passive_observations"]["installed"]
                )
                for r in output
            ),
            "passive_cycle_observed": sum(
                bool(
                    r["passive_observations"]
                    and r["passive_observations"]["cycle_observed"]
                )
                for r in output
            ),
            "passive_activation_observed": sum(
                bool(
                    r["passive_observations"]
                    and r["passive_observations"]["activation_observed"]
                )
                for r in output
            ),
            "semantic_verified": sum(r["semantic_verified"] for r in output),
            "client_verified": sum(r["client_verified"] for r in output),
        },
        "shared_system_backlog": backlog,
        "exhaustiveness": "unknown",
        "spells": output,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument(
        "--active-report",
        type=Path,
        action="append",
        default=[],
        help="Repeatable evidence reports, including Ready/unit metadata reports",
    )
    parser.add_argument("--extras-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--reference-time",
        default=datetime.now(timezone.utc).isoformat(),
        help="Set explicitly for byte-identical reproduction",
    )
    parser.add_argument(
        "--max-age-hours",
        type=float,
        help="Optional explicit age policy; default freshness uses source hashes",
    )
    args = parser.parse_args()
    if args.max_age_hours is not None and args.max_age_hours < 0:
        parser.error("--max-age-hours must be nonnegative")
    paths = [args.inventory] + args.active_report
    if args.extras_report:
        paths.append(args.extras_report)
    before = [source(p) for p in paths]
    reports = [(source(p)["path"], read_report(p)) for p in args.active_report]
    known_hashes, resolved_sources = current_report_hashes(reports)
    ledger = build_ledger(
        read_json(args.inventory),
        reports,
        read_json(args.extras_report) if args.extras_report else None,
        reference_time=args.reference_time,
        max_age_hours=args.max_age_hours,
        known_hashes=known_hashes,
    )
    after = [source(p) for p in paths]
    if before != after:
        raise RuntimeError("Ledger inputs changed during generation; no output written")
    if current_report_hashes(reports)[0] != known_hashes:
        raise RuntimeError(
            "Report source files changed during generation; no output written"
        )
    ledger["input_files"] = before
    ledger["input_files_stable"] = True
    ledger["current_report_sources"] = resolved_sources
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )
    with args.output.with_suffix(".csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "spell_id",
                "name",
                "breeds",
                "kind",
                "origin",
                "catalog_imported",
                "offline_execution",
                "semantic_verified",
                "client_verified",
                "status",
            )
            + CONTRACTS,
        )
        writer.writeheader()
        for row in ledger["spells"]:
            base = {k: row[k] for k in writer.fieldnames if k not in CONTRACTS}
            base["breeds"] = ";".join(map(str, row["breeds"]))
            base.update({name: row["contracts"][name]["status"] for name in CONTRACTS})
            writer.writerow(base)
    print(json.dumps(ledger["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
