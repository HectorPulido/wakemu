"""Synthetic eWf30 events reuse actual Qe local/global delivery machinery."""
from contextvars import ContextVar
from dataclasses import replace
from .combat_ordinary_events import OrdinaryHealingEvents

_payment = ContextVar("native_cost_payment", default=None)


class NativeCostPaymentEvents(OrdinaryHealingEvents):
    def __init__(self, *, adapter, preview, plan, replay, retention):
        def actual_cost_source(source, *, authority):
            costs = _payment.get()
            if costs is None:
                return replay(source, authority=authority)
            return replay(
                replace(
                    source,
                    cost_source={
                        "runner_class": "eWf",
                        "action_costs": dict(costs),
                        "spell_context": {"present": False},
                    },
                ),
                authority=authority,
            )

        super().__init__(
            adapter=adapter,
            preview=preview,
            plan=plan,
            replay=actual_cost_source,
            retention=retention,
        )

    @classmethod
    def from_healing(cls, source):
        return cls(
            adapter=source.adapter,
            preview=source.preview,
            plan=source.plan,
            replay=source.replay,
            retention=source.retention,
        )

    def definition(self, effect, invocation):
        if effect.get("effect_class") == 30 and invocation.reference == -1:
            return {"event_suppresses_level_one": False}
        definition = super().definition(effect, invocation)
        if effect.get("effect_class") == 923:
            return dict(definition, event_suppresses_level_one=True)
        return definition

    def identifiers(self, effect, invocation):
        if effect.get("effect_class") == 30 and invocation.reference == -1:
            return {
                "native_container": {"present": False},
                "effect_action_id": None,
                "effect_flags": None,
                "native_definition_present": False,
                "native_definition_variant": None,
            }
        return super().identifiers(effect, invocation)

    def phase(self, effect, invocation, **kwargs):
        if effect.get("effect_class") == 923:
            token = _payment.set(None)
            try:
                return super().phase(effect, invocation, **kwargs)
            finally:
                _payment.reset(token)
        costs = effect.get("native_costs")
        if (
            effect.get("effect_class") != 30
            or invocation.reference != -1
            or not isinstance(costs, dict)
            or set(costs) != {"ap", "mp", "wp"}
            or any(
                type(value) is not int or not -128 <= value <= 127
                for value in costs.values()
            )
        ):
            raise ValueError("Unverified native eWf action costs")
        token = _payment.set(costs)
        try:
            kwargs["_cost_source"] = {
                "runner_class": "eWf",
                "action_costs": dict(costs),
                "spell_context": {"present": False},
            }
            kwargs["_execution_status"] = -1
            return super().phase(effect, invocation, **kwargs)
        finally:
            _payment.reset(token)
