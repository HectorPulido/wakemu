"""Native eWQ/eWR runner lifecycle, independent of null400 and Qq effects."""
from wakfu_server import native_catalog as protocol_catalog
import json
from pathlib import Path
from dataclasses import replace
from .combat_stat_effects import (
    stat_parameters,
    current_stat_initial_eligible,
    apply_current_stat,
    owned_effect_payload,
    evaluated_effect_delivery,
)
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_value_transfer import apply_context_value
from .combat_summon_initialization import registered_or_detached_actor

_EVENTS = protocol_catalog.load(
    Path(__file__).resolve().parents[2] / "protocol" / "native-current-stat-events.json"
)["effects"]


def _target_pv(handler, identity):
    target = registered_or_detached_actor(handler.fight, identity)
    if target is None:
        from .combat_state_managers import registered_area_pv

        target = registered_area_pv(handler.fight, identity)
    return target


def _absent_area_characteristic(handler, target, stat):
    if not getattr(target, "native_is_area", False):
        return False
    from .combat_maximum_resource import _reduction_area_lacks_characteristic

    return _reduction_area_lacks_characteristic(handler.fight, target.id, stat)


def _context(handler, effect, invocation):
    from .combat_stat_handler import StatExecutionContext

    target = _target_pv(handler, invocation.target_id)
    source = registered_or_detached_actor(handler.fight, invocation.caster_id)
    if source is None:
        from .combat_state_managers import registered_area_pv

        source = registered_area_pv(handler.fight, invocation.caster_id)
    from .combat_npc_initialization import constructor_stat_context

    constructor = constructor_stat_context(handler.fight, invocation)
    if (
        (
            not constructor
            and (handler.fight.phase != "active" or handler.fight.current is None)
        )
        or target is None
        or source is None
    ):
        raise ValueError("Invalid current-stat effect actors or fight")
    context = handler.context(effect, invocation)
    if (
        not isinstance(context, StatExecutionContext)
        or context.source_guards_verified is not True
        or type(context.executable) is not bool
        or type(context.retained) is not bool
    ):
        raise ValueError("Unverified native current-stat guards")
    if (
        getattr(target, "native_is_area", False)
        and target.native_running_effect_manager is not True
    ):
        # An actual null-Qf PV executes without registering an owned Qe.
        context = replace(context, retained=False)
    if context.executable and not getattr(target, "native_is_area", False):
        from .combat_runner_target_life import verify_runner_target_life

        verify_runner_target_life(handler.fight, target, effect, invocation=invocation)
    return target, context


def _events(handler, effect, *, invocation=None, plan=None):
    row = _EVENTS.get(str(effect["effect_class"]))
    registry = handler.registry[str(effect["effect_class"])]
    if row is None or row["runner"] != registry.get(
        "native_prototype_runner", registry["runner"]
    ):
        raise ValueError("Missing original current-stat event prototype")
    masks = effect.get("target_masks")
    if not isinstance(masks, (list, tuple)) or len(masks) < 7:
        raise ValueError("Missing current-stat source event masks")
    events = {*row["events"], *(masks[6] or ())}
    if plan is not None and effect["effect_class"] == 40:
        from .combat_dynamic_current_loss_events import resolved_current_loss_events

        target = _target_pv(handler, invocation.target_id)
        stat = plan["stat_id"]
        present = (
            target is not None
            and not _absent_area_characteristic(handler, target, stat)
            and all(
                isinstance(getattr(target, name, None), dict)
                and type(getattr(target, name).get(stat)) is int
                for name in ("effect_stats", "effect_minima", "effect_maxima")
            )
        )
        events.update(
            resolved_current_loss_events(
                effect,
                registry,
                level=invocation.level,
                stat_id=stat,
                target_has_characteristic=present,
            )
        )
    return tuple(sorted(events))


def _calculate(handler, effect, invocation):
    target, context = _context(handler, effect, invocation)
    row = handler.registry[str(effect["effect_class"])]
    planner = getattr(handler, "native_current_stat_plan", None)
    plan = (
        planner(effect, invocation, target, context)
        if callable(planner)
        else stat_parameters(
            effect["parameters"],
            invocation.level,
            registered_stat_id=row["fixed_stat_id"],
            percent_default=row["percent_default"],
            trigger_value=context.trigger_value,
        )
    )
    value = plan["requested"]
    if row["limit_policy"] == "RESISTANCE_CAP":
        if row["runner"] != "eWR":
            raise ValueError("Invalid native resistance-cap family")
        from .combat_resistance_stack import capped_request, same_action_rows

        value = capped_request(
            value,
            same_action_rows(
                handler.fight.owned_stat_effects,
                target_id=target.id,
                effect_class=effect["effect_class"],
            ),
        )
    value = apply_context_value(
        value,
        None
        if invocation.native_context_hex is None
        else bytes.fromhex(invocation.native_context_hex),
    )
    return context, plan, value


