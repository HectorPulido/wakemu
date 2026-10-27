"""Build per-reference mechanic evidence and proposed earned-witness recipes.

This is an offline reader. It never imports World, executes a scenario, grants a
state/resource, changes admission or opens a database. Proposed native recipes,
preview success, framework support and earned encounter closure stay separate.
"""
import argparse
from collections import Counter
from copy import deepcopy
import hashlib
import json
import mmap
from pathlib import Path
import re

SCHEMA = "monster-mechanic-coverage-v1"
RECIPE_SCHEMA = "monster-earned-witness-plan-v1"
ADMIN_REFERENCE = 5482
BRIZLON_REFERENCES = frozenset((4251, 4280))
SHARED_RULES = {
    "native_passive_321_or_exact_421_removal_route": "native_callback_removal",
    "direct_player_attack_geometry_or_team_condition": "direct_attack_guard",
    "only_optional_owned_protection": "optional_owned_defense",
}
LEVELS = ("S0", "S1", "S2", "S3", "S4")
MAX_SMALL_DOCUMENT_BYTES = 8 * 1024 * 1024
MAX_FACT_ROW_BYTES = 8 * 1024 * 1024
SOURCE_REFERENCE_PATTERN = re.compile(
    r"\bReferences\s*(?:\{\s*get;\s*\}\s*=|=>)\s*new\[\]\s*\{([0-9,\s]+)\}"
)
COMPONENT_CHECKS = frozenset(
    (
        "native_ready",
        "actual_jondo_selection",
        "paid_player_action",
        "earned_component",
        "negative_control",
    )
)
ENCOUNTER_CHECKS = COMPONENT_CHECKS | frozenset(
    (
        "authored_scene",
        "complete_phase_path",
        "native_success",
        "failure_branch",
    )
)
DURABLE_CHECKS = ENCOUNTER_CHECKS | frozenset(
    (
        "durable_result",
        "replay_once",
        "reconnect",
        "exit_and_subsequent_play",
    )
)


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_small(path, *, limit=MAX_SMALL_DOCUMENT_BYTES):
    path = Path(path)
    if path.stat().st_size > limit:
        raise ValueError("Document exceeds bounded reader limit: " + str(path))
    return json.loads(path.read_bytes())


def fact_catalog_revision(path):
    """Read only the bounded header of the extracted producer inventory."""
    with Path(path).open("rb") as stream:
        header = stream.read(65536)
    match = re.search(rb'"catalog_revision"\s*:\s*"([0-9a-f]{64})"', header)
    return None if match is None else match.group(1).decode("ascii")


def streamed_fact_rows(path, *, maximum_row_bytes=MAX_FACT_ROW_BYTES):
    """Read the extracted fact rows without retaining its large graph in RAM.

    Input is the existing native-producer-facts JSON format. JSONDecoder parses
    one bounded row at a time; mmap is only backing storage, never json.loads of
    the complete source. The extracted facts contain no executable callbacks.
    """
    decoder = json.JSONDecoder()
    with Path(path).open("rb") as source:
        with mmap.mmap(source.fileno(), 0, access=mmap.ACCESS_READ) as mapped:
            marker = re.search(rb'"rows"\s*:\s*\[', mapped)
            if marker is None:
                raise ValueError("Producer facts have no rows array")
            position = marker.end()
            need_comma = False
            while True:
                while position < len(mapped) and mapped[position] in b" \r\n\t":
                    position += 1
                if position >= len(mapped):
                    raise ValueError("Truncated producer facts array")
                if mapped[position] == ord("]"):
                    if mapped[position + 1 :].strip() != b"}":
                        raise ValueError("Invalid producer facts root terminator")
                    return
                if need_comma:
                    if mapped[position] != ord(","):
                        raise ValueError("Invalid producer facts row delimiter")
                    position += 1
                    while position < len(mapped) and mapped[position] in b" \r\n\t":
                        position += 1
                    if position >= len(mapped) or mapped[position] == ord("]"):
                        raise ValueError("Missing producer facts row after comma")
                size = min(65536, maximum_row_bytes)
                while True:
                    raw = mapped[position : position + size]
                    try:
                        text = raw.decode("utf8")
                        row, consumed = decoder.raw_decode(text)
                        if not isinstance(row, dict):
                            raise ValueError("Producer fact row must be an object")
                        position += len(text[:consumed].encode("utf8"))
                        break
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        if size >= maximum_row_bytes or len(raw) < size:
                            raise ValueError("Truncated or oversized producer fact row")
                        size = min(size * 2, maximum_row_bytes)
                yield row
                need_comma = True


