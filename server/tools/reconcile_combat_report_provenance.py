"""Reconcile recorded report source identities with captured manifests, stdlib only."""
import hashlib
import json
from pathlib import Path

BASE = Path(".runtime/combat-review-20261008")
PAIRS = [
    ("normal635", "class-normal-casts-all18-01.json", "luna-normal-casts-smoke-01"),
    (
        "passive339",
        "class-passive-mechanics-optimized-full-01.json",
        "luna-passive-fast-01",
    ),
    ("semantic42", "class-passive-semantic-next-01.json", "luna-semantic-next-01"),
    ("Enutrof17", "enutrof-passive-replay-02.json", "luna-enutrof-passive-replay-02"),
    ("M2", "cra-precision-manual-05.json", "luna-cra-precision-05"),
    ("M3", "cra-beacon-manual-03.json", None),
    ("M7", "feca-glyph-manual-03.json", "luna-m7-m10-01"),
    ("M10", "sram-trap-manual-02.json", "luna-m7-m10-01"),
    ("resource923", "class-resource923-8405-02.json", "luna-resource923-01"),
    (
        "copy_rawfix",
        "class-character-copy-8559-rawfix-01.json",
        "luna-copy-8559-rawfix-01",
    ),
    ("Recall13", "summon-recall-retired-slot-13.json", "luna-recall-retired-slot-13"),
    (
        "Microbot02",
        "microbot-rail-lifecycle-02.json",
        "luna-microbot-rail-lifecycle-02",
    ),
    (
        "Sram_double_death01",
        "sram-double-lifecycle-01.json",
        "luna-sram-double-lifecycle-01",
    ),
    (
        "copy_book_final",
        "class-character-copy-lifecycle-8559-final-03.json",
        "luna-copy8559-lifecycle-final-03",
    ),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


BASENAME_INDEX = {}


def resolve(key, files):
    if key in files:
        return key
    if "/" in key:
        matches = [p for p in files if p.endswith("/" + key)]
        return matches[0] if len(matches) == 1 else None
    if id(files) not in BASENAME_INDEX:
        index = {}
        for p in files:
            index.setdefault(Path(p).name, []).append(p)
        BASENAME_INDEX[id(files)] = index
    matches = BASENAME_INDEX[id(files)].get(key, [])
    return matches[0] if len(matches) == 1 else None


def compare(values, files):
    result = {"matched": [], "missing": [], "different": []}
    for key, value in values.items():
        path = resolve(key, files)
        if path is None:
            result["missing"].append({"report_key": key, "sha256": value})
        elif files[path] != value:
            result["different"].append(
                {
                    "report_key": key,
                    "path": path,
                    "report_sha256": value,
                    "manifest_sha256": files[path],
                }
            )
        else:
            result["matched"].append(path)
    return dict(counts={k: len(v) for k, v in result.items()}, **result)


def run():
    manifests = {
        p.parent.name: (p, json.loads(p.read_text())["files"])
        for p in (BASE / "validation-snapshots").glob("*/validation-snapshot.json")
    }
    rows = []
    for label, name, chosen in PAIRS:
        report = BASE / name
        d = json.loads(report.read_text())
        before = d.get("source_before", d.get("source_hashes", {}))
        after = d.get("source_after")
        if chosen is None:
            ranked = sorted(
                manifests,
                key=lambda n: compare(before, manifests[n][1])["counts"]["matched"],
                reverse=True,
            )
            chosen = ranked[0]
            mapping = "best recorded-hash overlap; execution snapshot not independently attested"
        else:
            mapping = (
                "validation owner supplied snapshot or previously recorded assignment"
            )
        mp, files = manifests[chosen]
        b = compare(before, files)
        a = compare(after, files) if isinstance(after, dict) else None
        tools = []
        for key, value in d.items():
            if "tool" in key and key.endswith("sha256") and isinstance(value, str):
                matches = [p for p, v in files.items() if v == value]
                tools.append(
                    dict(
                        field=key,
                        sha256=value,
                        manifest_paths=matches,
                        status="matched" if matches else "missing",
                    )
                )
        stable = d.get("source_stable", d.get("sources_stable"))
        rows.append(
            dict(
                label=label,
                report=str(report),
                report_sha256=sha(report),
                manifest=str(mp),
                manifest_sha256=sha(mp),
                snapshot_mapping=mapping,
                source_stable_reported=stable,
                before_after_equal=(before == after) if after is not None else None,
                before=b,
                after=a,
                tool_hashes=tools,
                tool_hash_not_recorded=not tools,
                classification="recorded inputs match manifest"
                if stable is True
                and not b["counts"]["missing"]
                and not b["counts"]["different"]
                and (
                    a is None
                    or not a["counts"]["missing"]
                    and not a["counts"]["different"]
                )
                else "partial or mismatched provenance; inspect distinctions",
                limits=[
                    "Manifest equality proves recorded input identity, not isolated process cwd or unrecorded imports",
                    "Missing recorded after hashes/tool hashes stay unknown; semantic scope unchanged",
                ],
            )
        )
    diff_path = BASE / "cinetosis-formula-final-07-source-diff.json"
    diff = json.loads(diff_path.read_text())
    snapshot_log = BASE / "cinetosis-formula-snapshot-08.log"
    snapshot_data = json.loads(snapshot_log.read_text().splitlines()[0])
    snapshot_manifest = (
        BASE
        / "validation-snapshots/luna-cinetosis-formula-final-07/validation-snapshot.json"
    )
    out = dict(
        cinetosis_snapshot08=dict(
            log_path=str(snapshot_log),
            log_sha256=sha(snapshot_log),
            manifest=str(snapshot_manifest),
            manifest_sha256=sha(snapshot_manifest),
            sources_stable_reported=snapshot_data["sources_stable"],
            test_count=5,
            result="PASS",
            execution="validation owner attests actual cwd inside captured snapshot07",
            recorded_input_hash_map=None,
            limit="Log does not publish per-input hashes; isolated execution attestation distinct from exact hash-map comparison",
        ),
        cinetosis07=dict(
            source_diff_path=str(diff_path),
            source_diff_sha256=sha(diff_path),
            snapshot_manifest=diff["manifest"],
            snapshot_invalid_files=diff.get("invalid_snapshot"),
            changed_since_snapshot=diff.get("changed"),
            reported_source_stable=False,
            classification="requires isolated rerun; source-instability attested by validation owner, not inferred for unrelated reports",
        ),
        schema_version=1,
        method="Recorded before/after exact path or unique basename hashes compared against immutable manifest hashes; current worktree ignored",
        rows=rows,
        global_percentage=None,
    )
    path = Path(
        "docs/reports/combat-inventory/combat-provenance-reconciliation-20261008.json"
    )
    path.write_text(json.dumps(out, indent=2) + "\n")
    lines = [
        "# Combat report provenance reconciliation",
        "",
        "This stdlib audit compares recorded report inputs with snapshot manifests. Running from the live worktree does not automatically invalidate a report when its recorded inputs match the captured source. Conversely, a captured snapshot alone does not establish that the process executed from it. Semantic denominators and test outcomes remain frozen.",
        "",
        "| Scope | Snapshot | Before matched / missing / different | After hashes | Tool evidence |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        c = r["before"]["counts"]
        a = r["after"]
        tool = (
            ", ".join(t["field"] + ":" + t["status"] for t in r["tool_hashes"])
            or "not recorded"
        )
        lines.append(
            f"| {r['label']} | {Path(r['manifest']).parent.name} | {c['matched']} / {c['missing']} / {c['different']} | {str(a['counts']) if a else 'not recorded separately'} | {tool} |"
        )
    lines += [
        "",
        "[Detailed identities, missing paths and divergences](combat-provenance-reconciliation-20261008.json). Relative module paths resolve by a unique manifest path suffix; bare module filenames resolve only when the manifest basename is unique. The normal635 mapping is byte-confirmed by validation; the hash-based M3 snapshot candidate is explicitly provisional until execution mapping is confirmed. Missing tool or after hashes are unknown evidence, not automatically test failures.",
        "",
        "Cinetosis formula-final07 was reported source-unstable with nine source edits and cannot certify a frozen formal suite. The subsequent snapshot08 log records 5 tests PASS and stable source, with validation attesting execution inside snapshot07; it has no published per-input hash map and is recorded separately. The unstable earlier run remains historical; this does not invalidate unrelated stable reports. Current client verification and full mechanic coverage are not implied by provenance matches.",
    ]
    path.with_suffix(".md").write_text("\n".join(lines) + "\n")
    for r in rows:
        print(
            r["label"],
            Path(r["manifest"]).parent.name,
            r["before"]["counts"],
            "after",
            r["after"]["counts"] if r["after"] else None,
        )


if __name__ == "__main__":
    run()
