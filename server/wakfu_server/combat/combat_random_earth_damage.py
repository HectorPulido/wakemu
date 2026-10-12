"""Native proven AIR/EARTH eXP adapters sharing the initialized damage seam."""
from dataclasses import replace
from copy import deepcopy
from wakfu_server.combat_parameters import parameter_value
from wakfu_server.combat_property_stack import property_present
from wakfu_server.combat_random_child_level import random_child_level
from wakfu_server.combat_trigger_value_modifier import NativeRunnerAmount
from wakfu_server.combat_runner_target import (
    bind_runner_target,
    runner_target_invocation,
)
from wakfu_server.combat_value_transfer import apply_context_value


_SEAL = object()

# Installed eXP: AIR635 constructs eXt5; EARTH636 constructs eXt3.
_NATIVE_CHILD_FAMILIES = {635: 5, 636: 3}


class InitializedEarthChild:
    """Bound original PK plus the actual separately allocated eXt identity."""

    @classmethod
    def from_parent(cls, effect, invocation, *, uid, runner):
        if (
            effect.get("effect_class") not in _NATIVE_CHILD_FAMILIES
            or type(uid) is not int
            or uid <= 0
            or not isinstance(runner, NativeRunnerAmount)
            or runner.family != effect.get("effect_class")
            or runner.owner != "Qe"
            or runner.uid != invocation.native_running_uid
            or uid == runner.uid
        ):
            raise ValueError("Actual native eXP elemental child construction required")
        result = object.__new__(cls)
        result._seal = _SEAL
        result.original = deepcopy(effect)
        result.reference, result.level = invocation.reference, invocation.level
        result.uid, result.amount = uid, runner.value
        result.effect = dict(
            effect, effect_class=_NATIVE_CHILD_FAMILIES[effect["effect_class"]]
        )
        return result

    def verify(self, effect, invocation):
        if (
            getattr(self, "_seal", None) is not _SEAL
            or effect != self.effect
            or invocation.reference != self.reference
            or invocation.level != self.level
            or invocation.native_running_uid != self.uid
        ):
            raise ValueError(
                "Initialized eXt source differs from actual eXP construction"
            )

    def definition(self, retention, effect, invocation):
        self.verify(effect, invocation)
        return retention.definition(self.original, invocation)

    def identifiers(self, retention, effect, invocation):
        from wakfu_server.combat_trigger_identifiers import source_identifiers

        self.definition(retention, effect, invocation)
        result = source_identifiers(retention, self.original, invocation)
        result["effect_action_id"] = self.effect[
            "effect_class"
        ]  # eLK reads child baZ, not original PK ID.
        return result


def initialized_handler_type(damage_handler_type):
    class InitializedEarthDamageHandler(damage_handler_type):
        initialized_source = None

        def _damage_parameters(self, effect, invocation, **kwargs):
            self.initialized_source.verify(effect, invocation)
            return {"base": self.initialized_source.amount, "coefficient_mask": 3}

        def _context_amount(self, amount, invocation):
            # eXP applies inherited PN forcing to parent sampled base. Its
            # child calls fOC directly, skipping eXt.n and its second forcing.
            return amount

    return InitializedEarthDamageHandler


def child_events(source, events):
    """Keep actual definition verification while exposing the actual elemental child family."""
    cls = type(events)

    class InitializedChildEvents(cls):
        def definition(self, effect, invocation):
            return source.definition(self.retention, effect, invocation)

        def identifiers(self, effect, invocation):
            return source.identifiers(self.retention, effect, invocation)

    result = InitializedChildEvents.__new__(InitializedChildEvents)
    result.__dict__.update(events.__dict__)
    return result


