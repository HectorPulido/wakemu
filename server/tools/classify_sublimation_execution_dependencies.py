"""Classify bounded original effect closures, never acquisition or item names.

No gameplay imports, full catalog load, database connection or activation. The
only server dependency is the existing pure native local-criterion AST parser.
Unknown predicates/descriptors are unresolved, never silently quest-excluded.
"""
import argparse
import ast
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from wakfu_server.combat_local_criteria import parse_local_criterion


COMBAT_FUNCTIONS = frozenset(
    """GetAlliesCountInRange GetCharac GetCharacInPct
GetCharacMax GetCharacteristic GetCurrentFighterId
GetDistanceBetweenCasterAndTarget GetEffectCaster GetEffectTarget
GetEnnemyCountInRange GetFightCurrentTableTurn GetLevel GetStateCountInRange
GetStateLevel GetTeamId GetTotalHpInPercent GetTriggeringContainerStateId
GetTriggeringContainerType GetTriggeringEffectActionId GetTriggeringEffectCaster
GetTriggeringEffectCasterIsSameAsCaster GetTriggeringEffectId
GetTriggeringEffectTarget GetTriggeringEffectValue HasEffectWithSpecificId
HasFightProperty HasLineOfSight HasState HasStateFromLevel HasStateFromUser
HasWeaponType IsActivatedByElement IsActivatedBySpell IsBackstabbed IsBreed
IsCarried IsCharacter IsEnemy IsEnnemy IsFacestabbed IsInAlignment IsInDiagonal
IsObstacle IsSidestabbed IsTriggeredByEffectWithREP IsTriggeredByIndirectEffect
IsTriggeredByMeleeEffect IsTriggeredByZoneEffect IsTriggeringEffectBlocked
IsTriggeringEffectCritical""".split()
)

# Explicit original content gates with a separately documented native-source
# consumer. Unknown similarly named functions remain unresolved instead.
CONTENT_GATES = {
    "GetAchievementCategoryRunningCount": "environmental_modulox_contracts.offer_parameters: original category offer",
    "GetAchievementCategoryCount": "environmental_modulox_contracts.offer_parameters: original category offer",
    "GetAchievementCategoryCanBeResetCount": "environmental_modulox_contracts.offer_parameters: original category offer",
}

COMBAT_FAMILIES = frozenset(
    (
        1,
        24,
        25,
        26,
        27,
        31,
        33,
        39,
        40,
        41,
        43,
        48,
        55,
        56,
        57,
        71,
        80,
        82,
        83,
        84,
        85,
        100,
        120,
        122,
        123,
        124,
        125,
        126,
        129,
        130,
        132,
        133,
        134,
        135,
        149,
        150,
        160,
        161,
        168,
        173,
        174,
        175,
        176,
        177,
        178,
        180,
        182,
        183,
        185,
        186,
        191,
        192,
        193,
        303,
        304,
        321,
        330,
        400,
        421,
        430,
        447,
        560,
        561,
        562,
        563,
        566,
        844,
        875,
        876,
        912,
        913,
        986,
        988,
        999,
        1011,
        1013,
        1020,
        1047,
        1052,
        1053,
        1055,
        1056,
        1063,
        1083,
        1085,
        1093,
        1094,
        1095,
    )
)


