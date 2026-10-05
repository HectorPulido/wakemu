"""Native eWQ/eWR runner lifecycle, independent of null400 and Qq effects."""
import json
from pathlib import Path
from dataclasses import replace
from .combat_stat_effects import (
    stat_parameters,
    current_stat_initial_eligible,
    apply_current_stat,
    owned_effect_payload,
    owned_effect_delivery,
)
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_value_transfer import apply_context_value

_EVENTS = json.loads(
    (
        Path(__file__).resolve().parents[2]
        / "protocol"
        / "native-current-stat-events.json"
    ).read_text()
)["effects"]


def _context(handler, effect, invocation):
    from .combat_stat_handler import StatExecutionContext

    target = handler.fight.actors.get(invocation.target_id)
    if (
        handler.fight.phase != "active"
        or handler.fight.current is None
        or target is None
        or target.hp <= 0
        or invocation.caster_id not in handler.fight.actors
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
    return target, context


def _events(handler, effect):
    row = _EVENTS.get(str(effect["effect_class"]))
    registry = handler.registry[str(effect["effect_class"])]
    if row is None or row["runner"] != registry["runner"]:
        raise ValueError("Missing original current-stat event prototype")
    masks = effect.get("target_masks")
    if not isinstance(masks, (list, tuple)) or len(masks) < 7:
        raise ValueError("Missing current-stat source event masks")
    return tuple(sorted({*row["events"], *(masks[6] or ())}))


def _calculate(handler, effect, invocation):
    target, context = _context(handler, effect, invocation)
    row = handler.registry[str(effect["effect_class"])]
    plan = stat_parameters(
        effect["parameters"],
        invocation.level,
        registered_stat_id=row["fixed_stat_id"],
        percent_default=row["percent_default"],
        trigger_value=context.trigger_value,
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
        handler.event_lifecycle.phase(
            effect,
            invocation,
            uid=uid,
            value=value,
            channel=2,
            _event_ids=_events(handler, effect),
            runner_modifier=runner,
        )
    target = handler.fight.actors[invocation.target_id]
    stat = plan["stat_id"]
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
    actual = result["actual"]
    if runner is not None:
        runner.set_applied(actual)
        # eWR.d: fc(0); zero actual with fMz=true suppresses PR, not Qe/PT.
        if (
            row["runner"] == "eWR"
            and actual == 0
            and row["zero_initial_amount_rejected"]
        ):
            runner.notification_suppressed = True
    status = 0 if row["runner"] == "eWR" else None

    def payload_for(value):
        return owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=target.id,
            value=value,
            stat_id=stat,
            requested=plan["requested"],
            timing_payload=context.timing_payload,
            execution_status=status,
        )

    payload = payload_for(actual)
    _write(handler.fight, invocation.caster_id, target, stat, result["current"])
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
    if runner is None or not runner.notification_suppressed:
        handler.packets.append(
            owned_effect_delivery(
                handler.fight.id,
                handler.action_id,
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
                _event_ids=_events(handler, effect),
                runner_modifier=runner,
            )
    final = actual if runner is None else runner.value
    if context.retained:
        entry = handler.fight.owned_stat_effects[uid]
        entry["actual"], entry["payload"] = final, payload_for(final).hex()
    from .combat_runner_callbacks import notify_runner_value

    notify_runner_value(invocation, final)
    return True
