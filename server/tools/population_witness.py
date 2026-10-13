"""Bounded actual-population proposal; never mutates native resources or state."""
import ast


def required_enemy_population(criterion):
    """Recognize a positive bounded count conjunct without weakening others."""
    try:
        node = ast.parse("(" + criterion.strip() + ")", mode="eval").body
    except (SyntaxError, ValueError, AttributeError):
        return None
    nodes = (
        node.values
        if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And)
        else [node]
    )
    candidates = []
    for term in nodes:
        if not isinstance(term, ast.Compare) or len(term.ops) != 1:
            continue
        call = term.left
        if not (
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "GetEnnemyCountInRange"
            and not call.keywords
            and len(call.args) in (1, 2)
        ):
            continue
        if not all(isinstance(a, ast.Constant) for a in call.args):
            continue
        radius = call.args[0].value
        if len(call.args) == 2 and call.args[1].value != "caster":
            continue
        bound = term.comparators[0]
        if not isinstance(bound, ast.Constant) or type(bound.value) is not int:
            continue
        count = (
            bound.value + 1
            if isinstance(term.ops[0], ast.Gt)
            else bound.value
            if isinstance(term.ops[0], ast.GtE)
            else None
        )
        if (
            type(radius) is int
            and 1 <= radius <= 3
            and count is not None
            and 1 <= count <= 3
        ):
            candidates.append(dict(radius=radius, minimum_enemies=count))
    return max(candidates, key=lambda c: c["minimum_enemies"], default=None)


def choose_enemy_cells(source, existing_enemy_cells, free_native_cells, requirement):
    """Choose only genuine free scene cells; native constructor must add actors."""
    radius = requirement["radius"]
    close = (
        lambda c: c[2] == source[2]
        and abs(c[0] - source[0]) + abs(c[1] - source[1]) <= radius
    )
    existing = {
        tuple(c) for c in existing_enemy_cells if close(c) and tuple(c) != tuple(source)
    }
    need = requirement["minimum_enemies"] - len(existing)
    if need <= 0:
        return []
    cells = sorted(
        {tuple(c) for c in free_native_cells if close(c) and tuple(c) != tuple(source)}
        - existing,
        key=lambda c: (abs(c[0] - source[0]) + abs(c[1] - source[1]), c),
    )
    return cells[:need] if len(cells) >= need else None
