#!/usr/bin/env python3
"""Native6936/344011 common initialization with relative authority, offline."""
import json
from audit_class_initialization import run, PROJECT_ROOT

if __name__ == "__main__":
    result = run(
        [
            dict(breed=16, level=level, passive=[6936], mode="native_relative_passive")
            for level in (60, 200)
        ],
        with_relative_probability=True,
    )
    output = (
        PROJECT_ROOT
        / "docs/reports/combat-inventory/relative-initialization-audit.json"
    )
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    if not result["sources_stable"] or any(
        r["status"] != "initialized" or not r["rollback_preserved"]
        for r in result["rows"]
    ):
        raise SystemExit("Relative native audit failed or sources changed")
