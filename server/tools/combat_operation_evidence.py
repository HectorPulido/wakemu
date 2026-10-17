"""Join shared contracts to existing hash-bound offline evidence.

This is a read-only explanation layer. It neither creates accreditation nor
executes actors. Complete module passes establish their declared test scope,
not every variant of an operation, a combination, or client presentation.
"""
import argparse
from collections import defaultdict, deque
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.combat_operation_catalog import SCHEMA as CATALOG_SCHEMA
from tools.combat_validation_offline import REGISTRY, eligibility
from tools.combat_validation_reuse import LocalResultStore, StoreIntegrityError, digest
from wakfu_server.combat_operation_registry import OPERATIONS
from wakfu_server import combat_operation_registry as registry_module


SCHEMA = "wakemu-operation-evidence-v1"
REGISTRY_SOURCE = "server/wakfu_server/combat/combat_operation_registry.py"
METADATA_SOURCES = frozenset(
    (
        REGISTRY_SOURCE,
        "server/wakfu_server/combat/combat_subscription_contracts.py",
        "server/wakfu_server/combat/combat_damage_contracts.py",
        "server/wakfu_server/combat/combat_local_criteria.py",
        "server/tools/combat_operation_catalog.py",
    )
)


def _operation_ids(node):
    return node.get(
        "operation_ids",
        ([node["operation_id"]] if node.get("operation_id") is not None else []),
    )


def _verify_snapshot(report, root):
    """Never join a snapshot to a different imported contract implementation."""
    expected = hashlib.sha256(Path(registry_module.__file__).read_bytes()).hexdigest()
    supplied = hashlib.sha256((root / REGISTRY_SOURCE).read_bytes()).hexdigest()
    if supplied != expected:
        raise ValueError("Requested root differs from imported operation registry")
    source = report.get("registry_source")
    if source != {"path": REGISTRY_SOURCE, "sha256": supplied}:
        raise ValueError(
            "Compiled report operation registry identity is stale or missing"
        )
    metadata_sources = report.get("registry_sources")
    if type(metadata_sources) is not dict or set(metadata_sources) != METADATA_SOURCES:
        raise ValueError(
            "Compiled operation metadata source closure is missing or incomplete"
        )
    imported_root = Path(registry_module.__file__).resolve().parents[3]
    for name, checksum in metadata_sources.items():
        imported_hash = hashlib.sha256((imported_root / name).read_bytes()).hexdigest()
        root_hash = hashlib.sha256((root / name).read_bytes()).hexdigest()
        if checksum != root_hash or imported_hash != root_hash:
            raise ValueError("Compiled report operation metadata identity is stale")
    for node in report["nodes"].values():
        for identity in _operation_ids(node):
            contract = OPERATIONS.get(identity)
            binding = node.get("operation_contracts", {}).get(identity)
            checksum = (
                binding.get("contract_sha256")
                if binding is not None
                else node.get("contract_sha256")
                if identity == node.get("operation_id")
                else None
            )
            if contract is None or checksum != digest(asdict(contract)):
                raise ValueError(
                    "Compiled operation contract identity is stale or missing"
                )


def _reverse_graph(report):
    parents = defaultdict(set)
    for edge in report["edges"]:
        parents[edge["target"]].add(edge["source"])
    return parents


def _consumers(report, node_keys, parents):
    """Find all requested roots, including shared descendants and cycles."""
    visited = set(node_keys)
    pending = deque(sorted(visited))
    while pending:
        for parent in sorted(parents[pending.popleft()]):
            if parent not in visited:
                visited.add(parent)
                pending.append(parent)
    return [
        seed
        for seed in report["seeds"]
        if seed["kind"] + ":" + str(seed["reference"]) in visited
    ]


