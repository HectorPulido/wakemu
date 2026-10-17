"""Explain all-server test impact in observation mode; never omit or run tests.

Edges are conservative structural evidence, not proof that a test asserts a
contract. Dynamic reachability stays explicit and widens affected selections.
"""
from __future__ import annotations

import ast
from collections import defaultdict, deque
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re

from tools.combat_baseline_inventory import (
    canonical_digest,
    environment_manifest,
    source_manifest,
)

SCHEMA = "wakemu-test-impact-graph-v1"
PLAN_SCHEMA = "wakemu-test-impact-plan-v1"
CONTRACTS_PATH = Path(__file__).with_name("combat_test_impact_contracts.json")
DEFAULT_RUNNER_POLICY = {
    "execution_model": "one module per subprocess",
    "module_timeout_seconds": 240.0,
}
SCENARIO_PATH = "agents_docs/reports/combat-resilience-phase1-2/source-scenarios.json"
OPERATION_REGISTRY_PATH = "server/wakfu_server/combat/combat_operation_registry.py"
MIGRATION_REGISTRY_PATH = "server/wakfu_server/combat/combat_core_migration.py"


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _path_node(path):
    if path.endswith(".py"):
        return "module:" + path
    return (
        ("catalog:" + path.removeprefix("server/protocol/"))
        if path.startswith("server/protocol/")
        else "input:" + path
    )


def _names(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _names(node.value)
        return prefix + "." + node.attr if prefix else node.attr
    return ""


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError):
        return None


def _operation_source_contracts(root):
    """Read bounded registry declarations from this source tree without imports.

    Only literal impact fields of _contract calls are understood. Unknown
    construction remains unqualified rather than executing arbitrary source or
    substituting the builder workspace's registry for a supplied snapshot.
    """
    path = root / OPERATION_REGISTRY_PATH
    if not path.is_file():
        return None, [], [], None
    raw = path.read_bytes()
    rows, errors = [], []
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError) as error:
        return _sha(raw), [], ["registry-parse-error:" + type(error).__name__], None
    declarations = {}
    for item in tree.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name):
                    declarations[target.id] = item.value
    contracts = declarations.get("_CONTRACTS")
    if not isinstance(contracts, (ast.Tuple, ast.List)):
        errors.append("registry-contract-list-not-literal")
        calls = []
    else:
        calls = list(contracts.elts)
    exported = declarations.get("OPERATIONS")
    if exported is not None:
        # Read the actual named provider declarations from the literal export
        # tuple. No provider names or native family lists are duplicated here.
        expected = ast.parse(
            "MappingProxyType({entry.operation_id: entry for entry in ()})", mode="eval"
        ).body
        valid = (
            isinstance(exported, ast.Call)
            and len(exported.args) == 1
            and isinstance(exported.args[0], ast.DictComp)
            and len(exported.args[0].generators) == 1
            and isinstance(exported.args[0].generators[0].iter, (ast.Tuple, ast.List))
        )
        if valid:
            iterator = exported.args[0].generators[0].iter
            expected.args[0].generators[0].iter = iterator
            valid = ast.dump(exported) == ast.dump(expected)
        if valid:
            calls = []
            for entry in iterator.elts:
                if isinstance(entry, ast.Starred) and isinstance(entry.value, ast.Name):
                    collection = declarations.get(entry.value.id)
                    if isinstance(collection, (ast.Tuple, ast.List)):
                        calls.extend(collection.elts)
                    else:
                        errors.append("registry-export-sequence-unknown")
                elif isinstance(entry, ast.Name) and entry.id in declarations:
                    calls.append(declarations[entry.id])
                else:
                    errors.append("registry-export-provider-unknown")
        else:
            errors.append("registry-export-construction-unknown")
    elif "RETAINED_EXECUTION" in declarations:
        calls.append(declarations["RETAINED_EXECUTION"])
    # A newly added declaration outside the understood exported sources must
    # widen selection until the source reader is deliberately extended.
    known_calls = {id(call) for call in calls}
    if any(
        isinstance(item, ast.Call)
        and _names(item.func) == "_contract"
        and id(item) not in known_calls
        for item in ast.walk(tree)
    ):
        errors.append("registry-additional-contract-construction-unknown")
    seen = set()
    family_owners = {}
    qualified_calls = {}

    def literal_metadata(value):
        try:
            ast.literal_eval(value)
            return True
        except (TypeError, ValueError, SyntaxError):
            if isinstance(value, (ast.Tuple, ast.List)):
                return all(literal_metadata(child) for child in value.elts)
            return (
                isinstance(value, ast.Call)
                and _names(value.func) == "DependencySpec"
                and all(literal_metadata(child) for child in value.args)
                and all(
                    child.arg is not None and literal_metadata(child.value)
                    for child in value.keywords
                )
            )

    for call in calls:
        if not isinstance(call, ast.Call) or _names(call.func) != "_contract":
            errors.append("registry-contract-construction-unknown")
            continue
        fields = dict(
            zip(
                (
                    "identity",
                    "families",
                    "executor",
                    "prerequisites",
                    "mutations",
                    "events",
                    "presentation",
                    "tests",
                ),
                call.args,
            )
        )
        fields.update({item.arg: item.value for item in call.keywords if item.arg})
        identity, executor, tests = (
            _literal(fields.get(key)) for key in ("identity", "executor", "tests")
        )
        families = _literal(fields.get("families"))
        if (
            not isinstance(identity, str)
            or not identity
            or identity in seen
            or not isinstance(executor, str)
            or not re.fullmatch(r"[A-Za-z_]\w*\.[A-Za-z_]\w*", executor)
            or not isinstance(tests, (tuple, list))
            or any(
                not isinstance(value, str) or not re.fullmatch(r"test_\w+", value)
                for value in tests
            )
            or not isinstance(families, (tuple, list))
            or any(type(value) is not int for value in families)
        ):
            errors.append("registry-contract-impact-fields-unknown")
            continue
        seen.add(identity)
        for family in families:
            if family in family_owners:
                errors.append("registry-duplicate-family:" + str(family))
            else:
                family_owners[family] = identity
        if not all(literal_metadata(value) for value in call.args) or not all(
            value.arg is not None and literal_metadata(value.value)
            for value in call.keywords
        ):
            errors.append("registry-contract-metadata-not-literal")
        else:
            qualified_calls[id(call)] = identity
        rows.append(
            {
                "id": identity,
                "families": list(families),
                "executor": executor,
                "tests": list(tests),
                "line": call.lineno,
                "contract_sha256": _sha(ast.dump(call).encode()),
            }
        )

    class CommonImplementation(ast.NodeTransformer):
        def visit_Call(self, call):
            if id(call) in qualified_calls:
                return ast.Constant("operation-contract:" + qualified_calls[id(call)])
            return self.generic_visit(call)

    common_sha = (
        None if errors else _sha(ast.dump(CommonImplementation().visit(tree)).encode())
    )
    return _sha(raw), rows, sorted(set(errors)), common_sha


def _migration_source_contracts(root, operation_ids):
    """Read canonical family metadata without importing a runtime or catalog.

    The operation registry remains the sole source of operation/test lists.
    Missing policy in a historical snapshot is not replaced with workspace data.
    Unrecognized policy construction cannot authorize bounded selection.
    """
    path = root / MIGRATION_REGISTRY_PATH
    if not path.is_file():
        return None, [], []
    raw = path.read_bytes()
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError) as error:
        return _sha(raw), [], ["migration-registry-parse-error:" + type(error).__name__]
    declarations = {
        target.id: item.value
        for item in tree.body
        if isinstance(item, ast.Assign)
        for target in item.targets
        if isinstance(target, ast.Name)
    }
    rows, errors = [], []
    collection = declarations.get("_FAMILIES")
    exported = declarations.get("MIGRATION_FAMILIES")
    expected = ast.parse(
        "MappingProxyType({family.name: family for family in _FAMILIES})", mode="eval"
    ).body
    if not isinstance(collection, (ast.Tuple, ast.List)):
        errors.append("migration-family-list-not-literal")
        calls = []
    else:
        calls = collection.elts
        if not calls:
            errors.append("migration-family-list-empty")
    if exported is None or ast.dump(exported) != ast.dump(expected):
        errors.append("migration-family-export-construction-unknown")
    names, attributes = set(), set()
    for call in calls:
        if not isinstance(call, ast.Call) or _names(call.func) != "MigrationFamily":
            errors.append("migration-family-construction-unknown")
            continue
        fields = dict(
            zip(
                (
                    "name",
                    "backend_attribute",
                    "operation_ids",
                    "invariants",
                    "components",
                ),
                call.args,
            )
        )
        fields.update({item.arg: item.value for item in call.keywords if item.arg})
        name, attribute, operations, invariants = (
            _literal(fields.get(key))
            for key in ("name", "backend_attribute", "operation_ids", "invariants")
        )
        components = _literal(fields["components"]) if "components" in fields else ()
        required = {"name", "backend_attribute", "operation_ids", "invariants"}
        if (
            len(call.args) + len(call.keywords) not in (4, 5)
            or not required <= set(fields) <= required | {"components"}
            or len(call.args) + len(call.keywords) != len(fields)
            or any(item.arg is None for item in call.keywords)
            or not isinstance(name, str)
            or not re.fullmatch(r"[a-z][a-z0-9_]*", name)
            or name in names
            or not isinstance(attribute, str)
            or not re.fullmatch(r"[A-Za-z_]\w*", attribute)
            or attribute in attributes
            or not isinstance(operations, (tuple, list))
            or not operations
            or any(
                not isinstance(identity, str) or identity not in operation_ids
                for identity in operations
            )
            or len(set(operations)) != len(operations)
            or not isinstance(invariants, (tuple, list))
            or not invariants
            or any(not isinstance(value, str) or not value for value in invariants)
            or not isinstance(components, (tuple, list))
            or any(
                not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_]\w*", value)
                for value in components
            )
            or len(set(components)) != len(components)
        ):
            errors.append("migration-family-fields-missing-or-unknown")
            continue
        for component in components:
            component_path = root / "server/wakfu_server/combat" / (component + ".py")
            if not component_path.is_file() or component_path.is_symlink():
                errors.append("migration-component-source-unavailable:" + component)
        names.add(name)
        attributes.add(attribute)
        rows.append(
            dict(
                name=name,
                backend_attribute=attribute,
                operation_ids=list(operations),
                components=list(components),
                line=call.lineno,
                contract_sha256=_sha(ast.dump(call).encode()),
            )
        )
    known_calls = {id(call) for call in calls}
    if any(
        isinstance(item, ast.Call)
        and _names(item.func) == "MigrationFamily"
        and id(item) not in known_calls
        for item in ast.walk(tree)
    ):
        errors.append("migration-additional-family-construction-unknown")
    return _sha(raw), rows, sorted(set(errors))


def _category(path):
    if path.startswith("server/tests/"):
        return "test" if Path(path).name.startswith("test") else "test-helper"
    if "/combat/" in path or path == "server/local_game_server.py":
        return "combat"
    if "/tools/" in path:
        return "tool"
    if path.startswith("server/protocol/"):
        return "catalog"
    return "server"


def _module_index(paths, contracts):
    """Map every supported import spelling to its actual source file."""
    result = defaultdict(set)
    for path in paths:
        if not path.endswith(".py"):
            continue
        parts = Path(path).with_suffix("").parts
        if parts[0] != "server":
            continue
        module_parts = parts[1:]
        if module_parts[-1] == "__init__":
            module_parts = module_parts[:-1]
        if module_parts:
            result[".".join(module_parts)].add(path)
        if len(parts) == 3 and parts[1] in ("tests", "tools"):
            result[parts[-1]].add(path)
        for package, extensions in contracts["package_extensions"].items():
            if len(parts) >= 4 and parts[1] == package and parts[2] in extensions:
                flattened = (package, *parts[3:])
                if flattened[-1] == "__init__":
                    flattened = flattened[:-1]
                result[".".join(flattened)].add(path)
    return result


def _relative_import(path, node):
    package = list(Path(path).with_suffix("").parts[1:-1])
    # Flattened package imports use extended __path__, but source-relative
    # imports still have a canonical area spelling reaching the same file.
    if node.level:
        package = package[: len(package) - node.level + 1]
        return ".".join([*package, *(node.module or "").split(".")]).strip(".")
    return node.module or ""


def _load_scenarios(root, value):
    if value is None:
        candidate = root / SCENARIO_PATH
        if not candidate.is_file():
            return None, None
        raw = candidate.read_bytes()
        return json.loads(raw), _sha(raw)
    if isinstance(value, (str, Path)):
        raw = Path(value).read_bytes()
        return json.loads(raw), _sha(raw)
    return value, canonical_digest(value)


def _private_policy(name):
    return bool(
        re.search(
            r"(?i)(secret|password|credential|token|key|url|dsn|path|dir|file)", name
        )
    )


def runtime_policy_inputs(names):
    """Bind declared public policies; private inputs expose availability only.

    Private values and even their hashes must never enter evidence. Their
    consumers remain conservatively selected on every plan.
    """
    if not isinstance(names, (list, tuple, set)) or any(
        not isinstance(name, str)
        or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", name)
        for name in names
    ):
        raise ValueError("Invalid runtime policy names")
    names = sorted(set(names))
    observations = {}
    for name in names:
        available = name in os.environ
        observations[name] = {
            "available": available,
            "value_identity": None
            if _private_policy(name) or not available
            else canonical_digest(os.environ[name]),
        }
    return {
        "runtime_policy_sha256": canonical_digest(observations),
        "runtime_policy_names": names,
    }


def impact_inputs(root, scenarios=None):
    """Hash selector declarations and optional guide input without service I/O."""
    _, scenario_sha = _load_scenarios(Path(root).resolve(), scenarios)
    return {
        "scenario_manifest_sha256": scenario_sha,
        "contracts_sha256": _sha(CONTRACTS_PATH.read_bytes()),
        "builder_sha256": _sha(Path(__file__).read_bytes()),
    }


TEST_KINDS = {
    "contract",
    "interaction",
    "integration",
    "system-acceptance",
    "support-only",
    "unknown",
}


def _symbol_exists(tree, symbol):
    """Validate a lexical review locator without importing its module."""
    if tree is None or not isinstance(symbol, str) or not symbol:
        return False
    parts = symbol.split(".")
    body = tree.body
    for part in parts:
        current = next(
            (
                value
                for value in body
                if isinstance(
                    value, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
                )
                and value.name == part
            ),
            None,
        )
        if current is None:
            return False
        body = current.body
    return True


def _support_only_errors(path, tree, symbols, nodes, inheritance):
    errors = []
    if (
        not isinstance(symbols, list)
        or not symbols
        or any(not _symbol_exists(tree, symbol) for symbol in symbols)
    ):
        errors.append("missing-support-helper-symbol")
    if tree is None:
        return errors + ["support-source-unavailable"]
    for item in ast.walk(tree):
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            item.name.startswith("test") or item.name == "load_tests"
        ):
            errors.append("support-module-defines-test-or-loader")
        if isinstance(item, ast.ClassDef) and any(
            _names(base) != "object" for base in item.bases
        ):
            errors.append("support-class-inheritance-unqualified")
        if isinstance(item, ast.ImportFrom) and any(
            alias.name == "TestCase" for alias in item.names
        ):
            errors.append("support-module-imports-testcase")
        if isinstance(item, ast.ImportFrom) and (item.module or "").startswith(
            ("test", "wakfu_server", "tools")
        ):
            errors.append("support-project-reexports-unqualified")
        if isinstance(item, ast.Call) and (
            _names(item.func) in ("exec", "eval", "type", "__import__")
            or _names(item.func).endswith(
                ("import_module", "loadTestsFromName", ".discover")
            )
        ):
            errors.append("support-dynamic-discovery-unqualified")
    if any(
        row.get("kind") == "test-method" and row.get("path") == path
        for row in nodes.values()
    ):
        errors.append("support-module-has-inherited-or-local-tests")
    if any(
        nodes.get(identity, {}).get("path") == path and parents
        for identity, parents in inheritance.items()
    ):
        errors.append("support-inheritance-unqualified")
    return errors


