#!/usr/bin/env python3
"""Every installed passive, independently plus deterministic full-deck samples.

Only initialization is tested. No lifecycle events or gameplay are fabricated.
The shared runner loads native catalogs once for the entire workload.
"""
import csv
import json
from pathlib import Path
from audit_class_initialization import run, DATA_ROOT, PROJECT_ROOT, BREEDS


def cases():
    data = json.loads((DATA_ROOT / "spells.json").read_text())
    names = {
        r["id"]: r["name"]
        for r in json.loads((DATA_ROOT / "spell-names.json").read_text())["spells"]
    }
    passives = sorted(
        (r for r in data["spells"] if r["kind"] == "passive"),
        key=lambda r: (r["breed"], r["unlock_level"], r["id"]),
    )
    rows = []
    for spell in passives:
        minimum = max(10, spell["unlock_level"])
        for level in sorted({minimum, 200}):
            rows.append(
                dict(
                    breed=spell["breed"],
                    level=level,
                    passive=[spell["id"]],
                    mode="individual_passive_with_native_innates",
                    spell_id=spell["id"],
                    spell_name=names.get(spell["id"]),
                    native_unlock_level=spell["unlock_level"],
                )
            )
    for breed in sorted(BREEDS):
        owned = [
            s["id"]
            for s in passives
            if s["breed"] == breed and s["unlock_level"] <= 200
        ]
        seen = set()
        # Deterministic disjoint chunks plus overlapping first/last/alternating.
        samples = [owned[i : i + 6] for i in range(0, len(owned), 6)]
        samples.extend((owned[:6], owned[-6:], owned[::2][:6], owned[1::2][:6]))
        for selected in samples:
            key = tuple(selected)
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append(
                dict(
                    breed=breed,
                    level=200,
                    passive=selected,
                    mode="representative_owned_passive_combination",
                )
            )
    return rows, passives


def main():
    workload, passives = cases()
    # Production initialization supplies the same native relative-group
    # authority through server_runtime; omitting it invents a setup blocker.
    result = run(workload, with_relative_probability=True)
    result["coverage"] = {
        "native_passive_count": len(passives),
        "native_passive_ids": [p["id"] for p in passives],
        "individual_case_count": sum(
            r["mode"].startswith("individual") for r in result["rows"]
        ),
        "combination_case_count": sum(
            r["mode"].startswith("representative") for r in result["rows"]
        ),
        "all_deck_combinations_tested": False,
        "events_replayed": False,
        "gameplay_verified": False,
    }
    for name in ("spell-names.json",):
        import hashlib

        result["provenance"][name] = hashlib.sha256(
            (DATA_ROOT / name).read_bytes()
        ).hexdigest()
    output = PROJECT_ROOT / "docs/reports/combat-inventory"
    output.mkdir(parents=True, exist_ok=True)
    (output / "passive-initialization-audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    columns = (
        "breed",
        "level",
        "mode",
        "spell_id",
        "spell_name",
        "native_unlock_level",
        "passive",
        "status",
        "effect_reference",
        "effect_class",
        "reason",
        "rollback_preserved",
        "gameplay_verified",
    )
    with (output / "passive-initialization-audit.csv").open("w") as destination:
        writer = csv.DictWriter(destination, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(result["rows"])
    print(
        json.dumps(
            dict(
                coverage=result["coverage"],
                sources_stable=result["sources_stable"],
                blocked=sum(r["status"] == "blocked" for r in result["rows"]),
            )
        )
    )
    if not result["sources_stable"]:
        raise SystemExit("Source changes: rerun before treating audit as current")


if __name__ == "__main__":
    main()
