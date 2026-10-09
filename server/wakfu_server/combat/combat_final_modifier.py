"""eZJ1093 and faq.SX over an execution-local source runner, never actor stats."""
from wakfu_server import native_catalog as protocol_catalog
import json
from pathlib import Path
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from .combat_parameters import parameter_value
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_stat_handler import StatExecutionContext

# Exported from every eVi prototype implementing faq, including inherited
# interfaces. Membership describes source identity, not handler availability.
_catalog = protocol_catalog.load(
    Path(__file__).resolve().parents[2]
    / "protocol"
    / "native-final-modifier-families.json"
)
FAQ_FAMILIES = frozenset(int(key) for key in _catalog["families"])
del _catalog
_source = ContextVar("native_final_modifier_source", default=None)


def _i32(value):
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


@dataclass
class NativeFinalModifier:
    uid: int
    family: int
    value: int = 0

    def validate(self):
        if (
            type(self.uid) is not int
            or not 0 < self.uid < 1 << 63
            or type(self.family) is not int
            or self.family not in FAQ_FAMILIES
            or type(self.value) is not int
            or not -(1 << 31) <= self.value < 1 << 31
        ):
            raise ValueError("Missing native faq running-effect accumulator")

    def add(self, value):
        self.validate()
        if type(value) is not int or not -(1 << 31) <= value < 1 << 31:
            raise ValueError("Invalid native faq modifier")
        self.value = _i32(self.value + value)
        return self.value


@contextmanager
def final_modifier_source(source):
    token = _source.set(source)
    try:
        yield
    finally:
        _source.reset(token)


def triggering_runner_source():
    """Actual scoped triggering Qe; shared identity for separate mutation contracts."""
    return _source.get()


def update_triggering_final(invocation, value):
    """eZJ.c: null/non-faq source has no modifier; stale faq source rejects."""
    if invocation.native_trigger_context is None:
        return False
    source = _source.get()
    if source is None or source.uid != invocation.native_trigger_context.get("uid"):
        raise ValueError("Missing live native triggering runner for final modifier")
    if type(source.effect_action_id) is not int:
        raise ValueError("Missing native triggering runner family")
    if source.effect_action_id not in FAQ_FAMILIES:
        return False
    modifier = source.final_modifier
    if not isinstance(modifier, NativeFinalModifier):
        raise ValueError("Missing exact native faq source accumulator")
    modifier.validate()
    if modifier.uid != source.uid or modifier.family != source.effect_action_id:
        raise ValueError("Native faq source accumulator identity mismatch")
    modifier.add(value)
    return True


class NativeFinalModifierHandler:
    def __init__(self, fight, packets, *, action_id, allocate_uid, context):
        self.fight, self.packets, self.action_id = fight, packets, action_id
        self.allocate_uid, self.context = allocate_uid, context

    def __call__(self, effect, values, invocation):
        from .combat_native_actor_lookup import native_actor
        from .combat_state_managers import registered_area_pv

        def actual_pv(identity):
            return native_actor(self.fight, identity) or registered_area_pv(
                self.fight, identity
            )

        if (
            effect["effect_class"] != 1093
            or self.fight.phase != "active"
            or actual_pv(invocation.caster_id) is None
            or actual_pv(invocation.target_id) is None
        ):
            raise ValueError("Native eZJ requires owned native PVs")
        if set(effect["native_effect_flags"]) - {1, 3, 14, 16, 17, 26}:
            raise ValueError("Unaudited native eZJ flags")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Missing native eZJ execution/timing authority")
        if not context.executable:
            return False
        if context.retained:
            from .combat_state_managers import state_manager

            if state_manager(self.fight, invocation.target_id) is None:
                raise ValueError("Retained native eZJ requires actual target Qf")
        # eZJ.c changes only its source faq.SX accumulator. A real area PV
        # is a valid selected target and does not need actor characteristics.
        value = parameter_value(effect["parameters"], 0, invocation.level)
        update_triggering_final(invocation, value)
        uid = invocation.native_running_uid or self.allocate_uid()
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=invocation.target_id,
            value=value,
            timing_payload=context.timing_payload,
        )
        if context.retained and invocation.native_running_uid is None:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=invocation.target_id,
                caster_id=invocation.caster_id,
                effect_class=1093,
                family="eZJ",
                stat_id=None,
                actual=value,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        self.packets.append(
            (
                13497,
                owned_effect_application(
                    self.fight.id,
                    self.action_id,
                    effect_class=1093,
                    target_id=invocation.target_id,
                    uid=uid,
                    running_effect_payload=payload,
                ),
            )
        )
        return True