def _classification_review(declaration, files, trees, nodes, inheritance):
    """A review classifies source scope; it never accredits passing behavior."""
    errors = []
    path = declaration.get("path")
    if (
        not isinstance(path, str)
        or files.get(path) != declaration.get("source_sha256")
        or not declaration.get("source_sha256")
    ):
        errors.append("test-source-hash-missing-or-stale")
    kind = declaration.get("kind")
    if not isinstance(kind, str) or kind not in TEST_KINDS:
        errors.append("unknown-test-kind")
    if (
        not isinstance(declaration.get("scope"), str)
        or not declaration["scope"].strip()
    ):
        errors.append("missing-review-scope")
    if (
        not isinstance(declaration.get("rationale"), str)
        or not declaration["rationale"].strip()
    ):
        errors.append("missing-review-rationale")
    witnesses = declaration.get("assertion_witnesses", [])
    valid_witnesses = []
    if not isinstance(witnesses, list):
        errors.append("invalid-assertion-witness-list")
        witnesses = []
    for witness in witnesses:
        if (
            _symbol_exists(trees.get(path), witness)
            or "method:" + str(path) + ":" + str(witness) in nodes
        ):
            valid_witnesses.append(witness)
        else:
            errors.append("missing-assertion-witness:" + str(witness))
    valid_inheritance = []
    inheritance_proofs = declaration.get("inheritance_evidence", [])
    if not isinstance(inheritance_proofs, list):
        errors.append("invalid-inheritance-proof-list")
        inheritance_proofs = []
    for proof in inheritance_proofs:
        if not isinstance(proof, dict):
            errors.append("invalid-inheritance-proof")
            continue
        base_path, base_class = proof.get("base_path"), proof.get("base_class")
        base_id = "class:" + str(base_path) + ":" + str(base_class)
        pending = deque(
            identity
            for identity, row in nodes.items()
            if row.get("kind") == "class" and row.get("path") == path
        )
        visited = set()
        while pending:
            current = pending.popleft()
            if current in visited:
                continue
            visited.add(current)
            pending.extend(inheritance.get(current, ()))
        fixture_methods = proof.get("fixture_methods", [])
        valid = (
            isinstance(base_path, str)
            and isinstance(base_class, str)
            and bool(proof.get("source_sha256"))
            and files.get(base_path) == proof.get("source_sha256")
            and base_id in visited
        )
        valid = (
            valid
            and isinstance(fixture_methods, list)
            and bool(fixture_methods)
            and all(
                isinstance(method, str)
                and _symbol_exists(trees.get(base_path), str(base_class) + "." + method)
                for method in fixture_methods
            )
        )
        if valid:
            valid_inheritance.append(proof)
        else:
            errors.append("missing-or-stale-inheritance-proof:" + str(base_id))
    review_proofs = declaration.get("review_evidence", [])
    if not isinstance(review_proofs, list):
        errors.append("invalid-review-proof-list")
        review_proofs = []
    for proof in review_proofs:
        if not isinstance(proof, dict):
            errors.append("invalid-review-proof")
            continue
        proof_path = proof.get("path")
        if (
            not isinstance(proof_path, str)
            or not proof.get("source_sha256")
            or files.get(proof_path) != proof["source_sha256"]
            or not _symbol_exists(trees.get(proof_path), proof.get("symbol"))
        ):
            errors.append("missing-or-stale-review-evidence:" + str(proof_path))
    support_symbols = declaration.get("support_symbols", [])
    if kind == "support-only":
        errors.extend(
            _support_only_errors(
                path, trees.get(path), support_symbols, nodes, inheritance
            )
        )
    elif not valid_witnesses and not valid_inheritance:
        errors.append("missing-method-or-inheritance-review-proof")
    return {
        "status": "verified-source-review"
        if not errors
        else "unqualified-source-review",
        "errors": sorted(set(errors)),
        "kind": kind if not errors else "unknown",
        "source_sha256": declaration.get("source_sha256"),
        "scope": declaration.get("scope"),
        "rationale": declaration.get("rationale"),
        "assertion_witnesses": valid_witnesses,
        "inheritance_evidence": valid_inheritance,
        "support_symbols": support_symbols,
        "review_evidence": declaration.get("review_evidence", []),
        "qualification": "source-bound classification only; no behavioral pass accreditation",
    }


def _public_evidence(root, proof):
    """Read small declared public JSON evidence without following symlinks."""
    if not isinstance(proof, dict):
        raise ValueError("Evidence descriptor must be an object")
    name, digest = proof.get("path"), proof.get("sha256")
    if (
        not isinstance(name, str)
        or not name.startswith("server/")
        or "\\" in name
        or any(part in ("..", ".") or part.startswith(".") for part in name.split("/"))
    ):
        raise ValueError("Unsafe public evidence path")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Missing evidence SHA256")
    path = root / name
    if path.suffix != ".json" or any(
        parent.is_symlink() for parent in (path, *path.parents) if parent != root.parent
    ):
        raise ValueError("Unsafe public evidence file")
    if (
        not path.resolve().is_relative_to(root)
        or path.stat().st_size > 16 * 1024 * 1024
    ):
        raise ValueError("Evidence outside root or oversized")
    raw = path.read_bytes()
    if len(raw) > 16 * 1024 * 1024 or _sha(raw) != digest:
        raise ValueError("Evidence checksum mismatch")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Evidence JSON must be an object")
    return value


def _accepted_scenario_review(
    declaration, source_scenario, sources, root, files, trees, nodes, catalog
):
    """Qualify one reviewed interaction, never an entire guide or class."""
    errors, required_tests, evidence_paths = [], set(), []
    if source_scenario is None or canonical_digest(source_scenario) != declaration.get(
        "source_scenario_sha256"
    ):
        errors.append("source-scenario-missing-or-stale")
    if (
        not isinstance(declaration.get("scope"), str)
        or not declaration["scope"].strip()
        or not declaration.get("limitations")
    ):
        errors.append("missing-bounded-scope-or-limitations")
    if not declaration.get("rationale"):
        errors.append("missing-scenario-review-rationale")
    source_ids = declaration.get("source_ids", [])
    if (
        not isinstance(source_ids, list)
        or not source_ids
        or any(
            not isinstance(source_id, str) or source_id not in sources
            for source_id in source_ids
        )
    ):
        errors.append("guide-source-missing")
        source_ids = []
    if source_scenario and not set(source_ids).issubset(
        source_scenario.get("source_ids", [])
    ):
        errors.append("guide-source-not-in-scenario")
    operations = declaration.get("operation_ids", [])
    if (
        not isinstance(operations, list)
        or not operations
        or any("operation:" + str(operation) not in nodes for operation in operations)
    ):
        errors.append("operation-dependency-missing")
    implementations = declaration.get("implementation_dependencies", {})
    if not isinstance(implementations, dict) or not implementations:
        errors.append("missing-implementation-dependencies")
        implementations = {}
    for path, digest in implementations.items():
        if files.get(path) != digest or not isinstance(digest, str):
            errors.append("implementation-source-stale:" + str(path))
    dependencies = declaration.get("test_dependencies", [])
    if not isinstance(dependencies, list) or not dependencies:
        errors.append("missing-test-dependencies")
        dependencies = []
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            errors.append("invalid-test-dependency")
            continue
        path = dependency.get("path")
        if (
            not isinstance(path, str)
            or not dependency.get("source_sha256")
            or files.get(path) != dependency["source_sha256"]
        ):
            errors.append("test-dependency-missing-or-stale:" + str(path))
            continue
        witnesses = dependency.get("assertion_witnesses", [])
        if not isinstance(witnesses, list) or not witnesses:
            errors.append("missing-scenario-assertion-witness")
            continue
        for witness in witnesses:
            if (
                not _symbol_exists(trees.get(path), witness)
                and "method:" + path + ":" + str(witness) not in nodes
            ):
                errors.append("scenario-assertion-witness-missing:" + str(witness))
            else:
                required_tests.add(Path(path).stem + "." + witness)
    native_documents, oracle_hashes, native_test_sources = {}, set(), {}
    native_proofs = declaration.get("native_evidence", [])
    if not isinstance(native_proofs, list) or not native_proofs:
        errors.append("missing-native-evidence")
        native_proofs = []
    for proof in native_proofs:
        try:
            evidence = _public_evidence(root, proof)
            evidence_paths.append(proof)
            if evidence.get(
                "schema"
            ) != "wakemu-guide-native-interaction-evidence-v1" or evidence.get(
                "scenario_id"
            ) != declaration.get(
                "id"
            ):
                raise ValueError("Native evidence schema/scenario mismatch")
            guide = evidence.get("guide_source", {})
            if guide.get("id") not in source_ids or sources.get(
                guide.get("id"), {}
            ).get("url") != guide.get("url"):
                errors.append("native-evidence-guide-source-mismatch")
            if evidence.get("target_identity", {}).get(
                "published_catalog_revision"
            ) != catalog.get("revision"):
                errors.append("native-evidence-publication-revision-mismatch")
            for name, document in evidence.get("native_documents", {}).items():
                if (
                    name in native_documents
                    and native_documents[name] != document["sha256"]
                ):
                    errors.append("conflicting-native-document-evidence")
                native_documents[name] = document["sha256"]
            test_contract = evidence.get("test_contract", {})
            for source_path, source_hash in (
                (test_contract.get("path"), test_contract.get("source_sha256")),
                (
                    test_contract.get("fixture_path"),
                    test_contract.get("fixture_source_sha256"),
                ),
            ):
                if source_path is None and source_hash is None:
                    continue
                if (
                    not isinstance(source_path, str)
                    or not source_hash
                    or files.get(source_path) != source_hash
                ):
                    errors.append("native-fixture-test-authority-source-stale")
                else:
                    native_test_sources[source_path] = source_hash
            oracle_hashes.add(
                evidence.get("target_identity", {}).get("installed_jar_sha256")
            )
            if (
                evidence.get("target_identity", {}).get(
                    "native_export_jar_provenance_match"
                )
                is not True
            ):
                errors.append("native-export-oracle-provenance-unverified")
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            errors.append("native-evidence-missing-or-invalid")
    if not native_documents or not oracle_hashes or None in oracle_hashes:
        errors.append("missing-native-document-or-oracle-identity")
    if catalog.get("publication_verified") is not True or any(
        catalog.get("documents", {}).get(name) != digest
        for name, digest in native_documents.items()
    ):
        errors.append("native-documents-not-bound-to-publication")
    passing_proofs = declaration.get("passing_evidence", [])
    if not isinstance(passing_proofs, list) or not passing_proofs:
        errors.append("missing-passing-evidence")
        passing_proofs = []
    verified_tests = set()
    for proof in passing_proofs:
        try:
            receipt = _public_evidence(root, proof)
            evidence_paths.append(proof)
            if receipt.get(
                "schema"
            ) != "wakemu-bounded-scenario-pass-v1" or receipt.get(
                "scenario_id"
            ) != declaration.get(
                "id"
            ):
                raise ValueError("Passing receipt schema/scenario mismatch")
            clean = (
                receipt.get("terminal_status") == "passed"
                and type(receipt.get("return_code")) is int
                and receipt["return_code"] == 0
                and receipt.get("successful") is True
            )
            clean = (
                clean
                and type(receipt.get("tests_run")) is int
                and receipt["tests_run"] > 0
            )
            clean = clean and all(
                type(receipt.get(field)) is int and receipt[field] == 0
                for field in (
                    "failures",
                    "errors",
                    "skipped",
                    "unexpected_successes",
                    "expected_failures",
                )
            )
            clean = clean and receipt.get("native_runtime_enabled") is True
            if not clean:
                errors.append("passing-receipt-not-clean-terminal-native-run")
            test_sources, engine_sources = receipt.get("test_sources", {}), receipt.get(
                "engine_sources", {}
            )
            if (
                not engine_sources
                or not isinstance(engine_sources, dict)
                or any(
                    files.get(path) != digest for path, digest in engine_sources.items()
                )
            ):
                errors.append("passing-receipt-engine-source-missing-or-stale")
            for source_path, source_hash in native_test_sources.items():
                if (
                    test_sources.get(source_path) != source_hash
                    and engine_sources.get(source_path) != source_hash
                ):
                    errors.append("passing-receipt-native-fixture-source-not-bound")
            for dependency in dependencies:
                if isinstance(dependency, dict) and test_sources.get(
                    dependency.get("path")
                ) != dependency.get("source_sha256"):
                    errors.append("passing-receipt-test-source-missing-or-stale")
            if any(
                engine_sources.get(path) != digest
                for path, digest in implementations.items()
            ):
                errors.append("passing-receipt-implementation-closure-missing")
            if receipt.get("catalog_revision") != catalog.get("revision") or any(
                receipt.get("catalog_documents", {}).get(name) != digest
                for name, digest in native_documents.items()
            ):
                errors.append("passing-receipt-native-catalog-mismatch")
            if (
                receipt.get("oracle_identity", {}).get("installed_jar_sha256")
                not in oracle_hashes
            ):
                errors.append("passing-receipt-native-oracle-mismatch")
            declared_ids = proof.get("test_ids", [])
            actual_ids = receipt.get("test_ids", [])
            if (
                not isinstance(actual_ids, list)
                or receipt.get("tests_run") != len(actual_ids)
                or not declared_ids
                or not set(declared_ids).issubset(actual_ids)
            ):
                errors.append("passing-receipt-test-identity-missing")
            else:
                verified_tests.update(declared_ids)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            errors.append("passing-evidence-missing-or-invalid")
    if not required_tests or not required_tests.issubset(verified_tests):
        errors.append("required-scenario-assertions-not-terminally-verified")
    return {
        "status": "qualified-bounded-interaction"
        if not errors
        else "unqualified-source-scenario",
        "errors": sorted(set(errors)),
        "scope": declaration.get("scope"),
        "limitations": declaration.get("limitations", []),
        "source_scenario_id": declaration.get("source_scenario_id"),
        "test_ids": sorted(verified_tests),
        "operation_ids": operations,
        "native_documents": native_documents,
        "evidence": evidence_paths,
        "qualification": "Only the declared native interaction and fixture; no whole-guide or rendering accreditation",
    }


