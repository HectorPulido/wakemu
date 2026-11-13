"""Extract client scenario event declarations and callback references.

These records describe client presentation, not authoritative server transitions.
"""
import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


EVENT = re.compile(r"^function\s+event_(-?\d+)_(\d+)\s*\(([^)]*)\)", re.MULTILINE)
CALLBACK = re.compile(
    r'(?:Server\.triggerEvent\s*\(\s*|["\']Server\.triggerEvent["\']\s*,\s*)(\d+)'
)


def extract_events(source):
    """Extract declarations in source order; source order is not execution order."""
    matches = list(EVENT.finditer(source))
    events = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        preceding = source[: match.start()].splitlines()
        comments = []
        for line in reversed(preceding):
            if not line.strip():
                if comments:
                    break
                continue
            if not line.lstrip().startswith("--"):
                break
            comments.append(line.strip()[2:].strip())
        segment = source[match.end() : end]
        events.append(
            {
                "scenario_id": int(match.group(1)),
                "event_id": int(match.group(2)),
                "arguments": [
                    v.strip() for v in match.group(3).split(",") if v.strip()
                ],
                "comments": list(reversed([c for c in comments if c])),
                "callbacks": [int(m.group(1)) for m in CALLBACK.finditer(segment)],
                "line": source.count("\n", 0, match.start()) + 1,
            }
        )
    return events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=int, nargs="+")
    parser.add_argument(
        "--archive", type=Path, default=Path("client/contents/scripts/scripts.jar")
    )
    args = parser.parse_args()
    with zipfile.ZipFile(args.archive) as archive:
        result = []
        for scenario in args.scenario:
            name = f"scenario/{scenario}.lua"
            data = archive.read(name)
            result.append(
                {
                    "source": name,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "events": extract_events(data.decode("utf-8", errors="replace")),
                }
            )
    print(
        json.dumps(
            {"authority": "client presentation only", "scenarios": result}, indent=2
        )
    )


if __name__ == "__main__":
    main()
