"""Closed native resource-action criterion fragment, without runtime imports.

GetLevel() reads the interaction actor's effective level. Callers must supply
that authoritative value anew in prepare, reserve, and complete; a real-level
eligibility check does not replace modulation-aware action authorization.
"""
import ast
from functools import lru_cache

from wakfu_server.combat_local_criteria import parse_local_criterion


@lru_cache(maxsize=128)
def minimum_effective_level(text):
    """Return a native GetLevel minimum, or None for the empty criterion.

    Every other fragment fails closed. This is not an arbitrary Python evaluator.
    """
    if type(text) is not str or len(text) > 1024:
        raise ValueError("Invalid resource action criterion")
    text = text.strip()
    if not text:
        return None
    try:
        node = parse_local_criterion(text)
        if isinstance(node, ast.Expression):
            node = node.body
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise ValueError("Invalid resource action criterion syntax") from exc
    if not (
        isinstance(node, ast.Compare)
        and len(node.ops) == len(node.comparators) == 1
        and type(node.ops[0]) is ast.GtE
        and isinstance(node.left, ast.Call)
        and isinstance(node.left.func, ast.Name)
        and node.left.func.id == "GetLevel"
        and not node.left.args
        and not node.left.keywords
        and isinstance(node.comparators[0], ast.Constant)
        and type(node.comparators[0].value) is int
        and 0 <= node.comparators[0].value <= 32767
    ):
        raise ValueError("Unsupported native resource action criterion")
    return node.comparators[0].value


def allows(text, *, effective_level):
    """Evaluate only against a supplied current effective actor level."""
    minimum = minimum_effective_level(text)
    if type(effective_level) is not int or not 1 <= effective_level <= 32767:
        raise ValueError("Missing authoritative effective resource actor level")
    return minimum is None or effective_level >= minimum


def authorize(rule, *, effective_level):
    """Adapter for a source-verified resource action; preserves its identity."""
    if type(rule) is not dict or "criteria" not in rule:
        raise ValueError("Missing native resource action criterion")
    if not allows(rule["criteria"], effective_level=effective_level):
        raise ValueError("Resource action actor level requirement not met")
    return rule