class NativeRandomEarthDamageHandler:
    """eXP parent runner, separately initialized real eXt damage child."""

    native_runner_value_verified = True

    def __init__(
        self,
        *,
        fight,
        allocate_uid,
        rng,
        actor_authority,
        child_factory,
        parent_context,
        child_execution_gate,
        parent_events=None,
        damage_events=None
    ):
        self.fight, self.allocate_uid, self.rng = fight, allocate_uid, rng
        self.actor_authority, self.child_factory = actor_authority, child_factory
        self.parent_context = parent_context
        if not callable(child_execution_gate):
            raise ValueError("Actual initialized child bbH gate required")
        self.child_execution_gate = child_execution_gate
        self.parent_events, self.damage_events = parent_events, damage_events
        self.prepared = {}

    def phase(self, effect, invocation, runner, channel):
        if self.parent_events is not None:
            masks = effect["target_masks"]
            self.parent_events.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                _event_ids=tuple(sorted({0, *(masks[6] or ())})),
                runner_modifier=runner,
                _nullable_target=True,
            )

    def prepare(self, effect, values, invocation):
        from wakfu_server.combat_native_actor_lookup import native_actor

        if (
            effect.get("effect_class") not in _NATIVE_CHILD_FAMILIES
            or len(effect["parameters"]) != 4
        ):
            raise ValueError(
                "Native eXP proven elemental two-operand definition required"
            )
        if self.parent_events is None or self.damage_events is None:
            raise ValueError("Actual native random damage lifecycle required")
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, effect["effect_class"], rng=self.rng)
        bind_runner_target(runner, invocation)
        self.prepared[uid] = runner
        try:
            self.phase(effect, invocation, runner, 1)
            invocation = runner_target_invocation(runner, invocation)
            caster = native_actor(self.fight, invocation.caster_id)
            if caster is None:
                raise ValueError("Actual native eXP caster required")
            provider = getattr(self.actor_authority, "property_counts", None)
            if not callable(provider):
                raise ValueError("Registered eXP PB counter authority required")
            counts = provider(self.fight, caster)
            minimum, maximum = [
                parameter_value(effect["parameters"], i, invocation.level)
                for i in (0, 1)
            ]
            if property_present(counts, 106):
                amount = minimum
            elif property_present(counts, 107):
                amount = maximum
            else:
                amount = random_child_level([minimum, maximum], self.rng)
            runner.set_calculated(
                apply_context_value(
                    amount,
                    None
                    if invocation.native_context_hex is None
                    else bytes.fromhex(invocation.native_context_hex),
                )
            )
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)

    def __call__(self, effect, values, invocation):
        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        runner = self.prepared.get(invocation.native_running_uid)
        if runner is None:
            raise ValueError("Actual prepared native eXP runner required")
        try:
            from wakfu_server.combat_stat_handler import StatExecutionContext

            context = self.parent_context(effect, invocation)
            if (
                not isinstance(context, StatExecutionContext)
                or context.source_guards_verified is not True
            ):
                raise ValueError("Verified native eXP execution context required")
            if not context.executable or native_child_context(invocation)[2]:
                return False
            self.phase(effect, invocation, runner, 2)
            invocation = runner_target_invocation(runner, invocation)
            child_uid = self.allocate_uid()
            child_invocation = replace(invocation, native_running_uid=child_uid)
            source = InitializedEarthChild.from_parent(
                effect, invocation, uid=child_uid, runner=runner
            )
            child = self.child_factory(source)
            child.initialized_source = source
            child.event_lifecycle = (
                None
                if self.damage_events is None
                else child_events(source, self.damage_events)
            )
            # Native child eXt.b binds original PK/PL and initialized base,
            # then L1/fOC precede bbL/bbJ. The shared handler owns those phases.
            child_invocation = child.prepare(source.effect, {}, child_invocation)
            if child_invocation.native_running_uid != child_uid:
                raise ValueError("Initialized child UID changed during preparation")
            executable = self.child_execution_gate(source, child_invocation)
            if type(executable) is not bool:
                raise ValueError("Verified initialized child bbH gate result required")
            if executable:
                child(source.effect, {}, child_invocation)
            else:
                child.prepared.pop(child_uid, None)
                child.final_modifiers.pop(child_uid, None)
                child.runner_modifiers.pop(child_uid, None)
            runner.notification_suppressed = True
            runner.finish_application()
            self.phase(effect, invocation, runner, 3)
            self.phase(effect, invocation, runner, 4)
            from wakfu_server.combat_runner_callbacks import notify_runner_value

            notify_runner_value(invocation, runner.value)
            return True
        finally:
            self.cancel_prepared(invocation)