def read(path):
    raw = path.read_bytes()
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError("Expected bounded exported closure, not a full catalog")
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def classify(closure, inventory, state_proof):
    effects, states = closure["effects"], closure["states"]
    indexed = {item["reference"]: item for item in inventory["items"]}
    definitions = closure["source_definitions"]
    if (
        len(indexed) != 467
        or set(map(str, indexed)) != set(definitions)
        or closure["missing_effects"]
        or closure["missing_states"]
        or closure["missing_definitions"]
        or closure["unresolved_dynamic_state_references"]
    ):
        raise ValueError("Incomplete original scroll denominator or closure")
    proof_states = {int(r["record_key"]): r for r in state_proof["rows"]}
    if state_proof["revision"] != closure["revision"]:
        raise ValueError("External state evidence belongs to another catalog")
    dependencies = defaultdict(set)
    for row in closure["state_dependencies"]:
        dependencies[row["effect"]].add(row["state"])
    rows, union_effects, union_states = [], set(), set()
    all_functions, all_events, families = set(), set(), set()
    for reference, item in sorted(indexed.items()):
        pending = list(definitions[str(reference)]["raw_roots"])
        seen, selected_states, functions, events = set(), set(), set(), set()
        state_operands, excluded, unresolved = set(), [], []

        def state(identity):
            if identity in selected_states:
                return
            selected_states.add(identity)
            row = states[str(identity)]
            pending.extend(row.get("effect_ids", ()))
            for key in ("levels", "native_level_checks"):
                for level in row.get(key, ()):
                    pending.extend(level.get("effects", ()))

        # This is the previous source-proved eVZ5227 dependency, never a
        # numeric-operand guess or a new runtime rule/scroll allowlist.
        for identity in item.get("implicit_runtime_state_refs", ()):
            if str(identity) not in closure["implicit_runtime_state_dependencies"]:
                raise ValueError("Missing explicit implicit-dependency authority")
            state(identity)
        while pending:
            identity = pending.pop()
            if identity in seen:
                continue
            seen.add(identity)
            effect = effects[str(identity)]
            family = effect["effect_class"]
            families.add(family)
            if family not in COMBAT_FAMILIES or effect.get(
                "native_definition_class"
            ) not in ("eVE", "eVy"):
                unresolved.append(
                    dict(effect=identity, reason="Unaudited native operation domain")
                )
            pending.extend(effect.get("children", ()))
            for sid in dependencies[identity]:
                state(sid)
            masks = effect["target_masks"]
            if len(masks) != 7:
                raise ValueError("Malformed native combat subscription masks")
            for mask in masks:
                for event in mask or ():
                    if type(event) is not int:
                        raise ValueError("Malformed native event identifier")
                    events.add(event)
            expression = effect.get("criteria", "").strip()
            if not expression:
                continue
            tree = parse_local_criterion(expression)
            for node in ast.walk(tree):
                if isinstance(node, ast.Compare):
                    operands = (node.left, *node.comparators)
                    for left, right in zip(operands, operands[1:]):
                        for call, value in ((left, right), (right, left)):
                            if (
                                isinstance(call, ast.Call)
                                and isinstance(call.func, ast.Name)
                                and call.func.id == "GetTriggeringContainerStateId"
                                and isinstance(value, ast.Constant)
                                and type(value.value) is int
                            ):
                                state_operands.add(value.value)
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Name):
                    unresolved.append(
                        dict(effect=identity, reason="Indirect criterion call")
                    )
                    continue
                name = node.func.id
                functions.add(name)
                if name in CONTENT_GATES:
                    excluded.append(
                        dict(
                            effect=identity,
                            predicate=name,
                            criterion=expression,
                            authority=CONTENT_GATES[name],
                        )
                    )
                elif name not in COMBAT_FUNCTIONS:
                    unresolved.append(
                        dict(
                            effect=identity,
                            predicate=name,
                            reason="Unknown predicate source domain",
                        )
                    )
                if name in (
                    "HasState",
                    "HasStateFromLevel",
                    "HasStateFromUser",
                    "GetStateLevel",
                    "GetStateCountInRange",
                ):
                    operand = ast.literal_eval(node.args[0])
                    if type(operand) is not int:
                        unresolved.append(
                            dict(effect=identity, reason="Dynamic state operand")
                        )
                    else:
                        state_operands.add(operand)
        if seen != set(item["effect_refs"]):
            raise ValueError(
                "Current transitive closure differs from named source mapping"
            )
        for sid in state_operands:
            # −1 is the original native no-state sentinel, not a mission ID.
            if sid != -1 and str(sid) not in states and sid not in proof_states:
                unresolved.append(
                    dict(state=sid, reason="Unresolved external combat-state operand")
                )
        classification = (
            "excluded" if excluded else "unresolved" if unresolved else "relevant"
        )
        rows.append(
            dict(
                reference=reference,
                name=item["name"],
                kind=item["type"],
                classification=classification,
                reason="Original combat execution graph; no quest/achievement execution gate"
                if classification == "relevant"
                else "See source-bound evidence",
                roots=definitions[str(reference)]["raw_roots"],
                effect_ids=sorted(seen),
                state_ids=sorted(selected_states),
                criterion_functions=sorted(functions),
                event_ids=sorted(events),
                external_state_operands=sorted(
                    s for s in state_operands if str(s) not in states
                ),
                quest_gate_evidence=excluded,
                unresolved_evidence=unresolved,
            )
        )
        union_effects.update(seen)
        union_states.update(selected_states)
        all_functions.update(functions)
        all_events.update(events)
    if set(map(str, union_effects)) != set(effects) or set(
        map(str, union_states)
    ) != set(states):
        raise ValueError("Classifier did not cover every exported effect/state")
    counts = Counter(row["classification"] for row in rows)
    return dict(
        schema=1,
        policy="actual-execution-dependency-only-v1",
        native_revision=closure["revision"],
        acquisition_or_display_names_used_for_exclusion=False,
        counts={key: counts[key] for key in ("relevant", "excluded", "unresolved")},
        total=len(rows),
        effect_count=len(union_effects),
        state_count=len(union_states),
        criterion_functions=sorted(all_functions),
        event_ids=sorted(all_events),
        native_combat_families=sorted(families),
        execution_qualification_or_activation_claimed=False,
        rows=rows,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--closure", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--external-state-proof", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    closure, closure_sha = read(args.closure)
    inventory, inventory_sha = read(args.inventory)
    state_proof, state_sha = read(args.external_state_proof)
    result = classify(closure, inventory, state_proof)
    result["source_sha256"] = dict(
        closure=closure_sha,
        named_inventory=inventory_sha,
        external_state_proof=state_sha,
        classifier=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "counts",
                    "total",
                    "effect_count",
                    "state_count",
                    "source_sha256",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
