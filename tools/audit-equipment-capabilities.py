"""Read-only full native equipment inventory; no execution/admission changes.

Run once with the native catalog DB in an otherwise empty heavy-worker slot.
Outputs distinguish operation descriptions, working-tree admission and actual
runtime evidence. Native variant/context metadata never implies execution.
"""
import ast
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time
import argparse
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "server"))
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output-dir", type=Path, required=True)
parser.add_argument(
    "--unqualified-source-contract",
    action="append",
    default=[],
    help="Record staged source admission lacking lifecycle qualification.",
)
parser.add_argument(
    "--resume-output",
    type=Path,
    default=None,
    help="Backfill only references with errors in a prior receipt; base files remain unchanged.",
)
parser.add_argument(
    "--factory-graphs",
    action="store_true",
    help="Assess each complete source against one real native runtime factory; never execute effects.",
)
parser.add_argument(
    "--smoke-reference",
    type=int,
    action="append",
    default=[],
    help="Select an explicit smoke reference; requires --max-items and is never a full census.",
)
parser.add_argument(
    "--max-items",
    type=int,
    default=None,
    help="Bounded scanner smoke test only; omit for the full native inventory.",
)
args = parser.parse_args()
if args.max_items is not None and args.max_items <= 0:
    parser.error("--max-items must be positive")
if args.smoke_reference and (
    args.max_items is None or any(ref <= 0 for ref in args.smoke_reference)
):
    parser.error("--smoke-reference requires positive references and --max-items")
OUT = args.output_dir.resolve()
if ROOT / ".runtime" not in OUT.parents:
    parser.error("Generated/private reports must be beneath .runtime")
OUT.mkdir(parents=True, exist_ok=True)
resume_references = None
base_receipt = None
if args.resume_output is not None:
    base_path = args.resume_output.resolve()
    if ROOT / ".runtime" not in base_path.parents or base_path == OUT:
        parser.error("--resume-output must be a different .runtime directory")
    base_summary_path = base_path / "summary.json"
    base_summary = json.loads(base_summary_path.read_text())
    resume_references = set()
    for line in (base_path / "full-items.jsonl").read_text().splitlines():
        row = json.loads(line)
        if row.get("error") or any(
            case.get("static_context_or_data_error")
            or case.get("planner_context_or_data_error")
            for case in row.get("cases", ())
        ):
            resume_references.add(row["reference"])
    base_receipt = dict(
        output_directory=str(base_path),
        summary_sha256=hashlib.sha256(base_summary_path.read_bytes()).hexdigest(),
        base_source_hashes=base_summary.get("source_hashes_after", {}),
        retried_references=sorted(resume_references),
    )


def hashes():
    paths = set(Path("server/wakfu_server").rglob("*.py"))
    paths.add(Path(__file__).resolve().relative_to(ROOT))
    if args.factory_graphs:
        paths.update(
            (
                Path("server/tests/test_combat_spell_transaction.py"),
                Path("server/tests/test_aptitude_catalog_coverage.py"),
            )
        )
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


before = hashes()
started = time.monotonic()
from wakfu_server import (
    native_catalog,
    equipment_stats,
    inventory_elements,
    equipment_conditions,
)
from wakfu_server.equipment import RULES
from wakfu_server.empty_equipment_effects import template as empty_template
from wakfu_server.combat_character_copy_equipment import native_copied_equipment_catalog
from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
from wakfu_server.combat_copied_equipment_execution import equipment_effect_definitions
from wakfu_server.combat_equipment_initialization import plan
from wakfu_server.combat_owned_equipment import (
    compiled_with_sources,
    ordinary_turn_state_contract,
)
from wakfu_server.combat_server_spell import compiled_runtime_catalog
from wakfu_server.combat_static_catalogs import characteristic_registry
from wakfu_server.combat_operation_registry import (
    assess_operation,
    operation_for_family,
)
from wakfu_server.combat_equipment_operation_capability import (
    validate_effect,
    validate_graph,
)
from wakfu_server.combat_local_criteria import parse_local_criterion
from wakfu_server.combat_definitions import effect_profile
from wakfu_server.combat_set_current_characteristic import (
    FAMILIES as SET_CURRENT_FAMILIES,
)

