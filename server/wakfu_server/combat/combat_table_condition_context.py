"""Demand-limited context for criteria reading only the native table clock.

Only immutable AST classification is cached. Actor authority and the short
native clock are read again for each context; no action result is cached.
"""
import ast
from functools import lru_cache

from .combat_conditions import ConditionContext, _condition_root


@lru_cache(maxsize=512)
def table_clock_only(criteria):
    try:
        root = _condition_root(criteria.strip())
    except ValueError:
        return False  # The original full path retains its normal error policy.
    calls = [node for node in ast.walk(root) if isinstance(node, ast.Call)]
    return (
        bool(calls)
        and all(
            isinstance(node.func, ast.Name)
            and node.func.id == "GetFightCurrentTableTurn"
            and not node.args
            and not node.keywords
            for node in calls
        )
        and all(
            node.id == "GetFightCurrentTableTurn"
            for node in ast.walk(root)
            if isinstance(node, ast.Name)
        )
    )


def table_only_condition_context(preview, effect, invocation, authority_for):
    """Return None for every context outside the reviewed simple actor case."""
    if (
        not isinstance(effect, dict)
        or not isinstance(effect.get("criteria"), str)
        or not table_clock_only(effect["criteria"])
        or getattr(invocation, "native_target_cell_argument", False)
        or getattr(invocation, "native_trigger_context", None) is not None
    ):
        return None
    source = preview.actors.get(invocation.caster_id)
    target = preview.actors.get(invocation.target_id)
    # Area PVs, null/cell targets and detached constructors keep the complete
    # original context, including their existing QI/null/owner validation.
    if source is None or target is None:
        return None
    authority = authority_for(source)
    if authority.native_controller_id not in (None, source.id, target.id):
        return None
    if target is not source:
        authority_for(target)
    for actor in (source, target):
        affiliation = getattr(actor, "native_fight_affiliation", actor.team)
        if type(affiliation) is not int or not -128 <= affiliation < 128:
            raise ValueError("Missing native signed-byte bcM affiliation")
    return ConditionContext(
        {},
        fight_current_table_turn=getattr(preview, "native_table_turn", None),
    )
