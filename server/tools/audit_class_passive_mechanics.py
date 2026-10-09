"""Offline legal single-passive production Ready, cast and lifecycle evidence.

Native dependency presence and observed execution are separate. No state,
resource, summon or condition is injected to manufacture prerequisites.
"""
import gzip
import argparse
import ast
from collections import Counter, deque
from copy import deepcopy
import hashlib
import json
import random
import struct
from pathlib import Path

import audit_ready_start as ready
from audit_class_normal_casts import NormalCastAudit, actual_state_ledgers, root_failure
from audit_class_conditional_transitions import reach_owned_turn
from wakfu_server.combat_local_criteria import parse_local_criterion
from wakfu_server.combat_damage_events import ELEMENT_EVENT_IDS
from wakfu_server.combat_damage_healing import DAMAGE_FAMILIES, HEAL_ELEMENTS
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_area_transaction import prepare_area_movement
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import available_spells, ACTIVE_SLOT_LEVELS, validate_deck

ROOT = Path(__file__).resolve().parents[2]
GRAPH = ROOT / ".runtime/combat-review-20261007/mechanic-graph/native-graph.jsonl.gz"


def passive_plan(breeds, *, upper_level=False):
    cases, decks, inventory = [], {}, []
    for breed in sorted(breeds):
        for passive in available_spells(breed, 200):
            if passive["kind"] != "passive":
                continue
            levels = {max(10, passive["unlock_level"])}
            if upper_level:
                levels.add(200)
            for level in sorted(levels):
                capacity = sum(level >= threshold for threshold in ACTIVE_SLOT_LEVELS)
                active = sorted(
                    row["id"]
                    for row in available_spells(breed, level)
                    if row["kind"] == "active"
                )[:capacity]
                case = (breed, level, passive["id"])
                cases.append(case)
                decks[case] = active
                inventory.append(
                    dict(
                        breed=breed,
                        level=level,
                        passive=passive["id"],
                        unlock_level=passive["unlock_level"],
                        active_deck=active,
                        legal_active_capacity=capacity,
                    )
                )
    return cases, lambda breed, level, passive: decks[breed, level, passive], inventory