def reference_rows(rows, *, key="reference"):
    result = {}
    for row in rows:
        reference = row.get(key)
        if type(reference) is not int or reference <= 0 or reference in result:
            raise ValueError("Invalid or duplicate monster reference")
        result[reference] = row
    return result


def source_strategy_references(paths):
    """Observe literal source declarations; this is not a deployment claim."""
    references = []
    for path in paths:
        text = Path(path).read_text()
        for group in SOURCE_REFERENCE_PATTERN.findall(text):
            references.extend(int(value) for value in group.split(",") if value.strip())
    if not references or len(set(references)) != len(references):
        raise ValueError("Missing or duplicate literal strategy source references")
    return frozenset(references)


def preparation_recipes(reference, spells):
    # Reuse the existing finite source-owned preparation inventory. Importing
    # this module is light; scenario execution and World imports remain deferred.
    from monster_pending_scenarios import scenario_recipes

    return [
        dict(
            spell_id=spell,
            recipe=recipe,
            consumer="monster_pending_scenarios.prepare_scenario",
            validated=False,
        )
        for spell in sorted(set(spells))
        for recipe in scenario_recipes(reference, spell)
    ]


def witness_plan(row, fact=None):
    family = SHARED_RULES.get(row["rule"])
    if family is None:
        return None
    fact = {} if fact is None else fact
    if fact and fact.get("reference") != row["reference"]:
        raise ValueError("Producer facts belong to another reference")
    protection = deepcopy(fact.get("protection", ()))
    removers = [
        deepcopy(candidate)
        for field in ("protected_state_removals", "protected_effect_dispels")
        for candidate in fact.get(field, ())
        if candidate.get("source") == "innate"
    ]
    spells = fact.get("owned_spells", ())
    missing = deepcopy(fact.get("innate", {}).get("missing", ()))
    missing += deepcopy(fact.get("owned", {}).get("missing", ()))
    bindings = []
    if not fact:
        bindings.append("exact_native_producer_facts")
    if family == "native_callback_removal" and not removers:
        bindings.append("reachable_native_removal_producer")
    if family == "direct_attack_guard" and not any(
        p.get("conditions") for p in protection
    ):
        bindings.append("original_attack_guard_conditions")
    if missing:
        bindings.append("complete_native_dependency_graph")
    events = sorted(
        {
            event
            for remover in removers
            for listener in remover.get("listeners", ())
            for slot in listener.get("masks", ())
            if slot
            for event in slot
        }
    )
    unknown_events = [
        event
        for event in events
        if event
        not in (
            0,
            1,
            2,
            5,
            6,
            7,
            8,
            9,
            11,
            1001,
            1002,
            1003,
            1010,
            1012,
            1037,
            2215,
            2216,
            2217,
            2218,
            2268,
        )
    ]
    if unknown_events:
        bindings.append("actual_native_event_producer")
    steps = [
        dict(
            operation="construct_native_actor_and_ready",
            consumer="validate_monster_spell_activation.fixture",
            constraints="Use original level/book/resources/initialization; no gifts.",
        )
    ]
    if family == "native_callback_removal":
        steps += [
            dict(
                operation="earn_one_source_removal_path",
                consumer="monster_pending_scenarios.prepare_scenario",
                constraint="Select only a source-backed owned action or actual lifecycle/KO producer.",
            ),
            dict(
                operation="observe_exact_native_removal",
                constraint="Assert original state/effect removal; source/target and clock must match.",
            ),
        ]
    elif family == "direct_attack_guard":
        steps += [
            dict(
                operation="find_legal_paid_attack_geometry_and_type",
                consumer="wakfu_server.combat_server_spell.prepare_server_spell",
                constraint="Evaluate original guard; compare legal and protected controls.",
            ),
            dict(
                operation="commit_paid_positive_and_negative_controls",
                consumer="wakfu_server.combat_spell_commit.commit_spell_transaction",
            ),
        ]
    else:
        steps += [
            dict(operation="observe_original_constructor_vulnerability"),
            dict(operation="run_actual_jondo_opening_and_owned_defense_if_legal"),
            dict(
                operation="commit_paid_player_attack",
                consumer="wakfu_server.combat_spell_commit.commit_spell_transaction",
            ),
        ]
    steps.append(
        dict(
            operation="record_component_without_implying_victory",
            constraint="Keep terminal/exit/replay acceptance separate.",
        )
    )
    return dict(
        schema=RECIPE_SCHEMA,
        reference=row["reference"],
        family=family,
        proposed=True,
        executed=False,
        evidence_level="S0",
        source_status="source_bound_candidate"
        if not bindings
        else "requires_source_binding",
        initial_states=deepcopy(fact.get("initial_states", ())),
        protection=protection,
        removal_candidates=removers,
        owned_spells=list(spells),
        existing_preparations=preparation_recipes(row["reference"], spells),
        subscribed_events=events,
        unknown_event_producers=unknown_events,
        missing_bindings=bindings,
        dependency_gaps=missing,
        steps=steps,
        forbidden_operations=[
            "assign_state",
            "assign_hp",
            "assign_resources",
            "emit_unproven_event",
            "force_victory",
        ],
        executable_without_scene_binding=False,
    )


