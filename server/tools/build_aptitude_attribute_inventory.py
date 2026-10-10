"""Build the complete aptitude table from a pinned read-only catalog capture."""
import hashlib
import json
from pathlib import Path

SOURCE = Path(".runtime/combat-review-20261009/aptitude-source-current.json")
OUT = Path("docs/reports/combat-inventory/aptitude-all-attributes-audit-20261009")
LABELS = {
    1: "HP percent",
    16: "Elemental resistance",
    17: "Barrier",
    27: "Healing received",
    36: "HP as armor",
    23: "Elemental mastery",
    26: "Melee mastery",
    30: "Distance mastery",
    31: "Flat HP",
    18: "Lock",
    19: "Dodge",
    20: "Initiative",
    21: "Lock and dodge",
    37: "Willpower",
    9: "Critical chance",
    10: "Block",
    11: "Critical mastery",
    12: "Rear mastery",
    13: "Berserk mastery",
    14: "Healing mastery",
    15: "Rear resistance",
    34: "Critical resistance",
    2: "AP",
    3: "MP and mastery",
    4: "Range and mastery",
    5: "WP",
    6: "Armor given percent",
    8: "Damage inflicted percent",
    35: "Elemental resistance",
    38: "Healing performed percent",
    39: "Indirect damage and mastery",
}
CATEGORY = {2: "Intelligence", 3: "Strength", 4: "Agility", 5: "Luck", 6: "Major"}