def native_contracts(cases, path=GRAPH):
    """Stream original metadata; follow executable children/application references only."""
    wanted = {passive for _, _, passive in cases}
    spells, effects, states = {}, {}, {}
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with gzip.open(path, "rt") as stream:
        for line in stream:
            row = json.loads(line)
            kind, ref = row["kind"], row["reference"]
            if kind == "spell":
                spells[ref] = row["root_samples"]
            elif kind == "state":
                states[ref] = row.get("level_samples", {})
            elif kind == "effect":
                effects[ref] = {
                    key: row.get(key)
                    for key in (
                        "family",
                        "native_runner_class",
                        "children_ordered",
                        "criterion_raw",
                        "subscription",
                        "owner_on_caster",
                        "reverse_subscription",
                        "global_subscription",
                        "event_priority",
                        "event_execution_count",
                        "event_target_code",
                        "event_caster_code",
                        "suppresses_level_one",
                        "classified_reference_samples",
                        "reference_semantics",
                        "raw_parameters",
                        "native_metadata",
                    )
                }
                effects[ref]["native_timing_checks"] = {
                    key: sample["timing"]
                    for key, sample in row.get("samples", {}).items()
                    if key in ("0", "1", "200", "32767")
                }
    contracts = {}
    for breed, level, passive in cases:
        roots = spells.get(passive, {}).get(str(level))
        pending = deque(roots or [])
        visited, missing, applied, missing_states = set(), set(), set(), set()
        while pending:
            ref = pending.popleft()
            if ref in visited:
                continue
            visited.add(ref)
            row = effects.get(ref)
            if row is None:
                missing.add(ref)
                continue
            pending.extend(row["children_ordered"] or [])
            for edge in row["classified_reference_samples"] or []:
                if (
                    row["family"] == 304
                    and edge["kind"] == "state"
                    and edge["sample_level"] == level
                ):
                    state = edge["reference"]
                    applied.add(state)
                    if not states.get(state):
                        missing_states.add(state)
                    pending.extend(
                        sorted(
                            {
                                root
                                for sample in states.get(state, {}).values()
                                for root in sample.get("roots", [])
                            }
                        )
                    )
        contracts[str(passive) + "/" + str(level)] = dict(
            original_roots=roots,
            effect_contracts={
                str(ref): effects[ref] for ref in sorted(visited) if ref in effects
            },
            missing_effect_references=sorted(missing),
            applied_state_references=sorted(applied),
            missing_native_state_references=sorted(missing_states),
            dependency_traversal="ordered children plus possible native304 state roots across exported levels; not execution scheduling",
            state_level_semantics="actual requested level, existing stack and guards must come from runtime; metadata root union is conservative",
            dynamic_reachability="not inferred from graph presence",
        )
    feature_cache = {}
    for breed, level, passive in cases:
        contract = contracts[str(passive) + "/" + str(level)]
        condition_calls = set()
        criterion_spell_references = set()
        unparsed = []
        for ref, effect in contract["effect_contracts"].items():
            raw = effect.get("criterion_raw")
            if not raw:
                continue
            try:
                tree = parse_local_criterion(raw)
                condition_calls.update(
                    node.func.id
                    for node in ast.walk(tree)
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                )
                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id in ("IsActivatedBySpell", "IsSpellInDeck")
                        and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and type(node.args[0].value) is int
                        and node.args[0].value > 0
                    ):
                        criterion_spell_references.add(node.args[0].value)
                    if isinstance(node, ast.Compare):
                        values = [node.left, *node.comparators]
                        if any(
                            isinstance(value, ast.Call)
                            and isinstance(value.func, ast.Name)
                            and value.func.id == "GetActiveSpellId"
                            for value in values
                        ):
                            criterion_spell_references.update(
                                value.value
                                for value in values
                                if isinstance(value, ast.Constant)
                                and type(value.value) is int
                                and value.value > 0
                            )
            except Exception:
                unparsed.append(ref)
        subscription_events = {
            event
            for effect in contract["effect_contracts"].values()
            for mask in (effect.get("native_metadata") or {}).get("target_masks", [])
            for event in (mask or [])
        }
        desired_events = subscription_events.intersection(
            set(ELEMENT_EVENT_IDS.values()) - {None}
        )
        desired = set()
        if any("Heal" in name for name in condition_calls):
            desired.add("healing")
        if any("Melee" in name for name in condition_calls):
            desired.add("damage")
        if any("Distance" in name or "Damage" in name for name in condition_calls):
            desired.add("damage")
        cache_key = (breed, level)
        if cache_key not in feature_cache:
            features = {}
            for spell in available_spells(breed, level):
                if spell["kind"] != "active":
                    continue
                pending, seen = (
                    deque(spells.get(spell["id"], {}).get(str(level), [])),
                    set(),
                )
                while pending:
                    ref = pending.popleft()
                    if ref in seen:
                        continue
                    seen.add(ref)
                    pending.extend(effects.get(ref, {}).get("children_ordered") or [])
                families = {effects[ref]["family"] for ref in seen if ref in effects}
                tags = {"damage"} if families.intersection(DAMAGE_FAMILIES) else set()
                if families.intersection(HEAL_ELEMENTS):
                    tags.add("healing")
                tags.update(
                    "element_family_" + str(family)
                    for family in families.intersection({2, 3, 4, 5})
                )
                features[spell["id"]] = dict(
                    native_families=sorted(families),
                    source_feature_tags=sorted(tags),
                    native_element_event_candidates=sorted(
                        {
                            ELEMENT_EVENT_IDS[family]
                            for family in families
                            if family in ELEMENT_EVENT_IDS
                            and ELEMENT_EVENT_IDS[family] is not None
                        }
                    ),
                )
            feature_cache[cache_key] = features
        features = feature_cache[cache_key]
        # Ranking chooses bounded legal representatives; it does not evaluate native guards.
        ranked = sorted(
            features,
            key=lambda ref: (
                -int(ref in criterion_spell_references),
                -len(
                    set(features[ref]["native_element_event_candidates"]).intersection(
                        desired_events
                    )
                ),
                -len(set(features[ref]["source_feature_tags"]).intersection(desired)),
                -int("damage" in features[ref]["source_feature_tags"]),
                ref,
            ),
        )
        selected = ranked[:1]
        if desired or criterion_spell_references:
            uncovered = (
                desired - set(features[selected[0]]["source_feature_tags"])
                if selected
                else desired
            )
            alternate = next(
                (
                    ref
                    for ref in ranked[1:]
                    if set(features[ref]["source_feature_tags"]).intersection(uncovered)
                    or ref in criterion_spell_references
                ),
                None,
            )
            if alternate is not None:
                selected.append(alternate)
        contract["representative_action_plan"] = dict(
            owned_references=selected,
            desired_source_categories=sorted(desired),
            source_subscription_element_events=sorted(desired_events),
            source_literal_spell_references=sorted(criterion_spell_references),
            unselected_literal_spell_references=sorted(
                criterion_spell_references - set(selected)
            ),
            condition_function_names=sorted(condition_calls),
            unparsed_criteria_effects=unparsed,
            native_action_features={str(ref): features[ref] for ref in selected},
            omitted_owned_references=sorted(set(features) - set(selected)),
            policy="at most two source-ranked owned actions and one actual grant; ranking is not semantic guard verification",
            unexercised_requirements=[
                "critical branch",
                "all element variants",
                "all range/melee contexts",
                "summon/area/threshold prerequisites",
                "all omitted owned actions",
            ],
        )
    if before != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError("Original passive graph changed during metadata extraction")
    return contracts, before