def qualified_level(record, *, catalog_revision=None, runtime_generation=None):
    """Accept only explicit earned evidence; requested scope cannot promote it."""
    if record.get("schema") != "monster-mechanic-qualification-v1":
        raise ValueError("Unknown mechanic evidence schema")
    if type(record.get("reference")) is not int or record["reference"] <= 0:
        raise ValueError("Missing exact mechanic evidence reference")
    if record.get("passed") is not True or record.get("gifts") is not False:
        raise ValueError("Unpassed or gifted mechanic evidence cannot qualify")
    if not re.fullmatch(r"[0-9a-f]{64}", record.get("catalog_revision", "")):
        raise ValueError("Missing exact evidence catalog revision")
    if catalog_revision is not None and record["catalog_revision"] != catalog_revision:
        raise ValueError("Mechanic evidence belongs to another catalog revision")
    if (
        not isinstance(record.get("source_receipt"), str)
        or not record["source_receipt"]
        or not re.fullmatch(r"[0-9a-f]{64}", record.get("source_receipt_sha256", ""))
    ):
        raise ValueError("Mechanic evidence requires a hash-bound source receipt")
    if (
        runtime_generation is not None
        and record.get("runtime_generation") != runtime_generation
    ):
        raise ValueError("Mechanic evidence belongs to another runtime generation")
    scope = record.get("scope")
    if scope in ("selector_contract", "native_preview"):
        return "S1"
    if record.get("backend") != "jondo":
        raise ValueError("Earned Jondo evidence requires the actual Jondo backend")
    required = {
        "native_component": COMPONENT_CHECKS,
        "complete_encounter": ENCOUNTER_CHECKS,
        "durable_encounter": DURABLE_CHECKS,
    }.get(scope)
    if required is None:
        raise ValueError("Unknown mechanic evidence scope")
    checks = record.get("checks", {})
    if not isinstance(checks, dict) or any(
        checks.get(check) is not True for check in required
    ):
        raise ValueError(
            "Incomplete earned checks for requested mechanic evidence scope"
        )
    return {
        "native_component": "S2",
        "complete_encounter": "S3",
        "durable_encounter": "S4",
    }[scope]


