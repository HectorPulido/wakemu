"""eLI/eLK identifiers from the actual event source Qe, never its listener.

eII.aU selects eZR.fSd first, then eVt.fLP. eLI returns fyW.guI or0;
eLK returns source.baZ.awM (runner action family), not aZE definition ID.
"""


def source_identifiers(retention, effect, invocation):
    descriptor, identity = retention.container(invocation)
    present = descriptor["container_present"]
    if type(present) is not bool:
        raise ValueError("Native source container presence required")
    container = {"present": present}
    if present:
        kind = descriptor["container_type"]
        if type(kind) is not int:
            raise ValueError("Native source container kind required")
        container.update(type=kind, is_state=kind == 3)
        if kind == 3:
            if type(identity) is not int:
                raise ValueError("Native fyW packed identity required")
            raw = (identity >> 16) & 65535
            container["state_id"] = raw - 65536 if raw >= 32768 else raw
    action = effect["effect_class"]
    if type(action) is not int or not -(1 << 31) <= action < (1 << 31):
        raise ValueError("Native source awM action required")
    return {"native_container": container, "effect_action_id": action}


def condition_identifiers(source):
    if source is None:
        return dict(triggering_effect_present=False)
    if not isinstance(source, dict):
        raise ValueError("Native triggering source required")
    result = dict(triggering_effect_present=True)
    reference = source.get("generic_effect")
    if reference is not None:
        if type(reference) is not int or not -(1 << 31) <= reference < (1 << 31):
            raise ValueError("Invalid native running-effect definition")
        result["triggering_effect_reference_id"] = reference
    value = source.get("value")
    if value is not None:
        if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
            raise ValueError("Invalid native running-effect value")
        result["triggering_effect_value"] = value
    action = source.get("effect_action_id")
    if action is not None:
        if type(action) is not int or not -(1 << 31) <= action < (1 << 31):
            raise ValueError("Invalid native awM action")
        result["triggering_effect_action_id"] = action
    container = source.get("native_container")
    if container is None:
        return result  # Unknown metadata is not a null container.
    if not isinstance(container, dict) or type(container.get("present")) is not bool:
        raise ValueError("Invalid native source container")
    if not container["present"]:
        result["triggering_container_is_state"] = False
    elif type(container.get("is_state")) is bool:
        result["triggering_container_is_state"] = container["is_state"]
        if container["is_state"]:
            reference = container.get("state_id")
            if type(reference) is not int or not -32768 <= reference <= 32767:
                raise ValueError("Native fyW.guI short reference required")
            result["triggering_container_state_id"] = reference
    return result
