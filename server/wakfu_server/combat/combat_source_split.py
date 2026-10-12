"""Native eZh401 splits the actual live source Qe, never a synthetic hit."""
from dataclasses import dataclass, replace
from copy import deepcopy
from wakfu_server.combat_parameters import parameter_value
from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount
from wakfu_server.combat_runner_target import NativeRunnerTarget, bind_runner_target
from wakfu_server.combat_execution_context import constructed_execution_context


def i32(value):
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


@dataclass(frozen=True)
class SplitPlan:
    action: str
    amount: int
    remainder: int


def split_plan(value, ratio, cap, *, source_family, target_current_hp=None):
    for operand in (value, ratio, cap, source_family):
        if type(operand) is not int or not -(1 << 31) <= operand < (1 << 31):
            raise ValueError("Actual signed native split operands required")
    if source_family == 28:
        return SplitPlan("failed", 0, value)
    product = i32(value * ratio)
    amount = abs(product) // 100 * (1 if product >= 0 else -1)
    if cap == -1 and target_current_hp is not None:
        if type(target_current_hp) is not int or not -(1 << 31) <= target_current_hp < (
            1 << 31
        ):
            raise ValueError("Actual target current HP authority required")
        cap = target_current_hp
    if cap > 0:
        amount = min(amount, cap)
    if amount == 0:
        return SplitPlan("failed", 0, value)
    if amount >= value:
        return SplitPlan("redirect", amount, value)
    return SplitPlan("clone", amount, i32(value - amount))


class CalculatedDamageCloneSource:
    """Actual source PK plus fresh allocated Qe identity for the existing gate."""

    def __init__(self, effect, invocation):
        self.original = deepcopy(effect)
        self.effect = deepcopy(effect)
        self.reference, self.level, self.uid = (
            invocation.reference,
            invocation.level,
            invocation.native_running_uid,
        )

    def verify(self, effect, invocation):
        if (
            effect != self.effect
            or invocation.reference != self.reference
            or invocation.level != self.level
            or invocation.native_running_uid != self.uid
        ):
            raise ValueError("Cloned calculated source PK/UID changed")


class PreparedCalculatedClone:
    def __init__(self, handler, effect, invocation, source):
        self.handler, self.effect, self.invocation, self.source = (
            handler,
            effect,
            invocation,
            source,
        )
        self.uid = invocation.native_running_uid
        self.used = False

    def execute(self):
        if self.used:
            raise ValueError("Calculated Qe clone was already consumed")
        self.used = True
        try:
            eligible = self.handler.calculated_clone_gate(self.source, self.invocation)
            if type(eligible) is not bool:
                raise ValueError("Actual clone bbH decision required")
            return self.handler(self.effect, {}, self.invocation) if eligible else False
        finally:
            for name in ("prepared", "runner_modifiers", "final_modifiers"):
                getattr(self.handler, name).pop(self.uid, None)


class NativeCalculatedDamageCloneAuthority:
    def __init__(
        self, handler, effect, invocation, context, interpreted, runner, modifier
    ):
        self.handler, self.effect, self.invocation = (
            handler,
            deepcopy(effect),
            invocation,
        )
        self.context, self.interpreted = deepcopy(context), deepcopy(interpreted)
        self.runner, self.modifier = runner, modifier

    def prepare(self, *, caster_id, target_id, amount):
        handler = self.handler
        runner = self.runner
        if (
            runner.uid != self.invocation.native_running_uid
            or runner.family != self.effect["effect_class"]
            or not callable(getattr(handler, "calculated_clone_gate", None))
        ):
            raise ValueError("Actual calculated source clone owner/gate changed")
        uid = handler.allocate_uid()
        if type(uid) is not int or not 0 < uid < (1 << 63) or uid == runner.uid:
            raise ValueError("Qe.bbm requires a fresh allocated native UID")
        context = replace(
            constructed_execution_context(),
            bypass_probability=True,
            bypass_criteria=True,
        )
        invocation = replace(
            self.invocation,
            native_running_uid=uid,
            base_uid=uid,
            caster_id=caster_id,
            target_id=target_id,
            native_context_hex=context.payload().hex(),
            native_trigger_context=None,
            native_value_scope=None,
            native_preselected_target=True,
        )
        clone = NativeRunnerAmount(uid, runner.family, rng=runner.rng, value=amount)
        clone.additional_mastery = runner.additional_mastery
        clone.additional_resistance = runner.additional_resistance
        bind_runner_target(clone, invocation)
        handler.prepared[uid] = (
            deepcopy(self.context),
            deepcopy(self.interpreted),
            amount,
        )
        handler.runner_modifiers[uid] = clone
        if self.modifier is not None:
            handler.final_modifiers[uid] = replace(self.modifier, uid=uid)
        source = CalculatedDamageCloneSource(self.effect, invocation)
        return PreparedCalculatedClone(handler, self.effect, invocation, source)