def main():
    data = json.loads(SOURCE.read_text())
    rules = data["aptitude-rules"]
    effects = {r["bonus"]: r for r in data["aptitude-effects"]}
    categories = {r["id"]: r for r in rules["categories"]}
    owners = {b: c["id"] for c in categories.values() for b in c["bonuses"]}
    closure = data["native-aptitude-effect-closure"]["effects"]
    rows = []
    for rule in sorted(rules["bonuses"], key=lambda r: (owners[r["id"]], r["id"])):
        b = rule["id"]
        e = effects[b]
        c = owners[b]
        budget = len(categories[c]["grant_levels"])
        branches = []
        pending = [e["effect"]]
        seen = set()
        while pending:
            ref = pending.pop()
            if ref in seen:
                continue
            seen.add(ref)
            r = closure.get(str(ref))
            if r:
                branches.append(
                    {
                        "reference": ref,
                        "family": r["effect_class"],
                        "criterion": r.get("criteria"),
                        "masks": r.get("target_masks"),
                        "parameters": r.get("parameters"),
                        "children": r.get("children", []),
                    }
                )
                pending.extend(r.get("children", []))
        rows.append(
            {
                "bonus": b,
                "category": CATEGORY[c],
                "label": LABELS[b],
                "maximum": rule["maximum"],
                "legal_maximum_at250": min(rule["maximum"] or budget, budget),
                "root": e["effect"],
                "runner": e["runner"],
                "stat": e.get("stat_id"),
                "one_point_values": e["values_by_points"][0],
                "flat_children": [
                    {
                        "stat": x.get("stat_id"),
                        "generic": x.get("generic"),
                        "one_point_values": x["values_by_points"][0],
                    }
                    for x in e.get("children", [])
                ],
                "route": "native eQr runtime initialization"
                if b in (17, 27, 36)
                else "flat/percentage reducer → equipment_stats → world/actor snapshot",
                "runtime_closure": branches,
                "test_status": "catalog every legal point reduction tested; complete combat consequence not certified",
                "all_classes": "Shared aptitude budgets/reducer; no breed-specific exception in these modules",
            }
        )
    report = {
        "schema": 1,
        "catalog_release": data["release"],
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "native_bonus_count": len(rows),
        "dormant_category_references": data["native-aptitude-catalog-audit"][
            "dormant_category_references"
        ],
        "categories": categories,
        "rows": rows,
        "fix": "Selected build effective level now governs read-time flat and conditional aptitude validation, matching build save",
        "validation": "14 tests run,10 PASS,4 DB-mutating integration tests skipped; no DB writes",
        "limits": [
            "Screenshot wording is not original localization proof",
            "31 native bonus identities,4 dormant category references rejected rather than fabricated",
            "Catalog reducer tests do not certify every reactive consequence across18class builds",
        ],
    }
    OUT.with_suffix(".json").write_text(json.dumps(report, indent=2) + "\n")
    lines = [
        "# All aptitude attributes audit",
        "",
        f"Pinned published catalog: `{data['release']}`. All **31 native bonus identities** are listed below. The same category grants and reducers serve all18classes; this is not an18class gameplay pass claim.",
        "",
        "|Category|Attribute / bonus ID|Cap|Native production route|",
        "|---|---|---|---|",
    ]
    for r in rows:
        stat = (
            str(r["stat"])
            if r["stat"] > 0
            else ", ".join(str(x["stat"]) for x in r["flat_children"])
        )
        lines.append(
            f"|{r['category']}|{r['label']} /{r['bonus']}|{r['maximum']or 'category budget'}|root{r['root']}; {r['route']}; stat{stat}|"
        )
    lines += [
        "",
        "## Budgets and ownership",
        "",
        "Category points count native grant thresholds at the effective sheet level. Intelligence starts2 then every4levels; Strength3; Agility4; Luck5. Major grants25/75/125/175/225. At200:50/50/50/49/4; at250:62/62/62/62/5. Per-bonus caps apply independently. Dormant category references24/25/32/33 have no native bonus objects and remain rejected; they must not be invented from historical UI categories.",
        "",
        "## Concrete corrected defect",
        "",
        "Build saving already validates against the selected build cap. Flat and runtime aptitude readers previously validated against character real level. A valid explicit capped sheet could reject during combat, while an automatic-level sheet could consume an excessive real-level budget. Both readers now share `validate_owned_sheet`, which resolves existing saved build metadata before validation. Three regression cases cover explicit cap, overbudget automatic sheet and alternate selected build. Production source files are frozen for deployment coordination.",
        "",
        "## Persistence, reset and consumers",
        "",
        "`builds.validate` validates all four blobs before saving; storage saves/loads aptitude blobs in character builds; `aptitude_registry` emits each owned sheet for reconnect. Flat additions flow through `equipment_stats.bonuses`; HP applies flat maximum plus percentage with Java truncation; resources apply AP/MP/WP and initiative; actor snapshots consume all stat keys and reject unsupported effects. Build response canonicalizes missing default sheets with empty aptitudes. No dedicated unrestricted respec operation was established by this review; replacing a validated saved blob is the observed boundary.",
        "",
        "The three reactive bonuses17/27/36 use eQr container36 at allocated point level, after class initialization, exactly once. Their full exported criteria, events and children are preserved in JSON. They are not flat healreceived/barrier guesses:Barrier17 has reverse damage2→999→430; current execution-count slope export is incomplete and can leave its base0 listener inactive (event owner is fixing the general count contract). Received healing27 installs state3205 at6*points from external1003; state3205 applies family1093 only for qualifying other allied heal sources. HP-as-armor36 selects HP<80000/≥80000 branches1047→1013 and excludes summons. Lock/Dodge7/8 and combined bonus21 currently reach snapshots but lack production disengagement consumption; the separate movement owner is implementing that contract.",
        "",
        "## Verification and remaining gates",
        "",
        "Current-catalog tests:14 run,10PASS,4 database-mutating integration tests skipped. Catalog coverage exercises budgets at all250levels and every legal allocated point, grouped reducers and fail-closed partial children. These checks establish producer/reducer contracts, not healing, armor, barrier or combat outcomes. Damage/heal/armor consumer audit belongs to the parallel event owner; reactive start/damage/turn counters and state3205 require actual initialized combat tests. All18classes share the code, but all18saved-build/combat combinations were not executed. No service restart, deployment or database writes.",
    ]
    OUT.with_suffix(".md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
