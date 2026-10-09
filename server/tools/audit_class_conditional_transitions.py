"""Bounded real-owned-action conditional transitions, without state injection."""
import argparse
import ast
from collections import Counter, defaultdict, deque
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import struct
from class_state_source_paths import reverse_edges, shortest_source_path, graph_nodes

import audit_ready_start as ready_audit
from audit_class_normal_casts import actual_state_ledgers, root_failure
from class_spell_eligible_targets import eligible_cast_targets
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import server_runtime, prepare_server_spell
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.combat_morph_spellbook import morph_record
from wakfu_server.combat_local_criteria import parse_local_criterion
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import available_spells, ACTIVE_SLOT_LEVELS, validate_deck


def independent_transition_branches(precast):
    """ON and expiry control share actual precast authority, never cast costs."""
    return deepcopy(precast), deepcopy(precast)


def committed_state_absent(evidence, owner_id, state):
    """Only actual committed ordered-ledger evidence proves consumption."""
    owner = evidence.get("state_ledgers_after", {}).get(str(owner_id))
    return owner is not None and not any(
        entry["reference"] == state for entry in owner["entries"]
    )


def mandatory_caster_deck_references(raw):
    """Only conjunctive positive literal caster requirements constrain a deck."""

    def visit(node):
        if isinstance(node, ast.Expression):
            return visit(node.body)
        if isinstance(node, ast.BoolOp):
            children = [visit(child) for child in node.values]
            if isinstance(node.op, ast.And):
                return set().union(*children)
            return set.intersection(*children) if children else set()
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "IsSpellInDeck"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and type(node.args[0].value) is int
            and (
                len(node.args) == 1
                or len(node.args) == 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
                and node.args[1].value.lower() == "caster"
            )
        ):
            return {node.args[0].value}
        return set()

    return visit(parse_local_criterion(raw))


def literal_state_requirements(raw):
    requirements = []
    tree = parse_local_criterion(raw)
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    for node in ast.walk(tree):
        ancestor, negations = parents.get(node), 0
        while ancestor is not None:
            if isinstance(ancestor, ast.UnaryOp) and isinstance(ancestor.op, ast.Not):
                negations += 1
            ancestor = parents.get(ancestor)
        if negations % 2:
            continue
        if (
            isinstance(node, ast.Compare)
            and len(node.ops) == 1
            and len(node.comparators) == 1
            and isinstance(node.left, ast.Call)
            and isinstance(node.left.func, ast.Name)
            and node.left.func.id == "GetStateLevel"
            and node.left.args
            and isinstance(node.left.args[0], ast.Constant)
            and type(node.left.args[0].value) is int
            and isinstance(node.comparators[0], ast.Constant)
            and type(node.comparators[0].value) is int
        ):
            operation = {
                ast.Eq: "exact",
                ast.GtE: "minimum",
                ast.Gt: "exclusive_minimum",
                ast.LtE: "maximum",
                ast.Lt: "exclusive_maximum",
            }.get(type(node.ops[0]))
            if operation:
                selectors = [
                    arg.value.lower()
                    for arg in node.left.args[1:]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                ]
                requirements.append(
                    dict(
                        state=node.left.args[0].value,
                        selector=selectors[-1] if selectors else "caster",
                        level=node.comparators[0].value,
                        comparison=operation,
                    )
                )
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("HasState", "HasStateFromLevel")
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and type(node.args[0].value) is int
        ):
            continue
        values = [
            arg.value if isinstance(arg, ast.Constant) else None for arg in node.args
        ]
        selector = next(
            (value.lower() for value in values[1:] if isinstance(value, str)), "caster"
        )
        level = next((value for value in values[1:] if type(value) is int), None)
        requirements.append(
            dict(
                state=values[0],
                selector=selector,
                level=level,
                comparison="minimum"
                if node.func.id == "HasStateFromLevel"
                else "exact",
            )
        )
    return requirements


def observed_level_matches(level, requirement):
    expected = requirement["level"]
    if expected is None:
        return True
    comparisons = dict(
        exact=level == expected,
        minimum=level >= expected,
        exclusive_minimum=level > expected,
        maximum=level <= expected,
        exclusive_maximum=level < expected,
    )
    return comparisons.get(requirement["comparison"], False)