native = native_copied_equipment_catalog()
compiled = compiled_runtime_catalog()
registry = characteristic_registry()
conditions = equipment_conditions.catalog()
with native_catalog._database().connection() as db:
    db.execute("SET TRANSACTION READ ONLY")
    pets = {
        r["reference"]: dict(r) for r in db.execute("SELECT * FROM native_pet_models")
    }
    mounts = {r["reference"]: dict(r) for r in db.execute("SELECT * FROM mount_models")}
factory_routes = factory_provider = factory_character = owner_level_facts = None
factory_context = None
if args.factory_graphs:
    from random import Random

    # This existing fixture builds real native player/NPC snapshots and QI
    # surfaces, with the same controlled owner IDs used by the normal runtime.
    # No fake dispatcher, operation callbacks or substitute handlers are used.
    sys.path.insert(0, str(ROOT / "server/tests"))
    from test_combat_spell_transaction import SpellTransactionTests
    from wakfu_server.combat_server_spell import server_runtime
    from wakfu_server.combat_equipment_dynamic_levels import OwnerLevelFacts
    from wakfu_server.spells import encode_deck

    (
        factory_character,
        factory_monster,
        factory_fight,
    ) = SpellTransactionTests().native_server_fixture(
        8,
        245,
        native_qi=True,
        full_health=True,
        variation_seed=0,
    )
    audit_factory, audit_adapter = server_runtime(
        factory_character,
        {factory_monster["id"]: factory_monster},
        encode_deck((), ()),
        action_id=1,
        critical=False,
        rng=Random(0),
    )
    factory_routes, factory_provider = audit_factory.equipment_operation_capability()
    owner_level_facts = OwnerLevelFacts.capture(
        factory_fight,
        factory_character["id"],
        factory_character["account_id"],
    )
    factory_context = dict(
        factory_type=type(audit_factory).__name__,
        inner_factory_type=type(factory_routes.factory).__name__,
        provider_type=type(factory_provider).__name__,
        routes_type=type(factory_routes).__name__,
        fixture="SpellTransactionTests.native_server_fixture(native_qi=True)",
        actor_kind="owned_player",
        breed=factory_character["breed"],
        native_map_id=factory_character["map_id"],
        owner_level_facts=owner_level_facts.plain(),
        source_context="one real ordinary native factory; no per-item criteria truth or equipability inferred",
        runtime_execution_verified=False,
        effect_handlers_invoked=False,
        runtime_route_evidence="configured production factory declaration; no live dispatcher constructed",
        live_dispatcher_bindings_verified=False,
        actual_lifecycle_verified=False,
    )
    (OUT / "factory-context.json").write_text(
        json.dumps(factory_context, indent=2) + "\n"
    )
factory_blockers = {}
factory_family_graphs = defaultdict(Counter)
factory_source_rows = []

print("CATALOG_LOADED", len(RULES), flush=True)

operations, criteria = {}, {}
rejected_dimensions = {
    name: defaultdict(set)
    for name in (
        "criterion_functions",
        "event_channel_and_id",
        "selectors",
        "timing_definitions",
    )
}
counts = Counter()
errors = []
# This run inspects working-tree helpers. This newly written contract has not
# received actual PostgreSQL lifecycle qualification or deployment.
staged_unqualified = args.unqualified_source_contract


def json_default(value):
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(f"Unsupported report value: {type(value).__name__}")


def emit(handle, row):
    handle.write(
        json.dumps(row, default=json_default, ensure_ascii=False, separators=(",", ":"))
        + "\n"
    )


