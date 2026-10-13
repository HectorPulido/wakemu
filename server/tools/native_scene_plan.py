"""Compose native scene requirements and prioritize existing witnesses without grants."""
import ast


def native_requirements(record, index, criterion, *, available_resources=None):
    """Consume an already resolved native table; never infer a spell level or root."""
    from wakfu_server.combat_local_criteria import parse_local_criterion

    if not isinstance(record, dict) or type(index) is not int or index < 0:
        raise ValueError("Missing resolved native casting authority")
    levels, costs = record.get("levels"), record.get("costs")
    if (
        not isinstance(levels, list)
        or index >= len(levels)
        or not isinstance(costs, list)
        or index >= len(costs)
    ):
        raise ValueError("Missing resolved native casting table row")
    row, cost = levels[index], costs[index]
    if (
        not isinstance(row, (list, tuple))
        or len(row) != 3
        or any(type(v) is not int for v in row[:2])
        or not 0 <= row[0] <= row[1]
        or not isinstance(row[2], list)
        or any(type(v) is not int or v <= 0 for v in row[2])
    ):
        raise ValueError("Malformed native scene range or roots")
    if (
        not isinstance(cost, (list, tuple))
        or len(cost) != 3
        or any(type(v) is not int or v < 0 for v in cost)
    ):
        raise ValueError("Malformed native resource requirement")
    result = {
        "range": {"minimum": row[0], "maximum": row[1]},
        "native_root_ids": list(row[2]),
        "resources": dict(zip(("ap", "mp", "wp"), cost)),
        "features": set(),
        "population": [],
        "hp": [],
        "deferred_predicates": [],
        "flags": {
            k: record.get(k)
            for k in ("linear", "diagonal", "line_of_sight", "free_cell", "allow_self")
        },
    }
    if record.get("free_cell") is True:
        result["features"].add("empty_anchor")
    if criterion:
        root = parse_local_criterion(criterion)
        if len(list(ast.walk(root))) > 256:
            raise ValueError("Native criterion exceeds bounded planning scope")
        terms = (
            root.values
            if isinstance(root, ast.BoolOp) and isinstance(root.op, ast.And)
            else [root]
        )
        for term in terms:
            negative = isinstance(term, ast.UnaryOp) and isinstance(term.op, ast.Not)
            call = term.operand if negative else term
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                name = call.func.id
                if name == "IsEnnemy" and not call.args:
                    result["features"].add("ally" if negative else "enemy")
                elif name == "IsTargetCellFree" and not call.args:
                    result["features"].add(
                        "occupied_anchor" if negative else "empty_anchor"
                    )
                elif name == "IsPlayer" and not negative:
                    result["features"].add("player_target")
            if (
                isinstance(term, ast.Compare)
                and len(term.ops) == len(term.comparators) == 1
                and isinstance(term.left, ast.Call)
                and isinstance(term.left.func, ast.Name)
            ):
                call = term.left
                args = call.args
                bound = term.comparators[0]
                if (
                    not call.keywords
                    and all(isinstance(a, ast.Constant) for a in args)
                    and isinstance(bound, ast.Constant)
                    and type(bound.value) is int
                ):
                    values = [a.value for a in args]
                    if (
                        call.func.id
                        in ("GetEnnemyCountInRange", "GetAlliesCountInRange")
                        and len(values) in (1, 2)
                        and type(values[0]) is int
                        and 1 <= values[0] <= 3
                        and (len(values) == 1 or values[1] in ("caster", "target"))
                    ):
                        count = (
                            bound.value + 1
                            if isinstance(term.ops[0], ast.Gt)
                            else bound.value
                            if isinstance(term.ops[0], ast.GtE)
                            else None
                        )
                        if count is not None and 1 <= count <= 3:
                            result["features"].add("population")
                            result["population"].append(
                                {
                                    "relation": "enemy"
                                    if call.func.id == "GetEnnemyCountInRange"
                                    else "ally",
                                    "radius": values[0],
                                    "subject": values[1]
                                    if len(values) == 2
                                    else "caster",
                                    "minimum": count,
                                }
                            )
                    if (
                        call.func.id == "GetCharacInPct"
                        and len(values) in (1, 2)
                        and isinstance(values[0], str)
                        and values[0].upper() == "HP"
                        and isinstance(term.ops[0], ast.Lt)
                        and 1 <= bound.value <= 99
                    ):
                        subject = values[1] if len(values) == 2 else "caster"
                        if subject in ("caster", "target"):
                            result["features"].add("hp_prerequisite")
                            result["hp"].append(
                                {"subject": subject, "below_percent": bound.value}
                            )
        result["deferred_predicates"] = sorted(
            {
                n.func.id
                for n in ast.walk(root)
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name)
                and (
                    n.func.id
                    in (
                        "HasState",
                        "IsBreedId",
                        "IsSpecific",
                        "CasterAndTargetHaveSameOriginalController",
                    )
                    or n.func.id.startswith("IsSpecificArea")
                )
            }
        )
    if {"enemy", "ally"} <= result["features"] or {
        "empty_anchor",
        "occupied_anchor",
    } <= result["features"]:
        raise ValueError("Contradictory necessary native scene predicates")
    result["features"] = sorted(result["features"])
    result["resource_deficits"] = {}
    if available_resources is not None:
        if any(type(available_resources.get(k)) is not int for k in ("ap", "mp", "wp")):
            raise ValueError("Missing authoritative actor resources")
        result["resource_deficits"] = {
            k: max(0, v - available_resources[k])
            for k, v in result["resources"].items()
            if v > available_resources[k]
        }
    return result


