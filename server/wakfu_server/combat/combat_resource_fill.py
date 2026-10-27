"""Native eYP272/983: eWQ addition of actual PA maximum minus current.

These zero-parameter prototypes inherit eWW guards, Qe phases, eWQ.nG writes
and retained PA.oo reversal. eYP.C does not initialize rCB: AdditionalDatas
request25 remains JVM-zero even though the calculated runner amount is a delta.
"""
from .combat_stat_handler import NativeStatHandler

FAMILIES = {272: 3, 983: 2}


def resource_fill_amount(maximum, current):
    """Exact Java signed-int PA.aYU()-PA.aYS(), including negative results."""
    if any(
        type(value) is not int or not -(1 << 31) <= value < (1 << 31)
        for value in (maximum, current)
    ):
        raise ValueError("Native eYP requires signed-int maximum/current")
    return (maximum - current + (1 << 31)) % (1 << 32) - (1 << 31)


class NativeResourceFillHandler(NativeStatHandler):
    """Reuse the real current-characteristic runner without changing its effect."""

    def __init__(self, fight, packets, *, action_id, allocate_uid, context, rng):
        super().__init__(
            fight,
            packets,
            {
                "effects": {
                    str(family): dict(
                        runner="eWQ",
                        native_prototype_runner="eYP",
                        fixed_stat_id=stat,
                        percent_default=False,
                        zero_initial_amount_rejected=True,
                        limit_policy="NORMAL",
                    )
                    for family, stat in FAMILIES.items()
                }
            },
            action_id=action_id,
            allocate_uid=allocate_uid,
            context=context,
            rng=rng,
        )

    def native_current_stat_plan(self, effect, invocation, target, context):
        stat = FAMILIES.get(effect.get("effect_class"))
        if (
            stat is None
            or effect.get("parameter_count") != 0
            or not isinstance(effect.get("parameters"), (tuple, list))
            or len(effect["parameters"]) != 0
        ):
            raise ValueError(
                "Native eYP requires its original zero-parameter prototype"
            )
        from .combat_current_stat_consumer import _absent_area_characteristic

        if _absent_area_characteristic(self, target, stat):
            value = 0  # Original PV.a(PC)==false, then eWW.bbH rejects zero.
        else:
            from .combat_maximum_resource import _snapshot

            current, _, maximum, *_ = _snapshot(target, stat)
            value = resource_fill_amount(maximum, current)
        return dict(
            stat_id=stat, requested=value, percent=False, native_additional_requested=0
        )

    def cancel_prepared(self, invocation):
        self.prepared_current_stats.pop(invocation.native_running_uid, None)
        self.current_runner_amounts.pop(invocation.native_running_uid, None)