def prepare_current_stat(handler, effect, values, invocation):
    if handler.event_lifecycle is None:
        return invocation
    _context(handler, effect, invocation)
    uid = handler.allocate_uid()
    invocation = replace(invocation, native_running_uid=uid)
    runner = NativeRunnerAmount(uid, effect["effect_class"], rng=handler.rng)
    handler.current_runner_amounts[uid] = runner
    handler.event_lifecycle.phase(
        effect,
        invocation,
        uid=uid,
        value=0,
        channel=1,
        _event_ids=_events(handler, effect),
        runner_modifier=runner,
    )
    calculated = _calculate(handler, effect, invocation)
    handler.prepared_current_stats[uid] = calculated
    runner.set_calculated(calculated[2])
    return invocation


def apply_current_stat_runner(handler, effect, values, invocation):
    from .combat_stat_handler import _current, _bounds, _write

    row = handler.registry[str(effect["effect_class"])]
    uid = invocation.native_running_uid
    if uid is None:
        context, plan, value = _calculate(handler, effect, invocation)
    else:
        if uid not in handler.prepared_current_stats:
            raise ValueError("Missing prepared native current-stat runner")
        context, plan, value = handler.prepared_current_stats.pop(uid)
    runner = handler.current_runner_amounts.pop(uid, None)
    if not context.executable or not current_stat_initial_eligible(
        value, zero_initial_amount_rejected=row["zero_initial_amount_rejected"]
    ):
        return False
    uid = uid or handler.allocate_uid()
    if runner is None and handler.event_lifecycle is not None:
        runner = NativeRunnerAmount(
            uid, effect["effect_class"], rng=handler.rng, value=value
        )
    if handler.event_lifecycle is not None:
        # The reconstructed eWR(PC) source binds its actual PC once after C.
        # Later listener callbacks cannot rewrite that running source's events.
        event_ids = _events(handler, effect, invocation=invocation, plan=plan)
        handler.event_lifecycle.phase(
            effect,
            invocation,
            uid=uid,
            value=value,
            channel=2,
            _event_ids=event_ids,
            runner_modifier=runner,
        )
    target = _target_pv(handler, invocation.target_id)
    if target is None:
        raise ValueError("Missing current-stat target after native L2 callbacks")
    stat = plan["stat_id"]
    absent_area_pa = _absent_area_characteristic(handler, target, stat)
    if absent_area_pa:
        # eWW.c: PV.a(PC)==false calls mu(true), preserving calculated aSg.
        # No PA mutation, percentage conversion, fc(0), or PR is performed.
        result = {"actual": value if runner is None else runner.value}
    else:
        minimum, maximum = _bounds(target, stat)
        result = apply_current_stat(
            family=row["runner"],
            current=_current(target, stat),
            minimum=minimum,
            maximum=maximum,
            requested=value if runner is None else runner.value,
            percent=plan["percent"],
            executable=True,
            frozen=stat in target.effect_frozen,
            source_guards_verified=True,
            limit_policy="NORMAL"
            if row["limit_policy"] == "RESISTANCE_CAP"
            else row["limit_policy"],
        )
        if getattr(target, "native_copy_pa_source", None) is not None:
            from .combat_copied_pa import copied_current_stat_result

            result = copied_current_stat_result(
                target,
                stat,
                value if runner is None else runner.value,
                family=row["runner"],
                percent=plan["percent"],
            )
        elif (
            stat in (2, 3)
            and getattr(target, "effect_resource_raw_currents", None) is not None
        ):
            from .combat_resource_pa_notifications import resource_shift_result
            import math
            from wakfu_server.equipment_damage import _float

            requested = value if runner is None else runner.value
            amount = (
                math.trunc(
                    _float(
                        _float(_float(_current(target, stat)) / _float(100))
                        * _float(requested)
                    )
                )
                if plan["percent"]
                else requested
            )
            raw, current, actual = resource_shift_result(
                target, stat, amount, subtract=row["runner"] == "eWR"
            )
            result.update(raw_current=raw, current=current, actual=actual)
        elif stat == 1:
            from .combat_hp_raw import hp_raw_present, hp_shift_result

            if hp_raw_present(target):
                import math
                from wakfu_server.equipment_damage import _float

                requested = value if runner is None else runner.value
                amount = (
                    math.trunc(
                        _float(
                            _float(_float(target.hp) / _float(100)) * _float(requested)
                        )
                    )
                    if plan["percent"]
                    else requested
                )
                raw, current, actual = hp_shift_result(
                    target, amount, subtract=row["runner"] == "eWR"
                )
                result.update(raw_current=raw, current=current, actual=actual)
    actual = result["actual"]
    if runner is not None:
        runner.set_applied(actual)
        if absent_area_pa:
            runner.notification_suppressed = True
        # eWR.d: fc(0); zero actual with fMz=true suppresses PR, not Qe/PT.
        if (
            row["runner"] == "eWR"
            and actual == 0
            and row["zero_initial_amount_rejected"]
        ):
            runner.notification_suppressed = True
    status = 0 if row["runner"] == "eWR" and not absent_area_pa else None

    def payload_for(value):
        return owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=target.id,
            value=value,
            stat_id=stat,
            requested=plan.get("native_additional_requested", plan["requested"]),
            timing_payload=context.timing_payload,
            execution_status=status,
        )

    payload = payload_for(actual)
    if not absent_area_pa:
        _write(
            handler.fight,
            invocation.caster_id,
            target,
            stat,
            result.get("raw_current", result["current"]),
        )
        handler.fight._event(
            "characteristic_changed",
            source_id=invocation.caster_id,
            target_id=target.id,
            stat_id=stat,
            actual=actual,
            current=result["current"],
        )
    if context.retained:
        handler.fight.owned_stat_effects[uid] = dict(
            uid=uid,
            target_id=target.id,
            caster_id=invocation.caster_id,
            effect_class=effect["effect_class"],
            family=row["runner"],
            stat_id=stat,
            actual=actual,
            execution_status=status,
            limit_policy=row.get("limit_policy"),
            payload=payload.hex(),
            state_uid=invocation.state_uid,
            timer=None if context.timer is None else dict(vars(context.timer)),
        )
    if context.retained and absent_area_pa:
        handler.fight.owned_stat_effects[uid]["native_absent_characteristic"] = True
    if not absent_area_pa and (runner is None or not runner.notification_suppressed):
        handler.packets.append(
            evaluated_effect_delivery(
                handler.fight.id,
                handler.action_id,
                retained=context.retained,
                effect_class=effect["effect_class"],
                target_id=target.id,
                uid=uid,
                running_effect_payload=payload,
            )
        )
    if context.retained and handler.event_lifecycle is not None:
        register = getattr(handler.event_lifecycle, "register_applied", None)
        if callable(register):
            register(effect, invocation, uid)
    if runner is not None:
        runner.finish_application()
    if handler.event_lifecycle is not None:
        for channel in (3, 4):
            handler.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=actual if runner is None else runner.value,
                channel=channel,
                _event_ids=event_ids,
                runner_modifier=runner,
            )
    final = actual if runner is None else runner.value
    if context.retained:
        # L3/L4 listeners may remove this source Qe while it is notifying them.
        # Complete the live callback without recreating its released Qf entry.
        entry = handler.fight.owned_stat_effects.get(uid)
        if entry is not None:
            entry["actual"], entry["payload"] = final, payload_for(final).hex()
    from .combat_runner_callbacks import notify_runner_value

    notify_runner_value(invocation, final)
    return True


def remove_absent_current_stat(handler, uid):
    """eWW.bbR skips PA restoration for an actual PV lacking this PC."""
    from .combat_effect_removal import running_effect_removal

    entry = handler.fight.owned_stat_effects[uid]
    if (
        entry.get("family") not in ("eWQ", "eWR")
        or entry.get("native_absent_characteristic") is not True
    ):
        raise ValueError("Missing native absent-PA current-stat receipt")
    target = _target_pv(handler, entry["target_id"])
    if target is None or not _absent_area_characteristic(
        handler, target, entry["stat_id"]
    ):
        raise ValueError("Missing native absent-PA current-stat owner")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=entry["effect_class"],
        target_id=target.id,
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