def caller_rank(caller, breed, level, active, passive, requirements=(), state=None):
    observed = any(
        row.get("breed") == breed
        and row.get("level") == level
        and row.get("status") == "prepared_transaction"
        for row in caller.get("baseline_permission_observations", [])
    )
    known_owned = caller["spell"] in active or caller["spell"] in passive or observed
    parameters = caller.get("native_state_parameters")
    hints = [
        row
        for row in requirements
        if row["state"] == state and row["level"] is not None
    ]
    compatible = 1
    if (
        hints
        and isinstance(parameters, list)
        and len(parameters) >= 4
        and parameters[3] == 0
    ):
        compatible = (
            0 if all(observed_level_matches(parameters[2], row) for row in hints) else 2
        )
    return (
        not known_owned,
        compatible,
        caller["source_depth"],
        bool(caller.get("guard_positive_state_dependencies")),
        caller["spell"] not in active,
        caller["spell"],
        caller["native_state_applicator"],
    )


def native_state_selector(raw, state, reported_selector):
    if reported_selector in (
        "caster",
        "target",
        "castercontroller",
        "triggeringcaster",
        "triggeringtarget",
    ):
        return reported_selector
    for node in ast.walk(parse_local_criterion(raw)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("HasState", "HasStateFromLevel", "GetStateLevel")
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == state
        ):
            selectors = [
                arg.value.lower()
                for arg in node.args[1:]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str)
            ]
            return selectors[-1] if selectors else "caster"
    return reported_selector


def focused_plans(plans, states):
    selected = set(states)
    return [
        plan
        for plan in plans
        if any(row["state"] in selected for row in plan["preparation"])
    ]


def annotate_source_paths(cases, graph_path):
    parents = reverse_edges(graph_path)
    paths = {}
    for case in cases:
        key = case["caller"], case["native_state_applicator"]
        paths.setdefault(
            key,
            shortest_source_path(
                parents, "spell:" + str(key[0]), "effect:" + str(key[1])
            ),
        )
    nodes = graph_nodes(
        graph_path, {node for path in paths.values() for node in path.get("nodes", [])}
    )
    for case in cases:
        case["native_dependency_path"] = paths[
            case["caller"], case["native_state_applicator"]
        ]
        guards = [
            dict(node=key, criterion_raw=nodes[key]["criterion_raw"])
            for key in case["native_dependency_path"].get("nodes", [])
            if key in nodes and nodes[key].get("criterion_raw")
        ]
        case["ancestor_guards"] = guards
        case["ancestor_counter_requirements"] = [
            requirement
            for guard in guards
            if any(
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "GetStateLevel"
                for node in ast.walk(parse_local_criterion(guard["criterion_raw"]))
            )
            for requirement in literal_state_requirements(guard["criterion_raw"])
            if requirement["selector"] == "caster"
            and requirement["state"] != case["state"]
        ]