def criterion_info(expression, reference, node_id):
    if not expression or not expression.strip():
        return []
    try:
        tree = parse_local_criterion(expression)
        names = sorted(
            {
                n.func.id
                for n in ast.walk(tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            }
        )
    except (ValueError, TypeError, SyntaxError) as exc:
        names = ["UNPARSED:" + type(exc).__name__]
    for name in names:
        bucket = criteria.setdefault(
            name, dict(references=set(), nodes=set(), expressions=set())
        )
        bucket["references"].add(reference)
        bucket["nodes"].add(node_id)
        bucket["expressions"].add(expression)
    return names


def compact(row):
    # Raw parameter pairs and timing/selector/HMI definitions are authoritative;
    # omit only redundant sampled arrays, retaining level branch metadata.
    return {
        k: v
        for k, v in row.items()
        if k
        not in (
            "parameters_by_level",
            "parameter0_by_level",
            "probabilities",
            "native_realtime_durations",
            "native_skip_turn_timer_by_level",
        )
    }


def collect_graph(reference, roots, definitions, contract_reasons):
    pending = list(definitions)
    seen = set()
    states = {}
    nodes = []
    missing = []
    dynamic = []
    while pending:
        key = str(pending.pop())
        if key in seen:
            continue
        seen.add(key)
        row = (
            definitions.get(key)
            or compiled.effects.get(key)
            or compiled.source_states["effects"].get(key)
        )
        if row is None:
            missing.append(dict(kind="effect", reference=key))
            continue
        family = row["effect_class"]
        assessment = assess_operation(row, characteristic_registry=registry)
        operation = operation_for_family(
            family,
            characteristic_registry=registry,
            set_current_families=SET_CURRENT_FAMILIES,
        )
        calls = criterion_info(row.get("criteria", ""), reference, int(key))
        capability_level = row.get("minimum_level")
        if type(capability_level) is int:
            capability = validate_effect(
                row,
                capability_level,
                registry,
                runtime_bindings={},
                criteria_capability=None,
            )
            capability_evidence = dict(
                **asdict(capability),
                level_scope=dict(
                    sampled_level=capability_level,
                    minimum=row.get("minimum_level"),
                    maximum=row.get("maximum_level"),
                ),
                runtime_binding_evidence="not instantiated by read-only equipment audit",
                criteria_context_provider="not supplied; no conditional support inferred",
            )
        else:
            capability_evidence = dict(
                status="unknown",
                operation_id=None,
                family=family,
                level=None,
                parameters=(),
                dependencies=(),
                requires_context=(),
                reasons=("native operation level range is missing",),
                level_scope=None,
                runtime_binding_evidence="not instantiated by read-only equipment audit",
                criteria_context_provider="not supplied; no conditional support inferred",
            )
        node = dict(
            reference=int(key),
            family=family,
            definition=compact(row),
            operation=None if operation is None else asdict(operation),
            assessment=asdict(assessment),
            criterion_functions=calls,
            executable_capability=capability_evidence,
            runtime_execution_verified=False,
            source_graph_rejected=any(contract_reasons),
            native_context_metadata=dict(
                selector=row.get("native_target_selector"),
                timing=row.get("native_timing_definition"),
                event_masks=row.get("target_masks"),
                application=row.get("application_flag"),
                removal=row.get("removal_flag"),
            ),
            context_status="description-only; actual invocation/recipient/lifecycle required",
        )
        nodes.append(node)
        opid = (
            "NO_OPERATION_DESCRIPTION" if operation is None else operation.operation_id
        )
        bucketkey = (family, opid, assessment.status)
        bucket = operations.setdefault(
            bucketkey,
            dict(
                references=set(),
                nodes=set(),
                prerequisites=set(),
                reasons=set(),
                executors=set(),
                source_contract_rejections=set(),
                rejected_source_graph_references=set(),
                capability_statuses=set(),
                capability_context_requirements=set(),
                capability_reasons=set(),
            ),
        )
        bucket["references"].add(reference)
        bucket["nodes"].add(int(key))
        bucket["prerequisites"].update(assessment.prerequisites)
        bucket["reasons"].update(assessment.reasons)
        bucket["capability_statuses"].add(capability_evidence["status"])
        bucket["capability_context_requirements"].update(
            capability_evidence.get("requires_context", ())
        )
        bucket["capability_reasons"].update(capability_evidence.get("reasons", ()))
        if operation:
            bucket["executors"].add(operation.executor)
        bucket["source_contract_rejections"].update(r for r in contract_reasons if r)
        if any(contract_reasons):
            bucket["rejected_source_graph_references"].add(reference)
            for name in calls:
                rejected_dimensions["criterion_functions"][name].add(reference)
            for channel, ids in enumerate(row.get("target_masks") or ()):
                for event in ids or ():
                    rejected_dimensions["event_channel_and_id"][
                        f"{channel}:{event}"
                    ].add(reference)
            selector = row.get("native_target_selector") or {}
            rejected_dimensions["selectors"][
                f"{selector.get('class')}:{selector.get('mask')}"
            ].add(reference)
            rejected_dimensions["timing_definitions"][
                json.dumps(
                    row.get("native_timing_definition") or {},
                    default=json_default,
                    sort_keys=True,
                )
            ].add(reference)
        pending.extend(str(child) for child in row.get("children", ()))
        if family == 304:
            raw = row.get("parameters", ())
            if len(raw) < 2 or raw[1] != 0:
                dynamic.append(
                    dict(
                        effect=int(key),
                        reason="state identifier depends on invocation level",
                    )
                )
                continue
            state_id = int(raw[0])
            statekey = str(state_id)
            if statekey in states:
                continue
            state = compiled.source_states["states"].get(statekey)
            if state is None:
                missing.append(dict(kind="state", reference=state_id))
                continue
            states[statekey] = compact(state)
            pending.extend(str(child) for child in state.get("effect_ids", ()))
            # Record each native level-selected effect set. If it differs, also
            # traverse every explicitly exported alternate branch.
            checks = state.get("native_level_checks", {})
            for check in checks.values() if isinstance(checks, dict) else ():
                if isinstance(check, dict):
                    pending.extend(
                        str(child)
                        for child in check.get("effect_ids", check.get("effects", ()))
                    )
    return dict(
        reference=reference,
        passive_root_ids=roots,
        nodes=nodes,
        states=states,
        missing_native_definitions=missing,
        dynamic_identity_dependencies=dynamic,
        graph_complete_for_exported_static_identities=not missing and not dynamic,
        runtime_execution_verified=False,
    )


with (OUT / "full-items.jsonl").open("w") as items_file, (
    OUT / "complete-graphs.jsonl"
).open("w") as graphs_file:
    selected_rules = [
        (ref, rule)
        for ref, rule in sorted(RULES.items())
        if (resume_references is None or ref in resume_references)
        and (not args.smoke_reference or ref in args.smoke_reference)
    ]
    for index, (reference, rule) in enumerate(selected_rules, 1):
        if args.max_items is not None and index > args.max_items:
            break
        counts["ordinary_native_templates"] += 1
        base = dict(
            reference=reference,
            native_slots=rule["slots"],
            native_minimum_level=rule["minimum_level"],
        )
        try:
            template = equipment_stats.CATALOG.get(reference) or empty_template(
                reference
            )
            base["name"] = None if template is None else template.get("name")
            native_plan = copied_equipment_plan(reference, native)
            passive = [
                r
                for r in native_plan["roots"]
                if r["variant"] == 0 and r["metadata"]["native_active_effect"] is False
            ]
            definitions = equipment_effect_definitions({"roots": passive})
            item = dict(uid=101, character_id=7, reference=reference, quantity=1)
            selection = inventory_elements.create(reference)
            if selection is not None and template is not None:
                for e in template["effects"]:
                    if e["generic"] in inventory_elements.FIELDS:
                        selection[inventory_elements.FIELDS[e["generic"]]] = sum(
                            1 << n for n in range(1, int(e["params"][2]) + 1)
                        )
                inventory_elements.masks(selection)
                item.update(selection)
            base["native_element_selection"] = selection
            variants = [(None, item)]
            if reference in pets:
                model = pets[reference]
                variants = [
                    (
                        rank,
                        dict(
                            item,
                            pet=dict(
                                model_id=model["model_id"],
                                xp=rank * model["xp_per_level"],
                                xp_per_level=model["xp_per_level"],
                                maximum_level=model["maximum_level"],
                                health=model["maximum_health"],
                                sleep_item_ref=0,
                                sleep_date=0,
                            ),
                        ),
                    )
                    for rank in sorted({0, model["maximum_level"]})
                ]
            elif reference in mounts:
                model = mounts[reference]
                variants = [
                    (
                        rank,
                        dict(
                            item,
                            mount=dict(
                                model_id=model["model_id"],
                                xp=rank * model["xp_per_level"],
                            ),
                        ),
                    )
                    for rank in sorted({0, model["maximum_level"]})
                ]
            cases = []
            all_reasons = []
            for rank, typed in variants:
                character = dict(
                    factory_character or {},
                    id=7,
                    account_id=3 if args.factory_graphs else 9,
                    breed=8,
                    level=245,
                    active_build_index=0,
                    builds={},
                    inventory_items=[typed],
                )
                selected = [dict(uid=101, slot=rule["slots"][0])]
                static_error = planner_error = None
                try:
                    static = equipment_stats.bonuses(
                        character, _selected_entries=selected
                    )
                except (ValueError, KeyError, TypeError) as exc:
                    static = dict(unsupported=[])
                    static_error = dict(error_type=type(exc).__name__, error=str(exc))
                    counts["static_context_or_data_rejections"] += 1
                try:
                    sources = plan(
                        character,
                        ordinary_only=True,
                        _selected_entries=selected,
                        catalog=native,
                    )
                except (ValueError, KeyError, TypeError) as exc:
                    sources = ()
                    planner_error = dict(error_type=type(exc).__name__, error=str(exc))
                    counts["planner_context_or_data_rejections"] += 1
                    all_reasons.append("planner:" + str(exc))
                checks = []
                if sources:
                    extended = compiled_with_sources(compiled, sources)
                    for source in sources:
                        if args.factory_graphs:
                            result = validate_graph(
                                source,
                                extended,
                                registry,
                                runtime_bindings=factory_routes,
                                criteria_capability=factory_provider,
                                owner_level_facts=owner_level_facts,
                            )
                            reason = result.reasons[0] if result.reasons else None
                            graph_families = sorted(
                                {
                                    row["effect_class"]
                                    for row in source["effects"].values()
                                }
                            )
                            assessed = dict(
                                reference=reference,
                                native_companion_level=rank,
                                source_reference=source["source_reference"],
                                roots=source["roots"],
                                item_definition_families=graph_families,
                                capability=asdict(result),
                                family_membership_scope="item definition closure only; state graphs assessed separately by validate_graph",
                                evidence_scope="complete source assessment against configured factory",
                                runtime_execution_verified=False,
                                actual_lifecycle_verified=False,
                            )
                            factory_source_rows.append(assessed)
                            for family in graph_families:
                                factory_family_graphs[family][result.status] += 1
                            counts["factory_source_graphs"] += 1
                            counts["factory_graph_" + result.status] += 1
                            if result.status != "supported":
                                # Attribute failure to the returned blocking family,
                                # never every sibling merely present in this source.
                                key = (
                                    result.family,
                                    tuple(result.requires_context),
                                    reason,
                                    result.status,
                                )
                                bucket = factory_blockers.setdefault(
                                    key, dict(references=set(), roots=set(), sources=0)
                                )
                                bucket["references"].add(reference)
                                bucket["roots"].update(source["roots"])
                                bucket["sources"] += 1
                            checks.append(
                                dict(
                                    roots=source["roots"],
                                    unplanned=source.get(
                                        "unplanned_passive_effect_ids"
                                    ),
                                    reason=reason,
                                    status=result.status,
                                    factory_capability=asdict(result),
                                    assessment_authority="actual native factory routes and capability provider",
                                    structural_admission_only=True,
                                    runtime_execution_verified=False,
                                )
                            )
                        else:
                            reason = ordinary_turn_state_contract(
                                source, extended, registry
                            )
                            checks.append(
                                dict(
                                    roots=source["roots"],
                                    unplanned=source.get(
                                        "unplanned_passive_effect_ids"
                                    ),
                                    reason=reason,
                                    assessment_authority="legacy structural contract; not latest factory support",
                                    structural_admission_only=True,
                                    runtime_execution_verified=False,
                                )
                            )
                        all_reasons.append(reason)
                cases.append(
                    dict(
                        native_companion_level=rank,
                        static_unsupported=static["unsupported"],
                        static_context_or_data_error=static_error,
                        planner_context_or_data_error=planner_error,
                        ready_source_checks=checks,
                        has_ready_sources=bool(sources),
                    )
                )
                counts["typed_cases"] += 1
                counts["cases_with_static_unsupported"] += bool(static["unsupported"])
                counts["cases_with_rejected_ready_sources"] += any(
                    c["reason"] is not None for c in checks
                ) or bool(planner_error)
            base["cases"] = cases
            base["equip_criterion"] = conditions.get(str(reference), {}).get("EQUIP")
            base["equip_criterion_functions"] = criterion_info(
                base["equip_criterion"], reference, 0
            )
            base["runtime_execution_verified"] = False
            base["equipability_verified"] = False
            emit(items_file, base)
            graph = collect_graph(
                reference, [r["reference"] for r in passive], definitions, all_reasons
            )
            emit(graphs_file, graph)
            counts["complete_static_identity_graphs"] += graph[
                "graph_complete_for_exported_static_identities"
            ]
            counts["graph_nodes_occurrences"] += len(graph["nodes"])
        except Exception as exc:
            error = dict(
                reference=reference,
                phase="inventory-or-graph",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            errors.append(error)
            emit(items_file, dict(base, error=error))
        if index % 250 == 0:
            items_file.flush()
            graphs_file.flush()
            print(
                "PROGRESS",
                index,
                "errors",
                len(errors),
                "seconds",
                round(time.monotonic() - started, 2),
                flush=True,
            )


def serial_bucket(bucket):
    return {key: sorted(value) for key, value in bucket.items()}


(OUT / "operations.json").write_text(
    json.dumps(
        [
            dict(
                family=k[0],
                operation_id=k[1],
                assessment_status=k[2],
                **serial_bucket(v),
            )
            for k, v in sorted(operations.items())
        ],
        default=json_default,
        indent=2,
    )
    + "\n"
)
(OUT / "rejected-operations.json").write_text(
    json.dumps(
        [
            dict(
                family=k[0],
                operation_id=k[1],
                assessment_status=k[2],
                **serial_bucket(v),
            )
            for k, v in sorted(operations.items())
            if v["rejected_source_graph_references"]
        ],
        default=json_default,
        indent=2,
    )
    + "\n"
)
(OUT / "rejected-context-dimensions.json").write_text(
    json.dumps(
        {
            name: {key: sorted(refs) for key, refs in sorted(values.items())}
            for name, values in rejected_dimensions.items()
        },
        indent=2,
    )
    + "\n"
)
(OUT / "criteria-contexts.json").write_text(
    json.dumps({k: serial_bucket(v) for k, v in sorted(criteria.items())}, indent=2)
    + "\n"
)
if args.factory_graphs:
    with (OUT / "factory-source-graphs.jsonl").open("w") as handle:
        for row in factory_source_rows:
            emit(handle, row)
    blockers = [
        dict(
            blocking_family=key[0],
            requires_context=list(key[1]),
            first_blocker=key[2],
            status=key[3],
            sources=bucket["sources"],
            references=sorted(bucket["references"]),
            roots=sorted(bucket["roots"]),
            runtime_execution_verified=False,
        )
        for key, bucket in sorted(
            factory_blockers.items(), key=lambda pair: repr(pair[0])
        )
    ]
    (OUT / "factory-blocker-groups.json").write_text(
        json.dumps(blockers, indent=2) + "\n"
    )
    family_inventory = []
    for family in sorted({key[0] for key in operations} | set(factory_routes.routes)):
        route = factory_routes.routes.get(family)
        family_inventory.append(
            dict(
                family=family,
                configured_factory_route_declared=route is not None,
                live_dispatcher_binding_verified=False,
                native_item_references=sorted(
                    {
                        ref
                        for key, bucket in operations.items()
                        if key[0] == family
                        for ref in bucket["references"]
                    }
                ),
                native_effect_references=sorted(
                    {
                        ref
                        for key, bucket in operations.items()
                        if key[0] == family
                        for ref in bucket["nodes"]
                    }
                ),
                handler_type=None
                if route is None
                else route.handler_type.__module__
                + "."
                + route.handler_type.__qualname__,
                inline=None if route is None else route.inline,
                operation_contract=None
                if route is None or route.contract is None
                else asdict(route.contract),
                item_definition_source_statuses=dict(
                    factory_family_graphs.get(family, {})
                ),
                item_definition_membership_excludes_referenced_state_descendants=True,
                source_graph_counts_are_membership_not_failure_attribution=True,
                first_blocker_groups=[
                    row for row in blockers if row["blocking_family"] == family
                ],
                runtime_execution_verified=False,
                actual_lifecycle_verified=False,
            )
        )
    (OUT / "factory-family-routes.json").write_text(
        json.dumps(family_inventory, default=json_default, indent=2) + "\n"
    )
after = hashes()
summary = dict(
    counts=dict(counts),
    errors=errors,
    native_release=native_catalog.release(),
    elapsed_seconds=time.monotonic() - started,
    source_stable=before == after,
    source_hashes_before=before,
    source_hashes_after=after,
    working_tree_not_loaded_release=True,
    staged_unqualified_contract=staged_unqualified,
    factory_graph_assessment_enabled=args.factory_graphs,
    factory_context=factory_context,
    smoke_references=sorted(set(args.smoke_reference)),
    runtime_execution_verified=False,
    evidence_limit="No combat execution, lease, equipability or dynamic recipient qualification. Conditional operation descriptions are not runtime support.",
    population=(
        "Scoped backfill; combine with linked base receipt, not a homogeneous fresh all-source view"
        if base_receipt is not None
        else "Bounded smoke sample"
        if args.max_items is not None
        else "All current native ordinary equipment RULES, not the previous212 cohort. Pet/mount levels only native endpoints."
    ),
    full_population=args.max_items is None and base_receipt is None,
    base_receipt=base_receipt,
    source_differences_vs_base=(
        {
            key: dict(
                base=base_receipt["base_source_hashes"].get(key),
                current=before.get(key),
            )
            for key in set(before) | set(base_receipt["base_source_hashes"])
            if before.get(key) != base_receipt["base_source_hashes"].get(key)
        }
        if base_receipt
        else {}
    ),
    scanner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
)
(OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(
    "COMPLETE",
    dict(counts),
    "errors",
    len(errors),
    "source_stable",
    before == after,
    flush=True,
)
