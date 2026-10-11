"""Plan and optionally publish the reviewed shop's highest-rarity selection."""
import argparse
import collections
import csv
import hashlib
import importlib.util
import io
import json
import subprocess
from pathlib import Path


RANK = {
    name: rank
    for rank, name in enumerate(
        [
            "UNUSUAL",
            "COMMON",
            "RARE",
            "MYTHIC",
            "LEGENDARY",
            "PVP_SOUVENIR",
            "EPIC",
            "RELIC",
        ]
    )
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    source = Path("docs/reports/item-pricing-20261011/prices.csv")
    assert hashlib.sha256(source.read_bytes()).hexdigest() == (
        "ad7d7d30297d5fae083b81dfb0249667280cb630aa56818c93603507240c8d44"
    )
    rows = list(csv.DictReader(source.open()))
    native = json.loads(
        Path(
            ".runtime/local/item-shop-inventory-20261011/native-types.json"
        ).read_text()
    )
    native_items = {str(row["reference"]): row for row in native["items"]}
    types = {row["type_id"]: row for row in native["types"]}
    spec = importlib.util.spec_from_file_location(
        "curation", "tools/filter-game-item-inventory.py"
    )
    curation = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(curation)
    names = {lang: curation.locale_names(lang) for lang in ("es", "en", "fr")}
    import re

    prohibited_name = re.compile(
        r"\b(admin|administrator|moderador|moderator|modérateur|game\s*master"
        r"|test|debug|wip|placeholder)\b|\[(beta|bêta)\]",
        re.I,
    )
    groups = collections.defaultdict(list)
    reasons = {}
    for row in rows:
        ref = row["reference"]
        assert int(row["rarity_id"]) == native_items[ref]["rarity_id"]
        reason = row["publication_hold"]
        lineage = set()
        item_type = int(row["native_type_id"])
        while item_type in types and item_type not in lineage:
            lineage.add(item_type)
            item_type = types[item_type]["parent_id"]
        if (
            int(row["rarity_id"]) == 10
            or row["rarity_name"] == "ADMIN"
            or lineage & {727, 732, 837}
            or any(
                prohibited_name.search(names[lang].get(int(ref), "")) for lang in names
            )
        ):
            reason = "|".join(filter(None, [reason, "admin_or_internal_guard"]))
        reasons[ref] = reason
        if not reason:
            assert row["rarity_name"] in RANK
            groups[row["name_es"], row["native_type_id"]].append(row)
    winners = {}
    for members in groups.values():
        winner = max(
            members,
            key=lambda row: (
                RANK[row["rarity_name"]],
                int(row["level"]),
                int(row["reference"]),
            ),
        )
        for row in members:
            winners[row["reference"]] = winner["reference"]
    output = Path("docs/reports/item-pricing-20261011/deduplication")
    output.mkdir(exist_ok=True)
    plan = []
    for row in rows:
        ref = row["reference"]
        winner = winners.get(ref, "")
        reason = reasons[ref] or (
            "" if winner == ref else "lower_priority_same_name_and_type"
        )
        plan.append(
            {
                "reference": ref,
                "name_es": row["name_es"],
                "native_type_id": row["native_type_id"],
                "level": row["level"],
                "rarity_name": row["rarity_name"],
                "price_kamas": row["price_kamas"],
                "enabled": not bool(reason),
                "canonical_reference": winner,
                "disabled_reason": reason,
            }
        )
    with (output / "catalog.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(plan[0]))
        writer.writeheader()
        writer.writerows(plan)
    summary = {
        "source_prices_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "grouping": "exact Spanish name and native item type; publication-eligible only",
        "rarity_order_low_to_high": list(RANK),
        "tie_breaks": [
            "higher level",
            "higher reference ID (deterministic, not proof of superiority)",
        ],
        "references": len(plan),
        "enabled": sum(row["enabled"] for row in plan),
        "disabled": sum(not row["enabled"] for row in plan),
        "duplicate_variants_disabled": sum(
            row["disabled_reason"] == "lower_priority_same_name_and_type"
            for row in plan
        ),
        "admin_quality_references_disabled": sum(
            row["rarity_name"] == "ADMIN" for row in plan
        ),
        "duplicate_groups": sum(len(members) > 1 for members in groups.values()),
        "catalog_sha256": hashlib.sha256(
            (output / "catalog.csv").read_bytes()
        ).hexdigest(),
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    if not args.apply:
        return
    backup = Path(".runtime/backups/shop-deduplication-20261011")
    backup.mkdir(parents=True, exist_ok=True)
    command = ["docker", "compose", "exec", "-T", "postgres"]
    backup_path = backup / "catalog-before.sql"
    if not backup_path.exists():
        result = subprocess.run(
            command
            + [
                "pg_dump",
                "-U",
                "wakemu",
                "-d",
                "wakemu_runtime",
                "--data-only",
                "--table=shop_articles",
                "--table=shop_categories",
            ],
            check=True,
            capture_output=True,
        )
        backup_path.write_bytes(result.stdout)
    data = io.StringIO()
    writer = csv.writer(data, lineterminator="\n")
    for row in plan:
        writer.writerow([row["reference"], row["price_kamas"], row["enabled"]])
    sql = (
        """\\set ON_ERROR_STOP on
BEGIN;
LOCK TABLE shop_articles IN SHARE ROW EXCLUSIVE MODE;
CREATE TEMP TABLE dedup_stage(item_ref integer PRIMARY KEY, price bigint, enabled boolean) ON COMMIT DROP;
COPY dedup_stage FROM STDIN WITH CSV;
"""
        + data.getvalue()
        + "\\.\n"
        + """
DO $$ BEGIN
 IF (SELECT revision FROM native_catalog_active WHERE id=1) <> '677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d' THEN RAISE EXCEPTION 'Native catalog changed'; END IF;
 IF (SELECT count(*) FROM shop_articles) <> (SELECT count(*) FROM dedup_stage) THEN RAISE EXCEPTION 'Catalog size changed'; END IF;
 IF EXISTS(SELECT 1 FROM dedup_stage s LEFT JOIN shop_articles a USING(item_ref) WHERE a.id IS NULL OR a.price_kamas<>s.price OR a.quantity<>1 OR (s.enabled AND NOT a.enabled)) THEN RAISE EXCEPTION 'Catalog changed; review before applying'; END IF;
END $$;
UPDATE shop_articles a SET enabled=false FROM dedup_stage s WHERE a.item_ref=s.item_ref AND NOT s.enabled AND a.enabled;
DO $$ BEGIN
 IF EXISTS(SELECT 1 FROM shop_articles a JOIN dedup_stage s USING(item_ref) WHERE a.enabled<>s.enabled) THEN RAISE EXCEPTION 'Visibility mismatch'; END IF;
END $$;
COMMIT;
SELECT count(*) FILTER(WHERE enabled) AS enabled, count(*) FILTER(WHERE NOT enabled) AS disabled FROM shop_articles;
"""
    )
    (backup / "publish.sql").write_text(sql)
    result = subprocess.run(
        command + ["psql", "-U", "wakemu", "-d", "wakemu_runtime"],
        input=sql,
        text=True,
        capture_output=True,
    )
    (backup / "publish.log").write_text(result.stdout + result.stderr)
    print(result.stdout, result.stderr)
    result.check_returncode()


if __name__ == "__main__":
    main()
