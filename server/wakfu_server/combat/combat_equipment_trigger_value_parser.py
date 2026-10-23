"""Pure parser for native family 430 (eZL triggering-runner amount edits)."""

from .combat_parameters import parameter_value


def parse(effect, profile, level):
    raw = effect.get("parameters")
    evaluated = profile.get("parameters") if isinstance(profile, dict) else None
    # Native metadata permits additional pairs; the handler consumes only the
    # first three as mode, amount, and replace flag.
    if (
        not isinstance(raw, (tuple, list))
        or len(raw) < 6
        or len(raw) % 2
        or not isinstance(evaluated, (tuple, list))
        or len(evaluated) < 3
    ):
        raise ValueError("Native eZL requires three parameter pairs")
    mode, amount, replace_flag = (
        parameter_value(raw, index, level) for index in range(3)
    )
    return {
        "mode": mode,
        "amount": amount,
        "replace": replace_flag != 0,
    }
