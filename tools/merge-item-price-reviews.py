"""Merge independent manual price decisions; require exhaustive disjoint ownership."""
import csv
import hashlib
import json
from pathlib import Path


def main():
    root = Path("docs/reports/item-pricing-20261011")
    paths = sorted((root / "manual-reviews").glob("*-decisions.json"))
    paths.append(root / "manual-reviews/enchantment-economy.json")
    expected = {r["reference"] for r in csv.DictReader((root / "prices.csv").open())}
    by_reference, overrides, reviewers = {}, {}, []
    for path in paths:
        document = json.loads(path.read_text())
        reviewer = document["reviewer"]
        reviewers.append(
            dict(
                reviewer=reviewer,
                scope=document["scope_description"],
                references=len(document["reference_ids"]),
                cohorts=document["cohort_count"],
                verdict=document["verdict"],
                source=str(path),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
        for ref in document["reference_ids"]:
            key = str(ref)
            if key in by_reference:
                raise ValueError(f"Overlapping reviewers for {key}")
            by_reference[key] = dict(reviewer=reviewer, hold_reasons=[])
        for key, value in document["overrides"].items():
            if str(key) not in {str(ref) for ref in document["reference_ids"]}:
                raise ValueError(f"Override outside reviewer scope: {key}")
            overrides[str(key)] = value
        for key, reason in document["hold_additions"].items():
            by_reference[str(key)]["hold_reasons"].append(reason)
    if set(by_reference) != expected:
        raise ValueError(
            f"Incomplete manual review: missing {len(expected-set(by_reference))}, extra {len(set(by_reference)-expected)}"
        )
    recycling_path = root / "manual-reviews/recycling-floor-suggestions.json"
    for key, proposal in json.loads(recycling_path.read_text()).items():
        if key not in expected:
            raise ValueError(f"Recycling override outside retained inventory: {key}")
        if key in overrides:
            previous = overrides[key]
            proposal = dict(
                price_kamas=max(previous["price_kamas"], proposal["price_kamas"]),
                reason=previous["reason"] + " | " + proposal["reason"],
                reviewer=previous["reviewer"] + "; " + proposal["reviewer"],
            )
        overrides[key] = proposal
    index = dict(
        review_mode="All type/rarity/acquisition cohorts plus individual exceptions; not an individual visual inspection of every ordinary row",
        reviewers=reviewers,
        total_references=len(by_reference),
        total_cohorts=sum(x["cohorts"] for x in reviewers),
        recycling_cross_review=dict(
            path=str(recycling_path),
            sha256=hashlib.sha256(recycling_path.read_bytes()).hexdigest(),
        ),
        by_reference=by_reference,
    )
    (root / "manual-review-index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n"
    )
    (root / "manual-overrides.json").write_text(
        json.dumps(overrides, ensure_ascii=False, indent=2) + "\n"
    )
    print(
        f'{len(by_reference)} reviewed references; {index["total_cohorts"]} cohorts; {len(overrides)} overrides'
    )


if __name__ == "__main__":
    main()
