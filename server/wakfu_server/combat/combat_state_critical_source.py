"""Current causing critical branch for the qualified Wakemu state-pair policy.

This is separate from native eZk.rHA, the state carrier's creation flag. A
retained listener observes the current Qe source definition; without a source,
the owned execution boundary supplies its already selected critical branch.
"""


def causing_state_critical(invocation, *, current_critical):
    if type(current_critical) is not bool:
        raise ValueError("Missing current owned critical execution branch")
    source = getattr(invocation, "native_trigger_context", None)
    if source is None:
        return current_critical
    if not isinstance(source, dict):
        raise ValueError("Malformed actual triggering critical source")
    present = source.get("native_definition_present")
    if present is False:
        return False  # Actual source PK is null; native dd(1) cannot be set.
    if present is None:
        return None  # Unknown is only a blocker when paired selection needs it.
    if type(present) is not bool:
        raise ValueError("Invalid actual triggering definition presence")
    variant = source.get("native_definition_variant")
    if variant is None:
        return None
    if type(variant) is not int or not -(1 << 63) <= variant < 1 << 63:
        raise ValueError("Invalid actual triggering PK.dd(1) variant")
    return bool(variant & 1)
