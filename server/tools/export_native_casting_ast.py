"""Parse scoped casting expressions with the original grammar; no providers."""
import gzip
import ast
import hashlib
import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "docs/reports/combat-inventory"
INPUT = REPORT / "class-casting-gap-inventory-20261007.json"
OUTPUT = REPORT / "class-casting-native-ast-20261007.jsonl.gz"
MANIFEST = REPORT / "class-casting-native-ast-20261007.json"
JAVA = ROOT / "sniffer/java/ExportNativeCastingCriterionAst.java"
LOCAL = ROOT / "server/wakfu_server/combat/combat_local_criteria.py"
SOURCES = (
    INPUT,
    JAVA,
    LOCAL,
    Path(__file__).resolve(),
    ROOT / "client/lib/wakfu-client.jar",
    ROOT / "server/protocol/native-spell-casting.json",
    ROOT / "server/protocol/native-class-spell-level-zero.json",
)


def digests():
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in SOURCES
    }


def main():
    before = digests()
    with open(INPUT, "rt") as stream:
        inventory = json.load(stream)
    for path in SOURCES[-2:]:
        key = str(path.relative_to(ROOT))
        if inventory["sources_before"].get(key) != before[key]:
            raise ValueError("Casting inventory source must be regenerated: " + key)
    expressions = inventory["expressions"]
    spec = importlib.util.spec_from_file_location("casting_local_parse_only", LOCAL)
    local = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(local)
    counts = Counter()
    structural_classes = set()
    functions = defaultdict(
        lambda: dict(
            classes=set(),
            arities=set(),
            aliases=set(),
            occurrences=0,
            expression_ids=set(),
        )
    )
    with tempfile.TemporaryDirectory(prefix="wakemu-casting-ast-") as temporary:
        directory = Path(temporary)
        source = directory / "input.jsonl"
        native = directory / "native.jsonl"
        stderr = directory / "native.stderr"
        with source.open("w") as stream:
            for row in expressions:
                raw = row["raw"]
                stream.write(
                    json.dumps(
                        dict(
                            expression_id=f"spell:{row['spell_id']}/{row['location']}",
                            spell_id=row["spell_id"],
                            location=row["location"],
                            expression=raw,
                            expression_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                            function_names=row["function_names"],
                        )
                    )
                    + "\n"
                )
        subprocess.run(
            ["javac", "-proc:none", "-cp", "client/lib/*", "-d", temporary, str(JAVA)],
            cwd=ROOT,
            check=True,
        )
        with source.open() as incoming, native.open("w") as outgoing, stderr.open(
            "w"
        ) as errors:
            subprocess.run(
                [
                    "java",
                    "-Xmx256m",
                    "-cp",
                    f"{temporary}:client/lib/*",
                    "ExportNativeCastingCriterionAst",
                ],
                cwd=ROOT,
                stdin=incoming,
                stdout=outgoing,
                stderr=errors,
                check=True,
            )
        rows = [json.loads(line) for line in native.open()]
        if len(rows) != len(expressions):
            raise ValueError("Native casting AST population mismatch")
        seen = set()
        with gzip.open(OUTPUT, "wt") as output:
            for row, expected in zip(rows, expressions):
                identity = f"spell:{expected['spell_id']}/{expected['location']}"
                if (
                    row["expression_id"] != identity
                    or identity in seen
                    or row["expression"] != expected["raw"]
                    or row["expression_sha256"]
                    != hashlib.sha256(expected["raw"].encode()).hexdigest()
                ):
                    raise ValueError("Native casting AST identity mismatch")
                seen.add(identity)
                try:
                    tree = local.parse_local_criterion(row["expression"])
                    parsed_calls = [
                        node
                        for node in ast.walk(tree)
                        if isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                    ]
                    row["local_parse"] = dict(
                        success=True,
                        root=type(tree).__name__,
                        calls=[
                            dict(
                                name=node.func.id,
                                arity=len(node.args),
                                arguments=[
                                    ast.dump(argument, include_attributes=False)
                                    for argument in node.args
                                ],
                            )
                            for node in parsed_calls
                        ],
                    )
                except local.LocalCriterionSyntax as error:
                    row["local_parse"] = dict(success=False, error=str(error))
                native_success = row["native_parse"]["success"]
                counts[
                    "native_parse_success" if native_success else "native_parse_failure"
                ] += 1
                counts["native_consumed_all"] += int(
                    row["native_parse"].get("consumed_all") is True
                )
                structural_classes.update(row["native_parse"].get("classes", []))
                local_success = row["local_parse"]["success"]
                row["parse_comparison"] = (
                    "both_parse"
                    if native_success and local_success
                    else "native_only"
                    if native_success
                    else "local_only"
                    if local_success
                    else "both_reject"
                )
                counts[row["parse_comparison"]] += 1
                counts["expressions"] += 1
                for call in row["calls"]:
                    name = call["name"]
                    item = functions[name]
                    item["occurrences"] += 1
                    item["expression_ids"].add(identity)
                    item["arities"].add(call.get("arity"))
                    if call.get("native_class"):
                        item["classes"].add(call["native_class"])
                    if not call.get("native_parse", {}).get("success"):
                        counts["isolated_call_parse_failures"] += 1
                    for argument in call.get("arguments_raw", []):
                        if (
                            len(argument) >= 2
                            and argument[0] == argument[-1]
                            and argument[0] in "\"'"
                        ):
                            item["aliases"].add(argument)
                output.write(
                    json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                )
        parser_stderr = stderr.read_text()
    counts["native_structural_classes"] = len(structural_classes)
    after = digests()
    manifest = dict(
        schema="class-casting-native-ast-v1",
        scope=inventory["scope"],
        native_entry_point="bPS -> eQe.tz -> eQe.tx -> CR/LF stripping -> eQd.fGv; boolean conjunction",
        representation="Per-expression native root/statement IDs and reflected alS fields; references use node IDs. No provider evaluation.",
        identity="spell:<spell_id>/<location>, exact raw UTF-8 SHA256; all input rows matched one-to-one",
        sources_before=before,
        sources_after=after,
        sources_stable=before == after,
        counts=dict(counts),
        textual_names=len(functions),
        native_functions=[
            dict(
                name=name,
                native_classes=sorted(value["classes"]),
                observed_arities=sorted(
                    value["arities"], key=lambda v: -1 if v is None else v
                ),
                observed_literal_strings=sorted(value["aliases"]),
                occurrences=value["occurrences"],
                expression_ids=sorted(value["expression_ids"]),
            )
            for name, value in sorted(functions.items())
        ],
        output=str(OUTPUT.relative_to(ROOT)),
        output_sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        parser_stderr=parser_stderr,
        limitations=[
            "Parse equivalence is not semantic/provider equivalence.",
            "Isolated calls referencing bound script variables can reject although the complete script parses.",
            "Literal strings are preserved, not inferred to be actor aliases.",
            "No context-dependent criterion provider or monster spell population was executed.",
        ],
    )
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                counts=dict(counts),
                textual_names=len(functions),
                sources_stable=before == after,
            )
        )
    )
    if before != after:
        raise SystemExit("Native casting AST sources changed during export")


if __name__ == "__main__":
    main()
