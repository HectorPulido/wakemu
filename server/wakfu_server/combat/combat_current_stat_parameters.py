"""Pure native eWQ/eWR parameter interpretation shared with preflight."""
from .combat_parameters import parameter_value


def stat_parameters(
    parameters, level, *, registered_stat_id, percent_default, trigger_value
):
    """eWW.C for one-to-three parameter variants; dynamic stat is parameter2.

    Four parameters are dice (UK.d), five can include application chance; these
    shapes remain outside this deterministic parser. A value -1 copies the
    authoritative triggering value supplied by the caller.
    """
    if len(parameters) not in (2, 4, 6) or type(percent_default) is not bool:
        raise ValueError("Unsupported native current-stat parameter variant")
    values = [
        parameter_value(parameters, i, level) for i in range(len(parameters) // 2)
    ]
    value = values[0]
    if value == -1:
        if type(trigger_value) is not int:
            raise ValueError("Missing native triggering effect value")
        value = trigger_value
    stat = registered_stat_id
    if stat is None:
        if len(values) < 3:
            raise ValueError("Missing dynamic native characteristic")
        stat = values[2] & 255
    if type(stat) is not int or not 0 <= stat <= 255:
        raise ValueError("Invalid native characteristic registry ID")
    return dict(
        stat_id=stat,
        requested=value,
        percent=(values[1] == 1) if len(values) > 1 else percent_default,
    )
