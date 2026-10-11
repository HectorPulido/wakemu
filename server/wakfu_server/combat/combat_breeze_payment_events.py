"""Native fad post-events for already-paid Breeze receipts.

Wakemu policy places this native constructor lifecycle before spell roots;
the original server caller is unavailable. No second PA mutation occurs.
"""
from .combat_ordinary_events import OrdinaryHealingEvents


def valid_fad_source(source):
    return (
        isinstance(source, dict)
        and set(source)
        == {
            "runner_class",
            "runner_family",
            "stat_id",
            "requested_delta",
            "actual_delta",
            "spell_context",
            "payer_id",
            "caster_binding",
        }
        and source["runner_class"] == "fad"
        and source["runner_family"] == 1089
        and source["stat_id"] == 111
        and type(source["payer_id"]) is int
        and source["payer_id"] != 0
        and source["caster_binding"] == "wakemu.paid-caster-Qe.e-v1"
        and source["spell_context"] == {"present": False}
        and all(
            type(source[key]) is int and -(1 << 31) <= source[key] < (1 << 31)
            for key in ("requested_delta", "actual_delta")
        )
    )


def replay_paid_breeze_costs(dispatcher, plan):
    receipts = tuple(
        row for row in plan.get("extra_resource_payment", ()) if row["stat_id"] == 111
    )
    if not receipts:
        return
    factory = getattr(dispatcher, "native_breeze_payment_events_factory", None)
    if factory is None:
        raise ValueError("Missing native fad paid-resource event authority")
    from .combat_effect_dispatch import EffectInvocation

    events = factory()
    for receipt in receipts:
        # Fresh fad.b leaves bfr null. The explicit paid-cast caller binds
        # the actual payer with native Qe.e(PV) before native post-delivery.
        source = dict(
            runner_class="fad",
            runner_family=1089,
            stat_id=111,
            requested_delta=receipt["requested_delta"],
            actual_delta=receipt["actual_delta"],
            spell_context={"present": False},
            payer_id=plan["actor_id"],
            caster_binding="wakemu.paid-caster-Qe.e-v1",
        )
        if not valid_fad_source(source):
            raise ValueError("Invalid native fad payment receipt")
        invocation = EffectInvocation(
            -1,
            -1,
            plan["actor_id"],
            plan["actor_id"],
            (0, 0, 0),
            native_retained_container={"present": False},
        )
        # fad.mu(true) at zero suppresses PR notification, not Qe.a phases3/4.
        # This adapter emits no PR notification for either case.
        for channel in (3, 4):
            events.phase(
                dict(
                    effect_class=1089, native_effect_flags=[], native_fad_source=source
                ),
                invocation,
                uid=-1,
                value=source["requested_delta"],
                channel=channel,
                _event_ids=(0, 2246),
                _nullable_target=True,
                _execution_status=-1,
                _cost_source=source,
            )


class NativeBreezePaymentEvents(OrdinaryHealingEvents):
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
        if (
            effect.get("effect_class") != 1089
            or invocation.reference != -1
            or not valid_fad_source(effect.get("native_fad_source"))
        ):
            raise ValueError("Unverified native fad constructor")
        return {"event_suppresses_level_one": False}

    def identifiers(self, effect, invocation):
        self.definition(effect, invocation)
        return dict(
            native_container={"present": False},
            effect_action_id=None,
            effect_flags=None,
            native_definition_present=False,
            native_definition_variant=None,
        )
