"""fcN.c/fcH.a: AP_AS_MP forbids positive AP costs; it does not remap costs."""
from .combat_conditions import UnknownCondition


def native_ap_cost_available(cost, properties):
    if type(cost) is not int or not -(1 << 31) <= cost < (1 << 31):
        raise ValueError("Missing actual native AP cost")
    # fcN.c bypasses PB tests entirely for nonpositive calculated AP costs.
    if cost <= 0:
        return True
    if not isinstance(properties, (frozenset, set, tuple, list)) or any(
        type(value) is not int for value in properties
    ):
        raise UnknownCondition("Missing actual native AP-cost fight properties")
    return 50 not in properties


def require_native_ap_cost(cost, properties, *, weapon=False):
    if native_ap_cost_available(cost, properties):
        return
    error = ValueError(
        "Native AP_AS_MP property forbids positive-AP "
        + ("item casting" if weapon else "spell casting")
    )
    error.native_casting_result = "twJ"
    error.cast_validation_code = "native_ap_property"
    raise error
