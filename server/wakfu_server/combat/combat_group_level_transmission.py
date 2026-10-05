"""eYg/eZM flag16 gate and eZR.fRR, with explicit native inputs."""


def child_evaluation_level(*, override, container_present, container_level):
    """eZR.fRR on the newly built child PS, not on the parent's PS."""
    if type(override) is not int or not -(1 << 31) <= override < (1 << 31):
        raise ValueError("Signed native child SP required")
    if override != -1:
        return ((override + 32768) % 65536) - 32768
    if type(container_present) is not bool:
        raise ValueError("Explicit native child container presence required")
    if not container_present:
        if container_level is not None:
            raise ValueError("Null child container cannot have a level")
        return 0
    if type(container_level) is not int or not -32768 <= container_level <= 32767:
        raise ValueError("Authoritative child eVo.cmZ signed-short level required")
    return container_level


def transmitted_child_override(
    *, flags, child_override, parent_override, container_present, container_level
):
    """Keep a family override; otherwise transmit fRR only when flag16 exists.

    None parent override represents absent PS; -1 is eVt's sentinel. A null
    PL yields zero. Container level must be the actual eVo.cmZ, not an effect
    evaluation level guessed from the invocation.
    """
    if any(type(x) is not int for x in flags) or type(child_override) is not int:
        raise ValueError("Explicit native flags and child override required")
    if 16 not in flags or child_override != -1:
        return child_override
    if parent_override is not None and type(parent_override) is not int:
        raise ValueError("Native parent eVt override required")
    if parent_override is not None and parent_override != -1:
        if not -(1 << 31) <= parent_override < (1 << 31):
            raise ValueError("Native parent override must be signed int")
        return ((parent_override + 32768) % 65536) - 32768
    if type(container_present) is not bool:
        raise ValueError("Explicit native container presence required")
    if not container_present:
        if container_level is not None:
            raise ValueError("Null native container cannot have a level")
        return 0
    if type(container_level) is not int or not -32768 <= container_level <= 32767:
        raise ValueError("Authoritative eVo.cmZ signed-short level required")
    return container_level
