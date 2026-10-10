"""Join pinned published visual records with bounded native class state ownership."""
from collections import Counter
import hashlib
import json
from pathlib import Path

BASE = Path(".runtime/combat-review-20261010")
OUT = Path(
    "docs/reports/combat-inventory/class-visual-state-recipient-inventory-20261010"
)


def main():
    hmi_path = BASE / "visual-hmi-source.json"
    edge_path = BASE / "visual-state-edges.json"
    owners_path = Path("docs/reports/combat-inventory/class-state-gap-inventory.json")
    data = json.loads(hmi_path.read_text())
    edges = json.loads(edge_path.read_text())
    owners = json.loads(owners_path.read_text())
    assert data["release"] == edges["release"]
    class_states = {r["state_id"]: r for r in owners["states"]}
    children = {int(r["record_key"]): r["children"] for r in edges["edges"]}
    effects = {
        int(r["record_key"]): r["payload"]
        for r in data["rows"]
        if r["path"] == "combat-state-definitions.json"
    }
    all_types = Counter(
        a["type"]
        for r in data["rows"]
        for acts in r["payload"]["native_hmi_actions"].values()
        for a in acts
    )
    rows = []
    for state in edges["states"]:
        sid = int(state["record_key"])
        scope = class_states.get(sid)
        if not scope:
            continue
        roots = state["roots"]
        pending = list(roots)
        seen = set()
        while pending:
            ref = pending.pop()
            if ref in seen:
                continue
            seen.add(ref)
            pending.extend(children.get(ref, []))
        for ref in sorted(seen & effects.keys()):
            e = effects[ref]
            actions = e["native_hmi_actions"]
            types = sorted({a["type"] for acts in actions.values() for a in acts})
            direct = ref in roots
            rows.append(
                {
                    "state": sid,
                    "state_name": state["name"],
                    "effect": ref,
                    "direct_state_child": direct,
                    "breeds": scope["class_breeds"],
                    "dependent_spell_ids": scope["dependent_spell_ids"],
                    "family": e["effect_class"],
                    "area": e.get("area_class"),
                    "selector": e.get("native_target_selector"),
                    "criterion": e.get("criteria"),
                    "actions": actions,
                    "types": types,
                    "qualifier": "direct native state recipient-binding contract"
                    if direct
                    else "nested effect child path; intermediate group recipient contract requires qualification",
                    "empty_self_visual_risk": direct
                    and e.get("area_class") == "anA"
                    and e.get("native_target_selector", {}).get("mask") == 1,
                    "functional_status": "affected source route candidate; individual activation/client outcome unverified",
                }
            )
    byclass = {
        str(b): {
            "rows": sum(b in r["breeds"] for r in rows),
            "states": sorted({r["state"] for r in rows if b in r["breeds"]}),
            "direct_empty_self_effects": sorted(
                {
                    r["effect"]
                    for r in rows
                    if b in r["breeds"] and r["empty_self_visual_risk"]
                }
            ),
        }
        for b in range(1, 19)
    }
    report = {
        "schema": 1,
        "published_release": data["release"],
        "scope": "All published state HMI actions joined to frozen18class structural state ownership; all action styles retained, not appearance-only",
        "source_hashes": {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [hmi_path, edge_path, owners_path]
        },
        "published_catalog_hashes": data["hashes"],
        "counts": {
            "published_hmi_rows_scanned": len(data["rows"]),
            "published_states_scanned": len(edges["states"]),
            "class_state_ownership_rows": len(class_states),
            "visual_state_effect_pairs": len(rows),
            "distinct_effects": len({r["effect"] for r in rows}),
            "distinct_states": len({r["state"] for r in rows}),
            "direct_empty_self_effects": len(
                {r["effect"] for r in rows if r["empty_self_visual_risk"]}
            ),
        },
        "all_published_action_occurrences": dict(all_types),
        "per_class": byclass,
        "rows": rows,
        "incident": "Native eZk.bbA=true; child.g(parent.bfs) installs actual PV singleton, bypassing selector/area/aZX. Python cleared binding, causing empty anA fcE1 visual children to resolve zero actors. Runtime fix owned osa_capture_rejection.",
        "limits": [
            "Class reverse ownership is frozen earlier structural export, not refreshed dynamic reachability proof",
            "Common innate cosmetics can appear in many/all classes without proving a legal player spell activates them",
            "Direct and nested rows are different contracts; no count equals broken spells",
            "No client visual execution was performed; each appearance/animation cleanup remains manual pending",
        ],
    }
    OUT.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# Class visual state recipient inventory",
        "",
        report["incident"],
        "",
        f"Published release `{data['release']}`; scanned {len(edges['states'])} published states and {len(data['rows'])} nonempty HMI effect records. Class ownership uses the independently hash-pinned earlier state inventory, whose764structural state rows are not a current dynamic class-domain denominator.",
        "",
        "|Breed|Visual state/effect pairs|Distinct states|Direct empty/self effects|",
        "|---|---:|---:|---:|",
    ]
    for b, r in byclass.items():
        lines.append(
            f"|{b}|{r['rows']}|{len(r['states'])}|{len(r['direct_empty_self_effects'])}|"
        )
    lines += [
        "",
        "## Exact direct empty/self candidates",
        "",
        "These records have original direct state-child placement, empty `anA` and selector mask1. The source binding defect is shared. Criteria, sex, application/removal conditions and common cosmetic guards still determine actual reachability; this is not a broken-spell count.",
        "",
        "|State / label|Effect|Breeds|Visual action types|",
        "|---|---|---|---|",
    ]
    for r in rows:
        if r["empty_self_visual_risk"]:
            lines.append(
                f"|{r['state']} / {r['state_name']}|{r['effect']}|{', '.join(map(str,r['breeds']))}|{', '.join(r['types'])}|"
            )
    lines += [
        "",
        "## General acceptance and limits",
        "",
        "Test legal state application and removal/reversion for appearance, height, costume, scale, color, part visibility, animation/suffix/run/static changes, movement style, altitude, light and particle systems. Keep state/retained-effect packets and recipient actor identity in the trace; a committed spell or populated state ledger alone cannot prove client appearance. Reconnect while the state is active, then expire/remove it and confirm cleanup. All available styles are preserved in the JSON, including nested paths whose group recipient inheritance is a distinct contract.",
        "",
        "Structural reverse spell IDs include dependency references, not just direct active callers. Common class innate cosmetic trees must be qualified by their actual guards before prioritization. Full published catalogs were read only; no services, deployment or production code were changed.",
    ]
    OUT.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print(report["counts"])


if __name__ == "__main__":
    main()
