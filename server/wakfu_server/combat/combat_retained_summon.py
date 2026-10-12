"""Exact native eZl iR actor identity; no implied actor lifetime operation."""


def retained_summon_actor(payload):
    from .wire import proto_fields
    from .combat_effect_removal import _identity_fields

    messages = [value for tag, value in proto_fields(payload) if tag == 98]
    if len(messages) != 1 or not isinstance(messages[0], bytes):
        raise ValueError("Retained summon payload needs exactly one native iR")
    fields = _identity_fields(messages[0], integer_fields=(4,))
    identity = fields.get(4)
    if type(identity) is not int or not 0 < identity < (1 << 63):
        raise ValueError("Invalid retained summon actor identity")
    return identity