class PassiveAudit:
    def __init__(self, cases, contracts, candidate_limit, *, requested_actions=None):
        self.cases = deque(cases)
        self.contracts = contracts
        self.candidate_limit = candidate_limit
        self.requested_actions = requested_actions

    def __call__(self, runtime, character, monster, deck, packets, stats):
        parsed = validate_deck(deck, character["breed"], character["level"])
        breed, level = character["breed"], character["level"]
        if len(parsed["passive"]) != 1:
            raise ValueError("Exactly one legal owned passive required")
        passive = parsed["passive"][0]
        original = snapshot(runtime.fight)
        contract = self.contracts[str(passive) + "/" + str(level)]
        selected = set(contract["representative_action_plan"]["owned_references"])
        requested = (
            None
            if self.requested_actions is None
            else self.requested_actions.get(
                (breed, level, passive, tuple(parsed["active"]))
            )
        )

        def action_selector(actions):
            if requested is not None:
                return [
                    action for action in actions if action["reference"] == requested
                ]
            owned = [
                action
                for action in actions
                if action["origin"] == "normal_owned_deck"
                and action["reference"] in selected
            ]
            grants = [
                action for action in actions if action["origin"] != "normal_owned_deck"
            ][:1]
            return owned + grants

        result = NormalCastAudit(
            candidate_limit=self.candidate_limit,
            maximum_eligible=1,
            action_selector=action_selector,
        )(runtime, character, monster, deck, packets, stats)
        branch = deepcopy(runtime)
        trace, stages = [], []
        movement = dict(status="unavailable", reason="owned turn not reached")
        movement_trace = []
        before = actual_state_ledgers(branch.fight)
        try:
            with combat_diagnostic_scope(
                lambda **event: trace.append(event), limit=8192
            ):
                stages.extend(
                    reach_owned_turn(branch, character["id"], maximum_turns=12)
                )
                movement_branch = deepcopy(branch)
                moving = movement_branch.fight.current
                movement = dict(
                    status="unavailable", reason="no legal adjacent path accepted"
                )
                movement_trace = []
                for source_cell, target_cell in sorted(
                    movement_branch.fight.edges or ()
                ):
                    if tuple(source_cell) != tuple(moving.position):
                        continue
                    candidate = deepcopy(movement_branch)
                    try:

                        def area_provider(fight, **boundary):
                            return prepare_area_movement(
                                character,
                                {monster["id"]: monster},
                                fight,
                                deck,
                                rng=random.Random(27),
                                **boundary
                            )

                        body = struct.pack(">q", moving.id) + struct.pack(
                            ">iih", *target_cell
                        )
                        with combat_diagnostic_scope(
                            lambda **event: movement_trace.append(event), limit=8192
                        ):
                            movement_packets, event = apply_client(
                                candidate,
                                character["account_id"],
                                body,
                                lambda actor: stats(actor, candidate.fight),
                                area_provider=area_provider,
                            )
                        movement = dict(
                            status="production_movement_committed",
                            path=[target_cell],
                            packet_count=len(movement_packets),
                            event=event,
                            state_ledgers_after=actual_state_ledgers(candidate.fight),
                        )
                        break
                    except Exception as error:
                        movement["last_failure"] = root_failure(error, movement_trace)
                current = branch.fight.current
                emitted = branch.end_turn(
                    current.owner_id, current.id, current.turn_count
                )
                stages.append(dict(stage="owned_end", packet_count=len(emitted)))
                stages.extend(
                    reach_owned_turn(branch, character["id"], maximum_turns=12)
                )
            lifecycle = dict(
                status="actual_end_ack_start_completed",
                stages=stages,
                state_ledgers_before=before,
                state_ledgers_after=actual_state_ledgers(branch.fight),
                removal_policy="observed actual expiration only; permanent passives not forcibly removed",
            )
        except Exception as error:
            lifecycle = dict(
                status="lifecycle_unavailable",
                stages=stages,
                first_root_failure=root_failure(error, trace),
            )
        references = set(map(int, contract["effect_contracts"]))
        attributable = [
            event
            for event in trace
            if event.get("effect_reference") in references
            or references.intersection(event.get("ancestors") or [])
        ]
        cast_trace = [
            event
            for action in result.get("actions", [])
            for attempt in action.get("attempts", [])
            for event in attempt.get("trace", [])
        ]
        attributed_casts = [
            event
            for event in cast_trace
            if event.get("effect_reference") in references
            or references.intersection(event.get("ancestors") or [])
        ]
        result.update(
            passive_reference=passive,
            lifecycle=lifecycle,
            semantic_requested_action=requested,
            requested_action_available=requested is None
            or any(
                action["reference"] == requested for action in result.get("actions", [])
            ),
            representative_action_plan=contract["representative_action_plan"],
            cast_passive_trace=attributed_casts,
            attributable_completed_effect_observed=any(
                event.get("status") == "completed"
                for event in attributable
                + attributed_casts
                + [
                    event
                    for event in movement_trace
                    if event.get("effect_reference") in references
                    or references.intersection(event.get("ancestors") or [])
                ]
            ),
            lifecycle_passive_trace=attributable,
            lifecycle_trace_complete=not any(
                event.get("effects_omitted", 0) for event in trace
            ),
            movement=movement,
            movement_passive_trace=[
                event
                for event in movement_trace
                if event.get("effect_reference") in references
                or references.intersection(event.get("ancestors") or [])
            ],
            passive_execution_is_not_full_mechanic_verification=True,
        )
        if snapshot(runtime.fight) != original:
            raise AssertionError("Passive runtime audit changed original Ready source")
        return result


