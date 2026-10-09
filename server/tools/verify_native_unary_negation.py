#!/usr/bin/env python3
"""Original lexer/parser differential for valid and invalid unary NOT syntax."""
import argparse, hashlib, itertools, json, subprocess
from pathlib import Path
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    patterns = [
        "!{a}",
        "!!{a}",
        "!{a} and {b}",
        "!{a} or {b} and {c}",
        "not !{a} or !not {b}",
        "!({a} or {b}) and {c}",
        "x = !{a}; y = x; x = {b}; y or !x",
        "# !{a} # or !# {b} #",
        "if (!{a}) then (!{b}) else (!{c})",
        "!(if ({a}) then ({b}) else ({c}))",
    ]
    cases = [
        dict(source=pattern.format(a=a, b=b, c=c))
        for a, b, c in itertools.product(("True", "False"), repeat=3)
        for pattern in patterns
    ]
    cases += [dict(source=case["source"].replace("!", "not ")) for case in list(cases)]
    cases += [
        dict(source=s)
        for s in [
            "!(1 != 2)",
            "!(1 == 2) and not False",
            "!1 == 2",
            "!False == True",
            "!",
            "True and !",
            "!if (True) then (False) else (True)",
            "not 1 == 2",
            "not False == True",
            "not GetLevel() == 2",
            "x = 1; not x == 2",
            "x = False; not x == True",
            "not if (True) then (False) else (True)",
        ]
    ]
    cases += [
        dict(source=s)
        for s in (
            "true",
            "false",
            "True",
            "False",
            "TRUE",
            "FALSE",
            "tRue",
            "fAlse",
            "x=true; !x",
            "x=false; not x",
            "!false and not False",
            "if (true) then (false) else (True)",
            "trueish=false; falseValue=true; !trueish and falseValue",
            "true=False; true",
            "false=True; false",
            "True=False; True",
            "False=True; False",
        )
    ]
    cases += [
        dict(
            source='GetEffectCaster() != GetEffectTarget() and not IsCarrying("target") and !IsBreedId("target", 2382)',
            evaluate=False,
        ),
        dict(source='GetBooleanSystemConfiguration("! != #")', evaluate=False),
        dict(source="IsOwnArea(true)", evaluate=False),
        dict(source="IsOwnArea(false)", evaluate=False),
    ]
    command = [
        "/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/java",
        "-Xmx128m",
        "-classpath",
        ".runtime/local/range-oracle-classes:client/lib/*",
        "ProbeNativeUnaryNegation",
    ]
    result = subprocess.run(
        command,
        cwd=ROOT,
        input="".join(json.dumps(c) + "\n" for c in cases),
        capture_output=True,
        text=True,
        check=True,
    )
    native = [
        json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")
    ]
    if len(native) != len(cases):
        raise AssertionError("Native count mismatch")
    rows = []
    mismatches = []
    for case, row in zip(cases, native):
        actual = None
        error = None
        if case.get("evaluate", True):
            try:
                actual = evaluate_condition(case["source"], ConditionContext({}))
            except UnknownCondition as exc:
                error = str(exc)
            if (
                bool(error) != bool(row.get("error"))
                or error is None
                and actual != row["value"]
            ):
                mismatches.append(
                    dict(
                        source=case["source"],
                        python_value=actual,
                        python_error=error,
                        native=row,
                    )
                )
        for token in row.get("tokens", []):
            if token["text"] in ("!", "not") and token["type"] != 368:
                raise AssertionError("Native NOT token mismatch")
            if token["text"] == "!=" and token["type"] != 369:
                raise AssertionError("Native inequality token mismatch")
        rows.append(
            dict(
                source=case["source"],
                native_value=row.get("value"),
                native_error=row.get("error"),
                python_value=actual,
                python_error=error,
                native_class=row.get("native_class"),
            )
        )
    paths = [
        "server/wakfu_server/combat/combat_local_criteria.py",
        "sniffer/java/ProbeNativeUnaryNegation.java",
        "client/lib/wakfu-client.jar",
    ]
    report = dict(
        scope="Original eQb/eQd NOT token and boolean precedence; no catalog/server execution",
        cases=len(cases),
        mismatches=mismatches,
        native_not_token=368,
        native_inequality_token=369,
        rows=rows,
        sources_sha256={
            p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths
        },
    )
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(dict(cases=len(cases), mismatches=len(mismatches))))
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