def brizlon_evidence(document, root):
    """Adapt the actual earned pair receipt, preserving its component-only cap."""
    if document.get("schema") != "jondo-brizlon-large-body-qualification-v1":
        raise ValueError("Unknown Brizlon qualification format")
    revision = document["catalog"]["candidate"]
    records = []
    expected_stages = frozenset(
        (
            "genuine_ready",
            "selected_boss_producer_committed_owned1173",
            "actual1173_occupancy_and_player_turn_end_10016_4713",
            "real1001_4712_profile4252",
            "foreign_composite_uid_rejected_without_payment",
            "paid6007_removes4710_applies4711",
            "stale_transaction_retry_rejected_without_payment",
        )
    )
    for component in document.get("nativeComponents", ()):
        reference = component.get("reference")
        if reference not in BRIZLON_REFERENCES:
            raise ValueError("Foreign reference in shared prisoner evidence")
        path = (Path(root) / component["evidence"]).resolve()
        if Path(root).resolve() not in path.parents:
            raise ValueError("Native component receipt escaped repository root")
        envelope = read_small(path)
        result = envelope.get("result", {})
        expected_spell = 6011 if reference == 4251 else 6085
        if (
            component.get("passed") is not True
            or envelope.get("status") != "complete"
            or result.get("reference") != reference
            or result.get("passed") is not True
            or result.get("gifts") is not False
            or not expected_stages <= set(result.get("stages", ()))
            or result.get("initialSnapshot", {})
            .get("source", {})
            .get("catalogRevision")
            != revision
            or not any(
                row.get("action", {}).get("spellId") == expected_spell
                and row.get("strategyId") == "brizlon-prisoner"
                for row in result.get("actions", ())
            )
        ):
            raise ValueError("Unqualified native prisoner component receipt")
        payment = result.get("playerCast", {})
        if (
            payment.get("rawUid") != 6007
            or payment.get("costs", {}).get("ap") != 4
            or payment.get("before", {}).get("ap", 0)
            - payment.get("after", {}).get("ap", 0)
            != 4
        ):
            raise ValueError("Prisoner receipt does not prove actual native AP payment")
        records.append(
            dict(
                schema="monster-mechanic-qualification-v1",
                reference=reference,
                catalog_revision=revision,
                runtime_generation=document.get("catalog", {})
                .get("publication", {})
                .get("generation"),
                passed=True,
                gifts=False,
                backend="jondo",
                scope="native_component",
                checks={key: True for key in COMPONENT_CHECKS},
                source_receipt=str(path),
                source_receipt_sha256=checksum(path),
                limits=[
                    "Generic-map component; not an authored encounter or victory.",
                    "Natural book expiry is a separate earned branch, not post-kiss survival.",
                ],
            )
        )
    return records


def preview_evidence(document):
    """Existing spell-validator 'validated' means preview, never a paid fight."""
    if document.get("schema") != "native-npc-activation-validation-v1":
        raise ValueError("Unknown native spell validation format")
    for monster in document.get("monsters", ()):
        cases = [
            case
            for case in monster.get("cases", ())
            if case.get("status") == "validated"
            and any(
                target.get("effectful") is True
                and target.get("native_preview_source_unchanged") is True
                for target in case.get("successful_targets", ())
            )
        ]
        if cases:
            yield dict(
                reference=monster["ref"],
                level="S1",
                kind="native_spell_preview",
                spells=sorted({case["spell_id"] for case in cases}),
                limits="Native preview only; no earned mechanic, paid fight or result transferred.",
            )


