"""Typed original bIg outcome dispatch; reusable tools are never seed payments."""
import struct


def decode(body):
    if not isinstance(body, bytes) or len(body) != 20:
        raise ValueError("Invalid native bIg ground request")
    action, uid, x, y = struct.unpack(">iqii", body)
    if action <= 0 or uid <= 0:
        raise ValueError("Invalid native bIg source identity")
    return dict(action_id=action, source_uid=uid, x=x, y=y)


def dispatch(body, rules, *, optional_group, excavation_state, context):
    if not isinstance(body, bytes) or len(body) < 4:
        return None
    matches = [
        rule for rule in rules if rule["action_id"] == struct.unpack_from(">i", body)[0]
    ]
    if not matches:
        return None
    request = decode(body)
    if len(matches) != 1:
        raise ValueError("Ambiguous native ground action")
    rule = matches[0]
    if rule.get("enabled") is not True:
        raise ValueError("Native ground action is not qualified")
    # Existing reviewed seed rules retain their established outcome by default.
    outcome = rule.get("outcome", "optional_group")
    if outcome == "optional_group":
        return optional_group(request=request, rule=rule, **context)
    if outcome != "excavation_state" or rule.get("consume_units") != 0:
        raise ValueError("Invalid reusable excavation outcome")
    return excavation_state(request=request, rule=rule, **context)
