"""Summarize consumed casting rejection hooks without replay or eligibility claims."""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path


def rejection_groups(rows):
    groups = defaultdict(lambda: dict(references=set(), observations=0))
    for row in rows:
        result = row["result"]
        if result.get("status") == "validated":
            continue
        for diagnostic in result.get("cast_diagnostics", []):
            details = diagnostic.get("details", {})
            code = details.get("native_casting_result")
            if not isinstance(code, str) or not code.startswith("tw") or code == "twD":
                continue
            trace = details.get("native_casting_diagnostic", {}).get("trace", [])
            # Extra diagnostic records can follow result (e.g. LOS details).
            # Keep only the actual final consumed hook preceding that result.
            terminal = None
            for step in trace:
                if step.get("stage") == "result":
                    if step.get("value") != code:
                        raise ValueError("Casting trace result differs from rejection")
                    break
                terminal = step
            key = (code, terminal.get("stage") if terminal else None)
            group = groups[key]
            group["references"].add(row["ref"])
            group["observations"] += 1
    return [
        dict(
            result=code,
            terminal_hook=hook,
            observations=group["observations"],
            references=sorted(group["references"]),
        )
        for (code, hook), group in sorted(groups.items(), key=lambda item: str(item[0]))
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screening", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.screening.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    groups = rejection_groups(rows)
    args.output.write_text(
        json.dumps(
            dict(
                schema="monster-casting-rejection-observations-v1",
                offline=True,
                qualified=False,
                activated=False,
                note="Historical consumed hooks, not proof of runtime defects or complete monster coverage.",
                source_sha256=hashlib.sha256(raw).hexdigest(),
                groups=groups,
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(f"{len(groups)} observed rejection groups; no execution or readiness change")


if __name__ == "__main__":
    main()