def build_matrix(
    ownership,
    integration,
    *,
    strategy_references,
    facts=None,
    evidence=(),
    preview_documents=(),
    catalog_revision=None,
    runtime_generation=None,
    frameworks=()
):
    source = reference_rows(ownership["rows"])
    deferred = reference_rows(integration["rows"])
    if not set(deferred) <= source.keys() or ADMIN_REFERENCE in deferred:
        raise ValueError(
            "Integration references do not belong to the active source inventory"
        )
    active = {ref: row for ref, row in source.items() if ref != ADMIN_REFERENCE}
    if not set(strategy_references) <= active.keys():
        raise ValueError("Strategy reference is absent from active inventory")
    fact_rows = {} if facts is None else reference_rows(facts)
    proofs = {ref: [] for ref in active}
    rejected = []
    for record in evidence:
        ref = record.get("reference")
        if ref not in active:
            raise ValueError("Evidence belongs to an unknown or excluded reference")
        try:
            level = qualified_level(
                record,
                catalog_revision=catalog_revision,
                runtime_generation=runtime_generation,
            )
        except ValueError as error:
            rejected.append(
                dict(
                    reference=ref,
                    reason=str(error),
                    source_receipt=record.get("source_receipt"),
                )
            )
            continue
        proofs[ref].append(
            dict(
                level=level,
                kind=record["scope"],
                source_receipt=record.get("source_receipt"),
                source_receipt_sha256=record.get("source_receipt_sha256"),
                runtime_generation=record.get("runtime_generation"),
                limits=deepcopy(record.get("limits", ())),
            )
        )
    for document in preview_documents:
        compatible = (
            catalog_revision is None
            or document.get("catalog_revision", document.get("candidate_revision"))
            == catalog_revision
        )
        for record in preview_evidence(document):
            if record["reference"] in proofs:
                if compatible:
                    proofs[record["reference"]].append(record)
                else:
                    rejected.append(
                        dict(
                            reference=record["reference"],
                            reason="Legacy preview lacks exact current catalog identity; no compatibility inferred.",
                        )
                    )
    rows, recipes = [], []
    framework_refs = set(frameworks)
    if not framework_refs <= active.keys():
        raise ValueError("Framework annotation belongs to an unknown reference")
    for ref, row in sorted(active.items()):
        level = max((proof["level"] for proof in proofs[ref]), default="S0")
        post_pair = ref in deferred and ref not in BRIZLON_REFERENCES
        bucket = (
            "specific_source"
            if ref in strategy_references
            else ("integration_work" if ref in deferred else "normal_jondo")
        )
        rows.append(
            dict(
                reference=ref,
                name=row.get("name"),
                monster_type=row.get("monster_type"),
                original_classification=row["classification"],
                source_rule=row["rule"],
                work_bucket=bucket,
                source_strategy_declared=ref in strategy_references,
                framework_available=True if ref in framework_refs else None,
                evidence_level=level,
                earned_component_passed=level >= "S2",
                complete_encounter_passed=level >= "S3",
                case_closed=level == "S4",
                deployed=None,
                integration_original=ref in deferred,
                post_brizlon_backlog=post_pair,
                closure_status="durable_closed"
                if level == "S4"
                else (
                    "encounter_passed_durable_acceptance_pending"
                    if level == "S3"
                    else (
                        "native_component_passed_encounter_pending"
                        if level == "S2"
                        else "unresolved"
                    )
                ),
                integration_group=deferred.get(ref, {}).get("group"),
                evidence=proofs[ref],
            )
        )
        recipe = witness_plan(row, fact_rows.get(ref))
        if recipe is not None:
            recipes.append(recipe)
    backlog = [row for row in rows if row["post_brizlon_backlog"]]
    return dict(
        schema=SCHEMA,
        scope="Offline coverage and proposed recipes; no runtime or admission changes.",
        catalog_revision=catalog_revision,
        runtime_generation=runtime_generation,
        evidence_scope="Only supplied exact receipts. S0 is not a claim that no other tests exist.",
        summary=dict(
            active_references=len(rows),
            source_work_allocation=dict(Counter(r["work_bucket"] for r in rows)),
            baseline_classification=dict(
                Counter(r["original_classification"] for r in rows)
            ),
            evidence_levels=dict(Counter(r["evidence_level"] for r in rows)),
            proposed_recipes=len(recipes),
            executed_recipes=0,
            post_brizlon_backlog=len(backlog),
            post_brizlon_closed=sum(r["case_closed"] for r in backlog),
            post_brizlon_remaining=sum(not r["case_closed"] for r in backlog),
            full_victories_not_inferred=True,
        ),
        rows=rows,
        post_brizlon_closure=backlog,
        proposed_recipes=recipes,
        rejected_evidence=rejected,
        deployed_status="Not inferred by this offline tool.",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ownership", type=Path, required=True)
    parser.add_argument("--integration", type=Path, required=True)
    parser.add_argument("--producer-facts", type=Path)
    parser.add_argument("--strategy-source", type=Path, action="append", default=[])
    parser.add_argument("--evidence", type=Path, action="append", default=[])
    parser.add_argument("--spell-validation", type=Path, action="append", default=[])
    parser.add_argument("--catalog-revision")
    parser.add_argument("--runtime-generation")
    parser.add_argument("--framework-reference", type=int, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-recipes", type=int)
    parser.add_argument("--expected-active", type=int)
    parser.add_argument("--expected-backlog", type=int)
    parser.add_argument("--expected-strategies", type=int)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    sources = args.strategy_source or [
        root / "server/ai-jondo-service/Host" / name
        for name in ("BasicMechanicAis.cs", "SupremeMechanicAis.cs")
    ]
    ownership, integration = read_small(args.ownership), read_small(args.integration)
    selected = {
        row["reference"] for row in ownership["rows"] if row["rule"] in SHARED_RULES
    }
    facts = (
        []
        if args.producer_facts is None
        else [
            row
            for row in streamed_fact_rows(args.producer_facts)
            if row.get("reference") in selected
        ]
    )
    evidence = []
    for path in args.evidence:
        document = read_small(path)
        if document.get("schema") == "jondo-brizlon-large-body-qualification-v1":
            evidence.extend(brizlon_evidence(document, root))
        else:
            document.update(
                source_receipt=str(path), source_receipt_sha256=checksum(path)
            )
            evidence.append(document)
    report = build_matrix(
        ownership,
        integration,
        strategy_references=source_strategy_references(sources),
        facts=facts,
        evidence=evidence,
        preview_documents=[read_small(path) for path in args.spell_validation],
        catalog_revision=args.catalog_revision,
        runtime_generation=args.runtime_generation,
        frameworks=args.framework_reference,
    )
    for expected, actual, label in (
        (args.expected_recipes, report["summary"]["proposed_recipes"], "recipe"),
        (args.expected_active, report["summary"]["active_references"], "active"),
        (args.expected_backlog, report["summary"]["post_brizlon_backlog"], "backlog"),
        (
            args.expected_strategies,
            sum(r["source_strategy_declared"] for r in report["rows"]),
            "strategy",
        ),
    ):
        if expected is not None and expected != actual:
            raise ValueError("Unexpected " + label + " reference count")
    inputs = [
        args.ownership,
        args.integration,
        *sources,
        *args.evidence,
        *args.spell_validation,
    ]
    if args.producer_facts is not None:
        inputs.append(args.producer_facts)
    if args.output.resolve() in {path.resolve() for path in inputs}:
        raise ValueError("Coverage output must not replace a source input")
    fact_revision = (
        None
        if args.producer_facts is None
        else fact_catalog_revision(args.producer_facts)
    )
    for recipe in report["proposed_recipes"]:
        recipe.update(
            source_fact_catalog_revision=fact_revision,
            target_catalog_revision=args.catalog_revision,
            cross_catalog_execution_compatibility_assumed=False,
        )
        recipe["recipe_id"] = hashlib.sha256(
            json.dumps(
                recipe, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode()
        ).hexdigest()
    report["source_sha256"] = {str(path): checksum(path) for path in inputs}
    report["tool_sha256"] = checksum(__file__)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