def prioritize_existing_scenes(requirements, scenarios, witnesses=()):
    """Select existing native-derived recipes before blind defaults, keeping caps outside."""
    needed = set(requirements["features"])
    metadata = {}
    for witness in witnesses:
        if (
            not isinstance(witness, dict)
            or "scenario" not in witness
            or not isinstance(witness.get("features"), list)
        ):
            raise ValueError("Malformed existing scene witness")
        metadata[id(witness["scenario"])] = witness

    def rank(pair):
        index, scene = pair
        w = metadata.get(id(scene), {})
        features = set(w.get("features", []))
        deferred = w.get("deferred_identity_or_state", False)
        # Resource producers must already have independent native proof, never a grant.
        proven = w.get("native_producer_proven", False)
        if "resource_producer" in features and not proven:
            features.remove("resource_producer")
        return (bool(deferred), -len(needed & features), not bool(w), index)

    ordered = [scene for _, scene in sorted(enumerate(scenarios), key=rank)]
    return {
        "scenarios": ordered,
        "requirements": requirements,
        "uncovered_features": sorted(
            needed - set().union(*(set(w.get("features", [])) for w in witnesses))
            if witnesses
            else needed
        ),
        "resource_deficits_remain_pending": bool(requirements["resource_deficits"]),
        "creates_actors": False,
        "grants_resources": False,
        "changes_native_criteria": False,
    }


def existing_witnesses(scenarios):
    """Adapt existing recipe contracts; constructor/producers still execute normally."""
    witnesses = []
    for scene in scenarios:
        features = []
        deferred = False
        if isinstance(scene, str):
            features = {
                "enemy": ["enemy", "player_target"],
                "wounded_ally": ["ally"],
                "knocked_out_ally": ["ally"],
            }.get(scene, [])
        elif isinstance(scene, dict):
            discovery = scene.get("discovery", "")
            if scene.get("kind") == "native_opponent":
                features.append(
                    "ally" if scene.get("opponent", {}).get("team", 0) == 1 else "enemy"
                )
            if scene.get("population"):
                features.append("population")
            if discovery == "native_incoming_damage_hp_prerequisite_v1":
                features.append("hp_prerequisite")
            deferred = discovery in (
                "owned_conditional_self_state_v1",
                "positive_native_target_identity_v1",
            )
        witnesses.append(
            {
                "scenario": scene,
                "features": features,
                "deferred_identity_or_state": deferred,
            }
        )
    return witnesses


def plan_existing_native_scenes(record, index, criterion, scenarios):
    """Reorder existing simple scene witnesses; leave hard prerequisites unchanged."""
    from wakfu_server.combat_conditions import UnknownCondition

    try:
        requirements = native_requirements(record, index, criterion)
    except (ValueError, SyntaxError, UnknownCondition):
        # The ordinary validator/transaction still owns all missing-authority guards.
        return scenarios
    if requirements["deferred_predicates"] or not requirements["features"]:
        return scenarios
    return prioritize_existing_scenes(
        requirements, scenarios, existing_witnesses(scenarios)
    )["scenarios"]