def transition_cases(plans, levels=(20, 200), maximum_cases=96):
    """Pick bounded source edges per state; retain every skipped prerequisite."""
    candidates = defaultdict(list)
    requested_states = {
        preparation["state"] for plan in plans for preparation in plan["preparation"]
    }
    available_cache = {}
    for plan in plans:
        state_requirements = literal_state_requirements(plan["criterion_raw"])
        required = mandatory_caster_deck_references(plan["criterion_raw"])
        for preparation in plan["preparation"]:
            for caller in preparation.get("caller_candidates", []):
                for breed in sorted(set(plan["breeds"]) & set(caller["breeds"])):
                    for level in levels:
                        if (breed, level) not in available_cache:
                            available_cache[breed, level] = {
                                kind: {
                                    row["id"]
                                    for row in available_spells(breed, level)
                                    if row["kind"] == kind
                                }
                                for kind in ("active", "passive")
                            }
                        active = available_cache[breed, level]["active"]
                        passive = available_cache[breed, level]["passive"]
                        capacity = sum(
                            required <= level for required in ACTIVE_SLOT_LEVELS
                        )
                        # Literal deck requirements are source constraints, never
                        # grants. Nonliteral requirements remain pending evidence.
                        requested = {plan["spell"], caller["spell"]} | required
                        setup = []
                        required_passives = set(required & passive)
                        for prerequisite in plan["preparation"]:
                            options = [
                                row
                                for row in prerequisite["caller_candidates"]
                                if breed in row["breeds"]
                            ]
                            if not options:
                                continue
                            producer = min(
                                options,
                                key=lambda row: caller_rank(
                                    row,
                                    breed,
                                    level,
                                    active,
                                    passive,
                                    state_requirements,
                                    prerequisite["state"],
                                ),
                            )
                            setup.append(
                                dict(
                                    state=prerequisite["state"],
                                    selector=prerequisite["selector"],
                                    caller=producer["spell"],
                                    source_depth=producer["source_depth"],
                                    caller_is_passive=producer["spell"] in passive,
                                )
                            )
                            requested.add(producer["spell"])
                            if producer["spell"] in passive:
                                required_passives.add(producer["spell"])
                        deck = sorted(requested & active)
                        if not deck or len(deck) > capacity:
                            continue
                        candidates[preparation["state"]].append(
                            dict(
                                state=preparation["state"],
                                selector=native_state_selector(
                                    plan["criterion_raw"],
                                    preparation["state"],
                                    preparation["selector"],
                                ),
                                breed=breed,
                                level=level,
                                spell=plan["spell"],
                                branch=plan["branch"],
                                caller=caller["spell"],
                                deck=deck,
                                required_deck_references=sorted(required),
                                passive=next(iter(sorted(required_passives)), None),
                                additional_passive_requirements=sorted(
                                    required_passives
                                )[1:],
                                unavailable_deck_references=sorted(
                                    required - active - passive
                                ),
                                state_requirements=state_requirements,
                                setup_producers=setup,
                                source_depth=caller["source_depth"],
                                qualified_caller_rank=caller_rank(
                                    caller,
                                    breed,
                                    level,
                                    active,
                                    passive,
                                    state_requirements,
                                    preparation["state"],
                                ),
                                native_state_parameters=caller.get(
                                    "native_state_parameters"
                                ),
                                caller_is_passive=caller["spell"] in passive,
                                native_state_applicator=caller[
                                    "native_state_applicator"
                                ],
                                native_guard=caller["native_guard"],
                                guard_dependencies=caller.get(
                                    "guard_positive_state_dependencies", []
                                ),
                                positive_guard_cycles=preparation.get(
                                    "positive_guard_cycles", []
                                ),
                                direct_caller=caller["spell"] in active,
                            )
                        )
    selected = []
    for state in sorted(candidates):
        rows = sorted(
            candidates[state],
            key=lambda row: (
                bool(row["unavailable_deck_references"]),
                bool(row["additional_passive_requirements"]),
                row["qualified_caller_rank"],
                bool(row["guard_dependencies"]),
                row["breed"],
                row["caller"],
                row["spell"],
                row["branch"],
                row["level"],
            ),
        )
        # One representative per state/level. Additional alternatives are not
        # silently claimed tested, and guarded loops are not called unreachable.
        for level in levels:
            match = next((row for row in rows if row["level"] == level), None)
            if match is not None and len(selected) < maximum_cases:
                selected.append(match)
    return selected, dict(
        requested_states=len(requested_states),
        states_with_caller_candidates=len(candidates),
        states_without_usable_caller_candidates=sorted(
            requested_states - set(candidates)
        ),
        selected_cases=len(selected),
        selected_states=len({row["state"] for row in selected}),
        unselected_states=sorted(set(candidates) - {row["state"] for row in selected}),
        total_candidate_edges=sum(map(len, candidates.values())),
    )


def reach_owned_turn(runtime, actor_id, *, maximum_turns):
    stages = []
    for _ in range(maximum_turns):
        if runtime.fight.phase != "active":
            raise ValueError("Actual fight ended before transition owned turn")
        if runtime.awaiting_ack is not None:
            ack = runtime.awaiting_ack
            packets = runtime.acknowledge_turn(struct.pack(">i", ack))
            stages.append(dict(stage="ack", ack=ack, packet_count=len(packets)))
            continue
        current = runtime.fight.current
        if current is not None and current.id == actor_id:
            return stages
        if current is None:
            raise ValueError("Missing actual current transition actor")
        packets = (
            runtime.end_turn(current.owner_id, current.id, current.turn_count)
            if current.controlled
            else runtime.end_server_turn(current.id, runtime.fight.turn_id)
        )
        stages.append(
            dict(stage="end_turn", actor_id=current.id, packet_count=len(packets))
        )
    raise ValueError("Bounded transition turns did not reach the owned actor")


