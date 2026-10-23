"""Pure parameter parser for native family 447 (eWt fight properties)."""

from .combat_parameters import parameter_value


def parse(effect, profile, level):
    raw = effect.get("parameters")
    values = profile.get("parameters") if isinstance(profile, dict) else None
    if (
        not isinstance(raw, (tuple, list))
        or len(raw) < 2
        or len(raw) % 2
        or not isinstance(values, (tuple, list))
        or not values
    ):
        raise ValueError("Native eWt property operation requires one value")
    identity = parameter_value(raw, 0, level)
    if type(identity) is not int:
        raise ValueError("Native eWt property identity must be an evaluated integer")
    # Native eWt consumes only parameter zero; preserve any later native
    # parameter pairs instead of imposing a parser-only arity restriction.
    return {"property_id": identity}
