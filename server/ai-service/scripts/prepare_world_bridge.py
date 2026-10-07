"""Prepare the one world hook while preserving every unrelated source byte."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import textwrap

from wakfu_ai.bridge.world_hook_template import HOOK


def patch_source(source):
    tree = ast.parse(source)
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "pass_test_monster_turn"
    ]
    if len(matches) != 1:
        raise ValueError("Expected exactly one native NPC turn hook")
    function = matches[0]
    if function.decorator_list or isinstance(function, ast.AsyncFunctionDef):
        raise ValueError("Unsupported native hook declaration")
    lines = source.splitlines(keepends=True)
    before = "".join(lines[: function.lineno - 1])
    after = "".join(lines[function.end_lineno :])
    replacement = textwrap.indent(HOOK, " " * function.col_offset)
    result = before + replacement + after
    compile(result, "<prepared-world-bridge>", "exec")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    original = args.source.read_bytes()
    prepared = patch_source(original.decode("utf-8")).encode("utf-8")
    args.output.write_bytes(prepared)
    print(
        json.dumps(
            dict(
                sourceSha256=hashlib.sha256(original).hexdigest(),
                outputSha256=hashlib.sha256(prepared).hexdigest(),
                output=str(args.output),
                changedFunction="pass_test_monster_turn",
            )
        )
    )


if __name__ == "__main__":
    main()