class TransitionAudit:
    def __init__(self, cases, *, candidate_limit=256, maximum_targets=2):
        self.current_case = None
        self.candidate_limit = candidate_limit
        self.maximum_targets = maximum_targets

    def __call__(self, runtime, character, monster, deck, packets, stats_serializer):
        case = self.current_case
        if case is None or (case["breed"], case["level"]) != (
            character["breed"],
            character["level"],
        ):
            raise ValueError("Missing exact conditional audit case binding")
        original = snapshot(runtime.fight)
        baseline = deepcopy(runtime)
        result = dict(
            case=case,
            attempts=[],
            conditional_branch_verified=False,
            removal_control_verified=False,
        )
        try:
            result["turn_stages"] = reach_owned_turn(
                baseline,
                character["id"],
                maximum_turns=max(4, len(baseline.fight.actors) * 4),
            )
            parsed = validate_deck(deck, character["breed"], character["level"])

            def owned_uid(fight, reference):
                actor = fight.actors[character["id"]]
                form = morph_record(fight, actor.id)
                if form is not None:
                    return reference if reference in form["levels"] else None
                grant = granted_spells(fight, actor.id).get(reference)
                if grant is not None:
                    return grant["uid"]
                return (
                    (actor.id << 32) | reference
                    if reference in parsed["active"]
                    else None
                )

            def los(origin, target, fight):
                return authoritative_visible(
                    fight.map_id,
                    origin,
                    target,
                    fight,
                    blocking_footprints={
                        actor.id: {actor.position[:2]}
                        for actor in fight.actors.values()
                        if actor.hp > 0
                    },
                )

            def select(current, reference):
                uid = owned_uid(current.fight, reference)
                if uid is None:
                    return None, dict(
                        status="actual_owned_action_unavailable", reference=reference
                    )
                _, adapter = server_runtime(
                    character,
                    {monster["id"]: monster},
                    deck,
                    action_id=current.action_id + 1,
                    critical=False,
                    rng=random.Random(17),
                )
                selection = eligible_cast_targets(
                    current.fight,
                    character,
                    deck,
                    uid,
                    adapter=adapter,
                    line_of_sight=los,
                    limit=self.candidate_limit,
                    maximum_eligible=self.maximum_targets,
                )
                return uid, selection

            def cast(current, uid, target):
                trace = []
                with combat_diagnostic_scope(
                    lambda **event: trace.append(event), limit=4096
                ):
                    transaction = prepare_server_spell(
                        struct.pack(">qqiih", character["id"], uid, *target),
                        character,
                        {monster["id"]: monster},
                        current.fight,
                        character["account_id"],
                        deck,
                        action_id=current.action_id + 1,
                        line_of_sight=los,
                        critical=False,
                        rng=random.Random(17),
                    )
                    committed_packets = commit_spell_transaction(
                        current, transaction, stats_serializer=stats_serializer
                    )
                return transaction.plan, dict(
                    packet_count=len(committed_packets),
                    trace=trace,
                    selected=transaction.plan.get("native_casting_selection"),
                    flags=transaction.plan.get("native_casting_flags"),
                    costs=transaction.plan["costs"],
                    target_id=transaction.plan["target_id"],
                    state_ledgers_after=actual_state_ledgers(current.fight),
                )

            def state_entries(current, state, selector):
                ledgers = actual_state_ledgers(current.fight)
                owners = (
                    [str(character["id"])] if selector == "caster" else list(ledgers)
                )
                return [
                    dict(owner_id=int(owner), **entry)
                    for owner in owners
                    for entry in ledgers.get(owner, {}).get("entries", [])
                    if entry["reference"] == state
                ]

            def requested_level_met(current, state, selector):
                entries = state_entries(current, state, selector)
                requirements = [
                    row
                    for row in case.get("state_requirements", [])
                    if (row["state"], row["selector"]) == (state, selector)
                ]
                if not entries:
                    return False
                first_per_owner = {}
                for entry in entries:
                    first_per_owner.setdefault(entry["owner_id"], entry)
                return all(
                    any(
                        observed_level_matches(entry["level"], row)
                        for entry in first_per_owner.values()
                    )
                    for row in requirements
                )

            def advance(current):
                actor = current.fight.current
                if actor is None or current.fight.phase != "active":
                    raise ValueError("Actual conditional setup fight ended")
                ended = (
                    current.end_turn(actor.owner_id, actor.id, actor.turn_count)
                    if actor.controlled
                    else current.end_server_turn(actor.id, current.fight.turn_id)
                )
                stages = reach_owned_turn(
                    current,
                    character["id"],
                    maximum_turns=max(4, len(current.fight.actors) * 4),
                )
                return dict(
                    ended_actor=actor.id,
                    packet_count=len(ended),
                    stages=stages,
                    state_ledgers_after=actual_state_ledgers(current.fight),
                )

            result["ancestor_counter_preparation"] = []
            counter_requirements = case.get("ancestor_counter_requirements", [])
            for _ in range(8):
                unmet = []
                for requirement in counter_requirements:
                    entries = state_entries(
                        baseline, requirement["state"], requirement["selector"]
                    )
                    if not entries or not observed_level_matches(
                        entries[0]["level"], requirement
                    ):
                        unmet.append(
                            dict(requirement=requirement, current_entries=entries)
                        )
                if not unmet:
                    break
                result["ancestor_counter_preparation"].append(
                    dict(
                        unmet_literal_requirements=unmet, actual_turn=advance(baseline)
                    )
                )
            result["ancestor_counter_status"] = (
                "literal_counter_dependencies_observed"
                if not counter_requirements
                or all(
                    (entries := state_entries(baseline, row["state"], row["selector"]))
                    and observed_level_matches(entries[0]["level"], row)
                    for row in counter_requirements
                )
                else "bounded_actual_counter_preparation_pending"
            )

            result["setup_producers"] = []
            for producer in case.get("setup_producers", []):
                if (
                    producer["state"] == case["state"]
                    or producer["caller"] == case["caller"]
                ):
                    continue
                setup = dict(
                    producer,
                    state_entries_before=state_entries(
                        baseline, producer["state"], producer["selector"]
                    ),
                )
                result["setup_producers"].append(setup)
                if requested_level_met(
                    baseline, producer["state"], producer["selector"]
                ):
                    setup["status"] = "actual_ready_prerequisite_present"
                    continue
                if producer.get("caller_is_passive"):
                    # Retained passive applicators can require a real turn
                    # boundary; installation alone does not execute children.
                    setup["actual_passive_turn_boundaries"] = []
                    for _ in range(8):
                        actor = baseline.fight.actors.get(character["id"])
                        if actor is None or baseline.fight.phase != "active":
                            break
                        before_resources = dict(
                            current=dict(actor.effect_stats),
                            maximum=dict(actor.effect_maxima),
                        )
                        stages = advance(baseline)
                        setup["actual_passive_turn_boundaries"].append(
                            dict(
                                resources_before=before_resources,
                                actual_turn=stages,
                                state_entries_after=state_entries(
                                    baseline, producer["state"], producer["selector"]
                                ),
                            )
                        )
                        if requested_level_met(
                            baseline, producer["state"], producer["selector"]
                        ):
                            break
                    setup["status"] = (
                        "actual_passive_turn_prerequisite_produced"
                        if requested_level_met(
                            baseline, producer["state"], producer["selector"]
                        )
                        else "actual_ready_passive_prerequisite_not_produced"
                    )
                    setup["requires_actual_ancestor_guard_qualification"] = True
                    continue
                uid, setup_selection = select(baseline, producer["caller"])
                setup["selection"] = {
                    key: value
                    for key, value in setup_selection.items()
                    if key != "eligible"
                }
                targets = setup_selection.get("eligible", [])
                if not targets:
                    setup["status"] = "actual_prerequisite_producer_unavailable"
                    continue
                _, setup["commit"] = cast(baseline, uid, targets[0]["target"])
                setup["status"] = "actual_prerequisite_producer_committed"

            caller_uid, selection = select(baseline, case["caller"])
            result["caller_selection"] = {
                key: value for key, value in selection.items() if key != "eligible"
            }
            caller_paths = selection.get("eligible", [])
            if case.get("caller_is_passive") and requested_level_met(
                baseline, case["state"], case["selector"]
            ):
                result["caller_selection"] = dict(
                    status="actual_ready_passive_state_present",
                    passive_reference=case["caller"],
                    state_entries=state_entries(
                        baseline, case["state"], case["selector"]
                    ),
                )
                caller_paths = [dict(target=None, actual_ready_source=True)]
            for candidate in caller_paths:
                branch = deepcopy(baseline)
                attempt = dict(
                    caller_target=candidate["target"],
                    state_ledgers_before=actual_state_ledgers(branch.fight),
                )
                result["attempts"].append(attempt)
                try:
                    if candidate.get("actual_ready_source"):
                        attempt["caller_ready_source"] = dict(
                            passive_reference=case["caller"],
                            state_entries=state_entries(
                                branch, case["state"], case["selector"]
                            ),
                        )
                    else:
                        _, attempt["caller_commit"] = cast(
                            branch, caller_uid, candidate["target"]
                        )
                        events = attempt["caller_commit"]["trace"]
                        attempt["actual_producer_qualification"] = dict(
                            selected_native_applicator=case["native_state_applicator"],
                            observed_applicator_statuses=[
                                event["status"]
                                for event in events
                                if event.get("effect_reference")
                                == case["native_state_applicator"]
                                and "status" in event
                            ],
                            applicator_completed=any(
                                event.get("effect_reference")
                                == case["native_state_applicator"]
                                and event.get("status") == "completed"
                                for event in events
                            ),
                            required_state_entries_after=state_entries(
                                branch, case["state"], case["selector"]
                            ),
                            literal_required_level_met=requested_level_met(
                                branch, case["state"], case["selector"]
                            ),
                            note="A candidate ancestry is not execution evidence; current ledger and full selected conditional branch remain separate requirements",
                        )
                    attempt["threshold_producer_stages"] = []
                    # Native HasState(level) is exact equality; FromLevel is a
                    # minimum. Only actual committed producers can change it.
                    for _ in range(3):
                        entries = state_entries(branch, case["state"], case["selector"])
                        if not entries or requested_level_met(
                            branch, case["state"], case["selector"]
                        ):
                            break
                        uid, repeat_selection = select(branch, case["caller"])
                        repeated = dict(
                            state_entries_before=entries,
                            selection={
                                key: value
                                for key, value in repeat_selection.items()
                                if key != "eligible"
                            },
                        )
                        attempt["threshold_producer_stages"].append(repeated)
                        targets = repeat_selection.get("eligible", [])
                        if not targets:
                            repeated["actual_turn"] = advance(branch)
                            uid, repeat_selection = select(branch, case["caller"])
                            repeated["selection_after_turn"] = {
                                key: value
                                for key, value in repeat_selection.items()
                                if key != "eligible"
                            }
                            targets = repeat_selection.get("eligible", [])
                        if not state_entries(branch, case["state"], case["selector"]):
                            repeated[
                                "status"
                            ] = "required_state_expired_before_threshold_producer"
                            break
                        if not targets:
                            repeated["status"] = "actual_threshold_producer_unavailable"
                            break
                        repeated_target = next(
                            (
                                row["target"]
                                for row in targets
                                if row["target"] == candidate["target"]
                            ),
                            targets[0]["target"],
                        )
                        repeated["selected_target"] = repeated_target
                        _, repeated["commit"] = cast(branch, uid, repeated_target)
                        repeated["status"] = "actual_threshold_producer_committed"
                    conditional_uid, conditional_selection = select(
                        branch, case["spell"]
                    )
                    attempt["conditional_selection"] = {
                        key: value
                        for key, value in conditional_selection.items()
                        if key != "eligible"
                    }
                    attempt["eligibility_turn_stages"] = []
                    for _ in range(4):
                        if conditional_selection.get("eligible"):
                            break
                        ledgers = actual_state_ledgers(branch.fight)
                        owners = (
                            [str(character["id"])]
                            if case["selector"] == "caster"
                            else list(ledgers)
                        )
                        present = [
                            dict(owner_id=int(owner), **entry)
                            for owner in owners
                            for entry in ledgers.get(owner, {}).get("entries", [])
                            if entry["reference"] == case["state"]
                        ]
                        if not present:
                            attempt["eligibility_context_status"] = (
                                "required_state_absent_after_real_producer"
                                if not attempt["eligibility_turn_stages"]
                                else "required_state_expired_before_eligible_cast"
                            )
                            break
                        current = branch.fight.current
                        if current is None or branch.fight.phase != "active":
                            attempt[
                                "eligibility_context_status"
                            ] = "actual_fight_or_turn_ended"
                            break
                        ended = (
                            branch.end_turn(
                                current.owner_id, current.id, current.turn_count
                            )
                            if current.controlled
                            else branch.end_server_turn(
                                current.id, branch.fight.turn_id
                            )
                        )
                        stages = reach_owned_turn(
                            branch,
                            character["id"],
                            maximum_turns=max(4, len(branch.fight.actors) * 4),
                        )
                        conditional_uid, conditional_selection = select(
                            branch, case["spell"]
                        )
                        attempt["eligibility_turn_stages"].append(
                            dict(
                                required_state_entries_before=present,
                                ended_actor=current.id,
                                end_packet_count=len(ended),
                                stages=stages,
                                state_ledgers_after=actual_state_ledgers(branch.fight),
                                selection={
                                    key: value
                                    for key, value in conditional_selection.items()
                                    if key != "eligible"
                                },
                            )
                        )
                        attempt["conditional_selection"] = {
                            key: value
                            for key, value in conditional_selection.items()
                            if key != "eligible"
                        }
                    else:
                        attempt[
                            "eligibility_context_status"
                        ] = "bounded_actual_turn_context_pending"
                    for conditional_candidate in conditional_selection.get(
                        "eligible", []
                    ):
                        conditional, off_branch = independent_transition_branches(
                            branch
                        )
                        conditional_attempt = dict(
                            target=conditional_candidate["target"]
                        )
                        attempt.setdefault("conditional_attempts", []).append(
                            conditional_attempt
                        )
                        try:
                            plan, evidence = cast(
                                conditional,
                                conditional_uid,
                                conditional_candidate["target"],
                            )
                            conditional_attempt["commit"] = evidence
                            owner_id = (
                                character["id"]
                                if case["selector"] == "caster"
                                else plan["target_id"]
                            )
                            entries = (
                                actual_state_ledgers(branch.fight)
                                .get(str(owner_id), {})
                                .get("entries", [])
                            )
                            actual_state = any(
                                entry["reference"] == case["state"] for entry in entries
                            )
                            matched = plan.get("native_casting_selection", {}).get(
                                "matched_rules", []
                            )
                            actual_branch = any(
                                row["index"] == case["branch"] for row in matched
                            )
                            conditional_attempt.update(
                                actual_selector_owner_id=owner_id,
                                required_state_present_before_cast=actual_state,
                                expected_branch_matched=actual_branch,
                                conditional_branch_verified=actual_state
                                and actual_branch,
                            )
                            result["conditional_branch_verified"] |= (
                                actual_state and actual_branch
                            )
                            if actual_state and actual_branch:
                                original_uids = {
                                    entry["uid"]
                                    for entry in entries
                                    if entry["reference"] == case["state"]
                                }
                                control = dict(
                                    status="bounded_actual_expiry_pending",
                                    turns=[],
                                    independent_precast_branch=True,
                                    original_state_uids=sorted(original_uids),
                                )
                                conditional_attempt["removal_control"] = control
                                # A committed action can consume its prerequisite.
                                # Replay the actual owned producer independently;
                                # never copy the ON transaction or delete a state.
                                if committed_state_absent(
                                    evidence, owner_id, case["state"]
                                ):
                                    _, removal_evidence = cast(
                                        off_branch,
                                        conditional_uid,
                                        conditional_candidate["target"],
                                    )
                                    control[
                                        "actual_consumption_producer"
                                    ] = removal_evidence
                                    control[
                                        "removal_mechanism"
                                    ] = "actual_owned_spell_consumption"
                                else:
                                    control[
                                        "removal_mechanism"
                                    ] = "actual_timer_lifecycle"
                                for _ in range(8):
                                    current = off_branch.fight.current
                                    if (
                                        current is None
                                        or off_branch.fight.phase != "active"
                                    ):
                                        control["status"] = "fight_or_turn_ended"
                                        break
                                    ended = (
                                        off_branch.end_turn(
                                            current.owner_id,
                                            current.id,
                                            current.turn_count,
                                        )
                                        if current.controlled
                                        else off_branch.end_server_turn(
                                            current.id, off_branch.fight.turn_id
                                        )
                                    )
                                    stages = reach_owned_turn(
                                        off_branch,
                                        character["id"],
                                        maximum_turns=max(
                                            4, len(off_branch.fight.actors) * 4
                                        ),
                                    )
                                    control["turns"].append(
                                        dict(
                                            ended_actor=current.id,
                                            packet_count=len(ended),
                                            stages=stages,
                                            state_ledgers_after=actual_state_ledgers(
                                                off_branch.fight
                                            ),
                                        )
                                    )
                                    remaining = off_branch.fight.actors.get(owner_id)
                                    if remaining is None:
                                        control[
                                            "status"
                                        ] = "actual_selector_owner_removed"
                                        break
                                    remaining_uids = {
                                        entry.uid
                                        for entry in remaining.state_ledger.entries
                                    }
                                    control["original_state_uids_removed"] = sorted(
                                        original_uids - remaining_uids
                                    )
                                    if original_uids & remaining_uids:
                                        continue
                                    restored_uid, restored_selection = select(
                                        off_branch, case["spell"]
                                    )
                                    control["restored_selection"] = {
                                        key: value
                                        for key, value in restored_selection.items()
                                        if key != "eligible"
                                    }
                                    restored_targets = restored_selection.get(
                                        "eligible", []
                                    )
                                    if not restored_targets:
                                        control[
                                            "status"
                                        ] = "state_expired_restored_cast_context_unavailable"
                                        continue
                                    restored_plan, restored_evidence = cast(
                                        off_branch,
                                        restored_uid,
                                        restored_targets[0]["target"],
                                    )
                                    control["restored_commit"] = restored_evidence
                                    control[
                                        "restored_native_casting_selection"
                                    ] = restored_plan.get("native_casting_selection")
                                    restored_matches = (
                                        restored_plan.get("native_casting_selection")
                                        or {}
                                    ).get("matched_rules", [])
                                    restored = not any(
                                        row["index"] == case["branch"]
                                        for row in restored_matches
                                    )
                                    control["status"] = (
                                        (
                                            "actual_consumption_and_branch_restoration_verified"
                                            if control["removal_mechanism"]
                                            == "actual_owned_spell_consumption"
                                            else "actual_expiry_and_branch_restoration_verified"
                                        )
                                        if restored
                                        else "state_removed_branch_still_matches"
                                    )
                                    result["removal_control_verified"] |= restored
                                    break
                        except Exception as error:
                            conditional_attempt["first_root_failure"] = root_failure(
                                error
                            )
                    attempt["status"] = (
                        "actual_ready_passive_prerequisite_used"
                        if candidate.get("actual_ready_source")
                        else "actual_caller_committed"
                    )
                except Exception as error:
                    attempt.update(
                        status="caller_transaction_rejected",
                        first_root_failure=root_failure(error),
                    )
            result["status"] = (
                "conditional_branch_verified"
                if result["conditional_branch_verified"]
                else "prerequisite_or_conditional_context_pending"
            )
            result["removal_control_status"] = (
                "actual_removal_or_expiry_verified"
                if result["removal_control_verified"]
                else "pending_actual_removal_or_expiry_sequence"
            )
        except Exception as error:
            result.update(
                status="transition_authority_or_turn_rejected",
                first_root_failure=root_failure(error),
            )
        result["source_preserved"] = snapshot(runtime.fight) == original
        if not result["source_preserved"]:
            raise AssertionError(
                "Conditional transition mutated its actual Ready source"
            )
        return result


