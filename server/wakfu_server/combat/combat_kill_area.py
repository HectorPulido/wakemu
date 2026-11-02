"""Native eXc HP assignment on verified Qq, without invented fighter PCs."""
from .combat_caster_hp_maximum import hp_operand


def operand(fight, identity):
    row = getattr(fight, "native_effect_areas", {}).get(identity)
    if row is None or row.get("native_area_contract") not in ("faW", "fbd"):
        return None
    result = hp_operand(fight, identity)
    if result is None:
        return None
    # The audited wall/faW constructors provide HP but no KO_TIME PA. Future
    # dynamic PC populations must qualify their own setters before admission.
    if row["native_area_contract"] == "faW":
        from .combat_fake_fighter import verified_fake_fighter

        if (
            14
            in verified_fake_fighter(row, result["area"]["definition"])[
                "characteristic_ids"
            ]
        ):
            raise ValueError("Native eXc area KO characteristic is not audited")
    return result


def apply(handler, effect, invocation, context, uid, runner, suppress):
    if context.retained:
        raise ValueError("Retained native HP-area eXc authority is not audited")
    state = operand(handler.fight, invocation.target_id)
    if state is None:
        raise ValueError("Changed native eXc HP-area authority")
    lifecycle = handler.event_lifecycle
    areas = getattr(getattr(lifecycle, "retention", None), "area_events", None)
    row = state["area"]["row"]
    contract = row["native_area_contract"]
    death = getattr(
        areas, "fake_fighter_death" if contract == "faW" else "wall_death", None
    )
    if not callable(death) or (
        contract == "faW" and not callable(getattr(lifecycle, "area_death", None))
    ):
        raise ValueError("Missing native eXc HP-area death producer")
    from .combat_area_hp_pa import set_area_hp_current
    from .combat_stat_effects import owned_effect_payload, owned_effect_application
    from .combat_observation_delivery import evaluated_application_from_observation

    before = state["current"]
    payload = owned_effect_payload(
        uid=uid,
        base_uid=invocation.base_uid,
        generic_effect=invocation.reference,
        caster_id=invocation.caster_id,
        target_id=invocation.target_id,
        value=0,
        timing_payload=context.timing_payload,
        execution_status=0,
        executed=True,
    )
    packet = owned_effect_application(
        handler.fight.id,
        handler.action_id,
        effect_class=28,
        target_id=invocation.target_id,
        uid=uid,
        running_effect_payload=payload,
    )
    hp_state = {
        key: value for key, value in state.items() if key not in ("area", "current_key")
    }
    updated = set_area_hp_current(row, hp_state, state["minimum"], state["current_key"])
    if suppress:
        from .combat_area_property import add_kill_suppression_property

        add_kill_suppression_property(row, state["area"]["definition"])
    handler.packets.append(
        (12613, evaluated_application_from_observation(packet, execute=True))
    )
    if runner is not None:
        runner.finish_application()
    if before > 0 and updated["current"] == 0:
        if contract == "faW":
            death(
                row,
                invocation.caster_id,
                death_delivery=lambda: lifecycle.area_death(
                    invocation.target_id,
                    effect=effect,
                    invocation=invocation,
                    uid=uid,
                    value=0,
                ),
            )
        else:
            death(row, invocation.caster_id)
    if lifecycle is not None:
        for channel in (3, 4):
            lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=0,
                channel=channel,
                _event_ids=handler._events(effect),
                runner_modifier=runner,
            )
    from .combat_runner_callbacks import notify_runner_value

    notify_runner_value(invocation, 0)
    return True