def _declarations(root):
    # Unqualified declarations are diagnostic dependencies only. The eligibility
    # verifier, not this read, authorizes store lookup and checks every byte.
    try:
        document = json.loads((root / REGISTRY).read_bytes())
        if (
            type(document) is dict
            and document.get("schema") == "audited-offline-modules-v1"
            and type(document.get("modules")) is dict
        ):
            return document["modules"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return {}


def _module_evidence(root, module, store, inputs, declarations):
    result = eligibility(root, module, **inputs)
    entry = declarations.get(module, {})
    if type(entry) is not dict:
        entry = {}
    dependencies = {
        kind: dict(entry[kind]) if type(entry.get(kind)) is dict else {}
        for kind in ("source", "fixtures", "catalog", "oracles")
    }
    row = {
        "module": module,
        "status": "fresh-required",
        "reason": result.reason,
        "dependency_status": "unqualified-declaration",
        "reviewed_dependencies": dependencies,
    }
    if result.manifest is None:
        return row
    manifest = result.manifest
    document = manifest.as_dict()
    row.update(
        key=manifest.key,
        scope=document["scope"],
        dependency_status="current-qualified",
        test_ids=document["test_ids"],
        reviewed_dependencies={kind: document[kind] for kind in dependencies},
    )
    if store is None:
        row["reason"] = "No existing result store supplied"
        return row
    try:
        found = store.lookup(manifest)
    except StoreIntegrityError as error:
        row.update(status="invalid-evidence", reason=str(error))
        return row
    if found is None:
        row["reason"] = "No compatible terminal parent evidence"
        return row
    receipt = found.receipt.as_dict()
    row.update(
        status="reused",
        reason="Compatible original executed module pass",
        origin=receipt["origin"],
        invocation_id=receipt["parent"]["invocation_id"],
        report_sha256=receipt["report_sha256"],
    )
    return row


def _current_input(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_operation_evidence(
    report,
    *,
    root,
    store=None,
    runner_sha256,
    environment_sha256,
    policies,
    changed_operations=(),
    changed_paths=()
):
    """Explain bounded proof reuse and affected consumers without actor replay.

    Changes are explicit caller inputs, never inferred as an exhaustive selector.
    Unknown operations/paths request broader inspection rather than silently
    declaring that no tests are needed. This report does not suppress tests.
    """
    if hasattr(report, "report"):
        report = report.report()
    if report.get("schema") != CATALOG_SCHEMA:
        raise ValueError("Compiled operation catalog report required")
    root = Path(root).resolve()
    _verify_snapshot(report, root)
    declarations = _declarations(root)
    nodes = report["nodes"]
    parents = _reverse_graph(report)
    grouped = defaultdict(list)
    for key, row in nodes.items():
        for identity in _operation_ids(row):
            grouped[identity].append(key)
    inputs = dict(
        runner_sha256=runner_sha256,
        environment_sha256=environment_sha256,
        policies=policies,
    )
    modules = {}
    operations = {}
    for identity, keys in sorted(grouped.items()):
        contract = OPERATIONS.get(identity)
        if contract is None:
            raise ValueError(
                "Compiled report references an unknown operation: " + identity
            )
        tests = sorted(set(contract.tests))
        for module in tests:
            if module not in modules:
                modules[module] = _module_evidence(
                    root, module, store, inputs, declarations
                )
        contract_doc = asdict(contract)
        support = {
            key: (
                nodes[key].get("operation_support", "unknown")
                if nodes[key].get("operation_id") == identity
                else nodes[key].get("retained_execution", {}).get("status", "unknown")
            )
            for key in sorted(keys)
        }
        aggregate_support = (
            "unsupported"
            if "unsupported" in support.values()
            else "unknown"
            if "unknown" in support.values()
            else "conditional"
        )
        implementation_path = (
            "server/wakfu_server/combat/" + contract.executor.split(".")[0] + ".py"
        )
        test_paths = ["server/tests/" + test + ".py" for test in tests]
        operations[identity] = dict(
            contract_sha256=digest(contract_doc),
            contract=contract_doc,
            current_inputs={
                "implementation": {
                    implementation_path: _current_input(root, implementation_path)
                },
                "tests": {name: _current_input(root, name) for name in test_paths},
            },
            operation_support=aggregate_support,
            node_support=support,
            combination_verification="unknown",
            modeled_client_compatibility="unknown",
            nodes=sorted(keys),
            consumers=_consumers(report, keys, parents),
            relevant_tests=tests,
            reused_partial_scopes=[
                module for module in tests if modules[module]["status"] == "reused"
            ],
            limitations=[
                "Each reused scope covers only its exact listed tests.",
                "A contract description is not a complete dependency qualification.",
            ],
        )
    changed_operations = set(changed_operations)
    changed_paths = set(changed_paths)
    affected = changed_operations.intersection(operations)
    matched_paths = set()
    for identity, row in operations.items():
        contract = OPERATIONS[identity]
        executor_file = (
            "server/wakfu_server/combat/" + contract.executor.split(".")[0] + ".py"
        )
        dependencies = {
            executor_file,
            *("server/tests/" + test + ".py" for test in contract.tests),
        }
        for module in row["relevant_tests"]:
            for mapping in modules[module]["reviewed_dependencies"].values():
                dependencies.update(mapping)
        matches = changed_paths.intersection(dependencies)
        if matches:
            affected.add(identity)
            matched_paths.update(matches)
    unknown_operations = sorted(changed_operations.difference(operations))
    unknown_paths = sorted(changed_paths.difference(matched_paths))
    missing = {}
    family_nodes = defaultdict(list)
    for key, node in nodes.items():
        if "family" in node:
            family_nodes[node["family"]].append(key)
    missing_consumers = {}
    for issue in report["issues"]:
        if issue.get("reason") == "missing-shared-operation":
            family = issue["family"]
            if family not in missing_consumers:
                missing_consumers[family] = _consumers(
                    report, family_nodes[family], parents
                )
            row = missing.setdefault(
                family,
                dict(
                    family=family,
                    path=issue["path"],
                    paths=[],
                    affected_consumers=missing_consumers[family],
                ),
            )
            row["paths"].append(issue["path"])
    affected_keys = [
        key for identity in affected for key in operations[identity]["nodes"]
    ]
    return dict(
        schema=SCHEMA,
        catalog_sha256=digest(report),
        operations=operations,
        module_evidence=modules,
        missing_operations=[missing[family] for family in sorted(missing)],
        combination_verification="unknown",
        modeled_client_compatibility="unknown",
        impact=dict(
            changed_operations=sorted(changed_operations),
            changed_paths=sorted(changed_paths),
            affected_operations=sorted(affected),
            affected_consumers=_consumers(report, affected_keys, parents),
            relevant_tests=sorted(
                {
                    test
                    for identity in affected
                    for test in operations[identity]["relevant_tests"]
                }
            ),
            unknown_operations=unknown_operations,
            unknown_paths=unknown_paths,
            broader_inspection_required=bool(unknown_operations or unknown_paths),
            mode="explanation-only",
        ),
        limitations=[
            "No actor or level execution is performed by this join.",
            "No proof is published and no second result store is created.",
            "Operation availability, combination proof and modeled presentation are independent.",
            "Unqualified operations require fresh relevant tests; descriptions do not authorize reuse.",
        ],
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-report", type=Path, required=True)
    parser.add_argument(
        "--root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--result-store", type=Path)
    parser.add_argument("--runner-sha256", required=True)
    parser.add_argument("--environment-sha256", required=True)
    parser.add_argument("--policies", type=Path, required=True)
    parser.add_argument("--changed-operation", action="append", default=[])
    parser.add_argument("--changed-path", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.result_store is not None and not args.result_store.is_dir():
        parser.error("Result store must already exist; this tool never creates a store")
    store = (
        LocalResultStore(args.result_store) if args.result_store is not None else None
    )
    result = build_operation_evidence(
        json.loads(args.catalog_report.read_bytes()),
        root=args.root,
        store=store,
        runner_sha256=args.runner_sha256,
        environment_sha256=args.environment_sha256,
        policies=json.loads(args.policies.read_bytes()),
        changed_operations=args.changed_operation,
        changed_paths=args.changed_path,
    )
    with args.output.open("x", encoding="utf8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