def dispatcher_child_gate(dispatcher, *, native_eligibility):
    """Use original PK criteria/probability after the child's real fOC stage.

    The caller supplies actual child bbH recipient/context eligibility; do not
    derive baw, cancellation or blocked PN authority from an HP comparison.
    """
    if not callable(native_eligibility):
        raise ValueError("Actual initialized-child eligibility callback required")

    def gate(source, invocation):
        from wakfu_server.combat_conditions import evaluate_condition
        from wakfu_server.combat_definitions import effect_profile

        source.verify(source.effect, invocation)
        eligible = native_eligibility(source, invocation)
        if type(eligible) is not bool:
            raise ValueError("Actual initialized-child eligibility result required")
        if not eligible:
            return False
        effect = source.original
        if not effect["minimum_level"] <= invocation.level <= effect["maximum_level"]:
            return False
        activation = dispatcher._active_activation
        # Child bbJ calls I(null), not clone I(triggering source). Keep
        # original PK/PL while clearing only that criterion source argument.
        condition = dispatcher.condition_context(
            replace(invocation, native_trigger_context=None)
        )
        bypass_probability, bypass_criteria, cancelled = native_child_context(
            invocation
        )
        if not bypass_criteria and not evaluate_condition(
            effect["criteria"], condition
        ):
            return False
        if cancelled:
            return False
        if bypass_probability:
            return True
        retention = dispatcher.group_retention
        if (
            activation is None
            and retention is not None
            and retention.probability_bypassed(invocation)
        ):
            return True
        values = effect_profile(effect, invocation.level)
        accepted = dispatcher.probability_accepts(values["probability"], invocation)
        if type(accepted) is not bool:
            raise ValueError("Actual initialized-child probability decision required")
        return accepted

    return gate


def native_child_context(invocation):
    """Read the actual serialized eVt flags used by eZR.bbH, not HP guesses."""
    if invocation.native_context_hex is None:
        return False, False, False
    from wakfu_server.wire import proto_fields

    fields = {}
    for tag, value in proto_fields(bytes.fromhex(invocation.native_context_hex)):
        field, wire = tag >> 3, tag & 7
        if field in fields:
            raise ValueError("Duplicate native initialized-child context field")
        fields[field] = (wire, value)
    for field in (1, 2, 5, 7, 8):
        if field in fields and (
            fields[field][0] != 0 or fields[field][1] not in (0, 1)
        ):
            raise ValueError("Invalid native initialized-child context boolean")
    # eVt.fLN/ryl -> ir.Od/field1; fLO/rym -> Of/field2;
    # bbI/rys -> Op/field8. eVt.fLV and ir.writeTo prove these mappings.
    return tuple(bool(fields.get(field, (0, 0))[1]) for field in (1, 2, 8))


def ordinary_child_eligibility(
    target_context, *, fight, actor_authority, retention, special_state_container=None
):
    """Actual eGj.baw is constant true, after registered type validation.

    eXt.bcd bypasses the corpse gate; eXt.fNd delegates to eZR.fSb,
    which checks PB75 except an actual SPECIAL fyW state container.
    Other PV classes must provide their own installed baw contract.
    """
    if not callable(target_context):
        raise ValueError("Registered initialized-child PV authority required")

    def eligible(source, invocation):
        source.verify(source.effect, invocation)
        if invocation.target_id is None:
            return True  # eZR.bbH tests baw only for a non-null target.
        contexts = target_context(source.original, invocation)
        target = contexts.get(invocation.target_id)
        if not isinstance(target, dict) or target.get("is_eGj") is not True:
            raise ValueError("Missing installed initialized-child PV.baw authority")
        from wakfu_server.combat_native_actor_lookup import native_actor

        actor = native_actor(fight, invocation.target_id)
        counts = actor_authority.property_counts(fight, actor)
        if not property_present(counts, 75):
            return True
        container, _ = retention.container(invocation)
        if container.get("container_type") != 1:
            return False
        if not callable(special_state_container):
            raise ValueError("Actual fyW SPECIAL state category authority required")
        special = special_state_container(invocation)
        if type(special) is not bool:
            raise ValueError("Verified fyW SPECIAL state category required")
        return special

    return eligible
