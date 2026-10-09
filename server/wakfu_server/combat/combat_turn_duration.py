"""Native eWL668 marker; explicit Wakemu previous-granted-duration policy."""
POLICY = "wakemu.previous-granted-turn-duration-v1"


def duration_add_previous(parameters):
    if not isinstance(parameters, (list, tuple)) or any(
        type(v) is not int for v in parameters
    ):
        raise ValueError("Missing native evaluated eWL parameters")
    return len(parameters) == 1 and parameters[0] == 1


def turn_duration_policy(base, previous, *, add_previous):
    if (
        type(base) is not int
        or base <= 0
        or base >= 2**63
        or (
            previous is not None
            and (type(previous) is not int or previous <= 0 or previous >= 2**63)
        )
        or type(add_previous) is not bool
    ):
        raise ValueError("Missing authoritative granted turn duration")
    result = base if previous is None else base + previous if add_previous else previous
    if result >= 2**63:
        raise ValueError("Turn duration exhausted native signed-long range")
    return result


def current_turn_duration(fight, base):
    actor = fight.current
    if actor is None:
        raise ValueError("No current duration owner")
    state = getattr(fight, "native_turn_duration_policy", None)
    if state is not None:
        if (
            not isinstance(state, dict)
            or state.get("source") != POLICY
            or type(state.get("duration_ms")) is not int
            or state["duration_ms"] <= 0
        ):
            raise ValueError("Missing owned turn duration history")
        if state.get("turn_id") == fight.turn_id:
            if state.get("actor_id") != actor.id:
                raise ValueError("Turn duration owner changed")
            return state["duration_ms"]
    # First native timeline slot has no preceding fighter in this cycle.
    previous = None if state is None or fight.turn_index == 0 else state["duration_ms"]
    duration = turn_duration_policy(base, None, add_previous=False)
    rows = getattr(fight, "owned_stat_effects", {})
    if any(row.get("effect_class") == 668 for row in rows.values()):
        from .combat_retained_runtime import native_retained_condition_effects

        for _, family, uid in native_retained_condition_effects(fight, actor.id):
            if family == 668:
                row = rows.get(uid)
                if not isinstance(row, dict) or row.get("family") != "eWL":
                    raise ValueError("Missing native retained turn-duration marker")
                # Explicit server policy: first matching actual Qf marker wins.
                duration = turn_duration_policy(
                    base,
                    previous,
                    add_previous=row.get("native_turn_duration_add_previous"),
                )
                break
    fight.native_turn_duration_policy = dict(
        source=POLICY, actor_id=actor.id, turn_id=fight.turn_id, duration_ms=duration
    )
    return duration


class NativeTurnDurationHandler:
    def __init__(
        self, fight, packets, *, allocate_uid, action_id, context, authority, rng
    ):
        self.fight, self.packets = fight, packets
        self.allocate_uid, self.action_id = allocate_uid, action_id
        self.context, self.authority, self.rng = context, authority, rng
        self.event_lifecycle = None

    def __call__(self, effect, values, invocation):
        from .combat_carry_handler import NativeCarryHandler
        from .combat_stat_handler import StatExecutionContext
        from .combat_summon_initialization import (
            registered_or_detached_actor,
            detached_actor,
        )
        from .combat_global_pv_collections import global_fighter_registered
        from .combat_parameters import parameter_value
        from .combat_trigger_value_modifier import NativeRunnerAmount
        from .combat_ai_control import ai_control_delivery
        from .combat_runner_callbacks import notify_runner_value

        if effect.get("effect_class") != 668:
            raise ValueError("Wrong native eWL runner")
        NativeCarryHandler.require_execution_context(invocation)
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
            or type(ctx.executable) is not bool
            or type(ctx.retained) is not bool
        ):
            raise ValueError("Missing native eWL execution authority")
        if not ctx.executable:
            return False
        uid = self.allocate_uid()
        runner = NativeRunnerAmount(uid, 668, rng=self.rng)

        def phase(channel):
            if self.event_lifecycle is not None:
                masks = effect.get("target_masks")
                if not isinstance(masks, (list, tuple)) or len(masks) != 7:
                    raise ValueError("Missing native eWL event masks")
                self.event_lifecycle.phase(
                    effect,
                    invocation,
                    uid=uid,
                    value=0,
                    channel=channel,
                    runner_modifier=runner,
                    _event_ids=tuple(sorted({0, *(masks[6] or ())})),
                    _execution_status=-1,
                )

        phase(1)
        actor = registered_or_detached_actor(self.fight, invocation.target_id)
        add_previous = False
        if (
            actor is not None
            and detached_actor(self.fight, actor.id) is None
            and self.authority(self.fight, actor).targeting.get("is_eGj") is True
            and global_fighter_registered(self.fight, actor.id)
        ):
            parameters = effect.get("parameters")
            if not isinstance(parameters, (list, tuple)) or len(parameters) % 2:
                raise ValueError("Missing native eWL logical parameters")
            add_previous = duration_add_previous(
                [parameter_value(parameters, 0, invocation.level)]
                if len(parameters) == 2
                else []
            )
        phase(2)
        # Original c is empty; timing changes only through the retained marker.
        packet, payload = ai_control_delivery(
            self.fight.id,
            self.action_id,
            effect,
            invocation,
            uid=uid,
            value=0,
            timing_payload=ctx.timing_payload,
        )
        if ctx.retained:
            if actor is None:
                raise ValueError("Missing retained native eWL manager")
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                effect_class=668,
                family="eWL",
                target_id=actor.id,
                caster_id=invocation.caster_id,
                stat_id=None,
                actual=0,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
                native_turn_duration_add_previous=add_previous,
            )
        self.packets.append(packet)
        if ctx.retained and self.event_lifecycle is not None:
            self.event_lifecycle.register_applied(effect, invocation, uid)
        runner.finish_application()
        phase(3)
        phase(4)
        notify_runner_value(invocation, 0)
        return True


def remove_turn_duration(handler, uid):
    # Original eWL has no bbR override; removal deletes the marker only.
    from .combat_force_characteristic import remove_forced_characteristic

    return remove_forced_characteristic(handler, uid)
