"""Persist source-bound outcome events and report unique delivery throughput."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def receipt_event(path, kind, ids, timestamp=None):
    path = Path(path).resolve()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    document = json.loads(path.read_text())
    explicit = (
        timestamp or document.get("completed_at_utc") or document.get("timestamp_utc")
    )
    moment = (
        utc(explicit)
        if explicit
        else datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    )
    return dict(
        event_id=kind + ":" + digest,
        kind=kind,
        receipt=str(path),
        receipt_sha256=digest,
        observed_at_utc=moment.isoformat(),
        timestamp_source="explicit_receipt_utc" if explicit else "receipt_mtime_utc",
        ids=sorted(set(ids)),
    )


def append_events(existing, incoming):
    result = list(existing)
    known = {row["event_id"] for row in result}
    for row in incoming:
        if row["event_id"] not in known:
            result.append(row)
            known.add(row["event_id"])
    return result


def metrics(events, baseline_utc):
    start = utc(baseline_utc)
    output = dict(
        baseline_utc=start.isoformat(),
        repeated_event_ids_not_counted=True,
        level_tails_not_new_references=True,
        qualification_baseline_not_runtime_fix_throughput=True,
    )
    for kind, unit, scale in [
        ("resolved_spell", "unique_new_resolved_spells_per_minute", 60),
        ("healthy_published_ref", "healthy_new_published_refs_per_hour", 3600),
    ]:
        selected = [
            e
            for e in events
            if e["kind"] == kind and utc(e["observed_at_utc"]) >= start
        ]
        ids = sorted({identity for e in selected for identity in e["ids"]})
        end = max([utc(e["observed_at_utc"]) for e in selected], default=start)
        elapsed = (end - start).total_seconds()
        output[kind] = dict(
            unique_new_count=len(ids),
            ids=ids,
            observation_end_utc=end.isoformat(),
            elapsed_seconds=elapsed,
            **{unit: len(ids) * scale / elapsed if elapsed > 0 else None}
        )
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-utc", required=True)
    parser.add_argument("--baseline-count", type=int, required=True)
    parser.add_argument("--baseline-receipt", type=Path, required=True)
    parser.add_argument("--spell-inventory", type=Path, required=True)
    parser.add_argument("--deployment", type=Path, required=True)
    parser.add_argument("--activation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output / "ledger.json"
    existing = (
        json.loads(ledger_path.read_text())["events"] if ledger_path.exists() else []
    )
    inventory = json.loads(args.spell_inventory.read_text())
    incoming = [
        receipt_event(args.baseline_receipt, "baseline", [], args.baseline_utc),
        receipt_event(
            args.spell_inventory,
            "resolved_spell",
            inventory["new_effectful_unique_spell_ids_any_mode"],
        ),
    ]
    deployment = json.loads(args.deployment.read_text())
    activation = json.loads(args.activation.read_text())
    healthy = (
        deployment.get("status") == "healthy"
        and deployment["revision"] == activation["revision"]
        and all(
            s.get("health") == "healthy"
            and s.get("catalog_revision") == deployment["revision"]
            for s in deployment.get("services", {}).values()
        )
        and bool(deployment.get("services"))
    )
    if healthy:
        new_refs = activation["new_policy_references"]
        assert len(set(new_refs)) == deployment["new_enabled"]
        assert deployment["baseline_enabled"] == args.baseline_count
        assert not set(new_refs) & set(activation.get("extended_policy_references", []))
        event = receipt_event(args.deployment, "healthy_published_ref", new_refs)
        event["activation_receipt"] = str(args.activation.resolve())
        event["activation_receipt_sha256"] = hashlib.sha256(
            args.activation.read_bytes()
        ).hexdigest()
        incoming.append(event)
        incoming.append(receipt_event(args.activation, "activation_source", []))
    events = append_events(existing, incoming)
    ledger_path.write_text(
        json.dumps(
            dict(schema="monster-outcome-throughput-ledger-v1", events=events), indent=2
        )
        + "\n"
    )
    result = metrics(events, args.baseline_utc)
    result["resolved_spell"]["unique_new_resolved_spells_per_minute"] = None
    result["resolved_spell"][
        "rate_unavailable_reason"
    ] = "Consolidation receipt mtime is not the per-proof outcome timestamp; normalized native proof UTC events are not yet available"
    result["resolved_spell"]["observation_end_utc_is_inventory_snapshot_only"] = True
    result.update(
        baseline_published_refs=args.baseline_count,
        deployment_healthy_counted=healthy,
        published_refs=args.baseline_count
        + result["healthy_published_ref"]["unique_new_count"],
        spell_scope="Unique newly effectful spell IDs in any proven mode versus frozen 921; not all-level or runtime-fix-only proof",
        baseline_massive_qualification=921,
    )
    (args.output / "metrics.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
