"""eJE's current running effect -> eZR.fRR; never the triggering source."""
from .combat_effect_removal import _identity_fields
from .combat_native_container import resolve_state_container


def running_container_level(fight, plan, invocation):
    if invocation is None:
        return 0  # eJE's explicit third-argument null.
    if invocation.native_context_hex is not None:
        fields = _identity_fields(
            bytes.fromhex(invocation.native_context_hex), integer_fields=(4,)
        )
        if 4 not in fields:
            raise ValueError("Missing native current eVt level override")
        override = fields[4] & 0xFFFFFFFF
        if override >= (1 << 31):
            override -= 1 << 32
        if override != -1:
            return ((override + 32768) % 65536) - 32768
    if invocation.state_uid is not None:
        level = resolve_state_container(fight, invocation.state_uid).level
    elif "native_retained_container" in plan:
        container = plan["native_retained_container"]
        present = container.get("present")
        if type(present) is not bool:
            raise ValueError("Missing native PL presence")
        if not present:
            return 0
        level = container.get("level")
    elif type(plan.get("spell_id")) is int and plan["spell_id"] > 0:
        # This is the actual fyF instance created by the authoritative spell plan.
        level = plan.get("evaluation_level")
    else:
        raise ValueError("Missing native current PL level authority")
    if type(level) is not int or not -32768 <= level <= 32767:
        raise ValueError("Missing native eVo.cmZ signed-short level")
    return level
