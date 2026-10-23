"""One total guild weekly-cap interpretation for rewards and native UI."""


def effective_cap(policy, guild, state):
    if not isinstance(state, dict):
        raise ValueError("Missing stored guild weekly-cap authority")
    if "native_weekly_point_cap" in state:
        # fhc -> fgH.Up replaces the total; this is not a capacity increment.
        value = state["native_weekly_point_cap"]
    else:
        base, extra = policy.get("weekly_point_cap"), guild.get(
            "weekly_capacity_bonus", 0
        )
        if type(base) is not int or type(extra) is not int:
            raise ValueError("Invalid guild weekly-cap components")
        value = base + extra
    if type(value) is not int or not 1 <= value < 2**31:
        raise ValueError("Invalid total guild weekly point cap")
    return value