def _reflective_reader_write(tree, aliases, expressions):
    """Visible module/reader monkeypatches invalidate domain qualification."""
    symbols = {name.rsplit(".", 1)[-1] for name in expressions}
    modules = {name.rsplit(".", 1)[0] for name in expressions}

    def canonical(value):
        name = _names(value)
        base = name.split(".")[0]
        return aliases.get(base, base) + name[len(base) :]

    def native_target(value):
        name = canonical(value)
        return any(
            name == module or name.startswith(module + ".") for module in modules
        )

    for value in ast.walk(tree):
        if isinstance(value, ast.Attribute) and isinstance(
            value.ctx, (ast.Store, ast.Del)
        ):
            if value.attr in symbols or native_target(value):
                return True
        if isinstance(value, ast.Subscript) and isinstance(
            value.ctx, (ast.Store, ast.Del)
        ):
            key = _literal(value.slice)
            if isinstance(key, str) and key in symbols or native_target(value.value):
                return True
        if not isinstance(value, ast.Call):
            continue
        name = canonical(value.func)
        if (
            isinstance(value.func, ast.Attribute)
            and value.func.attr
            in (
                "update",
                "clear",
                "pop",
                "popitem",
                "setdefault",
                "__setitem__",
                "__delitem__",
            )
            and native_target(value.func.value)
        ):
            return True
        if name in ("setattr", "delattr") or name.endswith(
            (".__setattr__", ".__delattr__")
        ):
            key = _literal(value.args[1]) if len(value.args) > 1 else None
            if (
                not isinstance(key, str)
                or key in symbols
                or value.args
                and native_target(value.args[0])
            ):
                return True
        if name.endswith(".patch.object"):
            key = _literal(value.args[1]) if len(value.args) > 1 else None
            if (
                not isinstance(key, str)
                or key in symbols
                or value.args
                and native_target(value.args[0])
            ):
                return True
        if name.endswith(".patch"):
            target = _literal(value.args[0]) if value.args else None
            if not isinstance(target, str) or any(
                target == module or target.startswith(module + ".")
                for module in modules
            ):
                return True
        if name.endswith((".patch.multiple", ".patch.dict")):
            if value.args and native_target(value.args[0]):
                return True
            if any(
                keyword.arg in symbols or keyword.arg is None
                for keyword in value.keywords
            ):
                return True
            if len(value.args) > 1 and isinstance(value.args[1], ast.Dict):
                if any(
                    _literal(key) in symbols if isinstance(_literal(key), str) else True
                    for key in value.args[1].keys
                ):
                    return True
    return False


def _published_reader_contracts(root, contracts, index):
    """Source-bound reader qualification; a familiar method name is not proof."""
    qualified, errors = set(), []
    declared = contracts.get("published_reader_contracts", ())
    if not isinstance(declared, (list, tuple)):
        return qualified, ["invalid-published-reader-registry"]
    source_members = {path for sources in index.values() for path in sources}
    for declaration in declared:
        if not isinstance(declaration, dict):
            errors.append("invalid-published-reader-contract")
            continue
        path, symbol = declaration.get("source_path"), declaration.get("symbol")
        if (
            not isinstance(path, str)
            or path.startswith("/")
            or ".." in Path(path).parts
            or path not in source_members
            or not isinstance(symbol, str)
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", symbol)
            or declaration.get("domain") != "pinned-published-catalog-only"
        ):
            errors.append("invalid-published-reader-contract")
            continue
        try:
            supports = declaration.get("supporting_sources", {})
            if not isinstance(supports, dict) or any(
                not isinstance(name, str)
                or name not in source_members
                or _sha((Path(root) / name).read_bytes()) != digest
                for name, digest in supports.items()
            ):
                errors.append("stale-published-reader-support:" + path)
                continue
            raw = (Path(root) / path).read_bytes()
            parsed = ast.parse(raw)
            if _sha(raw) != declaration.get("source_sha256") or not any(
                isinstance(value, ast.FunctionDef) and value.name == symbol
                for value in parsed.body
            ):
                errors.append("stale-published-reader-contract:" + path)
                continue
        except (OSError, SyntaxError, ValueError):
            errors.append("unavailable-published-reader-contract:" + path)
            continue
        qualified.update(
            name + "." + symbol for name, sources in index.items() if sources == {path}
        )
    return qualified, sorted(set(errors))


def _qualified_isolated_reader_fixtures(
    root, declarations, files, published_readers, catalog
):
    """Verify actual singleton proof; retain unknown inputs and future isolation."""
    qualified, errors = {}, []
    for declaration in declarations or ():
        try:
            path = declaration["fixture_source_path"]
            if (
                declaration["status"] != "qualified-source-bound-isolated-fixture"
                or not path.startswith("server/tests/test")
                or not path.endswith(".py")
                or files.get(path) != declaration["fixture_source_sha256"]
                or not published_readers
            ):
                raise ValueError("fixture-source-or-reader-unqualified")
            if not declaration.get("reader_sources"):
                raise ValueError("fixture-reader-sources-missing")
            for source, digest in declaration["reader_sources"].items():
                if files.get(source) != digest:
                    raise ValueError("fixture-reader-source-stale")
            authority = declaration["terminal_authority"]
            records = {}
            for name, artifact in authority["artifacts"].items():
                resolved = (root / artifact["path"]).resolve()
                if (
                    not resolved.is_relative_to(root / ".runtime")
                    or _sha(resolved.read_bytes()) != artifact["sha256"]
                ):
                    raise ValueError("fixture-artifact-unbound")
                records[name] = json.loads(resolved.read_bytes())
            parent, child, environment = (
                records[key]
                for key in (
                    "receipt.json",
                    "child-results.json",
                    "effective-environment.json",
                )
            )
            preflight = records["preflight.json"]
            for field, artifact_name in (
                ("child_results", "child-results.json"),
                ("environment_digest_sidecar", "effective-environment.json"),
            ):
                if (
                    Path(parent[field]).resolve()
                    != (root / authority["artifacts"][artifact_name]["path"]).resolve()
                ):
                    raise ValueError("fixture-parent-artifact-path-mismatch")
            if any(
                preflight[field] != parent[field]
                for field in (
                    "command",
                    "exact_test_ids",
                    "actual_source_sha256_before",
                )
            ):
                raise ValueError("fixture-preflight-parent-mismatch")
            seal_path = (root / authority["api_source_seal_path"]).resolve()
            if (
                not seal_path.is_relative_to(root / ".runtime")
                or _sha(seal_path.read_bytes()) != authority["api_source_seal_sha256"]
            ):
                raise ValueError("fixture-api-source-seal-unbound")
            seal = json.loads(seal_path.read_bytes())
            if any(
                seal["files"].get(source, {}).get("after_sha256") != digest
                for source, digest in declaration["reader_sources"].items()
            ):
                raise ValueError("fixture-api-source-seal-mismatch")
            actual_catalog = child["catalog"]
            if (
                actual_catalog.get("publication_verified") is not True
                or catalog.get("publication_verified") is not True
                or actual_catalog.get("revision") != catalog.get("revision")
                or actual_catalog.get("catalog_sha256") != catalog.get("sha256")
            ):
                raise ValueError("fixture-catalog-authority-mismatch")
            module = Path(path).stem
            ids = [row["test_id"] for row in child["test_outcomes"]]
            fixture_tree = ast.parse((root / path).read_text())
            expected_ids = {
                module + "." + cls.name + "." + method.name
                for cls in fixture_tree.body
                if isinstance(cls, ast.ClassDef)
                for method in cls.body
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                and method.name.startswith("test_")
            }
            if set(ids) != expected_ids:
                raise ValueError("fixture-full-discovery-unbound")
            if (
                parent["return_code"] != 0
                or parent["source_stable"] is not True
                or not ids
                or len(ids) != len(set(ids))
                or ids != child["exact_test_ids_preflight"]
                or ids != parent["exact_test_ids"]
                or any(not identity.startswith(module + ".") for identity in ids)
                or any(row["status"] != "passed" for row in child["test_outcomes"])
                or child["result"]
                != {
                    "tests_run": len(ids),
                    "failures": 0,
                    "errors": 0,
                    "skips": 0,
                    "successful": True,
                }
                or parent["child_results_sha256"]
                != authority["artifacts"]["child-results.json"]["sha256"]
                or parent["actual_source_sha256_before"].get(path) != files[path]
                or parent["source_sha256_after"].get(path) != files[path]
            ):
                raise ValueError("fixture-execution-not-clean-singleton")
            expected_flags = {
                "isolated": True,
                "no_site": True,
                "ignore_environment": True,
            }
            if (
                child["python_flags"] != expected_flags
                or environment["python_flags"] != expected_flags
                or child["effective_environment_digest_before"]
                != child["effective_environment_digest_after"]
                or child["effective_environment_digest_before"]
                != environment["sha256_sorted_key_value_pairs"]
                or environment["actual_test_ids"] != ids
                or environment["discovered_affected_modules"]
            ):
                raise ValueError("fixture-isolation-or-environment-unbound")
            runner = (root / authority["runner_path"]).resolve()
            if (
                _sha(runner.read_bytes()) != authority["runner_sha256"]
                or environment["runner_sha256"] != authority["runner_sha256"]
                or parent["command"][1:3] != ["-I", "-S"]
                or Path(parent["command"][3]).resolve() != runner
            ):
                raise ValueError("fixture-runner-unbound")
            if any(
                source not in child["import_origins"].values()
                for source in declaration["reader_sources"]
            ):
                raise ValueError("fixture-api-import-origin-unbound")
            if child["import_origins"].get(module) != path:
                raise ValueError("fixture-import-origin-unbound")
            qualified[path] = {
                "source_sha256": files[path],
                "proof_sha256": canonical_digest(declaration),
                "required_execution_model": "singleton-test-module-subprocess",
                "unknown_input_scope": "owner-and-reverse-consumers-on-any-source-or-catalog-edit",
                "data_qualified": False,
                "reuse_qualified": False,
                "observed_execution_context": {
                    "effective_environment_sha256": child[
                        "effective_environment_digest_before"
                    ],
                    "capture_runner_sha256": authority["runner_sha256"],
                    "interpreter_sha256": environment["bootstrap_sha256"],
                    "startup_flags": expected_flags,
                    "catalog_revision": actual_catalog["revision"],
                    "catalog_inventory_sha256": actual_catalog["catalog_sha256"],
                    "future_runner_must_match_before_imports": True,
                },
            }
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            errors.append("isolated-reader-fixture-proof-invalid-or-stale")
    return qualified, errors


