"""Bounded real allied constructor proposals; never forge criterion counts."""
import ast


def required_allied_population(criterion):
    if not isinstance(criterion, str) or not criterion.strip() or len(criterion) > 2048:
        return None
    try:
        root = ast.parse("(" + criterion.strip() + ")", mode="eval").body
    except (SyntaxError, ValueError):
        return None
    if sum(1 for _ in ast.walk(root)) > 128:
        return None

    def terms(n):
        if isinstance(n, ast.BoolOp) and isinstance(n.op, ast.And):
            for v in n.values:
                yield from terms(v)
        else:
            yield n

    candidates = []
    for term in terms(root):
        if (
            not isinstance(term, ast.Compare)
            or len(term.ops) != 1
            or len(term.comparators) != 1
        ):
            continue
        call = term.left
        bound = term.comparators[0]
        if not (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "GetAlliesCountInRange"
            and not call.keywords
            and len(call.args) in (1, 2)
            and all(isinstance(a, ast.Constant) for a in call.args)
            and isinstance(bound, ast.Constant)
            and type(bound.value) is int
        ):
            continue
        radius = call.args[0].value
        selector = call.args[1].value if len(call.args) == 2 else "caster"
        needed = (
            bound.value + 1
            if isinstance(term.ops[0], ast.Gt)
            else bound.value
            if isinstance(term.ops[0], ast.GtE)
            else None
        )
        # Existing constructor adds exactly one ally; native eKn counts self.
        if (
            type(radius) is int
            and 1 <= radius <= 3
            and selector in ("caster", "target")
            and needed == 2
        ):
            candidates.append(
                {"radius": radius, "minimum_allies": 2, "center": selector}
            )
    return min(candidates, key=lambda p: p["radius"], default=None)


def allied_population_recipe(reference, level, capability, criterion, profile):
    requirement = required_allied_population(criterion)
    if (
        requirement is None
        or capability.get("minimum") != 0
        or capability.get("maximum") != 0
    ):
        return None
    if (
        type(reference) is not int
        or type(level) is not int
        or not isinstance(profile, dict)
        or profile.get("ref") != reference
        or not profile["min_level"] <= level <= profile["max_level"]
    ):
        raise ValueError("Missing exact allied native descriptor authority")
    return {
        "kind": "native_opponent",
        "opponent": {"reference": reference, "level": level, "team": 1},
        "discovery": "native_two_allied_population_v1",
        "allied_population": requirement,
    }


def allied_spare_eligible(scenario, source, enemy, spare):
    requirement = scenario.get("allied_population")
    if (
        scenario.get("discovery") != "native_two_allied_population_v1"
        or not isinstance(requirement, dict)
        or requirement.get("minimum_allies") != 2
        or requirement.get("center") not in ("caster", "target")
        or type(requirement.get("radius")) is not int
        or not 1 <= requirement["radius"] <= 3
        or scenario.get("opponent", {}).get("team") != 1
    ):
        raise ValueError("Invalid actual allied population recipe")
    return (
        tuple(spare) not in (tuple(source), tuple(enemy))
        and spare[2] == source[2]
        and 0
        < abs(spare[0] - source[0]) + abs(spare[1] - source[1])
        <= requirement["radius"]
    )
