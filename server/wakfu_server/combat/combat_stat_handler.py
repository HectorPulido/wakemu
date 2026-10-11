"""Registry-driven eWQ/eWR current-characteristic and null400 handlers.

All callbacks and outboxes belong to a transaction preview. Native guards,
retention and timing are explicit; RESISTANCE_CAP uses the ordered owned stack.
Owned removal reverses actual clamped deltas, never requested amounts.
"""
from dataclasses import dataclass
from .combat_stat_effects import (
    stat_parameters,
    apply_current_stat,
    remove_current_stat,
    owned_effect_payload,
    evaluated_effect_delivery,
    current_stat_initial_eligible,
    null_execution_status,
)
from .combat_effect_removal import running_effect_removal
from .combat_summon_initialization import registered_or_detached_actor


@dataclass(frozen=True)
class StatExecutionContext:
    executable: bool
    source_guards_verified: bool
    trigger_value: int | None
    retained: bool
    timing_payload: bytes | None
    timer: object = None


def _current(actor, stat):
    if stat == 1:
        return actor.hp
    if stat == 2:
        return actor.ap
    if stat == 3:
        return actor.mp
    if not isinstance(actor.effect_stats, dict) or stat not in actor.effect_stats:
        raise ValueError("Missing authoritative current characteristic")
    return actor.effect_stats[stat]


def _bounds(actor, stat):
    if (
        not isinstance(actor.effect_minima, dict)
        or stat not in actor.effect_minima
        or not isinstance(actor.effect_maxima, dict)
        or stat not in actor.effect_maxima
        or actor.effect_frozen is None
    ):
        raise ValueError("Missing native characteristic bounds or mutability")
    maximum = {1: actor.max_hp, 2: actor.max_ap, 3: actor.max_mp}.get(
        stat, actor.effect_maxima[stat]
    )
    if maximum != actor.effect_maxima[stat]:
        raise ValueError("Native bounds disagree with authoritative resource maximum")
    return actor.effect_minima[stat], maximum


def _write(fight, source_id, actor, stat, value):
    if stat == 111:
        from .combat_hupper_resource_binding import set_current

        if set_current(actor, value):
            return
    if getattr(actor, "native_copy_pa_source", None) is not None:
        from .combat_copied_pa import set_copied_current

        set_copied_current(fight, actor, stat, value)
        return
    from .combat_hp_raw import hp_raw_present, set_hp_raw_current

    if stat == 1 and hp_raw_present(actor):
        set_hp_raw_current(actor, value)
        return
    if (
        stat in (2, 3)
        and getattr(actor, "effect_resource_raw_currents", None) is not None
    ):
        from .combat_resource_pa_notifications import set_resource_current

        set_resource_current(fight, actor, stat, value)
        return
    before_current = actor.ap if stat == 2 else None
    if stat == 1:
        before = actor.hp
        if value < before:
            fight.apply_effect_damage(source_id, actor.id, before - value)
        elif value > before:
            fight.apply_effect_healing(source_id, actor.id, value - before)
    elif stat == 2:
        actor.ap = value
    elif stat == 3:
        actor.mp = value
    if actor.effect_stats is not None:
        # Initiative35 is mirrored by Actor.initiative for snapshots and
        # checkpoints. Keep the already-built timeline untouched; changing a
        # characteristic is not a timeline-reordering operation.
        if stat == 35:
            actor.initiative = value
        actor.effect_stats[stat] = value
    from .combat_resource_pa_notifications import notify_resource_pa

    notify_resource_pa(fight, actor, stat, before_current=before_current)


