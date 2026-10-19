"""Native eXD.q: explicit synthetic eVI runner, shared eVZ execution."""
from dataclasses import replace
from .combat_effect_dispatch import EffectInvocation
from .combat_resource_loss import collision_ap_packet


class NativeCollisionResourceExecutor:
    """Call inside the same private displacement transaction.

    The supplied handler must carry collision-specific null-PL timing and
    native runtime event2254 authority. Missing AP is a proven native skip,
    while missing characteristic-presence authority is an error.
    """

    def __init__(self, handler, definition, *, characteristic_present):
        if (
            definition.get("native_definition_class") != "eVI"
            or definition.get("reference") != -13
            or definition.get("effect_class") != 55
            or definition.get("parameters") != [1.0, 0.0]
            or definition.get("native_effect_flags") != []
            or definition.get("target_masks") != [None] * 7
            or not callable(characteristic_present)
        ):
            raise ValueError("Missing native synthetic collision definition")
        if handler.delivery is None or handler.event_lifecycle is None:
            raise ValueError("Missing native collision delivery/lifecycle authority")
        self.handler, self.definition = handler, dict(definition)
        self.characteristic_present = characteristic_present

    def delivery(self, effect, invocation, uid, amount, context):
        if invocation.reference != -13 or effect != self.definition:
            raise ValueError("Invalid synthetic collision delivery identity")
        return collision_ap_packet(
            self.handler.fight.id,
            self.handler.action_id,
            uid=uid,
            caster_id=invocation.caster_id,
            target_id=invocation.target_id,
            amount=amount,
            base_uid=0,
            timing_payload=context.timing_payload,
        )

    def __call__(self, caster_id, recipient_id):
        fight = self.handler.fight
        recipient = fight.actors.get(recipient_id)
        if recipient is None:
            from .combat_state_managers import registered_area_pv

            recipient = registered_area_pv(fight, recipient_id)
        if recipient is None or caster_id not in fight.actors:
            raise ValueError("Missing actual native collision PV")
        present = self.characteristic_present(recipient, 2)
        if type(present) is not bool:
            raise ValueError("Unknown native collision AP presence")
        if not present:
            return False
        if getattr(recipient, "native_is_area", False):
            raise ValueError(
                "Native collision area AP requires actual resource authority"
            )
        invocation = EffectInvocation(
            -13,
            0,
            caster_id,
            recipient_id,
            tuple(recipient.position),
            base_uid=0,
            native_retained_container={"present": False},
            native_explicit_target=True,
        )
        # Direct collision execution bypasses the ordinary dispatcher gate.
        # A native corpse rejection must not masquerade as a prepared runner.
        if not self.handler.native_eligibility(self.definition, invocation):
            return False
        invocation = replace(invocation, native_running_uid=self.handler.allocate_uid())
        values = {}
        try:
            selected = self.handler.prepare(self.definition, values, invocation)
            return self.handler(self.definition, values, selected)
        finally:
            # q(PV).bal releases this fresh runner even on an early guard exit.
            self.handler.prepared.pop(invocation.native_running_uid, None)
            self.handler.runner_amounts.pop(invocation.native_running_uid, None)
