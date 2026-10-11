#!/usr/bin/env python3
"""Inventory native Lua actor coordinates without inferring world spawn joins."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import zipfile


def audit(archive):
    calls = collections.Counter()
    records = []
    files = 0
    actor_calls = 0
    pattern = re.compile(
        r"(?<![\w.])(?P<api>Actor\.createActor|createActor)\s*\((?P<args>[^()\n]*)\)"
    )
    with zipfile.ZipFile(archive) as source:
        for name in source.namelist():
            if not name.endswith(".lua"):
                continue
            files += 1
            raw = source.read(name)
            text = raw.decode("utf-8", "replace")
            for api in re.findall(r"\b([A-Za-z_]\w*\.[A-Za-z_]\w*)\s*\(", text):
                calls[api] += 1
            actor_calls += len(re.findall(r"\bActor\.createActor\s*\(", text))
            for match in pattern.finditer(text):
                arguments = [value.strip() for value in match["args"].split(",")]
                start = 2 if match["api"] == "Actor.createActor" else 1
                coordinates = arguments[start : start + 3]
                if len(coordinates) != 3 or not all(
                    re.fullmatch(r"-?\d+", value) for value in coordinates
                ):
                    continue
                prefix = text[: match.start()]
                functions = re.findall(r"\bfunction\s+([\w.:]+)\s*\(", prefix)
                records.append(
                    {
                        "archive_entry": name,
                        "entry_sha256": hashlib.sha256(raw).hexdigest(),
                        "line": prefix.count("\n") + 1,
                        "nearest_preceding_function_declaration": functions[-1]
                        if functions
                        else None,
                        "api": match["api"],
                        "arguments": arguments,
                        "x": int(coordinates[0]),
                        "y": int(coordinates[1]),
                        "z": int(coordinates[2]),
                        "source_expression": match[0],
                        "qualification": "cinematic_coordinate_candidate_only",
                        "unproven_contracts": [
                            "world_map_id",
                            "native_breed_id",
                            "world_spawn_visibility",
                            "initial_dialogue_root",
                        ],
                    }
                )
    return {
        "archive": str(archive),
        "archive_sha256": hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
        "lua_files": files,
        "direct_actor_create_call_occurrences": actor_calls,
        "literal_coordinate_records": records,
        "api_call_counts": dict(sorted(calls.items())),
        "qualified_world_spawns": [],
        "note": "Lexical inventory includes comments and helper calls; preceding function is a source anchor, not a verified execution scope. Graphics IDs are not breed IDs.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--archive", type=Path, default=Path("client/contents/scripts/scripts.jar")
    )
    args = parser.parse_args()
    result = audit(args.archive)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "lua_files": result["lua_files"],
                "direct_actor_create_call_occurrences": result[
                    "direct_actor_create_call_occurrences"
                ],
                "literal_coordinate_records": len(result["literal_coordinate_records"]),
                "qualified_world_spawns": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
