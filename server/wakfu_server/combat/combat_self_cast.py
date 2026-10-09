"""Native fyP.cwE exception to minimum range at caster XY (fcj.a)."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT
from .combat_conditions import UnknownCondition, evaluate_condition


@lru_cache(maxsize=1)
def catalog():
    return protocol_catalog.load(DATA_ROOT / "native-self-cast-policies.json")["spells"]


def allows_self(reference, context, *, policies=None):
    rows = catalog() if policies is None else policies
    row = rows.get(str(reference))
    if not isinstance(row, dict) or type(row.get("allowed")) is not bool:
        raise UnknownCondition("Missing native self-cast policy")
    base = row["allowed"]
    if all(rule.get("allowed") is base for rule in row["conditional"]):
        return base  # Every condition-selected table has the same native flag.
    if context is None:
        raise UnknownCondition("Missing native self-cast conditional context")
    matches = set()
    unknown = False
    for rule in row["conditional"]:
        allowed = rule["allowed"]
        if type(allowed) is not bool:
            raise UnknownCondition("Invalid native self-cast conditional policy")
        try:
            matched = evaluate_condition(rule["criteria"], context)
        except UnknownCondition:
            if allowed != base:
                raise
            unknown = True
            continue
        if matched:
            matches.add(allowed)
    if len(matches) > 1 or unknown and any(value != base for value in matches):
        raise UnknownCondition("Ambiguous native self-cast conditional policy")
    return next(iter(matches)) if matches else base