def build_graph(
    root,
    catalog_inventory=None,
    scenarios=None,
    *,
    runner_policy=None,
    isolated_reader_fixtures=None,
    require_observed_execution_context=False,
):
    """Build deterministic structural/semantic evidence for all server tests.

    No test/runtime modules are imported and no catalog/database calls are made.
    Catalog authority must be supplied by the caller's provenance capture.
    """
    root = Path(root).resolve()
    source = source_manifest(root)
    files = source["files"]
    environment = environment_manifest()
    contracts_raw = CONTRACTS_PATH.read_bytes()
    contracts = json.loads(contracts_raw)
    if contracts.get("schema") != "wakemu-test-impact-contracts-v1":
        raise ValueError("Unsupported semantic declaration schema")
    scenarios, scenario_sha = _load_scenarios(root, scenarios)
    catalog = catalog_inventory or {
        "status": "unavailable",
        "documents": {},
        "sha256": None,
        "revision": None,
    }
    catalog_documents = catalog.get("documents", {})
    if not isinstance(catalog_documents, dict):
        raise ValueError("Invalid catalog document inventory")
    nodes, edges, unknowns = {}, {}, []
    unknown_keys = set()

    def node(identity, kind, **attributes):
        entry = nodes.setdefault(identity, {"id": identity, "kind": kind})
        entry.update(attributes)
        return identity

    def edge(consumer, dependency, kind, path=None, line=None, confidence="static"):
        evidence = {"path": path, "line": line}
        entry = dict(
            consumer=consumer,
            dependency=dependency,
            kind=kind,
            confidence=confidence,
            evidence=evidence,
        )
        edges[canonical_digest(entry)] = entry

    def unknown(
        owner,
        reason,
        *,
        domain="source",
        target=None,
        line=None,
        fallback="owner-consumers",
    ):
        entry = dict(
            owner=owner,
            reason=reason,
            domain=domain,
            target=target,
            line=line,
            fallback=fallback,
        )
        digest = canonical_digest(entry)
        if digest not in unknown_keys:
            unknown_keys.add(digest)
            unknowns.append(entry)

    node("domain:catalog", "domain")
    index = _module_index(files, contracts)
    published_readers, published_reader_errors = _published_reader_contracts(
        root, contracts, index
    )
    isolated_fixtures, isolated_fixture_errors = _qualified_isolated_reader_fixtures(
        root, isolated_reader_fixtures, files, published_readers, catalog
    )
    module_names = []
    class_bases, class_methods = {}, defaultdict(list)
    class_paths, imported_symbols, imported_modules = {}, {}, {}
    trees, reader_summaries = {}, {}
    reader_methods = set()
    reader_parameters = {}
    for path, digest in files.items():
        identity = (
            node(
                "module:" + path,
                "module",
                path=path,
                sha256=digest,
                category=_category(path),
            )
            if path.endswith(".py")
            else node(
                _path_node(path),
                "catalog-document" if path.startswith("server/protocol/") else "input",
                path=path,
                sha256=digest,
            )
        )
        if (
            path.startswith("server/tests/")
            and Path(path).parent == Path("server/tests")
            and Path(path).name.startswith("test")
            and path.endswith(".py")
        ):
            test_id = node(
                "test-module:" + path,
                "test-module",
                path=path,
                module_name=Path(path).stem,
                test_kind="unknown",
                classification_evidence=[],
                classification_review={
                    "status": "missing-source-review",
                    "errors": ["no-source-bound-review"],
                },
            )
            edge(test_id, identity, "executes-module", path)
            module_names.append(Path(path).stem)
    for name, digest in sorted(catalog_documents.items()):
        if (
            not isinstance(name, str)
            or name.startswith("/")
            or ".." in Path(name).parts
        ):
            raise ValueError("Unsafe catalog document identity")
        identity = node("catalog:" + name, "catalog-document", published_sha256=digest)
    for operation in contracts["operations"]:
        op = node(
            "operation:" + operation["id"],
            "operation",
            declaration_sha256=_sha(contracts_raw),
            qualification="structural",
        )
        matches = [
            path
            for path in files
            if any(
                fnmatch.fnmatchcase(path, pattern) for pattern in operation["modules"]
            )
        ]
        for path in matches:
            # Both directions intentionally group declared implementations;
            # a shared contract change affects the operation's other producers.
            edge(
                op,
                "module:" + path,
                "implemented-by",
                path,
                confidence="declared-conservative",
            )
            edge(
                "module:" + path,
                op,
                "shares-operation-contract",
                path,
                confidence="declared-conservative",
            )
    (
        registry_sha,
        registry_operations,
        registry_errors,
        registry_common_sha,
    ) = _operation_source_contracts(root)
    registry_node = "module:" + OPERATION_REGISTRY_PATH
    for reason in registry_errors:
        # An unresolved registry export can bind any executor or consumer.
        # Its uncertainty remains active even when the registry file itself
        # is unchanged and only an otherwise known executor was edited.
        unknown(registry_node, reason, domain="source-unbounded", fallback="full")
    for operation in registry_operations:
        op = node(
            "operation:" + operation["id"],
            "operation",
            contract_sha256=operation["contract_sha256"],
            families=operation["families"],
            executor=operation["executor"],
            qualification="source-declared-structural",
        )
        edge(
            op,
            registry_node,
            "operation-registry-definition",
            OPERATION_REGISTRY_PATH,
            operation["line"],
            confidence="source-literal",
        )
        executor_path = (
            "server/wakfu_server/combat/" + operation["executor"].split(".")[0] + ".py"
        )
        if executor_path in files:
            edge(
                op,
                "module:" + executor_path,
                "operation-executor",
                OPERATION_REGISTRY_PATH,
                operation["line"],
                confidence="source-literal",
            )
            edge(
                "module:" + executor_path,
                op,
                "shares-operation-contract",
                OPERATION_REGISTRY_PATH,
                operation["line"],
                confidence="declared-conservative",
            )
        else:
            unknown(
                op,
                "registry-executor-source-unavailable",
                domain="operation",
                target=executor_path,
                fallback="full",
            )
        for test_name in operation["tests"]:
            test_path = "server/tests/" + test_name + ".py"
            if test_path in files:
                edge(
                    "test-module:" + test_path,
                    op,
                    "declared-operation-test",
                    OPERATION_REGISTRY_PATH,
                    operation["line"],
                    confidence="source-literal-not-accreditation",
                )
            else:
                unknown(
                    op,
                    "registry-test-source-unavailable",
                    domain="operation",
                    target=test_path,
                    fallback="full",
                )
    for fact in contracts.get("event_contracts", []):
        event_id = node(
            "event-contract:" + fact["id"],
            "event-contract",
            phases=fact["phases"],
            argument_contract=fact["arguments"],
            qualification=fact["qualification"],
        )
        for role in ("producers", "consumers"):
            for declaration in fact[role]:
                path = declaration["path"]
                if path in files:
                    edge(
                        "module:" + path,
                        event_id,
                        role.removesuffix("s") + "-event-contract",
                        path,
                        confidence="declared-reviewed",
                    )
                    edge(
                        event_id,
                        "module:" + path,
                        "contract-implementation",
                        path,
                        confidence="declared-reviewed",
                    )
    for declaration in contracts.get("explicit_dependencies", []):
        for consumer in files:
            if not any(
                fnmatch.fnmatchcase(consumer, pattern)
                for pattern in declaration["consumers"]
            ):
                continue
            for pattern in declaration["dependencies"]:
                matches = [path for path in files if fnmatch.fnmatchcase(path, pattern)]
                if not matches and not any(char in pattern for char in "*?["):
                    matches = [pattern]
                for dependency in matches:
                    dep_id = (
                        "module:" + dependency
                        if dependency.endswith(".py")
                        else _path_node(dependency)
                    )
                    node(
                        dep_id,
                        "module"
                        if dependency.endswith(".py")
                        else "catalog-document"
                        if dependency.startswith("server/protocol/")
                        else "input",
                        path=dependency,
                    )
                    edge(
                        "module:" + consumer,
                        dep_id,
                        "declared-source-or-fixture",
                        consumer,
                        confidence="declared-reviewed",
                    )
    for path in sorted(p for p in files if p.endswith(".py")):
        owner = "module:" + path
        try:
            tree = ast.parse((root / path).read_text(encoding="utf8"))
        except (OSError, UnicodeError, SyntaxError) as error:
            unknown(owner, "parse-error:" + type(error).__name__, fallback="full")
            continue
        trees[path] = tree
        bindings = {
            target.id: assignment.value
            for assignment in tree.body
            if isinstance(assignment, ast.Assign)
            for target in assignment.targets
            if isinstance(target, ast.Name)
        }
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        aliases, source_aliases = {}, {}
        imports = {}
        for item in ast.walk(tree):
            if isinstance(item, ast.Import):
                candidates = [
                    (a.name, a.asname or a.name.split(".")[0], None) for a in item.names
                ]
            elif isinstance(item, ast.ImportFrom):
                base = _relative_import(path, item)
                candidates = [
                    (base + "." + a.name, a.asname or a.name, (base, a.name))
                    for a in item.names
                ]
            else:
                continue
            for target, local, symbol in candidates:
                aliases[local] = target
                resolved = index.get(target, set())
                if not resolved and symbol:
                    resolved = index.get(symbol[0], set())
                if not resolved and isinstance(item, ast.ImportFrom) and item.level:
                    parts = target.split(".")
                    if (
                        len(parts) > 2
                        and parts[0] == "wakfu_server"
                        and parts[1] in contracts["package_extensions"]["wakfu_server"]
                    ):
                        flattened = ".".join([parts[0], *parts[2:]])
                        resolved = index.get(flattened, set())
                        if not resolved and symbol:
                            resolved = index.get(flattened.rsplit(".", 1)[0], set())
                if resolved:
                    source_aliases[local] = sorted(resolved)
                    for dependency in resolved:
                        edge(
                            owner, "module:" + dependency, "imports", path, item.lineno
                        )
                    if symbol:
                        imports[local] = [(p, symbol[1]) for p in resolved]
                elif target.startswith(("wakfu_server", "tools", "tests")) or (
                    symbol and item.level
                ):
                    unknown(owner, "unresolved-import", target=target, line=item.lineno)
                if local == "*":
                    unknown(owner, "wildcard-import", target=target, line=item.lineno)
        imported_symbols[path] = imports
        imported_modules[path] = source_aliases
        for item in ast.walk(tree):
            if (
                isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                and item.name == "load_tests"
            ):
                unknown(
                    owner,
                    "dynamic-test-discovery",
                    domain="source-unbounded",
                    line=item.lineno,
                )
            if isinstance(item, ast.ClassDef):
                class_id = node(
                    "class:" + path + ":" + item.name,
                    "class",
                    path=path,
                    name=item.name,
                )
                edge(class_id, owner, "defined-in", path, item.lineno)
                if (path, item.name) in class_paths:
                    unknown(
                        owner,
                        "ambiguous-class-lexical-name",
                        target=item.name,
                        line=item.lineno,
                    )
                if item.keywords:
                    unknown(
                        owner,
                        "dynamic-class-construction",
                        target=item.name,
                        line=item.lineno,
                    )
                class_paths[(path, item.name)] = class_id
                class_bases[class_id] = [(path, _names(base)) for base in item.bases]
                if item.name in contracts.get("provider_classes", []):
                    for field in item.body:
                        if isinstance(field, ast.AnnAssign) and isinstance(
                            field.target, ast.Name
                        ):
                            slot = node(
                                "provider-slot:" + item.name + "." + field.target.id,
                                "provider-slot",
                                qualification="requires-runtime-binding",
                            )
                            edge(owner, slot, "requires-provider", path, field.lineno)
                            unknown(
                                owner,
                                "runtime-provider-binding",
                                domain="operation",
                                target=slot,
                                line=field.lineno,
                            )
                for method in item.body:
                    if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if method.name.startswith("test") or method.name in (
                            "setUp",
                            "tearDown",
                            "setUpClass",
                            "tearDownClass",
                            "doCleanups",
                            "addCleanup",
                        ):
                            method_id = node(
                                "method:" + path + ":" + item.name + "." + method.name,
                                "test-method"
                                if method.name.startswith("test")
                                else "fixture-method",
                                path=path,
                                lexical_name=item.name + "." + method.name,
                                discovery="static-unconfirmed",
                            )
                            edge(method_id, class_id, "member-of", path, method.lineno)
                            class_methods[class_id].append(method_id)
                            if path.startswith("server/tests/test"):
                                edge(
                                    "test-module:" + path,
                                    method_id,
                                    "contains-method",
                                    path,
                                    method.lineno,
                                )
            if isinstance(item, ast.Assign):
                value_name = _names(item.value)
                value_base = value_name.split(".")[0]
                canonical_value = (
                    aliases.get(value_base, value_base) + value_name[len(value_base) :]
                )
                if (
                    "native_catalog" in canonical_value
                    and canonical_value.rsplit(".", 1)[-1]
                    in contracts["data_call_names"]
                ):
                    for target in item.targets:
                        if isinstance(target, ast.Name):
                            aliases[target.id] = canonical_value
                    unknown(
                        owner,
                        "escaped-catalog-reader-binding",
                        domain="catalog-or-data",
                        target=canonical_value,
                        line=item.lineno,
                    )
                for target in item.targets:
                    if (
                        isinstance(target, ast.Name)
                        and target.id in contracts["family_constants"]
                    ):
                        value = _literal(item.value)
                        if isinstance(value, (tuple, list, set, dict)):
                            for family in value:
                                if type(family) is int:
                                    family_id = node(
                                        "effect-family:" + str(family),
                                        "effect-family",
                                        qualification="structural",
                                    )
                                    edge(
                                        owner,
                                        family_id,
                                        "registers-family",
                                        path,
                                        item.lineno,
                                    )
                                    edge(
                                        family_id,
                                        owner,
                                        "implemented-by",
                                        path,
                                        item.lineno,
                                    )
                        else:
                            unknown(
                                owner,
                                "dynamic-family-registration",
                                domain="operation",
                                target=target.id,
                                line=item.lineno,
                            )
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                for kind, literals in contracts["semantic_literals"].items():
                    if item.value in literals:
                        identity = node(
                            kind + ":" + item.value,
                            kind,
                            qualification="literal-candidate",
                        )
                        edge(
                            owner,
                            identity,
                            "mentions-" + kind,
                            path,
                            item.lineno,
                            "literal-candidate",
                        )
            if isinstance(item, ast.Call):
                expression = _names(item.func)
                base = expression.split(".")[0]
                resolved_expression = aliases.get(base, base) + expression[len(base) :]
                leaf = resolved_expression.rsplit(".", 1)[-1]
                constructs_class = leaf == "type" and len(item.args) >= 3
                assigns_test = (
                    leaf == "setattr"
                    and len(item.args) >= 2
                    and isinstance(_literal(item.args[1]), str)
                    and _literal(item.args[1]).startswith("test")
                )
                if path.startswith("server/tests/test") and (
                    constructs_class or assigns_test
                ):
                    unknown(owner, "dynamic-test-construction", line=item.lineno)
                if leaf in contracts.get("provider_classes", []):
                    for keyword in item.keywords:
                        unknown(
                            owner,
                            "injected-provider-expression",
                            domain="operation",
                            target=keyword.arg,
                            line=item.lineno,
                        )
                if expression == "__import__" or expression.endswith("import_module"):
                    target = _literal(item.args[0]) if item.args else None
                    targets = index.get(target, ()) if isinstance(target, str) else ()
                    if targets:
                        for dependency in targets:
                            edge(
                                owner,
                                "module:" + dependency,
                                "literal-dynamic-import",
                                path,
                                item.lineno,
                            )
                    else:
                        unknown(
                            owner,
                            "unresolved-dynamic-import",
                            domain="source-unbounded",
                            target=target,
                            line=item.lineno,
                        )
                elif expression in ("exec", "eval"):
                    unknown(
                        owner,
                        "dynamic-code-or-import",
                        target=str(_literal(item.args[0])) if item.args else None,
                        line=item.lineno,
                    )
                catalog_call = (
                    "native_catalog" in resolved_expression
                    or "protocol_catalog" in expression
                )
                if catalog_call and leaf == "_database":
                    unknown(
                        owner, "direct-catalog-sql", domain="catalog", line=item.lineno
                    )
                    edge(
                        owner,
                        "domain:catalog",
                        "unknown-catalog-dependency",
                        path,
                        item.lineno,
                    )
                if leaf in contracts["data_call_names"]:
                    reader_base = expression.split(".")[0]
                    reader_bindings = [
                        value
                        for value in ast.walk(tree)
                        if reader_base in _bound_names(value)
                    ]
                    # A canonical import must be the sole binding of the reader base.
                    # Function/class definitions and other string-valued binders also shadow it.
                    reader_shadowed = (
                        len(reader_bindings) != 1
                        or not isinstance(
                            reader_bindings[0], (ast.Import, ast.ImportFrom)
                        )
                        or any(
                            isinstance(value, ast.Attribute)
                            and isinstance(value.ctx, (ast.Store, ast.Del))
                            and _names(value) == expression
                            for value in ast.walk(tree)
                        )
                    )
                    strict_published = (
                        resolved_expression in published_readers
                        and not reader_shadowed
                        and not _reflective_reader_write(
                            tree, aliases, published_readers
                        )
                    )
                    if (
                        leaf == "read_published_bytes"
                        and catalog_call
                        and not strict_published
                    ):
                        unknown(
                            owner,
                            "unqualified-published-reader",
                            domain="source-unbounded",
                            line=item.lineno,
                            fallback="owner-consumers"
                            if path in isolated_fixtures
                            else "full",
                        )
                        continue
                    data = (
                        _data_path(
                            item.args[0],
                            path,
                            _lexical_bindings(tree, item, parents, bindings),
                        )
                        if item.args
                        else (
                            _data_path(
                                item.func.value,
                                path,
                                _lexical_bindings(tree, item, parents, bindings),
                            )
                            if isinstance(item.func, ast.Attribute)
                            else None
                        )
                    )
                    if strict_published:
                        literal_name = _literal(item.args[0]) if item.args else None
                        data = (
                            "server/protocol/" + literal_name
                            if isinstance(literal_name, str)
                            and literal_name
                            and "\\" not in literal_name
                            and "\0" not in literal_name
                            and all(
                                part not in ("", ".", "..")
                                for part in literal_name.split("/")
                            )
                            else None
                        )
                    if (
                        data is None
                        and catalog_call
                        and item.args
                        and not strict_published
                    ):
                        literal_path = _literal(item.args[0])
                        if (
                            isinstance(literal_path, str)
                            and literal_path.endswith(".json")
                            and not Path(literal_path).is_absolute()
                            and ".." not in Path(literal_path).parts
                        ):
                            data = "server/protocol/" + literal_path
                    if data:
                        data_id = _path_node(data)
                        node(
                            data_id,
                            "catalog-document"
                            if data.startswith("server/protocol/")
                            else "input",
                            path=data,
                        )
                        edge(
                            owner,
                            data_id,
                            "reads-catalog" if catalog_call else "reads-input",
                            path,
                            item.lineno,
                        )
                        if leaf == "record" and len(item.args) >= 3:
                            collection, key = _literal(item.args[1]), _literal(
                                item.args[2]
                            )
                            if isinstance(collection, str) and isinstance(
                                key, (str, int)
                            ):
                                record_id = node(
                                    data_id + ":record:" + collection + ":" + str(key),
                                    "catalog-record",
                                    granularity="document-conservative",
                                )
                                edge(
                                    owner, record_id, "reads-record", path, item.lineno
                                )
                                edge(
                                    record_id,
                                    data_id,
                                    "contained-in",
                                    path,
                                    item.lineno,
                                )
                    elif catalog_call:
                        rooted = item.args and any(
                            isinstance(value, ast.Name) and value.id == "DATA_ROOT"
                            for value in ast.walk(item.args[0])
                        )
                        unknown(
                            owner,
                            "published-catalog-domain"
                            if strict_published
                            else "dynamic-catalog-path",
                            domain="catalog"
                            if strict_published or rooted
                            else "catalog-or-data",
                            line=item.lineno,
                        )
                        edge(
                            owner,
                            "domain:catalog",
                            "unknown-catalog-dependency",
                            path,
                            item.lineno,
                        )
                    elif leaf in ("read_bytes", "read_text", "open"):
                        enclosing = parents.get(item)
                        while enclosing is not None and not isinstance(
                            enclosing, (ast.FunctionDef, ast.AsyncFunctionDef)
                        ):
                            enclosing = parents.get(enclosing)
                        parameters = set()
                        if enclosing is not None:
                            parameters = {
                                argument.arg
                                for argument in [
                                    *enclosing.args.posonlyargs,
                                    *enclosing.args.args,
                                    *enclosing.args.kwonlyargs,
                                ]
                            }
                        argument_names = {
                            value.id
                            for value in ast.walk(item)
                            if isinstance(value, ast.Name)
                        }
                        forwarded = sorted(
                            (parameters - {"self", "cls"}) & argument_names
                        )
                        if forwarded:
                            positional = [
                                argument.arg
                                for argument in [
                                    *enclosing.args.posonlyargs,
                                    *enclosing.args.args,
                                ]
                            ]
                            summary_key = (path, enclosing.name)
                            if positional and positional[0] in ("self", "cls"):
                                reader_methods.add(summary_key)
                            reader_parameters[summary_key] = positional
                            reader_summaries.setdefault(summary_key, set()).update(
                                positional.index(name) if name in positional else name
                                for name in forwarded
                            )
                            unknown(
                                owner,
                                "parameterized-input-reader",
                                domain="data-parameter",
                                target=",".join(forwarded),
                                line=item.lineno,
                            )
                        else:
                            unknown(
                                owner,
                                "unresolved-input-path",
                                domain="data",
                                line=item.lineno,
                            )
            environment_name = None
            default = None
            if (
                isinstance(item, ast.Call)
                and resolved_expression in ("os.environ.get", "os.getenv")
                and item.args
            ):
                environment_name = _literal(item.args[0])
                default = _literal(item.args[1]) if len(item.args) > 1 else None
            elif isinstance(item, ast.Subscript):
                raw_environment = _names(item.value)
                base = raw_environment.split(".")[0]
                canonical_environment = (
                    aliases.get(base, base) + raw_environment[len(base) :]
                )
                if canonical_environment == "os.environ":
                    environment_name = _literal(item.slice)
                    if not isinstance(environment_name, str):
                        unknown(
                            owner,
                            "dynamic-runtime-policy-name",
                            domain="environment-unbounded",
                            line=item.lineno,
                        )
            environment_reads = (
                [(environment_name, default)]
                if isinstance(environment_name, str)
                else None
            )
            if (
                isinstance(item, ast.Call)
                and resolved_expression in ("os.environ.get", "os.getenv")
                and environment_reads is None
            ):
                environment_reads = _finite_environment_reads(
                    item, tree, parents, bindings, imports, root
                )
                if environment_reads is None:
                    unknown(
                        owner,
                        "dynamic-runtime-policy-name",
                        domain="environment-unbounded",
                        line=item.lineno,
                    )
            for environment_name, default in environment_reads or ():
                private = _private_policy(environment_name)
                identity = node(
                    "runtime-policy:" + environment_name,
                    "runtime-policy",
                    available=environment_name in os.environ,
                    value_identity=None
                    if private
                    else canonical_digest(os.environ.get(environment_name, default)),
                    qualification="availability-only-private-input"
                    if private
                    else "nonsecret-policy-identity",
                )
                edge(owner, identity, "reads-runtime-policy", path, item.lineno)
                if private:
                    unknown(
                        owner,
                        "private-environment-input-not-content-bound",
                        domain="environment-private",
                        target=environment_name,
                        line=item.lineno,
                    )
            if isinstance(item, ast.Compare) and _names(item.left).rsplit(".", 1)[
                -1
            ] in ("opcode", "message_id", "packet_id"):
                for value_node in item.comparators:
                    value = _literal(value_node)
                    values = value if isinstance(value, (list, tuple, set)) else [value]
                    for opcode in values:
                        if type(opcode) is int:
                            op_id = node(
                                "opcode:direction-unknown:" + str(opcode),
                                "opcode",
                                direction="unknown",
                                qualification="branch-candidate",
                            )
                            edge(owner, op_id, "opcode-branch", path, item.lineno)
    # A parameterized reader is a summary, not a global wildcard. Resolve
    # its actual arguments at call sites; unresolved arguments stay unknown.
    covered_readers = set()

    def resolve_reader(target, seen=None):
        seen = set() if seen is None else seen
        if target in seen:
            return []
        seen.add(target)
        if target in reader_summaries:
            return [target]
        path, symbol = target
        result = []
        for forwarded in imported_symbols.get(path, {}).get(symbol, []):
            result.extend(resolve_reader(forwarded, seen))
        return result

    for path, tree in trees.items():
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        for reference in (
            item
            for item in ast.walk(tree)
            if isinstance(item, (ast.Name, ast.Attribute))
        ):
            expression = _names(reference)
            if (
                not expression
                or isinstance(parents.get(reference), ast.Call)
                and parents[reference].func is reference
            ):
                continue
            candidates = [(path, expression)] + imported_symbols[path].get(
                expression, []
            )
            if "." in expression:
                head, symbol = expression.split(".", 1)
                candidates.extend(
                    (dependency, symbol)
                    for dependency in imported_modules[path].get(head, [])
                )
            for target in [
                resolved
                for candidate in candidates
                for resolved in resolve_reader(candidate)
            ]:
                unknown(
                    "module:" + path,
                    "escaped-parameterized-reader",
                    domain="data",
                    target=target[1],
                    line=getattr(reference, "lineno", None),
                )
        bindings = {
            target.id: assignment.value
            for assignment in tree.body
            if isinstance(assignment, ast.Assign)
            for target in assignment.targets
            if isinstance(target, ast.Name)
        }
        for call in (item for item in ast.walk(tree) if isinstance(item, ast.Call)):
            expression = _names(call.func)
            targets = []
            if "." not in expression:
                targets.append((path, expression))
                targets.extend(imported_symbols[path].get(expression, []))
            else:
                head, symbol = expression.split(".", 1)
                targets.extend(
                    (dependency, symbol)
                    for dependency in imported_modules[path].get(head, [])
                )
            targets = [
                resolved for target in targets for resolved in resolve_reader(target)
            ]
            for target in targets:
                covered_readers.add(target)
                for position in reader_summaries.get(target, ()):
                    parameter_name = (
                        reader_parameters[target][position]
                        if type(position) is int
                        else position
                    )
                    argument = (
                        call.args[position]
                        if type(position) is int and position < len(call.args)
                        else next(
                            (
                                keyword.value
                                for keyword in call.keywords
                                if keyword.arg == parameter_name
                            ),
                            None,
                        )
                    )
                    if argument is None:
                        unknown(
                            "module:" + path,
                            "unresolved-reader-argument",
                            domain="data",
                            target=target[1] + ":" + parameter_name,
                            line=call.lineno,
                        )
                        continue
                    data = _data_path(
                        argument, path, _lexical_bindings(tree, call, parents, bindings)
                    )
                    if data:
                        data_id = _path_node(data)
                        node(
                            data_id,
                            "catalog-document"
                            if data.startswith("server/protocol/")
                            else "input",
                            path=data,
                        )
                        edge(
                            "module:" + path,
                            data_id,
                            "parameterized-reader-argument",
                            path,
                            call.lineno,
                        )
                    else:
                        # Already classified native readers retain their
                        # catalog-domain declaration instead of a second
                        # unbounded filesystem dependency.
                        if "native_catalog" not in target[0]:
                            unknown(
                                "module:" + path,
                                "unresolved-reader-argument",
                                domain="data",
                                target=target[1],
                                line=call.lineno,
                            )
    for target in reader_summaries:
        if "native_catalog" not in target[0] and (
            target not in covered_readers or target in reader_methods
        ):
            unknown(
                "module:" + target[0],
                "unresolved-parameterized-reader-callers",
                domain="data",
                target=target[1],
            )
    for class_id, bases in class_bases.items():
        for path, base in bases:
            resolved = []
            if (path, base) in class_paths:
                resolved.append(class_paths[(path, base)])
            for imported_path, symbol in imported_symbols[path].get(base, []):
                if (imported_path, symbol) in class_paths:
                    resolved.append(class_paths[(imported_path, symbol)])
            if "." in base:
                head, tail = base.split(".", 1)
                for imported_path in imported_modules[path].get(head, []):
                    candidate = class_paths.get((imported_path, tail))
                    if candidate:
                        resolved.append(candidate)
            if resolved:
                for dependency in resolved:
                    edge(class_id, dependency, "inherits", path)
                    # A subclass receives the base's methods and fixtures.
                    edge(
                        "module:" + path, dependency, "inherited-fixture-or-test", path
                    )
            elif base not in (
                "unittest.TestCase",
                "TestCase",
                "object",
                "Exception",
                "ValueError",
                "RuntimeError",
                "tuple",
                "dict",
                "list",
                "Enum",
                "IntEnum",
                "Protocol",
                "Generic",
            ):
                unknown("module:" + path, "unresolved-base-class", target=base)
    # Materialize inherited method identities without executing unittest
    # discovery. They remain explicitly unconfirmed until a runner receipt.
    inheritance = defaultdict(set)
    for declaration in edges.values():
        if declaration["kind"] == "inherits":
            inheritance[declaration["consumer"]].add(declaration["dependency"])
    for child in class_bases:
        child_path = nodes[child]["path"]
        if not child_path.startswith("server/tests/test"):
            continue
        pending, visited = deque(inheritance[child]), set()
        local_names = {
            nodes[method]["lexical_name"].rsplit(".", 1)[-1]
            for method in class_methods[child]
        }
        while pending:
            parent = pending.popleft()
            if parent in visited:
                continue
            visited.add(parent)
            for method in class_methods[parent]:
                name = nodes[method]["lexical_name"].rsplit(".", 1)[-1]
                if not name.startswith("test") or name in local_names:
                    continue
                inherited = node(
                    "method:" + child_path + ":" + nodes[child]["name"] + "." + name,
                    "test-method",
                    path=child_path,
                    lexical_name=nodes[child]["name"] + "." + name,
                    discovery="inherited-static-unconfirmed",
                    inherited_from=method,
                )
                edge(inherited, method, "inherits-test-method", child_path)
                edge(
                    "test-module:" + child_path,
                    inherited,
                    "contains-inherited-method",
                    child_path,
                )
                local_names.add(name)
            pending.extend(sorted(inheritance[parent]))
    reviewed_paths = defaultdict(int)
    for declaration in contracts.get("test_classifications", []):
        if isinstance(declaration, dict) and isinstance(declaration.get("path"), str):
            reviewed_paths[declaration["path"]] += 1
    for declaration in contracts.get("test_classifications", []):
        if not isinstance(declaration, dict):
            continue
        test_id = "test-module:" + str(declaration.get("path"))
        if test_id not in nodes:
            continue
        review = _classification_review(declaration, files, trees, nodes, inheritance)
        if reviewed_paths[declaration["path"]] > 1:
            review.update(
                kind="unknown",
                status="unqualified-source-review",
                errors=sorted(
                    set(review["errors"] + ["duplicate-classification-reviews"])
                ),
            )
        nodes[test_id].update(
            test_kind=review["kind"],
            classification_evidence=review["assertion_witnesses"]
            + review["inheritance_evidence"],
            classification_review=review,
        )
    migration_sha, migration_families, migration_errors = _migration_source_contracts(
        root, {operation["id"] for operation in registry_operations}
    )
    migration_node = "module:" + MIGRATION_REGISTRY_PATH
    for reason in migration_errors:
        unknown(migration_node, reason, domain="source-unbounded", fallback="full")
    families = {family["name"]: family for family in migration_families}
    for name, family in families.items():
        identity = node(
            "migration-family:" + name,
            "migration-family",
            backend_attribute=family["backend_attribute"],
            operation_ids=family["operation_ids"],
            components=family["components"],
            contract_sha256=family["contract_sha256"],
            qualification="source-declared-not-execution-proof",
        )
        edge(
            identity,
            migration_node,
            "migration-policy",
            MIGRATION_REGISTRY_PATH,
            family["line"],
            confidence="source-literal",
        )
        for operation in family["operation_ids"]:
            edge(
                "operation:" + operation,
                identity,
                "uses-migration-family",
                MIGRATION_REGISTRY_PATH,
                family["line"],
                confidence="source-literal",
            )
        for component in family["components"]:
            component_path = "server/wakfu_server/combat/" + component + ".py"
            if component_path not in files:
                unknown(
                    identity,
                    "migration-component-outside-source-manifest",
                    domain="source-unbounded",
                    target=component_path,
                    fallback="full",
                )
                continue
            edge(
                identity,
                "module:" + component_path,
                "migration-shared-component",
                MIGRATION_REGISTRY_PATH,
                family["line"],
                confidence="source-literal",
            )
    if families:
        for path, tree in trees.items():
            if path == MIGRATION_REGISTRY_PATH:
                continue
            for call in ast.walk(tree):
                if not isinstance(call, ast.Call):
                    continue
                expression = _names(call.func)
                bindings = list(imported_symbols.get(path, {}).get(expression, ()))
                if "." in expression:
                    head, symbol = expression.split(".", 1)
                    bindings.extend(
                        (source, symbol)
                        for source in imported_modules.get(path, {}).get(head, ())
                    )
                methods = {
                    symbol
                    for source, symbol in bindings
                    if source == MIGRATION_REGISTRY_PATH
                    and symbol
                    in (
                        "resolve_backend",
                        "family_backend_scope",
                        "operation_contracts",
                    )
                }
                if not methods:
                    continue
                method = next(iter(methods))
                if method in ("resolve_backend", "operation_contracts"):
                    argument_index = 1 if method == "resolve_backend" else 0
                    argument = (
                        call.args[argument_index]
                        if len(call.args) > argument_index
                        else next(
                            (
                                value.value
                                for value in call.keywords
                                if value.arg == "family"
                            ),
                            None,
                        )
                    )
                    literal = _literal(argument)
                    requested = (
                        [literal] if isinstance(literal, str) else list(families)
                    )
                else:
                    argument = (
                        call.args[0]
                        if call.args
                        else next(
                            (
                                value.value
                                for value in call.keywords
                                if value.arg == "backends"
                            ),
                            None,
                        )
                    )
                    literal = _literal(argument)
                    requested = (
                        list(literal) if isinstance(literal, dict) else list(families)
                    )
                runtime = (
                    path.startswith("server/wakfu_server/combat/")
                    or path == "server/local_game_server.py"
                )
                for name in requested:
                    if not isinstance(name, str) or name not in families:
                        # Invalid-family negative tests are not unknown live
                        # producers. Their import still binds policy changes.
                        if runtime:
                            unknown(
                                "module:" + path,
                                "migration-caller-family-unknown",
                                domain="source-unbounded",
                                target=str(name),
                                line=call.lineno,
                                fallback="full",
                            )
                        continue
                    family_node = "migration-family:" + name
                    module_node = "module:" + path
                    producer = runtime and method != "operation_contracts"
                    edge(
                        family_node if producer else module_node,
                        module_node if producer else family_node,
                        "migration-runtime-boundary"
                        if producer
                        else "migration-family-consumer",
                        path,
                        call.lineno,
                        confidence="source-literal"
                        if literal is not None
                        else "dynamic-all-declared-families",
                    )
    operation_interaction_errors = []
    interaction_ids = set()
    exact_registry_ids = {operation["id"] for operation in registry_operations}
    declarations = contracts.get("operation_interactions", [])
    if not isinstance(declarations, list):
        declarations = []
        operation_interaction_errors.append("interaction-declarations-not-list")
    has_interaction_source = any(
        isinstance(row, dict)
        and isinstance(row.get("test_dependencies"), list)
        and any(
            isinstance(dependency, dict)
            and isinstance(dependency.get("path"), str)
            and dependency["path"] in files
            for dependency in row["test_dependencies"]
        )
        for row in declarations
    )
    if registry_sha is None and not has_interaction_source:
        # An older or isolated tree with neither registry nor these test
        # sources cannot consume later source-bound interaction declarations.
        declarations = []
    for declaration in declarations:
        errors = []
        if not isinstance(declaration, dict):
            operation_interaction_errors.append("interaction-declaration-not-object")
            continue
        identity = declaration.get("id")
        operations = declaration.get("operation_ids")
        dependencies = declaration.get("test_dependencies")
        if (
            not isinstance(identity, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", identity)
            or identity in interaction_ids
        ):
            errors.append("interaction-id-invalid-or-duplicate")
        else:
            interaction_ids.add(identity)
        if declaration.get("status") != "source-bound-interaction":
            errors.append("interaction-status-unqualified")
        if (
            not isinstance(operations, list)
            or not operations
            or any(
                operation not in exact_registry_ids
                for operation in operations
                if isinstance(operation, str)
            )
            or any(not isinstance(operation, str) for operation in operations or [])
        ):
            errors.append("interaction-operation-unavailable")
        if (
            not isinstance(declaration.get("source_ids"), list)
            or not declaration["source_ids"]
            or any(
                not isinstance(value, str) or not value
                for value in declaration["source_ids"]
            )
        ):
            errors.append("interaction-source-identities-missing")
        if (
            not isinstance(declaration.get("scope"), str)
            or not declaration["scope"].strip()
        ):
            errors.append("interaction-scope-missing")
        if not isinstance(dependencies, list) or not dependencies:
            dependencies = []
            errors.append("interaction-test-dependencies-missing")
        for dependency in dependencies:
            if not isinstance(dependency, dict):
                errors.append("interaction-test-dependency-invalid")
                continue
            path = dependency.get("path")
            witnesses = dependency.get("assertion_witnesses")
            test_tree = trees.get(path) if isinstance(path, str) else None
            if (
                not isinstance(path, str)
                or "test-module:" + path not in nodes
                or not dependency.get("source_sha256")
                or files.get(path) != dependency["source_sha256"]
            ):
                errors.append("interaction-test-source-missing-or-stale")
            if (
                not isinstance(witnesses, list)
                or not witnesses
                or any(not _symbol_exists(test_tree, witness) for witness in witnesses)
            ):
                errors.append("interaction-test-witness-missing")
        if errors:
            operation_interaction_errors.extend(
                str(identity) + ":" + error for error in errors
            )
            continue
        interaction = node(
            "operation-interaction:" + identity,
            "operation-interaction",
            qualification="source-bound-interaction-not-accreditation",
            declaration_sha256=canonical_digest(declaration),
            source_ids=declaration["source_ids"],
            scope=declaration["scope"],
        )
        for operation in operations:
            edge(
                interaction,
                "operation:" + operation,
                "researched-operation-interaction",
                confidence="source-bound-selection-only",
            )
        for dependency in dependencies:
            edge(
                "test-module:" + dependency["path"],
                interaction,
                "source-bound-interaction-test",
                dependency["path"],
                confidence="source-and-symbol-bound-not-accreditation",
            )
    for error in operation_interaction_errors:
        unknown(registry_node, error, domain="source-unbounded", fallback="full")
    if scenarios:
        for source_entry in scenarios.get("sources", []):
            node(
                "guide-source:" + source_entry["id"],
                "guide-intent",
                sha256=canonical_digest(source_entry),
            )
        for scenario in scenarios.get("scenarios", []):
            identity = node(
                "scenario:" + scenario["id"],
                "scenario",
                status=scenario.get("status"),
                acceptance_status="unqualified-source-scenario",
                sha256=canonical_digest(scenario),
            )
            for operation in contracts.get("scenario_operations", {}).get(
                scenario["id"], []
            ):
                op = "operation:" + operation
                if op in nodes:
                    edge(
                        identity,
                        op,
                        "candidate-usage-operation",
                        confidence="declared-intent",
                    )
            for reference_kind, values in scenario.get("native_refs", {}).items():
                values = values if isinstance(values, list) else [values]
                for reference in values:
                    if type(reference) is int:
                        ref_id = node(
                            "native-reference:"
                            + scenario["id"]
                            + ":"
                            + reference_kind
                            + ":"
                            + str(reference),
                            "native-reference",
                            qualification="scenario-declared-unqualified",
                            reference=reference,
                        )
                        edge(
                            identity,
                            ref_id,
                            "declared-native-reference",
                            confidence="declared-partial",
                        )
            for candidate in scenario.get("test_candidates", []):
                if "test-module:" + candidate in nodes:
                    edge(
                        "test-module:" + candidate,
                        identity,
                        "candidate-scenario-test",
                        candidate,
                        confidence="candidate-not-accredited",
                    )
            for source_id in scenario.get("source_ids", []):
                source_id = node("guide-source:" + source_id, "guide-intent")
                edge(identity, source_id, "usage-intent", confidence="declared-intent")
            for path in scenario.get("mapping_evidence", []):
                if path in files:
                    edge(
                        identity,
                        "module:" + path,
                        "mapping-evidence",
                        path,
                        confidence="declared-partial",
                    )
                    if path.startswith("server/tests/test"):
                        edge(
                            "test-module:" + path,
                            identity,
                            "scenario-mapping",
                            path,
                            confidence="declared-partial",
                        )
            if scenario.get("unresolved"):
                unknown(
                    identity,
                    "partial-native-scenario-mapping",
                    domain="scenario",
                    target=scenario["id"],
                )
    scenario_rows = {row["id"]: row for row in (scenarios or {}).get("scenarios", [])}
    guide_rows = {row["id"]: row for row in (scenarios or {}).get("sources", [])}
    for declaration in contracts.get("accepted_scenarios", []):
        if not isinstance(declaration, dict) or not isinstance(
            declaration.get("id"), str
        ):
            continue
        identity = node(
            "scenario:" + declaration["id"],
            "scenario",
            acceptance_status="unqualified-source-scenario",
        )
        review = _accepted_scenario_review(
            declaration,
            scenario_rows.get(declaration.get("source_scenario_id")),
            guide_rows,
            root,
            files,
            trees,
            nodes,
            catalog,
        )
        nodes[identity].update(
            acceptance_status=review["status"], acceptance_review=review
        )
        for proof in review["evidence"]:
            evidence_id = _path_node(proof["path"])
            node(evidence_id, "input", path=proof["path"], sha256=proof["sha256"])
            edge(
                identity,
                evidence_id,
                "bounded-scenario-evidence",
                proof["path"],
                confidence="hash-bound-reviewed",
            )
        if review["status"] == "qualified-bounded-interaction":
            for operation in review["operation_ids"]:
                edge(
                    identity,
                    "operation:" + operation,
                    "verified-bounded-operation",
                    confidence="reviewed-terminal-receipt",
                )
            for path in declaration["implementation_dependencies"]:
                edge(
                    identity,
                    "module:" + path,
                    "bounded-implementation-dependency",
                    path,
                    confidence="source-hash-bound",
                )
            for dependency in declaration["test_dependencies"]:
                edge(
                    "test-module:" + dependency["path"],
                    identity,
                    "asserts-bounded-guide-interaction",
                    dependency["path"],
                    confidence="reviewed-terminal-receipt",
                )
            for name in review["native_documents"]:
                edge(
                    identity,
                    "catalog:" + name,
                    "bounded-native-document",
                    confidence="published-hash-bound",
                )
        else:
            unknown(
                identity,
                "accepted-scenario-evidence-unqualified",
                domain="scenario",
                target=declaration["id"],
            )
    policy = dict(DEFAULT_RUNNER_POLICY if runner_policy is None else runner_policy)
    policy_inputs = runtime_policy_inputs(
        [
            identity.removeprefix("runtime-policy:")
            for identity in nodes
            if identity.startswith("runtime-policy:")
        ]
    )
    graph = {
        "schema": SCHEMA,
        "mode": "observation",
        "builder": {
            "sha256": _sha(Path(__file__).read_bytes()),
            "contracts_sha256": _sha(contracts_raw),
        },
        "provenance": {
            **policy_inputs,
            "builder_sha256": _sha(Path(__file__).read_bytes()),
            "contracts_sha256": _sha(contracts_raw),
            "source_manifest_sha256": source["sha256"],
            "catalog_inventory_sha256": catalog.get("sha256"),
            "catalog_revision": catalog.get("revision"),
            "catalog_status": catalog.get("status"),
            "catalog_publication_verified": catalog.get("publication_verified") is True,
            "environment_sha256": environment["sha256"],
            "scenario_manifest_sha256": scenario_sha,
            "runner_sha256": files.get("server/tools/combat_validation_profile.py"),
            "runner_policy": policy,
            "snapshot_status": source.get("validation_snapshot", {}).get("status"),
        },
        "module_names": sorted(module_names),
        "nodes": sorted(nodes.values(), key=lambda row: row["id"]),
        "edges": sorted(
            edges.values(),
            key=lambda row: (
                row["consumer"],
                row["dependency"],
                row["kind"],
                str(row["evidence"]),
            ),
        ),
        "unknowns": sorted(unknowns, key=canonical_digest),
        "classification_summary": {
            kind: sum(
                row.get("kind") == "test-module" and row.get("test_kind") == kind
                for row in nodes.values()
            )
            for kind in sorted(TEST_KINDS)
        },
        "accepted_scenario_count": sum(
            row.get("kind") == "scenario"
            and row.get("acceptance_status") == "qualified-bounded-interaction"
            for row in nodes.values()
        ),
        "test_kind_categories": sorted(TEST_KINDS),
        "global_invalidation": contracts["global_invalidation"],
        "limitations": [
            "Static/declared reachability is conservative and does not certify behavioral assertions.",
            "Method inventory is static; dynamic discovery and inherited fixtures remain explicit.",
            "Observation mode never suppresses execution or reuses results.",
            "Protocol opcode direction is unknown unless separately declared; guide sources are usage intent.",
            "Private runtime data, external/JAR oracles and public probes outside the supplied source/snapshot manifest are unqualified inputs; unchanged graphs do not prove their freshness.",
            "Private environment values are never hashed or emitted; availability-only bindings cannot prove backend or policy equivalence.",
        ],
    }
    graph["operation_registry"] = {
        "path": OPERATION_REGISTRY_PATH,
        "source_sha256": registry_sha,
        "common_implementation_sha256": registry_common_sha,
        "errors": registry_errors,
        "operation_ids": sorted(operation["id"] for operation in registry_operations),
    }
    graph["migration_registry"] = {
        "path": MIGRATION_REGISTRY_PATH,
        "source_sha256": migration_sha,
        "errors": migration_errors,
        "families": sorted(families),
    }
    graph["published_reader_registry"] = {
        "qualified_expressions": sorted(published_readers),
        "errors": published_reader_errors,
    }
    graph["isolated_reader_fixture_registry"] = {
        "qualified": isolated_fixtures,
        "errors": isolated_fixture_errors,
    }
    if require_observed_execution_context:
        contexts = {
            canonical_digest(row["observed_execution_context"]): row[
                "observed_execution_context"
            ]
            for row in isolated_fixtures.values()
        }
        if isolated_fixture_errors or len(contexts) != 1:
            raise ValueError(
                "Observed execution context is unavailable, invalid or mixed"
            )
        graph["provenance"]["required_observed_execution_context"] = next(
            iter(contexts.values())
        )
    graph["operation_interaction_errors"] = sorted(set(operation_interaction_errors))
    graph["sha256"] = canonical_digest(graph)
    return graph


def _bound_names(node):
    if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
        return (node.id,)
    if isinstance(node, ast.arg):
        return (node.arg,)
    if isinstance(node, ast.Import):
        return tuple(value.asname or value.name.split(".")[0] for value in node.names)
    if isinstance(node, ast.ImportFrom):
        return tuple(value.asname or value.name for value in node.names)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return (node.name,)
    if isinstance(node, ast.ExceptHandler) and node.name:
        return (node.name,)
    if isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
        return (node.name,)
    if isinstance(node, ast.MatchMapping) and node.rest:
        return (node.rest,)
    return ()


def _lexical_bindings(tree, item, parents, module_bindings):
    """Resolve single unconditional assignments preceding a read, never execute.

    Branch/repeated writes, parameters and nested scopes cannot inherit a
    same-named module binding. Unknown locals remain explicitly unresolved.
    """
    scope = item
    while scope is not None and not isinstance(
        scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
    ):
        scope = parents.get(scope)
    result = dict(module_bindings)
    for name in tuple(result):
        if sum(name in _bound_names(value) for value in ast.walk(tree)) != 1 or any(
            isinstance(value, (ast.Global, ast.Nonlocal)) and name in value.names
            for value in ast.walk(tree)
        ):
            result.pop(name, None)
    if scope is None:
        return result
    outer = parents.get(scope)
    while outer is not None:
        if isinstance(outer, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            for value in ast.walk(outer):
                for name in _bound_names(value):
                    result.pop(name, None)
        outer = parents.get(outer)
    blocked = {
        name
        for value in ast.walk(scope)
        if isinstance(value, (ast.Global, ast.Nonlocal))
        for name in value.names
    }
    for name in blocked:
        result.pop(name, None)
    writes = {}

    def visit(node):
        if node is not scope:
            for name in _bound_names(node):
                writes.setdefault(name, []).append(node)
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
            ):
                return
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(scope)
    for name in writes:
        result.pop(name, None)
    body = getattr(scope, "body", ())
    for assignment in body if isinstance(body, (list, tuple)) else ():
        if (
            isinstance(assignment, ast.Assign)
            and len(assignment.targets) == 1
            and isinstance(assignment.targets[0], ast.Name)
            and assignment.lineno < item.lineno
            and len(writes.get(assignment.targets[0].id, ())) == 1
            and assignment.targets[0].id not in blocked
        ):
            result[assignment.targets[0].id] = assignment.value
    return result


def _finite_environment_reads(call, tree, parents, bindings, imports, root):
    """Resolve only inline/local immutable tuples; mutable/imported maps stay unknown."""
    scoped = _lexical_bindings(tree, call, parents, bindings)

    def immutable(value):
        return (
            value is None
            or type(value) in (str, int, bool)
            or type(value) is tuple
            and all(immutable(cell) for cell in value)
        )

    def constant(node):
        if isinstance(node, ast.Name):
            node = scoped.get(node.id)
            if node is None:
                raise ValueError("Imported or unknown policy collection")
        value = ast.literal_eval(node)
        if type(value) is not tuple or not immutable(value) or len(value) > 128:
            raise ValueError("Mutable or unbounded policy collection")
        return value

    def expression(node, values):
        if isinstance(node, ast.Constant) and (
            node.value is None or type(node.value) in (str, int, bool)
        ):
            return node.value
        if isinstance(node, ast.Name) and node.id in values:
            return values[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = expression(node.left, values), expression(node.right, values)
            if type(left) is str and type(right) is str:
                return left + right
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("upper", "lower")
            and not node.args
            and not node.keywords
        ):
            value = expression(node.func.value, values)
            if type(value) is str:
                return value.upper() if node.func.attr == "upper" else value.lower()
        raise ValueError("Unbounded policy expression")

    ancestor = call
    generators = []
    while ancestor is not None and not isinstance(
        ancestor, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
    ):
        ancestor = parents.get(ancestor)
        if isinstance(ancestor, ast.For):
            generators.append((ancestor.target, ancestor.iter))
        elif isinstance(
            ancestor, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        ):
            generators.extend(
                (generator.target, generator.iter) for generator in ancestor.generators
            )
    results = set()
    try:
        for target, iterable in generators:
            names = [
                value.id for value in ast.walk(target) if isinstance(value, ast.Name)
            ]
            enclosing = call
            while enclosing is not None and not isinstance(
                enclosing, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                enclosing = parents.get(enclosing)
            domain = enclosing if enclosing is not None else tree
            candidate_scope = parents.get(target)
            if isinstance(candidate_scope, ast.comprehension):
                domain = parents.get(candidate_scope, domain)
            for name in names:
                if (
                    sum(
                        isinstance(value, ast.Name)
                        and value.id == name
                        and isinstance(value.ctx, (ast.Store, ast.Del))
                        for value in ast.walk(domain)
                    )
                    != 1
                ):
                    raise ValueError("Reassigned loop policy")
            for row in constant(iterable):
                if isinstance(target, ast.Name):
                    values = {target.id: row}
                elif isinstance(target, (ast.Tuple, ast.List)) and all(
                    isinstance(value, ast.Name) for value in target.elts
                ):
                    if type(row) is not tuple or len(row) != len(target.elts):
                        continue
                    values = {value.id: cell for value, cell in zip(target.elts, row)}
                else:
                    continue
                name = expression(call.args[0], values)
                if type(name) is not str or not re.fullmatch(
                    r"[A-Za-z_][A-Za-z0-9_]{0,127}", name
                ):
                    raise ValueError("Invalid literal policy name")
                default = (
                    expression(call.args[1], values) if len(call.args) > 1 else None
                )
                results.add((name, default))
    except (ValueError, TypeError, SyntaxError, RecursionError):
        return None
    return sorted(results, key=lambda value: value[0]) if results else None


def _data_path(node, owner, bindings=None, depth=0):
    """Resolve trusted literal paths, never execute an AST or inspect a client."""
    if depth > 16:
        return None

    def resolve(child):
        return _data_path(child, owner, bindings, depth + 1)

    if isinstance(node, ast.Name):
        if node.id == "__file__":
            return owner
        if node.id == "DATA_ROOT":
            return "server/protocol"
        if bindings and node.id in bindings:
            return resolve(bindings[node.id])
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        value = node.value
        if value.startswith("server/") and ".." not in Path(value).parts:
            return value
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        base = resolve(node.value)
        if base is not None:
            return Path(base).parent.as_posix()
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "parents"
    ):
        base, index = resolve(node.value.value), _literal(node.slice)
        if (
            base is not None
            and type(index) is int
            and 0 <= index < len(Path(base).parents)
        ):
            return Path(base).parents[index].as_posix()
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        value = _literal(node.right)
        if (
            isinstance(value, str)
            and ".." not in Path(value).parts
            and not Path(value).is_absolute()
        ):
            base = resolve(node.left)
            if base is not None:
                return (Path(base) / value).as_posix()
    if isinstance(node, ast.Call):
        leaf = _names(node.func).rsplit(".", 1)[-1]
        if leaf in ("Path", "PurePath") and node.args:
            return resolve(node.args[0])
        if leaf in ("resolve", "absolute") and isinstance(node.func, ast.Attribute):
            return resolve(node.func.value)
    return None


def _verify_graph(graph):
    if not isinstance(graph, dict) or graph.get("schema") != SCHEMA:
        raise ValueError("Unsupported impact graph schema")
    payload = {key: value for key, value in graph.items() if key != "sha256"}
    if graph.get("sha256") != canonical_digest(payload):
        raise ValueError("Impact graph digest mismatch")


def verify_required_execution_context(
    plan, *, actual_catalog, enforced_singleton_fixture_paths=()
):
    """Read actual child inputs before using a context-bound scope.

    Never accept an environment identity copied from expected plan labels.
    Catalog metadata must come from the runner's verified publication probe.
    """
    import sys

    required_fixtures = set(plan.get("required_isolated_reader_fixtures", {}))
    if not required_fixtures.issubset(set(enforced_singleton_fixture_paths)):
        raise ValueError("Required isolated fixture execution is not enforced")
    required = plan.get("required_observed_execution_context")
    if not required:
        return {
            "status": "no-context-qualification",
            "reuse_qualified": False,
            "required_fixture_paths": sorted(required_fixtures),
        }
    if actual_catalog.get("publication_verified") is not True:
        raise ValueError("Actual catalog authority is unavailable")
    observed = {
        "effective_environment_sha256": _sha(
            json.dumps(
                sorted(os.environ.items()), separators=(",", ":"), ensure_ascii=False
            ).encode()
        ),
        "interpreter_sha256": _sha(Path(sys.executable).read_bytes()),
        "startup_flags": {
            "isolated": bool(sys.flags.isolated),
            "no_site": bool(sys.flags.no_site),
            "ignore_environment": bool(sys.flags.ignore_environment),
        },
        "catalog_revision": actual_catalog.get("revision"),
        "catalog_inventory_sha256": actual_catalog.get("sha256"),
    }
    if any(
        required.get(field) is None or observed[field] != required[field]
        for field in observed
    ):
        raise ValueError("Actual execution context does not match the impact plan")
    return {
        "status": "actual-context-matched-before-imports",
        "reuse_qualified": False,
        "required_fixture_paths": sorted(required_fixtures),
    }


def select_changes(before, after):
    """Union before/after reverse closure, with explicit conservative fallback."""
    _verify_graph(after)
    if before is not None:
        _verify_graph(before)
    before_nodes = {row["id"]: row for row in before["nodes"]} if before else {}
    after_nodes = {row["id"]: row for row in after["nodes"]}
    changed = sorted(
        identity
        for identity in before_nodes.keys() | after_nodes.keys()
        if before_nodes.get(identity) != after_nodes.get(identity)
    )
    registry_node = "module:" + OPERATION_REGISTRY_PATH
    old_registry = before.get("operation_registry", {}) if before else {}
    new_registry = after.get("operation_registry", {})
    exact_operations = {
        "operation:" + identity
        for registry in (old_registry, new_registry)
        for identity in registry.get("operation_ids", ())
    }
    previous_context = (
        before.get("provenance", {}).get("required_observed_execution_context")
        if before
        else None
    )
    current_context = after.get("provenance", {}).get(
        "required_observed_execution_context"
    )
    matching_execution_context = bool(
        previous_context
        and previous_context == current_context
        and current_context.get("future_runner_must_match_before_imports") is True
    )
    metadata_only = bool(
        before
        and old_registry.get("common_implementation_sha256")
        and old_registry.get("common_implementation_sha256")
        == new_registry.get("common_implementation_sha256")
        and not old_registry.get("errors")
        and not new_registry.get("errors")
        and not before.get("operation_interaction_errors")
        and not after.get("operation_interaction_errors")
        and not before.get("migration_registry", {}).get("errors")
        and not after.get("migration_registry", {}).get("errors")
        and before["provenance"].get("catalog_publication_verified") is True
        and after["provenance"].get("catalog_publication_verified") is True
        and all(
            before["provenance"].get(key) == after["provenance"].get(key)
            for key in (
                "catalog_inventory_sha256",
                "catalog_revision",
                "environment_sha256",
                "runtime_policy_sha256",
                "runtime_policy_names",
                "runner_policy",
                "snapshot_status",
            )
        )
        and registry_node in changed
        and set(changed) <= exact_operations | {registry_node}
    )
    if metadata_only:
        changed.remove(registry_node)
    registry_integrity_guards = set()
    reverse = defaultdict(set)
    for graph in [before, after] if before else [after]:
        for edge in graph["edges"]:
            if metadata_only:
                # Literal contract data has its own operation fingerprint.
                # The executor's code and returned handler have not changed.
                # Its ordinary runtime import fanout therefore is not evidence
                # of a metadata dependency. Contract tests and registry/tool
                # integrity consumers remain explicit metadata consumers.
                if edge["dependency"] == registry_node:
                    consumer = edge["consumer"]
                    row = after_nodes.get(consumer, before_nodes.get(consumer, {}))
                    if row.get("category") in ("test", "test-helper", "tool"):
                        registry_integrity_guards.add(consumer)
                    continue
                if edge["kind"] == "shares-operation-contract":
                    continue
                if edge["kind"] in (
                    "shares-operation-contract",
                    "implemented-by",
                ) and any(
                    value.startswith("operation:") and value not in exact_operations
                    for value in (edge["consumer"], edge["dependency"])
                ):
                    continue
            reverse[edge["dependency"]].add(edge["consumer"])
    # Removed or added edges also change semantic reachability independently
    # of source hashes (for explicit declaration/observation graph updates).
    old_edges = (
        {(e["consumer"], e["dependency"], e["kind"]) for e in before["edges"]}
        if before
        else set()
    )
    new_edges = {(e["consumer"], e["dependency"], e["kind"]) for e in after["edges"]}
    changed = sorted(
        set(changed) | {value for edge in old_edges ^ new_edges for value in edge[:2]}
    )
    if metadata_only:
        changed = [identity for identity in changed if identity != registry_node]
    if any(identity.startswith("catalog:") for identity in changed):
        changed.append("domain:catalog")
    reached, explanations = set(changed), {identity: [identity] for identity in changed}
    queue = deque(changed)
    active_registry_guards = (
        registry_integrity_guards
        if metadata_only and any(identity in exact_operations for identity in changed)
        else set()
    )
    if active_registry_guards:
        for guard in sorted(active_registry_guards):
            if guard not in reached:
                reached.add(guard)
                explanations[guard] = [registry_node, guard]
                queue.append(guard)
    while queue:
        identity = queue.popleft()
        for consumer in sorted(reverse.get(identity, ())):
            if consumer not in reached:
                reached.add(consumer)
                explanations[consumer] = explanations[identity] + [consumer]
                queue.append(consumer)
    unknowns = [
        item
        for graph in ([before, after] if before else [after])
        for item in graph["unknowns"]
    ]
    selected_source_owners = {
        "module:" + row["path"]
        for identity in reached
        if (row := after_nodes.get(identity, before_nodes.get(identity, {}))).get(
            "kind"
        )
        == "test-module"
    }
    uncertainty_reached = reached | selected_source_owners
    affected_unknowns = [
        item
        for item in unknowns
        if item["owner"] in uncertainty_reached
        or item["domain"] in ("catalog", "catalog-or-data")
        and "domain:catalog" in reached
    ]
    fallbacks = []
    if before is None:
        fallbacks.append({"reason": "missing-before-graph", "scope": "full"})
    if before and before["builder"] != after["builder"]:
        fallbacks.append(
            {"reason": "builder-or-contract-policy-changed", "scope": "full"}
        )
    changed_paths = {
        row.get("path")
        for identity, row in {**before_nodes, **after_nodes}.items()
        if identity in changed
    }
    for path in after["global_invalidation"]:
        if path in changed_paths:
            fallbacks.append(
                {"reason": "global-policy-change", "path": path, "scope": "full"}
            )
    provenance = after["provenance"]
    if provenance.get("catalog_inventory_sha256") is None or not provenance.get(
        "catalog_publication_verified"
    ):
        fallbacks.append({"reason": "catalog-authority-unverified", "scope": "full"})
    if provenance.get("snapshot_status") in ("invalid", "mismatch"):
        fallbacks.append({"reason": "snapshot-integrity-unverified", "scope": "full"})
    if before and before["provenance"].get("runner_policy") != provenance.get(
        "runner_policy"
    ):
        fallbacks.append({"reason": "runner-policy-changed", "scope": "full"})
    if before and before["provenance"].get("environment_sha256") != provenance.get(
        "environment_sha256"
    ):
        fallbacks.append({"reason": "execution-class-changed", "scope": "full"})
    if previous_context != current_context:
        fallbacks.append(
            {
                "reason": "required-execution-context-changed-or-unavailable",
                "scope": "full",
            }
        )
    # Unresolved data readers can consume any changed fixture or catalog. A
    # missing bounded domain forces full scope rather than silent independence.
    data_changed = any(
        identity.startswith(("input:", "catalog:", "module:")) for identity in changed
    )
    source_changed = any(identity.startswith("module:") for identity in changed)
    for item in unknowns:
        activate = item["domain"] in ("data", "catalog-or-data") and data_changed
        activate |= item["domain"] == "source-unbounded" and (
            source_changed
            or item["reason"] == "dynamic-test-discovery"
            and data_changed
        )
        activate |= (
            item["reason"]
            in ("runtime-provider-binding", "injected-provider-expression")
            and source_changed
        )
        # A literal metadata edit cannot change unrelated environment readers.
        # Keep private/dynamic uncertainty for every actually reached metadata
        # consumer; ordinary source edits retain the existing global policy.
        absent_private = False
        if item["domain"] == "environment-private" and before:
            policy_id = "runtime-policy:" + str(item.get("target"))
            previous, current = before_nodes.get(policy_id, {}), after_nodes.get(
                policy_id, {}
            )
            absent_private = (
                previous.get("kind") == current.get("kind") == "runtime-policy"
                and previous.get("available") is False
                and current.get("available") is False
            )
        activate |= (
            item["domain"] in ("environment-unbounded", "environment-private")
            and not absent_private
            and (not matching_execution_context or item["owner"] in uncertainty_reached)
            and (not metadata_only or item["owner"] in uncertainty_reached)
        )
        if activate and item not in affected_unknowns:
            affected_unknowns.append(item)
    scoped_selected = set()
    combat_consumer_names = None
    for item in affected_unknowns:
        if item["domain"] == "scenario":
            continue
        owner_row = after_nodes.get(item["owner"], before_nodes.get(item["owner"], {}))
        owner_path = owner_row.get("path", "")
        if item["fallback"] == "full":
            scope = "full"
        elif (
            owner_path.startswith("server/tests/test")
            and item["domain"] != "source-unbounded"
        ):
            scope = "owner-module"
            scoped_selected.add(Path(owner_path).stem)
        elif (
            item["domain"]
            in (
                "data",
                "data-parameter",
                "source-unbounded",
                "environment-private",
                "environment-unbounded",
            )
            or item["domain"] == "catalog-or-data"
            and "domain:catalog" not in reached
            or item["reason"] == "published-catalog-domain"
            and item["domain"] == "catalog"
            and before
            and "domain:catalog" not in reached
            and before["provenance"].get("catalog_inventory_sha256")
            == provenance.get("catalog_inventory_sha256")
            and before["provenance"].get("catalog_revision")
            == provenance.get("catalog_revision")
            and before["provenance"].get("catalog_publication_verified") is True
            and provenance.get("catalog_publication_verified") is True
            or metadata_only
            and owner_row.get("category") == "tool"
            and item["domain"] == "catalog"
            and before["provenance"].get("catalog_inventory_sha256")
            == provenance.get("catalog_inventory_sha256")
            and before["provenance"].get("catalog_publication_verified") is True
            and provenance.get("catalog_publication_verified") is True
        ):
            scope = "owner-consumers"
            pending, visited = deque([item["owner"]]), {item["owner"]}
            while pending:
                current = pending.popleft()
                current_row = after_nodes.get(current, {})
                if current_row.get("kind") == "test-module":
                    scoped_selected.add(current_row["module_name"])
                for consumer in reverse.get(current, ()):
                    if consumer not in visited:
                        visited.add(consumer)
                        pending.append(consumer)
        elif owner_row.get("category") == "combat":
            scope = "combat-consumers"
            if combat_consumer_names is None:
                combat_consumer_names = set()
                combat_seeds = [
                    identity
                    for identity, row in after_nodes.items()
                    if row.get("category") == "combat"
                ]
                pending, visited = deque(combat_seeds), set(combat_seeds)
                while pending:
                    current = pending.popleft()
                    current_row = after_nodes.get(current, {})
                    if current_row.get("kind") == "test-module":
                        combat_consumer_names.add(current_row["module_name"])
                    for consumer in reverse.get(current, ()):
                        if consumer not in visited:
                            visited.add(consumer)
                            pending.append(consumer)
            scoped_selected.update(combat_consumer_names)
        else:
            scope = "full"
        fallbacks.append(
            {
                "reason": item["reason"],
                "owner": item["owner"],
                "scope": scope,
                "evidence": item,
            }
        )
    selected = {
        after_nodes[identity]["module_name"]
        for identity in reached
        if identity in after_nodes and after_nodes[identity]["kind"] == "test-module"
    }
    selected.update(scoped_selected)
    selected.intersection_update(after["module_names"])
    # Source workflow and evidence freshness are separate axes. A bounded
    # source closure never asserts that excluded modules passed or were reused.
    source_seeds = {
        identity
        for identity in changed
        if identity.startswith(
            (
                "module:",
                "input:",
                "operation:",
                "migration-family:",
                "class:",
                "method:",
                "fixture:",
                "event:",
                "operation-interaction:",
                "scenario:",
            )
        )
    }
    source_reached = set(source_seeds)
    source_queue = deque(sorted(source_seeds))
    source_paths = {identity: [identity] for identity in source_seeds}
    if metadata_only and source_seeds:
        for guard in active_registry_guards:
            if guard not in source_reached:
                source_reached.add(guard)
                source_queue.append(guard)
                source_paths[guard] = [registry_node, guard]
    while source_queue:
        identity = source_queue.popleft()
        for consumer in sorted(reverse.get(identity, ())):
            if consumer not in source_reached:
                source_reached.add(consumer)
                source_paths[consumer] = source_paths[identity] + [consumer]
                source_queue.append(consumer)
    source_modules = sorted(
        {
            after_nodes[identity]["module_name"]
            for identity in source_reached
            if identity in after_nodes
            and after_nodes[identity]["kind"] == "test-module"
        }
        & set(after["module_names"])
    )
    source_explanations = {
        after_nodes[identity]["module_name"]: source_paths[identity]
        for identity in source_reached
        if identity in after_nodes and after_nodes[identity]["kind"] == "test-module"
    }
    environment_uncertainty = [
        item for item in affected_unknowns if item["domain"].startswith("environment-")
    ]
    source_input_uncertainty = [
        item
        for item in affected_unknowns
        if not item["domain"].startswith("environment-")
        and item["domain"] != "scenario"
    ]
    source_workflow = {
        "mode": "known-source-dependency-closure",
        "explanations": source_explanations,
        "unresolved_source_or_input_dependencies": sorted(
            {
                canonical_digest(item): item for item in source_input_uncertainty
            }.values(),
            key=canonical_digest,
        ),
        "environment_uncertainty": sorted(
            {canonical_digest(item): item for item in environment_uncertainty}.values(),
            key=canonical_digest,
        ),
        "strict_freshness_required": True,
        "reuse_qualified": False,
        "excluded_module_status": "not-executed-not-reused-not-proven",
        "limitations": [
            "Known source consumers are a fresh affected-workflow scope, not permission to publish cached passes.",
            "Unresolved source/data readers remain visible possible additional consumers; no independence claim is made.",
            "Strict selected_module_names retains all existing conservative full/scoped fallbacks.",
        ],
    }
    if any(item["scope"] == "full" for item in fallbacks):
        selected = set(after["module_names"])
    for fallback in fallbacks:
        fallback["id"] = canonical_digest(fallback)
    selected_explanations = {}
    for identity, row in after_nodes.items():
        if row["kind"] == "test-module" and row["module_name"] in selected:
            selected_explanations[row["module_name"]] = {
                "path": explanations.get(identity),
                "reason": "reverse-dependency-closure"
                if identity in reached
                else "conservative-fallback",
                "fallback_ids": [
                    item["id"] for item in fallbacks if identity not in reached
                ],
            }
    plan = {
        "schema": PLAN_SCHEMA,
        "mode": "observation",
        "suppression_enabled": False,
        "before_graph_sha256": before.get("sha256") if before else None,
        "after_graph_sha256": after["sha256"],
        "before_provenance": before.get("provenance") if before else None,
        "after_provenance": after["provenance"],
        "changed_node_ids": sorted(set(changed)),
        "selected_module_names": sorted(selected),
        "discovered_module_names": after["module_names"],
        "removed_module_names": sorted(
            set(before["module_names"] if before else ()) - set(after["module_names"])
        ),
        "explanations": selected_explanations,
        "unknowns": sorted(
            {canonical_digest(u): u for u in affected_unknowns}.values(),
            key=canonical_digest,
        ),
        "fallbacks": fallbacks,
        "notes": [
            "All tests must still execute; this plan is observation only.",
            "Coverage of an exposing assertion is independent of structural reachability.",
        ],
    }
    plan["required_isolated_reader_fixtures"] = {
        path: row
        for path, row in after.get("isolated_reader_fixture_registry", {})
        .get("qualified", {})
        .items()
        if Path(path).stem in selected
    }
    plan["required_observed_execution_context"] = current_context
    plan["execution_context_verified_before_tests"] = False
    if matching_execution_context:
        plan["notes"].append(
            "This scope requires the future runner to verify the exact observed full environment digest, interpreter, startup flags and catalog before imports; a mismatch forbids using this scope. This is not historical or global cached-pass qualification."
        )
    plan["source_impacted_module_names"] = source_modules
    plan["source_workflow"] = source_workflow
    plan["registry_metadata_only"] = metadata_only
    plan["registry_integrity_guard_ids"] = sorted(active_registry_guards)
    plan["selected_test_source_owner_ids"] = sorted(selected_source_owners)
    if metadata_only:
        plan["notes"].append(
            "Only literal operation contract metadata changed; common registry AST and export shape are unchanged. Declared operation tests and registry/tool integrity consumers are selected. Unchanged executor runtime imports and historical broad family groupings are not metadata dependencies; uncertainty belonging to reached metadata consumers remains conservative."
        )
    plan["sha256"] = canonical_digest(plan)
    return plan


def compare_shadow(plan, full_report):
    """Compare only matching full-run provenance; never infer regressions."""
    if plan.get("schema") != PLAN_SCHEMA or plan.get("sha256") != canonical_digest(
        {k: v for k, v in plan.items() if k != "sha256"}
    ):
        raise ValueError("Invalid impact selection plan")
    expected = plan["after_provenance"]
    mismatches = []
    for boundary in ("provenance_before", "provenance_after"):
        actual = full_report.get(boundary) or {}
        pairs = {
            "source_manifest_sha256": actual.get("source", {}).get("sha256"),
            "catalog_inventory_sha256": actual.get("catalog", {}).get("sha256"),
            "catalog_revision": actual.get("catalog", {}).get("revision"),
            "environment_sha256": actual.get("environment", {}).get("sha256"),
            "runner_sha256": full_report.get("runner", {}).get("sha256"),
        }
        for field, value in pairs.items():
            if expected.get(field) is None or value != expected[field]:
                mismatches.append(boundary + ":" + field)
        if actual.get("catalog", {}).get("publication_verified") is not True:
            mismatches.append(boundary + ":catalog-publication-unverified")
    for boundary in ("impact_inputs_before", "impact_inputs_after"):
        actual_inputs = full_report.get(boundary)
        for field in (
            "scenario_manifest_sha256",
            "contracts_sha256",
            "builder_sha256",
            "runtime_policy_sha256",
            "runtime_policy_names",
        ):
            if (
                not isinstance(actual_inputs, dict)
                or field not in actual_inputs
                or actual_inputs[field] != expected.get(field)
            ):
                mismatches.append(boundary + ":" + field)
    actual_policy = full_report.get("runner", {}).get("policy")
    if actual_policy != expected["runner_policy"]:
        mismatches.append("runner-policy")
    discovered = full_report.get("discovery", {}).get("module_names")
    if discovered is None or sorted(discovered) != plan["discovered_module_names"]:
        mismatches.append("discovery-module-set")
    if full_report.get("provenance_stable") is not True:
        mismatches.append("run-provenance-not-stable")
    missing = not all(
        full_report.get(key)
        for key in (
            "provenance_before",
            "provenance_after",
            "runner",
            "discovery",
            "impact_inputs_before",
            "impact_inputs_after",
        )
    )
    missing |= any(
        not isinstance(full_report.get(boundary), dict)
        or any(
            field not in full_report[boundary]
            for field in (
                "scenario_manifest_sha256",
                "contracts_sha256",
                "builder_sha256",
                "runtime_policy_sha256",
                "runtime_policy_names",
            )
        )
        for boundary in ("impact_inputs_before", "impact_inputs_after")
    )
    if mismatches:
        return {
            "schema": "wakemu-test-impact-shadow-v1",
            "status": "unavailable" if missing else "incompatible",
            "mismatches": sorted(set(mismatches)),
            "regression_attribution": "not-established",
            "outcomes": [],
        }
    reports = full_report.get("module_timing", {})
    if any(name not in reports for name in plan["discovered_module_names"]):
        return {
            "schema": "wakemu-test-impact-shadow-v1",
            "status": "unavailable",
            "mismatches": ["incomplete-module-reports"],
            "regression_attribution": "not-established",
            "outcomes": [],
        }
    outcomes = []
    for name in plan["discovered_module_names"]:
        item = reports.get(name, {})
        result = item.get("result", {})
        status = item.get("status", "missing")
        count_fields = (
            "failures",
            "errors",
            "unexpected_successes",
            "skipped",
            "expected_failures",
            "tests_run",
        )
        counts_valid = all(
            type(result.get(field)) is int and result[field] >= 0
            for field in count_fields
        )
        discovered_count = item.get("discovery", {}).get("tests")
        counts_valid = (
            counts_valid
            and type(discovered_count) is int
            and discovered_count >= 0
            and result["tests_run"] <= discovered_count
        )
        # setUpModule/setUpClass errors can stop every test before startTest;
        # error/subtest counts are therefore not bounded by tests_run.
        complete = counts_valid and result["tests_run"] == discovered_count
        no_failures = counts_valid and not any(
            result[field] for field in ("failures", "errors", "unexpected_successes")
        )
        explained_fixture_skip = counts_valid and result["skipped"] > 0 and no_failures
        success_claim_consistent = (
            result.get("successful") is not True
            or no_failures
            and (complete or explained_fixture_skip)
        )
        origin = item.get("origin", "unknown")
        reused_tests = result.get("reused_tests", 0)
        fresh_origin = (
            origin == "executed" and type(reused_tests) is int and reused_tests == 0
        )
        report_consistent = (
            counts_valid
            and type(result.get("successful")) is bool
            and type(item.get("return_code")) is int
            and success_claim_consistent
            and fresh_origin
        )
        clean = (
            status == "completed"
            and item.get("return_code") == 0
            and result.get("successful") is True
            and report_consistent
        )
        if clean and (
            discovered_count == 0
            or not complete
            or result.get("skipped", 0)
            or result.get("expected_failures", 0)
        ):
            status = "completed-with-unverified-cases"
        elif clean:
            status = "terminal-pass"
        elif status == "completed":
            status = (
                "terminal-nonpass"
                if report_consistent
                else "inconsistent-terminal-report"
            )
        elif status == "reused":
            # The selector does not verify the store's original terminal
            # receipt. Cached assertions cannot witness a fresh full run.
            status = (
                "reused-not-fresh"
                if origin == "reused"
                else "inconsistent-terminal-report"
            )
        outcomes.append(
            {
                "module": name,
                "would_select": name in plan["selected_module_names"],
                "status": status,
                "result": result,
                "origin": origin,
            }
        )
    return {
        "schema": "wakemu-test-impact-shadow-v1",
        "status": "matched",
        "mismatches": [],
        "regression_attribution": "not-established",
        "outcomes": outcomes,
        "outside_subset_nonpasses": [
            row["module"]
            for row in outcomes
            if not row["would_select"] and row["status"] != "terminal-pass"
        ],
        "notes": [
            "Historical failures outside a proposed subset are observed omissions, not automatically regressions.",
            "Before-pass/after-fail attribution requires a separately comparable before run.",
        ],
    }


def _read_json(path, max_bytes=256 * 1024 * 1024):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise ValueError("Invalid or oversized JSON input")
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        raise ValueError("JSON input exceeds size bound")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("JSON input must be an object")
    return value


def _write_json_exclusive(path, value):
    import os

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600
    )
    with os.fdopen(descriptor, "w", encoding="utf8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main(argv=None):
    """Capture/explain/shadow artifacts without running any test suite."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture = commands.add_parser(
        "capture", help="Build a before/after dependency graph without test execution"
    )
    capture.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    capture.add_argument(
        "--catalog-inventory",
        type=Path,
        help="Previously captured publication metadata; no live read when supplied",
    )
    capture.add_argument("--scenarios", type=Path)
    capture.add_argument(
        "--isolated-reader-fixtures",
        type=Path,
        help="Source-bound actual singleton fixture authority list",
    )
    capture.add_argument(
        "--require-observed-execution-context",
        action="store_true",
        help="Scope is valid only under the exact supplied observed child environment",
    )
    capture.add_argument("--output", type=Path, required=True)
    explain = commands.add_parser(
        "explain", help="Explain impact from captured graphs without skipping tests"
    )
    explain.add_argument("--before", type=Path)
    explain.add_argument("--after", type=Path, required=True)
    explain.add_argument("--output", type=Path, required=True)
    shadow = commands.add_parser(
        "shadow", help="Compare a plan against an existing matching full report"
    )
    shadow.add_argument("--plan", type=Path, required=True)
    shadow.add_argument("--full-report", type=Path, required=True)
    shadow.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            if args.catalog_inventory:
                inventory = _read_json(args.catalog_inventory, 32 * 1024 * 1024)
            else:
                from tools.combat_baseline_inventory import catalog_manifest

                inventory = catalog_manifest()
            scenarios = (
                _read_json(args.scenarios, 32 * 1024 * 1024) if args.scenarios else None
            )
            fixtures = (
                _read_json(args.isolated_reader_fixtures)
                if args.isolated_reader_fixtures
                else None
            )
            value = build_graph(
                args.root,
                catalog_inventory=inventory,
                scenarios=scenarios,
                isolated_reader_fixtures=fixtures,
                require_observed_execution_context=args.require_observed_execution_context,
            )
        elif args.command == "explain":
            before = _read_json(args.before) if args.before else None
            value = select_changes(before, _read_json(args.after))
        else:
            value = compare_shadow(_read_json(args.plan), _read_json(args.full_report))
        _write_json_exclusive(args.output, value)
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(
            2, "Impact artifact operation failed: " + type(error).__name__ + "\n"
        )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "schema": value["schema"],
                "mode": value.get("mode"),
                "status": value.get("status"),
                "sha256": value.get("sha256"),
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