def run(output, *, breeds=None, upper_level=False, candidate_limit=16, plan_only=False):
    tool_before = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    breeds = sorted(ready.BREEDS) if breeds is None else breeds
    cases, provider, inventory = passive_plan(breeds, upper_level=upper_level)
    contracts, graph_hash = native_contracts(cases)
    decks = {}
    for row in inventory:
        key = (row["breed"], row["level"], row["passive"])
        chosen = contracts[str(row["passive"]) + "/" + str(row["level"])][
            "representative_action_plan"
        ]["owned_references"]
        row["active_deck"] = list(dict.fromkeys(chosen + row["active_deck"]))[
            : row["legal_active_capacity"]
        ]
        decks[key] = row["active_deck"]
    provider = lambda breed, level, passive: decks[breed, level, passive]
    output = Path(output)
    if plan_only:
        report = dict(
            finished=True,
            scope="planned legal single-passive decks; metadata only",
            rows=[],
        )
    else:
        report = ready.run(
            output,
            basics_only=True,
            turn_cycle=True,
            turn_steps=0,
            cases_override=cases,
            active_deck_provider=provider,
            on_runtime=PassiveAudit(cases, contracts, candidate_limit),
        )
    report.update(
        passive_inventory=inventory,
        original_native_contracts=contracts,
        original_graph_sha256=graph_hash,
        planned_case_count=len(cases),
        planned_passive_count=len({passive for _, _, passive in cases}),
        optional_passive_combination_policy="one legal optional passive per deck, no active Cartesian product",
        source_tool_sha256=tool_before,
        source_tool_stable=tool_before
        == hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        full_passive_mechanics_verified=False,
        full_client_verified=False,
        unavailable_counts=dict(
            Counter(
                row.get("runtime_access", {})
                .get("lifecycle", {})
                .get("status", "ready_or_runtime_not_reached")
                for row in report["rows"]
            )
        ),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--breeds", nargs="+", type=int)
    parser.add_argument("--upper-level", action="store_true")
    parser.add_argument("--candidate-limit", type=int, default=16)
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    run(
        args.output,
        breeds=args.breeds,
        upper_level=args.upper_level,
        candidate_limit=args.candidate_limit,
        plan_only=args.plan_only,
    )
