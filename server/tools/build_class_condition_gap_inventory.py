#!/usr/bin/env python3
"""Inventory native condition structure and guarded Python routes without combat imports."""
import ast, csv, gzip, hashlib, importlib.util, io, json, re, subprocess, tokenize
from collections import Counter, defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/reports/combat-inventory"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def read(p):
    return json.loads(p.read_text())


def native_expression(expression):
    tokens = list(tokenize.generate_tokens(io.StringIO(expression).readline))
    return tokenize.untokenize(
        [
            (
                t.type,
                json.dumps(ast.literal_eval(t.string))
                if t.type == tokenize.STRING
                else t.string,
            )
            for t in tokens
        ]
    )


def build():
    graphpath = OUT / "class-native-mechanic-graph-20261007.json"
    sourcepaths = [
        graphpath,
        ROOT / "server/wakfu_server/combat/combat_conditions.py",
        ROOT / "server/wakfu_server/combat/combat_runtime_adapter.py",
        ROOT / "server/wakfu_server/combat/combat_local_criteria.py",
        OUT / "verification-ledger-20261007.json",
        ROOT / "server/protocol/breed-innate-definitions.json",
        ROOT / "sniffer/java/ExportNativeCriterionCallClasses.java",
        Path(__file__).resolve(),
    ]
    before = {str(p.relative_to(ROOT)): sha(p) for p in sourcepaths}
    graph = json.loads(graphpath.read_bytes())
    nodes = graph["nodes"]
    source = sourcepaths[1].read_text()
    tree = ast.parse(source)
    spec = importlib.util.spec_from_file_location(
        "local_criterion_inventory", sourcepaths[3]
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    routes = defaultdict(list)
    for fn in ast.walk(tree):
        if (
            not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
            or fn.name == "evaluate_condition"
        ):
            continue
        for branch in ast.walk(fn):
            if not isinstance(branch, ast.If):
                continue
            tests = [
                t
                for t in ast.walk(branch.test)
                if isinstance(t, ast.Compare)
                and isinstance(t.left, ast.Name)
                and t.left.id == "name"
            ]
            values = []
            for right in [right for test in tests for right in test.comparators]:
                if isinstance(right, ast.Constant) and isinstance(right.value, str):
                    values.append(right.value)
                elif isinstance(right, (ast.Tuple, ast.List)):
                    values.extend(
                        x.value
                        for x in right.elts
                        if isinstance(x, ast.Constant) and isinstance(x.value, str)
                    )
            body = ast.Module(body=branch.body, type_ignores=[])
            dependencies = sorted(
                {
                    x.attr
                    for x in ast.walk(body)
                    if isinstance(x, ast.Attribute)
                    and isinstance(x.value, ast.Name)
                    and x.value.id in ("context", "actor")
                }
            )
            guards = sorted(
                {
                    x.value
                    for x in ast.walk(body)
                    if isinstance(x, ast.Constant)
                    and isinstance(x.value, str)
                    and any(
                        t in x.value.lower()
                        for t in (
                            "missing",
                            "unsupported",
                            "unknown",
                            "requires",
                            "native",
                            "authoritative",
                            "unaudited",
                        )
                    )
                }
            )
            for name in values:
                routes[name].append(
                    dict(
                        function=fn.name,
                        line=branch.lineno,
                        signature_guard=ast.unparse(branch.body[0])[:1200]
                        if branch.body
                        else "",
                        provider_fields=dependencies,
                        explicit_guard_messages=guards,
                    )
                )
    adaptertree = ast.parse(sourcepaths[2].read_text())
    provider_bindings = {}
    for call in ast.walk(adaptertree):
        if (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "ConditionContext"
        ):
            for keyword in call.keywords:
                provider_bindings[keyword.arg] = dict(
                    source=str(sourcepaths[2].relative_to(ROOT)),
                    line=keyword.value.lineno,
                    expression=ast.unparse(keyword.value),
                    authority="actual adapter binding; producer completeness unproved",
                )
    calls = defaultdict(list)
    failures = []
    lexical = set()
    for key, node in nodes.items():
        raw = node.get("criterion_raw")
        if not raw:
            continue
        lexical.update(re.findall(r"\b([A-Za-z_]\w*)\s*\(", raw))
        normalized = (
            raw.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n")
        )
        try:
            expression = module.parse_local_criterion(normalized)
        except Exception as exc:
            failures.append(dict(node=key, error=str(exc), raw=raw))
            continue
        for call in ast.walk(expression):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                calls[call.func.id].append(
                    dict(
                        node=key,
                        expression=ast.unparse(call),
                        argument_shapes=[type(a).__name__ for a in call.args],
                        literal_arguments=[
                            a.value if isinstance(a, ast.Constant) else None
                            for a in call.args
                        ],
                    )
                )
    private = ROOT / ".runtime/combat-review-20261007/condition-inventory"
    private.mkdir(parents=True, exist_ok=True)
    inputpath = private / "native-call-input.jsonl"
    inputpath.write_text(
        "".join(
            json.dumps(
                dict(name=name, expression=native_expression(examples[0]["expression"]))
            )
            + "\n"
            for name, examples in sorted(calls.items())
        )
    )
    java = "/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/java"
    result = subprocess.run(
        [
            java,
            "-Xmx128m",
            "-classpath",
            ".runtime/local/range-oracle-classes:client/lib/*",
            "ExportNativeCriterionCallClasses",
        ],
        cwd=ROOT,
        input=inputpath.read_text(),
        text=True,
        capture_output=True,
        check=True,
    )
    (private / "native-call-output.jsonl").write_text(result.stdout)
    nativecalls = {
        r["name"]: r
        for r in (
            json.loads(line)
            for line in result.stdout.splitlines()
            if line.startswith("{")
        )
    }
    adjacency = defaultdict(set)
    for edge in graph["edges"]:
        if edge["target"] in nodes and not edge["target"].startswith(
            "native_condition_class:"
        ):
            adjacency[edge["source"]].add(edge["target"])
    owners = defaultdict(set)
    ledger = read(sourcepaths[4])
    breeds = read(sourcepaths[5])["breeds"]
    classnodes = defaultdict(set)
    for spell in ledger["spells"]:
        for breed in spell["breeds"]:
            classnodes[breed].add("spell:" + str(spell["spell_id"]))
    for breed in breeds:
        classnodes[breed["breed"]].update(
            "state:" + str(s["reference"]) for s in breed["innate_states"]
        )
    for breed, seeds in classnodes.items():
        queue = deque(seeds)
        seen = set(seeds)
        while queue:
            key = queue.popleft()
            owners[key].add(breed)
            for child in adjacency[key]:
                if child not in seen:
                    seen.add(child)
                    queue.append(child)
    reverse = defaultdict(set)
    for source, targets in adjacency.items():
        for target in targets:
            reverse[target].add(source)

    def ancestors(keys):
        seen = set(keys)
        queue = deque(keys)
        while queue:
            for parent in reverse[queue.popleft()]:
                if parent not in seen:
                    seen.add(parent)
                    queue.append(parent)
        return {
            kind: sorted(int(x.split(":")[1]) for x in seen if x.startswith(kind + ":"))
            for kind in ("spell", "state", "area", "effect")
        }

    entries = []
    for name in sorted(
        (lexical - {"not", "and", "or", "True", "False", "if", "then", "else"})
        | set(calls)
    ):
        examples = calls.get(name, [])
        keys = {x["node"] for x in examples}
        rs = routes.get(name, [])
        # Presence establishes a guarded route, never complete semantic coverage.
        status = "partial" if rs else "absent"
        native = nativecalls.get(name, {})
        entries.append(
            dict(
                name=name,
                entry_kind="textual_function",
                status=status,
                status_reason="Guarded Python route exists; exhaustive native argument/provider equivalence is not accredited."
                if rs
                else "No explicit Python function-name branch in the current evaluator/validator.",
                native_class=native.get("native_class"),
                native_parse_error=native.get("error"),
                native_mapping_authority="original eQb/eQd isolated parse"
                if native.get("native_class")
                else "unknown",
                native_argument_contract="Native parsed sample signature only; full native null/PV/cell contract is unproved",
                python_argument_contract=[r["signature_guard"] for r in rs],
                observed_pv_selectors=sorted(
                    {
                        a
                        for x in examples
                        for a in x["literal_arguments"]
                        if isinstance(a, str)
                        and a
                        in ("caster", "target", "triggeringCaster", "triggeringTarget")
                    }
                ),
                observed_argument_shapes=sorted(
                    {tuple(x["argument_shapes"]) for x in examples}
                ),
                observed_literal_selectors=sorted(
                    {
                        a
                        for x in examples
                        for a in x["literal_arguments"]
                        if isinstance(a, str)
                    }
                ),
                python_routes=rs,
                provider_dependencies=sorted(
                    {p for r in rs for p in r["provider_fields"]}
                ),
                adapter_bindings={
                    p: provider_bindings.get(p)
                    for r in rs
                    for p in r["provider_fields"]
                },
                explicit_blockers=sorted(
                    {p for r in rs for p in r["explicit_guard_messages"]}
                ),
                effect_nodes=sorted(keys),
                breeds=sorted({b for key in keys for b in owners[key]}),
                reverse_index=ancestors(keys),
                examples=examples[:3],
                reachability="unknown",
                functional_complete=False,
            )
        )
    proved_contracts = {
        "IsCarried": (
            "eNv resolves eHg: eHH buX only; explicit null/non-eHH returns false; unknown selector remains unknown.",
            "native-null-pv-predicates-20261007.md",
        ),
        "IsCarrying": (
            "eNw resolves typed eGj: explicit null returns false; non-eGj registered PV rejects; actual frA carry relation required.",
            "native-null-pv-predicates-20261007.md",
        ),
        "IsCharacter": (
            "eND: explicit null false; nonnull eHg CHARACTER ancestry; area PV is noncharacter, not null.",
            "native-null-pv-predicates-20261007.md",
        ),
        "HasState": (
            "eME selected eHg null falls back to ePy.fyI; false only if fallback proven absent; nonnull null-Qf area state query false.",
            "native-null-pv-predicates-20261007.md",
        ),
        "HasStateFromLevel": (
            "eMF same selected-PV/ePy fallback and null-Qf boundary; level equality uses actual running state.",
            "native-null-pv-predicates-20261007.md",
        ),
        "HasStateFromUser": (
            "eMG same selected-PV/ePy fallback and null-Qf boundary; source identity is direct actual PV.",
            "native-null-pv-predicates-20261007.md",
        ),
        "GetDistanceToClosestSpecificArea": (
            "eJT/eIw: selector, numeric reference, bool pathMode, optional direct-owner selector; null/nonfighter returns -1; positive distances only; false mode Java-int XY Manhattan, true mode exact Sn authority required.",
            "native-closest-specific-area-contract-20261007.md",
        ),
        "IsInDiagonal": (
            "eNY requires actual fight coordinates, compares saturated native square arithmetic; distinct from fcj casting linear/diagonal/path restrictions.",
            "native-alignment-path-contract-20261007.md",
        ),
    }
    for entry in entries:
        if entry["name"] in proved_contracts:
            contract, evidence = proved_contracts[entry["name"]]
            entry["native_argument_contract"] = contract
            entry["native_contract_evidence"] = (
                "docs/reports/combat-inventory/" + evidence
            )
    mapped = defaultdict(list)
    for entry in entries:
        if entry["native_class"]:
            mapped[entry["native_class"]].append(entry["name"])
    nativeclasses = sorted(
        key.split(":", 1)[1]
        for key in nodes
        if key.startswith("native_condition_class:")
    )
    nativeentries = []
    for cls in nativeclasses:
        keys = {
            e["source"]
            for e in graph["edges"]
            if e["target"] == "native_condition_class:" + cls
        }
        nativeentries.append(
            dict(
                native_class=cls,
                textual_names=mapped[cls],
                status="partial" if mapped[cls] else "unknown",
                role="textual call root"
                if mapped[cls]
                else "unclassified structural object: may be operator, literal, selector or predicate",
                native_argument_contract="unknown unless linked to a separately proved contract",
                effect_nodes=sorted(keys),
                breeds=sorted({b for key in keys for b in owners[key]}),
                reverse_index=ancestors(keys),
                functional_complete=False,
            )
        )
    after = {str(p.relative_to(ROOT)): sha(p) for p in sourcepaths}
    data = dict(
        schema=1,
        scope="18 class spell and innate-state graph; no general monster/AI execution; dynamic captured summon ability roster remains unknown",
        sources_before=before,
        sources_after=after,
        sources_stable=before == after,
        native_graph_sources_stable=graph["sources_stable"],
        normalization="Raw native aNw.cyi preserved in graph; literal escaped CR/LF decoded only for inventory parsing, never rewritten in runtime.",
        classification_policy="No literal route is treated as complete. partial means source route present with guarded providers; absent means no explicit source branch; unknown means native structure not yet semantically classified. No speculative broken classification.",
        counts=dict(
            textual_names=len(entries),
            native_structural_classes=len(nativeentries),
            statuses=dict(Counter(e["status"] for e in entries)),
            local_parse_failures=len(failures),
        ),
        conditions=entries,
        source_only_routes=[
            dict(
                name=name,
                python_routes=routes[name],
                status="unknown",
                reason="Runtime route exists but no textual call occurrence in this class effect criterion graph; not added to native predicate denominator.",
            )
            for name in sorted(set(routes) - {e["name"] for e in entries})
        ],
        native_structural_classes=nativeentries,
        parse_failures=failures,
        classes=[
            dict(
                breed=b["breed"],
                name=b["name_bdata"],
                conditions=[e["name"] for e in entries if b["breed"] in e["breeds"]],
                native_classes=[
                    e["native_class"]
                    for e in nativeentries
                    if b["breed"] in e["breeds"]
                ],
            )
            for b in breeds
        ],
        unproved_domains=[
            "Complete native signature/null/PV/cell contracts",
            "Casting conditional criteria absent from graph effect raw criterion field",
            "Historical 122-name list not yet supplied; observed 116 is not asserted equivalent",
            "Dynamic Osa captured profile/book predicates",
            "Reachability and client/manual equivalence",
        ],
    )
    (OUT / "class-condition-gap-inventory.json").write_text(
        json.dumps(data, indent=2) + "\n"
    )
    with (OUT / "class-condition-gap-inventory.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "name",
                "native_class",
                "status",
                "breeds",
                "provider_dependencies",
                "effect_count",
                "spell_count",
                "state_count",
                "native_argument_contract",
            ]
        )
        for e in entries:
            writer.writerow(
                [
                    e["name"],
                    e["native_class"],
                    e["status"],
                    ",".join(map(str, e["breeds"])),
                    ";".join(e["provider_dependencies"]),
                    len(e["effect_nodes"]),
                    len(e["reverse_index"]["spell"]),
                    len(e["reverse_index"]["state"]),
                    e["native_argument_contract"],
                ]
            )
    lines = [
        "# Class condition and selector gap inventory",
        "",
        f"Textual calls: {len(entries)}. Native structural classes: {len(nativeentries)}. Status counts: {dict(Counter(e['status'] for e in entries))}.",
        "",
        "This is a source-level inventory, not functional completion. Native classes include operators and literals. Present guarded routes are partial until all native signatures, PV/cell/null branches and actual providers are proved. Unmapped structures remain unknown; absent textual calls have no explicit current route. The JSON preserves route lines, signature checks, provider fields, blocker messages, native parser mapping and reverse spell/state/area/effect/class indices.",
        "",
        f"Source snapshot stable: {before==after}. Raw escaped line breaks are normalized only for inventory parsing. Local parser failures: {len(failures)}.",
        "",
        "Casting criteria and dynamically captured Osa ability rosters remain explicit denominator gaps. All graph reachability stays unknown. No services, worlds, databases or client sessions were used.",
        "",
        "| Condition | Native class | Status | Classes |",
        "|---|---|---|---|",
    ]
    lines.extend(
        f"| {e['name']} | {e['native_class'] or 'unknown'} | {e['status']} | {','.join(map(str,e['breeds']))} |"
        for e in entries
    )
    (OUT / "class-condition-gap-inventory.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(data["counts"]))


if __name__ == "__main__":
    build()