def run(
    output,
    plan_path,
    *,
    levels=(20, 200),
    maximum_cases=96,
    candidate_limit=256,
    states=None,
):
    source = Path(plan_path).read_bytes()
    plans = json.loads(source)["plans"]
    matrix_path = (
        Path(plan_path).parent / "class-casting-precondition-matrix-20261008.json"
    )
    matrix = json.loads(matrix_path.read_text())
    source_parameters = {
        row["effect"]: row["raw_parameters"]
        for index in matrix["state_source_index"].values()
        for row in index["native_state_apply_candidates"]
    }
    for plan in plans:
        for preparation in plan["preparation"]:
            for caller in preparation["caller_candidates"]:
                caller["native_state_parameters"] = source_parameters.get(
                    caller["native_state_applicator"]
                )
    if states is not None:
        selected_states = set(states)
        # Focus selects cases, never removes the other real prerequisites of
        # the same native boolean criterion.
        plans = focused_plans(plans, selected_states)
    cases, inventory = transition_cases(plans, levels, maximum_cases)
    if states is not None:
        cases = [case for case in cases if case["state"] in selected_states]
        inventory.update(
            requested_focus_states=sorted(selected_states),
            selected_cases=len(cases),
            selected_states=len({case["state"] for case in cases}),
            required_dependency_states=sorted(
                {row["state"] for plan in plans for row in plan["preparation"]}
                - selected_states
            ),
        )
    graph_path = Path(plan_path).parent / "class-native-mechanic-graph-20261007.json"
    annotate_source_paths(cases, graph_path)
    queues = defaultdict(deque)
    for case in cases:
        queues[(case["breed"], case["level"])].append(case)
    audit = TransitionAudit(cases, candidate_limit=candidate_limit)

    def deck_provider(breed, level, passive):
        audit.current_case = queues[breed, level].popleft()
        return audit.current_case["deck"]

    tool_before = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report = ready_audit.run(
        Path(output),
        basics_only=True,
        turn_cycle=True,
        turn_steps=0,
        cases_override=[
            (case["breed"], case["level"], case["passive"]) for case in cases
        ],
        active_deck_provider=deck_provider,
        on_runtime=audit,
    )
    transitions = [row.get("runtime_access", {}) for row in report["rows"]]
    report.update(
        transition_inventory=inventory,
        transition_plan_sha256=hashlib.sha256(source).hexdigest(),
        transition_source_matrix_sha256=hashlib.sha256(
            matrix_path.read_bytes()
        ).hexdigest(),
        transition_source_graph_sha256=hashlib.sha256(
            graph_path.read_bytes()
        ).hexdigest(),
        requested_transition_cases=cases,
        transition_tool_sha256=tool_before,
        transition_tool_stable=tool_before
        == hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        transition_status_counts=dict(
            Counter(row.get("status") for row in transitions)
        ),
        verified_conditional_cases=sum(
            row.get("conditional_branch_verified", False) for row in transitions
        ),
        verified_removal_cases=sum(
            row.get("removal_control_verified", False) for row in transitions
        ),
        scoped_execution_case_count=len(cases),
        scoped_conditional_pending_cases=sum(
            not row.get("conditional_branch_verified", False) for row in transitions
        ),
        scoped_removal_pending_cases=sum(
            not row.get("removal_control_verified", False) for row in transitions
        ),
        removal_control_complete=False,
        all_conditional_branches_verified=False,
    )
    Path(output).write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path(
            "docs/reports/combat-inventory/class-casting-transition-plan-20261008.json"
        ),
    )
    parser.add_argument("--levels", type=int, nargs="+", default=[20, 200])
    parser.add_argument("--maximum-cases", type=int, default=96)
    parser.add_argument("--candidate-limit", type=int, default=256)
    parser.add_argument("--states", type=int, nargs="+")
    args = parser.parse_args()
    report = run(
        args.output,
        args.plan,
        levels=args.levels,
        maximum_cases=args.maximum_cases,
        candidate_limit=args.candidate_limit,
        states=args.states,
    )
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "transition_inventory",
                    "transition_status_counts",
                    "verified_conditional_cases",
                )
            }
        )
    )