class NativeStatHandler:
    native_runner_value_verified = True

    def __init__(
        self, fight, packets, registry, *, action_id, allocate_uid, context, rng=None
    ):
        self.fight, self.packets, self.registry = fight, packets, registry["effects"]
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )
        self.event_lifecycle = None
        self.area_events = None
        self.rng = rng
        self.prepared_current_stats = {}
        self.current_runner_amounts = {}

    def native_eligibility(self, effect, invocation):
        """eZR.i's known corpse rejection skips before PA calculation/UID."""
        target = registered_or_detached_actor(self.fight, invocation.target_id)
        if target is None or target.hp > 0:
            return True  # Null/Qq and actual actor guards remain with executor.
        from .combat_runner_target_life import runner_target_life_eligible

        return runner_target_life_eligible(
            self.fight, target, effect, invocation=invocation
        )

    def prepare(self, effect, values, invocation):
        from .combat_current_stat_consumer import prepare_current_stat

        return prepare_current_stat(self, effect, values, invocation)

    def __call__(self, effect, values, invocation):
        if not self.native_eligibility(effect, invocation):
            return False
        row = self.registry.get(str(effect["effect_class"]))
        if row is None:
            raise ValueError("Missing native current-stat registry entry")
        if row["runner"] in ("eWQ", "eWR"):
            from .combat_current_stat_consumer import apply_current_stat_runner

            return apply_current_stat_runner(self, effect, values, invocation)
        target = registered_or_detached_actor(self.fight, invocation.target_id)
        area_target = None
        source = registered_or_detached_actor(self.fight, invocation.caster_id)
        if source is None:
            from .combat_state_managers import registered_area_pv

            source = registered_area_pv(self.fight, invocation.caster_id)
        if target is None and row["runner"] == "eXE":
            from .combat_effect_area_targets import area_targets

            area_target = next(
                (
                    area
                    for area in area_targets(self.fight)
                    if area.id == invocation.target_id
                ),
                None,
            )
            target = area_target
        from .combat_npc_initialization import constructor_stat_context

        constructor = constructor_stat_context(self.fight, invocation)
        if (
            (
                not constructor
                and (self.fight.phase != "active" or self.fight.current is None)
            )
            or target is None
            or source is None
        ):
            raise ValueError("Invalid current-stat effect actors or fight")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
        ):
            raise ValueError("Unverified native current-stat guards")
        if type(context.executable) is not bool or type(context.retained) is not bool:
            raise ValueError("Unknown native effect execution or retention")
        if area_target is not None:
            # Qe registers on PV.bax only when that actual Qf exists. Most
            # HOURs, including1558, have null Qf; state PL does not fabricate it.
            area = self.fight.native_effect_areas[area_target.id]
            if area.get("native_running_effect_manager") is not True:
                from dataclasses import replace

                context = replace(context, retained=False)
            if self.area_events is None:
                raise ValueError("Native Qq null-effect source provider required")
        if not context.executable:
            return False
        if area_target is None:
            from .combat_runner_target_life import verify_runner_target_life

            verify_runner_target_life(self.fight, target, effect, invocation=invocation)
        stat = None
        actual = requested = 0
        after = None
        execution_status = None
        from .combat_value_transfer import apply_context_value

        value_context = (
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex)
        )
        if row["runner"] == "eXE":
            execution_status = null_execution_status(effect["parameters"])
            actual = apply_context_value(0, value_context)
        elif row["runner"] in ("eWQ", "eWR"):
            plan = stat_parameters(
                effect["parameters"],
                invocation.level,
                registered_stat_id=row["fixed_stat_id"],
                percent_default=row["percent_default"],
                trigger_value=context.trigger_value,
            )
            stat = plan["stat_id"]
            minimum, maximum = _bounds(target, stat)
            requested_for_apply = plan["requested"]
            if row["limit_policy"] == "RESISTANCE_CAP":
                if row["runner"] != "eWR":
                    raise ValueError("Invalid native resistance-cap family")
                from .combat_resistance_stack import capped_request, same_action_rows

                requested_for_apply = capped_request(
                    requested_for_apply,
                    same_action_rows(
                        self.fight.owned_stat_effects,
                        target_id=target.id,
                        effect_class=effect["effect_class"],
                    ),
                )
            # eZR.n invokes C (including the cap) before applying eVt value.
            # AdditionalDatas.Mt remains the original amount calculated by eWW.C.
            requested_for_apply = apply_context_value(
                requested_for_apply, value_context
            )
            if not current_stat_initial_eligible(
                requested_for_apply,
                zero_initial_amount_rejected=row["zero_initial_amount_rejected"],
            ):
                return False
            result = apply_current_stat(
                family=row["runner"],
                current=_current(target, stat),
                minimum=minimum,
                maximum=maximum,
                requested=requested_for_apply,
                percent=plan["percent"],
                executable=context.executable,
                frozen=stat in target.effect_frozen,
                source_guards_verified=context.source_guards_verified,
                limit_policy=(
                    "NORMAL"
                    if row["limit_policy"] == "RESISTANCE_CAP"
                    else row["limit_policy"]
                ),
            )
            # eWW.Mt remains the original prepercent, precap requested amount.
            result["requested"] = plan["requested"]
            if row["runner"] == "eWR":
                execution_status = 0  # eWR.d explicitly calls fc(0).
            actual, requested, after = (
                result["actual"],
                result["requested"],
                result["current"],
            )
        else:
            raise ValueError("Unsupported native characteristic runner")
        clone = invocation.native_running_uid is not None
        if clone and row["runner"] != "eXE":
            raise ValueError("Unaudited current-stat event clone runner")
        uid = invocation.native_running_uid if clone else self.allocate_uid()
        if area_target is not None:
            for channel in (1, 2):
                if self.event_lifecycle is not None:
                    self.event_lifecycle.phase(
                        effect,
                        invocation,
                        uid=uid,
                        value=actual,
                        channel=channel,
                        _event_ids=tuple(
                            sorted({0, *(effect["target_masks"][6] or ())})
                        ),
                    )
                else:
                    self.area_events.running_source(
                        effect, invocation, uid=uid, value=actual, channel=channel
                    )
        elif row["runner"] == "eXE" and self.event_lifecycle is not None:
            for channel in (1, 2):
                self.event_lifecycle.phase(
                    effect,
                    invocation,
                    uid=uid,
                    value=actual,
                    channel=channel,
                    _event_ids=tuple(sorted({0, *(effect["target_masks"][6] or ())})),
                )
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=target.id,
            value=actual,
            stat_id=stat,
            requested=requested if stat is not None else None,
            timing_payload=context.timing_payload,
            execution_status=execution_status,
        )
        if clone:
            from .combat_stat_effects import null_listener_clone_payload

            listener = self.fight.native_owned_group_effects.get(invocation.base_uid)
            if listener is None or listener["effect_class"] != 400:
                raise ValueError("Missing native null listener clone source")
            payload = null_listener_clone_payload(
                bytes.fromhex(listener["payload"]),
                uid=uid,
                base_uid=invocation.base_uid,
                execution_status=execution_status,
                caster_id=invocation.caster_id,
                target_id=target.id,
            )
        packet = evaluated_effect_delivery(
            self.fight.id,
            self.action_id,
            retained=context.retained,
            effect_class=effect["effect_class"],
            target_id=target.id,
            uid=uid,
            running_effect_payload=payload,
        )
        if stat is not None:
            _write(self.fight, invocation.caster_id, target, stat, after)
            self.fight._event(
                "characteristic_changed",
                source_id=invocation.caster_id,
                target_id=target.id,
                stat_id=stat,
                actual=actual,
                current=after,
            )
        if context.retained and not clone:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=target.id,
                caster_id=invocation.caster_id,
                effect_class=effect["effect_class"],
                family=row["runner"],
                stat_id=stat,
                actual=actual,
                execution_status=execution_status,
                limit_policy=row.get("limit_policy"),
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        self.packets.append(packet)
        if context.retained and not clone and self.event_lifecycle is not None:
            # Qf registration precedes post-application callbacks, which may
            # inspect/remove the complete retained population synchronously.
            register = getattr(self.event_lifecycle, "register_applied", None)
            if callable(register):
                register(effect, invocation, uid)
        if area_target is not None:
            for channel in (3, 4):
                if self.event_lifecycle is not None:
                    self.event_lifecycle.phase(
                        effect,
                        invocation,
                        uid=uid,
                        value=actual,
                        channel=channel,
                        _event_ids=tuple(
                            sorted({0, *(effect["target_masks"][6] or ())})
                        ),
                    )
                else:
                    self.area_events.running_source(
                        effect, invocation, uid=uid, value=actual, channel=channel
                    )
        elif row["runner"] == "eXE" and self.event_lifecycle is not None:
            for channel in (3, 4):
                self.event_lifecycle.phase(
                    effect,
                    invocation,
                    uid=uid,
                    value=actual,
                    channel=channel,
                    _event_ids=tuple(sorted({0, *(effect["target_masks"][6] or ())})),
                )
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, actual)
        return True  # Qe.a records an application even when the actual delta is zero.

    def remove(self, uid):
        entry = self.fight.owned_stat_effects.get(uid)
        if entry is None:
            raise ValueError("Missing owned current-stat effect")
        if entry.get("family") == "eWG":
            from .combat_morph_handler import remove_morph_effect

            return remove_morph_effect(self, uid)
        if entry.get("family") == "eWK":
            from .combat_redirect_runner import remove_redirect_runner

            return remove_redirect_runner(self, uid)
        if entry.get("family") == "eWs":
            from .combat_area_property import remove_area_property

            return remove_area_property(self, uid)
        if entry.get("family") == "eXc":
            from .combat_kill import remove_kill

            return remove_kill(self, uid)
        if entry.get("family") == "eXO":
            from .combat_current_hp_restore import remove_current_hp_restore

            return remove_current_hp_restore(self, uid)
        if entry.get("family") == "eYV":
            from .combat_affiliation_effect import remove_affiliation

            return remove_affiliation(self, uid)
        if entry.get("family") == "eWq":
            from .combat_ap_as_mp import remove_ap_as_mp

            return remove_ap_as_mp(self, uid)
        if entry.get("family") == "eZG":
            from .combat_protected_kill import remove_protected_kill

            return remove_protected_kill(self, uid)
        if entry.get("family") == "eWX":
            from .combat_set_current_characteristic import (
                remove_set_current_characteristic,
            )

            return remove_set_current_characteristic(self, uid)
        if entry.get("family") == "eYG":
            from .combat_capture_handler import remove_capture

            return remove_capture(self, uid)
        if entry.get("family") == "eZc":
            from .combat_reflect_runner import remove_reflect_runner

            return remove_reflect_runner(self, uid)
        if entry.get("family") == "eXZ":
            from .combat_fight_property_clear import remove_fight_property_clear

            return remove_fight_property_clear(self, uid)
        if entry.get("family") == "eZb":
            from .combat_disabled_spell_level import remove_disabled_spell_level

            return remove_disabled_spell_level(self, uid)
        if entry.get("family") == "eWE":
            from .combat_death_script import remove_death_script

            return remove_death_script(self, uid)
        if entry.get("family") == "eYH":
            from .combat_ai_control import remove_ai_control

            return remove_ai_control(self, uid)
        if entry.get("family") == "eYZ":
            from .combat_triggered_spell_handler import remove_triggered_spell

            return remove_triggered_spell(self, uid)
        if entry.get("family") == "eZF":
            from .combat_aura_removal import remove_aura_removal_runner

            return remove_aura_removal_runner(self, uid)
        if entry.get("family") == "eVZ":
            from .combat_resource_loss_handler import remove_owned_resource_loss

            return remove_owned_resource_loss(self, uid)
        if entry.get("family") == "eXA":
            from .combat_movement_link import remove_movement_link

            return remove_movement_link(self, uid)
        if entry.get("family") == "eWF":
            from .combat_orientation_effect import remove_orientation

            return remove_orientation(self, uid)
        if entry.get("family") == "eXf":
            from .combat_turn_suppression import remove_turn_suppression

            return remove_turn_suppression(self, uid)
        if entry.get("family") == "eWl":
            from .combat_additional_turn import remove_additional_turn

            return remove_additional_turn(self, uid)
        if entry.get("family") == "eWL":
            from .combat_turn_duration import remove_turn_duration

            return remove_turn_duration(self, uid)
        if entry.get("family") == "eWZ":
            from .combat_copy_characteristic import remove_copied_characteristic

            return remove_copied_characteristic(self, uid)
        if entry.get("family") == "eYO":
            from .combat_force_characteristic import remove_forced_characteristic

            return remove_forced_characteristic(self, uid)
        if entry.get("family") == "eWt":
            from .combat_fight_property import remove_fight_property

            return remove_fight_property(self, uid)
        if entry.get("family") == "eXG":
            from .combat_cell_null import remove_cell_null

            return remove_cell_null(self, uid)
        if entry.get("family") == "eWn":
            from .combat_spell_grant import remove_spell_grant

            return remove_spell_grant(self, uid)
        if entry.get("family") == "eWV":
            from .combat_minimum_resource import remove_minimum_resource

            return remove_minimum_resource(self, uid)
        if entry.get("family") == "eWU":
            from .combat_parameter_maximum import remove_parameter_maximum

            return remove_parameter_maximum(self, uid)
        if entry.get("family") == "eZI":
            from .combat_maximum_resource import remove_percentage_hp

            return remove_percentage_hp(self, uid)
        if entry.get("family") == "eWO":
            from .combat_maximum_resource import remove_maximum_reduction

            return remove_maximum_reduction(self, uid)
        if entry.get("family") == "eWh":
            from .combat_characteristic_link import remove_characteristic_link

            return remove_characteristic_link(self, uid)
        if entry.get("family") == "eWN":
            from .combat_maximum_resource import remove_maximum_resource

            return remove_maximum_resource(self, uid)
        if entry.get("family") in ("eZe", "eZg"):
            from .combat_spell_cost_effect import remove_spell_cost

            return remove_spell_cost(self, uid)
        actor = registered_or_detached_actor(self.fight, entry["target_id"])
        if actor is None and entry.get("family") == "eXE":
            from .combat_state_managers import state_manager

            actor = state_manager(self.fight, entry["target_id"])
        if actor is None:
            raise ValueError("Missing native effect owner")
        stat = entry["stat_id"]
        after = None
        stack_updates = []
        if stat is not None:
            minimum, maximum = _bounds(actor, stat)
            after = remove_current_stat(
                family=entry["family"],
                current=_current(actor, stat),
                minimum=minimum,
                maximum=maximum,
                actual=entry["actual"],
                frozen=stat in actor.effect_frozen,
                limit_policy=(
                    "NORMAL"
                    if entry["limit_policy"] == "RESISTANCE_CAP"
                    else entry["limit_policy"]
                ),
            )
            if entry["limit_policy"] == "RESISTANCE_CAP":
                if entry["family"] != "eWR":
                    raise ValueError("Invalid native resistance-cap removal family")
                from .combat_resistance_stack import refill, same_action_rows

                after, stack_updates = refill(
                    after,
                    minimum,
                    maximum,
                    stat in actor.effect_frozen,
                    same_action_rows(
                        self.fight.owned_stat_effects,
                        target_id=actor.id,
                        effect_class=entry["effect_class"],
                        excluding_uid=uid,
                    ),
                )
        packet = running_effect_removal(
            self.fight.id,
            self.action_id,
            effect_class=entry["effect_class"],
            target_id=actor.id,
            uid=uid,
            running_effect_payload=bytes.fromhex(entry["payload"]),
        )
        if stat is not None:
            if getattr(actor, "native_copy_pa_source", None) is not None:
                from .combat_copied_pa import copied_shift_result

                after, _, _ = copied_shift_result(
                    actor, stat, entry["actual"], subtract=entry["family"] == "eWQ"
                )
            elif (
                stat in (2, 3)
                and getattr(actor, "effect_resource_raw_currents", None) is not None
            ):
                from .combat_resource_pa_notifications import resource_shift_result

                after, _, _ = resource_shift_result(
                    actor, stat, entry["actual"], subtract=entry["family"] == "eWQ"
                )
            elif stat == 1:
                from .combat_hp_raw import hp_raw_present, hp_shift_result

                if hp_raw_present(actor):
                    after, _, _ = hp_shift_result(
                        actor, entry["actual"], subtract=entry["family"] == "eWQ"
                    )
            _write(self.fight, entry["caster_id"], actor, stat, after)
        for other_uid, new_actual, new_payload in stack_updates:
            owned = self.fight.owned_stat_effects[other_uid]
            owned["actual"] = new_actual
            owned["payload"] = new_payload.hex()
        del self.fight.owned_stat_effects[uid]
        self.packets.append((13560, packet))
