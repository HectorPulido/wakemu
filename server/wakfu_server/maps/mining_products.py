"""Fixed products and explicitly local selection for native mining candidates.

The native catalog exposes both a fixed ``item_reference`` and a list of
``product_references``. The selection semantics of the latter are not inferred
from raw native getters; this module only resolves them under a persisted local
policy and only when every candidate has an installed native stack rule.
"""
import secrets


def _stack_rules():
    from wakfu_server.inventory_move import STACKS

    return STACKS


def _eligible_action(rule):
    return (
        isinstance(rule, dict)
        and rule.get("profession_id") == 73
        and isinstance(rule.get("criteria"), str)
        and not rule["criteria"].strip()
        and isinstance(rule.get("raw_getters"), dict)
        and rule["raw_getters"].get("cvF") == 0
    )


def _candidates(rule):
    values = rule.get("product_references")
    if not isinstance(values, (list, tuple)) or not values:
        return None
    if any(type(value) is not int or value <= 0 for value in values):
        return None
    if len(set(values)) != len(values):
        return None
    stacks = _stack_rules()
    if any(value not in stacks for value in values):
        return None
    return list(values)


def supports_action(rule):
    """Whether an unconditional terminal mining action has a known product.

    Fixed native products remain the primary rule. A zero fixed item may use
    its native candidate list only if each candidate is a positive, installed
    stackable item. No unsupported item is fabricated or silently discarded.
    """
    if not _eligible_action(rule):
        return False
    stacks = _stack_rules()
    fixed = rule.get("item_reference")
    if type(fixed) is int and fixed > 0:
        return fixed in stacks
    return _candidates(rule) is not None


def resolve(db, rule):
    """Resolve one fixed/native-candidate product under the local policy.

    A fixed native product is returned unchanged. Candidate-list actions need
    the explicit ``native_candidates_weighted`` local policy seeded by the
    mining migration; omitted candidate weights default to uniform selection.
    """
    if not _eligible_action(rule):
        raise ValueError("Unsupported native mining action")
    stacks = _stack_rules()
    fixed = rule.get("item_reference")
    if type(fixed) is int and fixed > 0:
        if fixed not in stacks:
            raise ValueError("Unknown native mining product stack rule")
        return fixed

    candidates = _candidates(rule)
    if candidates is None:
        raise ValueError("Native mining candidates are malformed or unsupported")
    setting = db.execute(
        "SELECT value FROM settings WHERE name='mining_vein_policy'"
    ).fetchone()
    policy = None if setting is None else setting["value"]
    selection = policy.get("product_selection") if isinstance(policy, dict) else None
    if (
        not isinstance(selection, dict)
        or set(selection) != {"mode", "weights"}
        or selection.get("mode") != "native_candidates_weighted"
        or not isinstance(selection.get("weights"), dict)
    ):
        raise ValueError("Missing or invalid local mining product-selection policy")
    weights_by_reference = selection["weights"]
    candidate_keys = {str(reference) for reference in candidates}
    if set(weights_by_reference) - candidate_keys:
        raise ValueError("Mining product weights include a non-candidate item")
    weights = []
    for reference in candidates:
        weight = weights_by_reference.get(str(reference), 1)
        if type(weight) is not int or not 1 <= weight <= 1_000_000:
            raise ValueError("Mining product weights must be positive bounded integers")
        weights.append(weight)
    return secrets.SystemRandom().choices(candidates, weights=weights, k=1)[0]