def bind_calculated_damage_clone(
    handler, effect, invocation, context, interpreted, runner, modifier=None
):
    """Called by the real eXt owner immediately before its native L2 delivery."""
    from wakfu_server.combat_damage_healing import DAMAGE_FAMILIES

    if (
        effect["effect_class"] not in DAMAGE_FAMILIES
        or not isinstance(runner, NativeRunnerAmount)
        or runner.uid != invocation.native_running_uid
        or runner.family != effect["effect_class"]
        or type(context.blocked) is not bool
        or interpreted.get("native_no_resources")
    ):
        raise ValueError("Unknown actual calculated eXt source clone contract")
    runner.native_calculated_clone = NativeCalculatedDamageCloneAuthority(
        handler, effect, invocation, context, interpreted, runner, modifier
    )


def split_actual_source(fight, invocation, ratio, cap, *, caster_code):
    from wakfu_server.combat_final_modifier import triggering_runner_source
    from wakfu_server.combat_event_replay import NativeEventSource
    from wakfu_server.combat_native_actor_lookup import native_actor
    from wakfu_server.combat_state_managers import registered_area_pv
    from wakfu_server.combat_native_events import subscription_actor_ids

    source = triggering_runner_source()
    if source is None:
        if invocation.native_trigger_context is not None:
            raise ValueError("Missing actual direct-trigger/PS.fLP source")
        return False
    if not isinstance(source, NativeEventSource):
        raise ValueError("Actual source Qe required")
    source.validate()
    if (
        invocation.native_trigger_context is not None
        and invocation.native_trigger_context.get("uid") != source.uid
    ):
        raise ValueError("Stale actual split source UID")
    runner = source.runner_modifier
    if (
        not isinstance(runner, NativeRunnerAmount)
        or runner.uid != source.uid
        or runner.family != source.effect_action_id
    ):
        raise ValueError("Missing actual source amount ownership")
    binding = getattr(runner, "native_target_binding", None)
    if (
        not isinstance(binding, NativeRunnerTarget)
        or binding.uid != runner.uid
        or binding.family != runner.family
    ):
        raise ValueError("Missing actual source target ownership")
    if invocation.caster_id is None or runner.family == 28:
        return False
    target = native_actor(fight, invocation.target_id)
    if target is None:
        target = registered_area_pv(fight, invocation.target_id)
        if target is None:
            raise ValueError("Missing actual split target PV")
        if cap == -1:
            raise ValueError("Area target current HP source is unaudited")
    plan = split_plan(
        runner.value,
        ratio,
        cap,
        source_family=runner.family,
        target_current_hp=getattr(target, "hp", None),
    )
    if plan.action == "failed":
        return False
    if plan.action == "redirect":
        binding.target_id = invocation.target_id
        return True
    if caster_code == 2:
        raise ValueError("Actual split listener manager PV binding required")
    caster, _ = subscription_actor_ids(
        target_code=0,
        caster_code=caster_code,
        original_caster=invocation.caster_id,
        original_target=invocation.target_id,
        manager_actor=None,
        source_caster=source.caster_id,
        source_target=source.target_id,
        source_present=True,
    )
    authority = getattr(runner, "native_calculated_clone", None)
    if (
        not isinstance(authority, NativeCalculatedDamageCloneAuthority)
        or authority.runner is not runner
    ):
        raise ValueError("Actual source subclass clone continuation is unaudited")
    if caster is None or (
        native_actor(fight, caster) is None
        and registered_area_pv(fight, caster) is None
    ):
        raise ValueError("Actual cloned source caster PV is absent")
    clone = authority.prepare(
        caster_id=caster, target_id=invocation.target_id, amount=plan.amount
    )
    runner.set_calculated(plan.remainder)
    clone.execute()
    return True


def calculated_source_clone_gate(*, native_eligibility):
    """Exact eZh-created PS: both PK criteria and probability are bypassed.

    Reuse the proven ordinary eXt bbH/baw/PB75 guard producer. Do not even
    construct a criterion context or sample probability for this native PS.
    """
    if not callable(native_eligibility):
        raise ValueError("Actual calculated clone PV guard producer required")

    def gate(source, invocation):
        from wakfu_server.combat_random_earth_damage import native_child_context

        source.verify(source.effect, invocation)
        if native_child_context(invocation) != (True, True, False):
            raise ValueError(
                "Calculated split clone PS differs from actual eVt.a(true,true,null)"
            )
        eligible = native_eligibility(source, invocation)
        if type(eligible) is not bool:
            raise ValueError("Actual calculated clone bbH result required")
        if not eligible:
            return False
        return (
            source.original["minimum_level"]
            <= invocation.level
            <= source.original["maximum_level"]
        )

    return gate
