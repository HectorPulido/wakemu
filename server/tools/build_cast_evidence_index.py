#!/usr/bin/env python3
"""Index the latest stable saved observation per spell/level/scenario.

This is a historical evidence index, not a current-source or gameplay pass.
Reports without timestamps, unstable reports and partial outputs cannot replace
stable evidence. The original reports remain authoritative and untouched.
"""
import csv
import datetime
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / "docs/reports/combat-inventory"


def collect(directory):
    latest = {}
    excluded = []
    for path in sorted(directory.glob("active-*.json")):
        if ".partial." in path.name:
            continue
        report = json.loads(path.read_text())
        stamp = report.get("generated_at")
        if not stamp or report.get("sources_stable") is not True:
            excluded.append(path.name)
            continue
        when = datetime.datetime.fromisoformat(stamp)
        if when.tzinfo is None:
            excluded.append(path.name)
            continue
        for row in report.get("rows", []):
            if not all(
                key in row for key in ("spell_id", "level", "variant", "status")
            ):
                continue
            branch = row.get("critical", report.get("critical", False))
            if type(branch) is not bool:
                continue
            key = (row["spell_id"], row["level"], row["variant"], branch)
            if key in latest and latest[key][0] >= when:
                continue
            latest[key] = (
                when,
                dict(
                    spell_id=key[0],
                    level=key[1],
                    variant=key[2],
                    critical=key[3],
                    status=row["status"],
                    reason=row.get("reason"),
                    generated_at=stamp,
                    report=path.name,
                    rollback_preserved=row.get("rollback_preserved"),
                    client_verified=False,
                    current_source_revalidated=False,
                ),
            )
    return [value[1] for _, value in sorted(latest.items())], excluded


def main():
    rows, excluded = collect(REPORTS)
    data = dict(
        scope="Última observación guardada por escenario; no es porcentaje de hechizos completos ni acredita la fuente actual.",
        counts=dict(Counter(row["status"] for row in rows)),
        excluded_reports=excluded,
        rows=rows,
    )
    (REPORTS / "cast-evidence-index.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    )
    with (REPORTS / "cast-evidence-index.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(rows[0]) if rows else ["spell_id"]
        )
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(data["counts"]))


if __name__ == "__main__":
    main()
