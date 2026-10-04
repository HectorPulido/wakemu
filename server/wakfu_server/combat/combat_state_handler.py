"""Native apply-state304 -> owned carrier310 and nested effects.

Use only on a spell transaction preview. Clock/flags must come from an audited
runtime context, not a guessed duration. The ledger retains subscribed roots
for later event delivery; this handler executes only immediate roots.
"""
from dataclasses import dataclass, replace
from contextlib import nullcontext
from .combat_state_carrier import state_carrier_payload, state_carrier_application
from .combat_effect_removal import running_effect_removal
from .combat_effect_dispatch import UnsupportedEffectExecution
from .combat_state_parameters import interpret_state_parameters


@dataclass(frozen=True)
class StateCarrierContext:
    native_turn_clock: int
    native_realtime_remaining: int
    applying_effect_has_delay: bool
    timeline: object
    parent_uid: int | None
    critical: bool
    flag17: bool
    flag18: bool
    related_uid: int
    timing_payload: bytes | None


class NativeStateHandler:
    def __init__(
        self,
        fight,
        packets,
        catalog,
        *,
        action_id,
        allocate_uid,
        context,
        execute_child,
        remove_child_effect=None,
        register_subscription=None,
        applied_state_scope=None,
    ):
        self.fight, self.packets, self.catalog = fight, packets, catalog
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.execute_child = context, execute_child
        self.remove_child_effect = remove_child_effect
        self.register_subscription = register_subscription
        self.applied_state_scope = applied_state_scope

    def remove_state_children(self, state_uid):
        """Undo retained current-stat effects before their owned carrier.

        Bind remove_child_effect to NativeStatHandler.remove on this same
        transaction preview. Ownership uses the carrier UID, not the state ID,
        parent applicator UID or caster; multiple instances remain distinct.
        """
        if type(state_uid) is not int or not 0 < state_uid < (1 << 63):
            raise UnsupportedEffectExecution(
                "Missing owned state carrier UID for child removal"
            )
        children = tuple(
            uid
            for uid, child in self.fight.owned_stat_effects.items()
            if child.get("state_uid") == state_uid
        )
        if not children:
            return
        if not callable(self.remove_child_effect):
            raise UnsupportedEffectExecution(
                "Retained state children require an explicit removal callback"
            )
        owner = getattr(self.remove_child_effect, "__self__", None)
        if owner is not None and getattr(owner, "fight", self.fight) is not self.fight:
            raise UnsupportedEffectExecution(
                "State child removal callback belongs to another fight preview"
            )
        for uid in children:
            self.remove_child_effect(uid)
            if uid in self.fight.owned_stat_effects:
                raise UnsupportedEffectExecution(
                    "State child removal callback did not remove the owned effect"
                )

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 304:
            raise UnsupportedEffectExecution(
                "Unsupported native state applicator parameters"
            )
        try:
            parameters = interpret_state_parameters(values["parameters"])
        except ValueError as error:
            raise UnsupportedEffectExecution(str(error)) from error
        return self.apply_reference(
            effect, invocation, parameters["reference"], parameters["level"]
        )

    def apply_reference(
        self,
        effect,
        invocation,
        reference,
        level,
        *,
        carrier_context=None,
        protected=None,
    ):
        """Apply a native carrier from an already interpreted reference/level.

        304's separate chance gate belongs to its parameter interpreter;321
        reapplication has no invented304 parameters and uses its own context.
        """
        context = (
            self.context(effect, invocation)
            if carrier_context is None
            else carrier_context
        )
        if not isinstance(context, StateCarrierContext):
            raise ValueError("Missing audited native state carrier context")
        uid = self.allocate_uid()
        change = self.fight.apply_state(
            invocation.caster_id,
            invocation.target_id,
            reference,
            level,
            uid=uid,
            catalog=self.catalog,
            applying_effect_has_delay=context.applying_effect_has_delay,
            timeline=context.timeline,
            protected=protected,
        )
        entry = change.applied
        if entry is None:
            return False
        for old in change.removed:
            original = self.fight.state_wire_payloads.get(old.uid)
            if original is None:
                raise UnsupportedEffectExecution(
                    "Missing owned payload for replaced state"
                )
            packet = running_effect_removal(
                self.fight.id,
                self.action_id,
                effect_class=310,
                target_id=old.target_id,
                uid=old.uid,
                running_effect_payload=bytes.fromhex(original),
            )
            self.remove_state_children(old.uid)
            self.packets.append((13560, packet))
            del self.fight.state_wire_payloads[old.uid]
        if entry.retained:
            payload = state_carrier_payload(
                uid=uid,
                base_uid=context.parent_uid,
                caster_id=entry.caster_id,
                target_id=entry.target_id,
                state_id=entry.reference,
                level=entry.level,
                native_turn_clock=context.native_turn_clock,
                native_realtime_remaining=context.native_realtime_remaining,
                critical=context.critical,
                flag17=context.flag17,
                flag18=context.flag18,
                related_uid=context.related_uid,
                timing_payload=context.timing_payload,
            )
            packet = state_carrier_application(
                self.fight.id,
                self.action_id,
                uid=uid,
                target_id=entry.target_id,
                running_effect_payload=payload,
            )
            self.fight.state_wire_payloads[uid] = payload.hex()
            self.packets.append((13497, packet))
        scope = (
            nullcontext()
            if self.applied_state_scope is None
            else self.applied_state_scope(entry)
        )
        with scope:
            for child_id in entry.effect_ids:
                child = self.catalog["effects"][str(child_id)]
                masks = child.get("target_masks")
                if masks is None or len(masks) != 7:
                    raise UnsupportedEffectExecution(
                        "Missing nested state's native trigger masks"
                    )
                if any(masks[:6]):
                    if not entry.retained:
                        raise UnsupportedEffectExecution(
                            "Instant state cannot retain event subscriptions"
                        )
                    if self.register_subscription is not None:
                        if child["effect_class"] not in (
                            330,
                            400,
                            844,
                            910,
                            912,
                            913,
                            999,
                            1020,
                            1047,
                        ):
                            error = UnsupportedEffectExecution(
                                f"Subscribed state child family {child['effect_class']} reference {child_id} has no central registration machinery"
                            )
                            error.audit_reference = child_id
                            error.audit_level = entry.level
                            raise error
                        self.register_subscription(
                            replace(
                                invocation,
                                reference=child_id,
                                level=entry.level,
                                caster_id=entry.caster_id,
                                target_id=entry.target_id,
                                cell=self.fight.actors[entry.target_id].position,
                                base_uid=None,
                                state_uid=uid,
                                native_context_hex="0801100020ffffffffffffffffff0128013000380040004800",
                            )
                        )
                    continue  # Unbound legacy paths retain subscriptions only in ledger.effect_ids.
                self.execute_child(
                    replace(
                        invocation,
                        reference=child_id,
                        level=entry.level,
                        caster_id=entry.caster_id,
                        target_id=entry.target_id,
                        cell=self.fight.actors[entry.target_id].position,
                        base_uid=None,
                        state_uid=uid,
                        native_context_hex="0801100020ffffffffffffffffff0128013000380040004800"
                        if self.register_subscription is not None
                        else invocation.native_context_hex,
                    )
                )
        return True
