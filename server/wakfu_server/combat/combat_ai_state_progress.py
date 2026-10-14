"""Read-only progress toward a native owned spell's explicit state threshold.

This values preparation for a concrete owned action, never arbitrary states.
Native eLs uses the first matching state ledger entry, not their sum/max.
"""
import ast
from functools import lru_cache


@lru_cache(maxsize=512)
def state_threshold(criterion):
    """Recognize only a standalone monotonic caster-state prerequisite."""
    if not isinstance(criterion, str) or not criterion or len(criterion) > 2048:
        return None
    from .combat_local_criteria import parse_local_criterion

    try:
        root = parse_local_criterion(criterion)
    except (ValueError, SyntaxError):
        return None
    if isinstance(root, ast.Expression):
        root = root.body
    if (
        not isinstance(root, ast.Compare)
        or len(root.ops) != 1
        or len(root.comparators) != 1
        or not isinstance(root.ops[0], (ast.GtE, ast.Gt))
        or not isinstance(root.left, ast.Call)
        or not isinstance(root.left.func, ast.Name)
        or root.left.func.id != "GetStateLevel"
        or root.left.keywords
        or not 1 <= len(root.left.args) <= 2
        or not isinstance(root.left.args[0], ast.Constant)
        or type(root.left.args[0].value) is not int
        or not 0 < root.left.args[0].value < 2**63
        or not isinstance(root.comparators[0], ast.Constant)
        or type(root.comparators[0].value) is not int
    ):
        return None
    if len(root.left.args) == 2 and (
        not isinstance(root.left.args[1], ast.Constant)
        or root.left.args[1].value != "caster"
    ):
        return None
    threshold = root.comparators[0].value + int(isinstance(root.ops[0], ast.Gt))
    if not 1 <= threshold <= 32767:
        return None
    return root.left.args[0].value, threshold


def progress(actor, owned_spells, casting):
    """Measure capped first-entry levels from live ownership and native tables."""
    if actor is None or actor.hp <= 0 or actor.controlled:
        return 0
    thresholds = {}
    for spell in owned_spells:
        record = casting.get(str(spell))
        if not isinstance(record, dict):
            continue
        requirement = state_threshold(record.get("cast_criterion_raw", ""))
        if requirement is not None:
            reference, threshold = requirement
            thresholds[reference] = max(thresholds.get(reference, 0), threshold)
    if not thresholds:
        return 0
    first_levels = {}
    for entry in actor.state_ledger.entries:
        first_levels.setdefault(entry.reference, entry.level)
    return sum(
        min(threshold, max(0, first_levels.get(reference, -1)))
        for reference, threshold in thresholds.items()
    )
