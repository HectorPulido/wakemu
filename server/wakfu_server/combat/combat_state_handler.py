"""Native apply-state304 -> owned carrier310 and nested effects.

Use only on a spell transaction preview. Clock/flags must come from an audited
runtime context, not a guessed duration. The ledger retains subscribed roots
for later event delivery; this handler executes only immediate roots.
"""
from .combat_state_managers import state_manager
from dataclasses import dataclass, replace
from contextlib import nullcontext
import math
from .combat_state_carrier import (
    state_carrier_payload,
    state_carrier_application,
    STATE_CARRIER_APPLICATION_OPCODE,
)
from .combat_effect_removal import running_effect_removal
from .combat_effect_dispatch import UnsupportedEffectExecution
from .combat_state_parameters import interpret_state_parameters
from .combat_state_parameters import native_float_parameter, _float32
from .combat_parameters import _integer
from .combat_subscription_runners import SUBSCRIPTION_FAMILIES


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
        rng=None,
        state_spell_level=None,
        state_random=None,
    ):
        self.fight, self.packets, self.catalog = fight, packets, catalog
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.execute_child = context, execute_child
        self.remove_child_effect = remove_child_effect
        self.register_subscription = register_subscription
        self.applied_state_scope = applied_state_scope
        self.rng = rng
        self.state_spell_level = state_spell_level
        self.state_random = state_random
        self.event_lifecycle = None
        self.prepared_runners = {}
        self.prepared_parameters = {}
        self.prepared_rejections = set()

    def _parameters(
        self, effect, values, invocation, *, allow_signed_calculation=False
    ):
        raw = values["parameters"]
        if not isinstance(raw, (list, tuple)) or (
            len(raw) not in (3, 4, 5) and len(raw) < 6
        ):
            raise UnsupportedEffectExecution(
                "Unsupported native state applicator parameter mode"
            )
        owned_level = level_factor = None
        if len(raw) in (4, 5):
            if not callable(self.state_spell_level):
                raise UnsupportedEffectExecution(
                    "Dynamic eWu level requires native caster spellbook authority"
                )
            try:
                owned_level = self.state_spell_level(effect, invocation, raw[3])
            except (KeyError, TypeError, ValueError) as error:
                raise UnsupportedEffectExecution(str(error)) from error
            if owned_level is not None and len(raw) == 5:
                from .combat_state_parameters import native_float_parameter

                level_factor = native_float_parameter(
                    effect["parameters"], 4, invocation.level
                )
        return interpret_state_parameters(
            raw,
            owned_spell_level=owned_level,
            level_factor=level_factor,
            allow_signed_calculation=allow_signed_calculation,
        )

    def _application_chance(self, effect, values, invocation, parameters):
        raw_chance = parameters["chance_parameter"]
        chance = raw_chance
        if len(values["parameters"]) >= 6:
            from .combat_state_managers import state_manager

            target = state_manager(self.fight, invocation.target_id)
            if target is not None:
                entries = getattr(
                    getattr(target, "state_ledger", None), "entries", None
                )
                if entries is None:
                    raise UnsupportedEffectExecution(
                        "Missing native eWu target state manager entries"
                    )
                state_reference = values["parameters"][3]
                existing = next(
                    (entry for entry in entries if entry.reference == state_reference),
                    None,
                )
                allow_absent = values["parameters"][4] == 1
                if existing is None:
                    if not allow_absent:
                        chance = -2
                elif raw_chance != -1:
                    factor = native_float_parameter(
                        effect["parameters"], 5, invocation.level
                    )
                    product = _float32(_float32(factor) * _float32(existing.level))
                    change = (
                        _integer(math.floor(product + 0.5))
                        if math.isfinite(product)
                        else _integer(product)
                    )
                    chance += change

        if chance == -1:
            return True
        if chance != -2:
            from .combat_state_resistance_metadata import (
                native_state_absence_proven,
                native_state_resistance_mode,
            )

            # eWu.fNa returns zero for an original null fyZ.aax lookup.
            # Keep the ordinary zero-chance draw below; do not fabricate a mode.
            native_missing = native_state_absence_proven(parameters["reference"])
            mode = (
                None
                if native_missing
                else native_state_resistance_mode(parameters["reference"])
            )
            if native_missing:
                chance = 0
            if not native_missing and (
                not isinstance(mode, dict) or mode.get("enum_class") != "fza"
            ):
                raise UnsupportedEffectExecution(
                    "Missing native eWu state resistance mode"
                )
            if not native_missing and not (
                mode.get("name") == "POSITIF" and mode.get("ordinal") == 2
            ):
                caster = self.fight.actors.get(invocation.caster_id)
                target = self.fight.actors.get(invocation.target_id)
                caster_stats = getattr(caster, "effect_stats", None)
                target_stats = getattr(target, "effect_stats", None)
                if not isinstance(caster_stats, dict) or not isinstance(
                    target_stats, dict
                ):
                    raise UnsupportedEffectExecution(
                        "State chance requires native caster and target characteristics"
                    )
                modifier = _float32(0.0)
                if 78 in target_stats:
                    if type(target_stats[78]) is not int:
                        raise UnsupportedEffectExecution(
                            "Invalid native target state resistance"
                        )
                    modifier = _float32(modifier - _float32(target_stats[78]))
                if 77 in caster_stats:
                    if type(caster_stats[77]) is not int:
                        raise UnsupportedEffectExecution(
                            "Invalid native caster state application bonus"
                        )
                    modifier = _float32(modifier + _float32(caster_stats[77]))
                adjusted = _float32(
                    _float32(_float32(chance) * modifier) / _float32(100.0)
                )
                adjustment = _integer(
                    math.trunc(adjusted) if math.isfinite(adjusted) else adjusted
                )
                chance = ((chance + adjustment + (1 << 31)) % (1 << 32)) - (1 << 31)
            chance = max(0, min(100, chance))

        if chance == -2:
            chance = 0
        if chance >= 100:
            return True
        if not callable(self.state_random):
            raise UnsupportedEffectExecution(
                "State chance requires native transaction random authority"
            )
        draw = self.state_random(100)
        if type(draw) is not int or not 0 <= draw < 100:
            raise UnsupportedEffectExecution("Invalid native state chance draw")
        return chance >= draw

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            # eWu inherits Qe.bbw: fresh bfA includes0, plus PK.aZO.
            masks = effect.get("target_masks")
            if masks is None or len(masks) != 7:
                raise ValueError("Missing native eWu produced event masks")
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                runner_modifier=runner,
                _event_ids=tuple(sorted({0, *(masks[6] or ())})),
            )

    def prepare(self, effect, values, invocation):
        if self.event_lifecycle is None:
            return invocation
        if not self.native_eligibility(effect, invocation):
            self.prepared_rejections.add(id(invocation))
            return invocation
        # Qe.d(Collection) emits L1 before eWu.c checks PV.bax for null.
        # Leave the null-Qf rejection to __call__, which also releases this
        # prepared runner before L2 or carrier application.
        if self._area_target_blocked(effect, invocation):
            self.prepared_rejections.add(id(invocation))
            return invocation
        # Native eWu.C computes a signed short before Qe evaluates criteria.
        # Application retains its strict level validation in __call__.
        parameters = self._parameters(
            effect, values, invocation, allow_signed_calculation=True
        )
        if not self._application_chance(effect, values, invocation, parameters):
            self.prepared_rejections.add(id(invocation))
            return invocation
        from .combat_state_runner import NativeRunnerStateLevel

        runner = NativeRunnerStateLevel(self.allocate_uid(), rng=self.rng)
        invocation = replace(invocation, native_running_uid=runner.uid)
        # Ordinary Qe.d(Collection): L1 precedes C and its level reseeding.
        self._phase(effect, invocation, runner, 1)
        runner.seed(parameters["reference"], parameters["level"])
        from .combat_value_transfer import apply_context_value

        runner.set_calculated(
            apply_context_value(
                0,
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
        )
        self.prepared_runners[runner.uid] = runner
        self.prepared_parameters[runner.uid] = parameters
        return invocation

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

    def _null_qf_target(self, invocation):
        if invocation.target_id is None or invocation.target_id in self.fight.actors:
            return False
        from .combat_state_managers import registered_area_pv

        area = registered_area_pv(self.fight, invocation.target_id)
        return area is not None and area.native_running_effect_manager is False

    def native_eligibility(self, effect, invocation):
        """Run eZR.bcd before Qe runner preparation for HP0 state targets."""
        if effect.get("effect_class") != 304:
            return True
        target = self.fight.actors.get(invocation.target_id)
        if target is None or target.hp > 0:
            return True
        from .combat_runner_target_life import runner_target_life_eligible

        return runner_target_life_eligible(
            self.fight, target, effect, invocation=invocation
        )

    def _area_target_blocked(self, effect, invocation):
        if invocation.target_id is None or invocation.target_id in self.fight.actors:
            return False
        from .combat_area_authority import area_guards
        from .combat_ordinary_death import corpse_gate_bypassed

        return area_guards(self.fight, invocation.target_id)[
            "baK"
        ] and not corpse_gate_bypassed(effect, fight=self.fight, invocation=invocation)

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 304:
            raise UnsupportedEffectExecution(
                "Unsupported native state applicator parameters"
            )
        try:
            if id(invocation) in self.prepared_rejections:
                self.prepared_rejections.remove(id(invocation))
                return False
            parameters = self._parameters(effect, values, invocation)
        except ValueError as error:
            raise UnsupportedEffectExecution(str(error)) from error
        if not self.native_eligibility(effect, invocation):
            return False
        runner = None
        if self.event_lifecycle is not None:
            if invocation.native_running_uid is not None:
                runner = self.prepared_runners.pop(invocation.native_running_uid, None)
                if runner is None:
                    raise ValueError("Missing prepared native eWu applicator")
                parameters = self.prepared_parameters.pop(
                    invocation.native_running_uid, None
                )
                if parameters is None:
                    raise ValueError("Missing prepared native eWu parameters")
            else:
                if not self._application_chance(effect, values, invocation, parameters):
                    return False
                # Qe.k replay: C precedes L1/L2; mutations now survive.
                from .combat_state_runner import NativeRunnerStateLevel

                runner = NativeRunnerStateLevel(
                    self.allocate_uid(),
                    rng=self.rng,
                    reference=parameters["reference"],
                    level=parameters["level"],
                )
                from .combat_value_transfer import apply_context_value

                runner.set_calculated(
                    apply_context_value(
                        0,
                        None
                        if invocation.native_context_hex is None
                        else bytes.fromhex(invocation.native_context_hex),
                    )
                )
                self._phase(effect, invocation, runner, 1)
            if self._null_qf_target(invocation):
                return False  # eWu.bbH rejects before L2 and carrier application.
            if self._area_target_blocked(effect, invocation):
                return False
            self._phase(effect, invocation, runner, 2)
            if self._area_target_blocked(effect, invocation):
                return False  # Qe.bbJ checks baK again after L2 callbacks.
        elif self._null_qf_target(invocation):
            return False
        elif self._area_target_blocked(effect, invocation):
            return False
        elif not self._application_chance(effect, values, invocation, parameters):
            return False
        result = self.apply_reference(
            effect,
            invocation,
            parameters["reference"] if runner is None else runner.reference,
            parameters["level"] if runner is None else runner.pending_level,
        )
        if runner is not None:
            runner.finish_application()
            self._phase(effect, invocation, runner, 3)
            self._phase(effect, invocation, runner, 4)
            from .combat_runner_callbacks import notify_runner_value

            notify_runner_value(invocation, runner.value)
        return result

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
        if str(reference) not in self.catalog["states"]:
            from .combat_state_resistance_metadata import native_state_absence_proven

            if native_state_absence_proven(reference):
                # eZk.a/fRb returns null; eWu.D returns before allocating or
                # registering a carrier. Unattested missing data still fails.
                return False
        context = (
            self.context(effect, invocation)
            if carrier_context is None
            else carrier_context
        )
        if not isinstance(context, StateCarrierContext):
            raise ValueError("Missing audited native state carrier context")
        native_corpse_target = False
        target = self.fight.actors.get(invocation.target_id)
        if target is not None and target.hp <= 0:
            from .combat_runner_target_life import runner_target_life_eligible

            if not runner_target_life_eligible(
                self.fight, target, effect, invocation=invocation
            ):
                return False
            native_corpse_target = True

        def before_replace(old):
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
            target_manager = state_manager(self.fight, old.target_id)
            if (
                target_manager is None
                or target_manager.state_ledger.remove(old.uid) is None
            ):
                raise UnsupportedEffectExecution("Missing actual replaced carrier")
            del self.fight.state_wire_payloads[old.uid]

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
            native_corpse_target=native_corpse_target,
            before_replace=before_replace,
        )
        entry = change.applied
        if entry is None:
            return False
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
            self.packets.append((STATE_CARRIER_APPLICATION_OPCODE, packet))
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
                # Removal-only masks (index2) still execute at installation.
                if any(masks[index] for index in (0, 1, 3, 4, 5)):
                    # eZk.c constructs subscribed children with its actual fyW
                    # PL even when the state carrier's own Ty() is false.
                    # Each child independently proves its native Qf retention.
                    if self.register_subscription is not None:
                        if child["effect_class"] not in SUBSCRIPTION_FAMILIES:
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
                                cell=state_manager(
                                    self.fight, entry.target_id
                                ).position,
                                base_uid=None,
                                native_running_uid=None,
                                state_uid=uid,
                                native_context_hex="0801100020ffffffffffffffffff0128013000380040004800",
                                native_value_scope=None,
                                native_explicit_target=False,
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
                        cell=state_manager(self.fight, entry.target_id).position,
                        base_uid=None,
                        native_running_uid=None,
                        state_uid=uid,
                        native_context_hex="0801100020ffffffffffffffffff0128013000380040004800"
                        if self.register_subscription is not None
                        else invocation.native_context_hex,
                        native_value_scope=None
                        if self.register_subscription is not None
                        else invocation.native_value_scope,
                        native_explicit_target=False,
                        # eZk.bbA is true: c(Qe,boolean) calls child.g(bfs)
                        # before bal(), including empty-area graphical roots.
                        native_preselected_target=True,
                        wakemu_fresh_child_selection=False,
                    )
                )
        return True
