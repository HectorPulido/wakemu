#!/usr/bin/env python3
"""Index literal client interactive-action script calls and world references.

The index exposes candidates for review; an action or UI call is not evidence
that the server starts or advances a particular quest.
"""
import argparse
import csv
import json
import re
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_NAME = re.compile(r"genericIEActions/(\d+)\.lua\Z")
LUA_CALL = re.compile(r"\b([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+)\s*\(([^\n()]*)\)")


def index_scripts(archive, objects):
    actions = {}
    with zipfile.ZipFile(archive) as scripts:
        for name in scripts.namelist():
            match = SCRIPT_NAME.fullmatch(name)
            if not match:
                continue
            source = scripts.read(name).decode("utf-8", errors="replace")
            # Remove Lua line comments before extracting literal calls.
            calls = []
            for line in source.splitlines():
                code = line.split("--", 1)[0]
                calls.extend(
                    {"function": call.group(1), "arguments": call.group(2).strip()}
                    for call in LUA_CALL.finditer(code)
                )
            actions[int(match.group(1))] = {
                "script": name,
                "calls": calls,
                "objects": [],
            }
    with objects.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            raw = row.get("native_outcome_definitions")
            if not raw:
                continue
            definition = json.loads(raw)
            if not isinstance(definition, dict):
                continue
            for state in definition.get("states", []):
                for outcome in state.get("outcomes", []):
                    for effect in outcome.get("effects", []):
                        # ExportRiftInteractionEvidence establishes that class is
                        # effect.awM(), the genericIEActions script reference.
                        entry = actions.get(effect.get("class"))
                        if entry is not None:
                            item = {
                                key: row[key]
                                for key in (
                                    "map_id",
                                    "object_id",
                                    "type",
                                    "x",
                                    "y",
                                    "z",
                                )
                            }
                            item.update(
                                {
                                    "native_action": state.get("action"),
                                    "effect_criterion": effect.get("criteria"),
                                    "outcome_criterion": outcome.get("criteria"),
                                }
                            )
                            entry["objects"].append(item)
    return actions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scripts", type=Path, default=ROOT / "client/contents/scripts/scripts.jar"
    )
    parser.add_argument(
        "--objects",
        type=Path,
        default=ROOT / "agents_docs/reports/ENVIRONMENT-OBJECTS-20261011.csv",
    )
    parser.add_argument(
        "--function", help="Return actions containing this exact Lua function"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    actions = index_scripts(args.scripts, args.objects)
    if args.function:
        actions = {
            k: v
            for k, v in actions.items()
            if any(call["function"] == args.function for call in v["calls"])
        }
    result = {
        "schema": "native-interactive-script-candidates-v1",
        "note": "Client calls and static object references are candidate evidence, not quest effects.",
        "actions": actions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Indexed {len(actions)} actions in {args.output}")


if __name__ == "__main__":
    main()
