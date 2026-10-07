"""Native exchange criteria and initial binding for the complete item catalog.

Template binding is distinct from any persisted per-instance binding override.
Unknown instances/references/expressions cannot acquire exchange eligibility.
"""
import json
from .paths import DATA_ROOT


CATALOG = json.loads((DATA_ROOT / "item-exchange-metadata.json").read_text())
if (
    CATALOG.get("errors") != 0
    or CATALOG.get("raw_records") != CATALOG.get("loaded_records")
    or CATALOG.get("loaded_records") != len(CATALOG.get("items", {}))
):
    raise ValueError("Incomplete native exchange metadata")
ITEMS = CATALOG["items"]


def eligibility(reference, *, bound=None):
    """Evaluate native template plus an optional authoritative instance state.

    This catalog has only NOT_BOUND and the two BOUND_ON_PICKUP variants.
    A persisted true binding can deny a unit; false cannot undo template binding.
    """
    if type(reference) is not int or reference <= 0:
        raise ValueError("Invalid exchange item reference")
    row = ITEMS.get(str(reference))
    if row is None or row.get("reference") != reference:
        raise ValueError("Unknown native exchange item reference")
    template = row.get("binding_template", {})
    native_bound = template.get("default_eKo")
    if type(native_bound) is not bool or template.get("enum") not in (
        "NOT_BOUND",
        "BOUND_ON_PICKUP_TO_ACCOUNT",
        "BOUND_ON_PICKUP_TO_CHARACTER",
    ):
        raise ValueError("Unsupported native item binding")
    if bound is not None and type(bound) is not bool:
        raise ValueError("Invalid persisted exchange binding")
    if native_bound or bound is True:
        return False
    criteria = row.get("raw_criteria")
    if not isinstance(criteria, dict):
        raise ValueError("Missing native exchange criteria")
    expression = criteria.get("EXCHANGE")
    if expression is None:
        return True
    # Faux is the native French false literal; verified with amb.b offline.
    if expression in ("False", "Faux"):
        return False
    raise ValueError("Unsupported native exchange criterion")
