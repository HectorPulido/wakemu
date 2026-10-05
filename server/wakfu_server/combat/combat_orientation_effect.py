"""eWF303: native orientation modes, no reversal when the effect is removed."""
from dataclasses import replace
from .combat_displacement import cardinal_vector
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_force_characteristic import remove_forced_characteristic
from .combat_observation_delivery import evaluated_application_from_observation

VECTORS = (
    (1, -1),
    (1, 0),
    (1, 1),
    (0, 1),
    (-1, 1),
    (-1, 0),
    (-1, -1),
    (0, -1),
    (0, 0),
    (0, 0),
)
MODES = {1: 5, 2: 7, 3: 1, 4: 3}


def _direction(value):
    if type(value) is not int or value not in range(-1, 10):
        raise ValueError("Missing native aAS actor direction")
    return value


def _toward(source, target):
    vector = cardinal_vector(target[0] - source[0], target[1] - source[1])
    return -1 if vector == (0, 0) else VECTORS.index(vector)


def orientation_transition(
    mode,
    *,
    caster_position,
    caster_direction,
    target_position,
    target_direction,
    cell,
    draw_mode
):
    if type(mode) is not int or not -(1 << 31) <= mode < (1 << 31):
        raise ValueError("Missing native evaluated eWF mode")
    if mode == 5:
        mode = draw_mode()
        if type(mode) is not int or mode not in MODES:
            raise ValueError("Invalid native inclusive orientation roll1..4")
    # eWF.C draws mode5 before its null-target check.
    if target_position is None:
        return False, -1
    rebind = mode == 8
    if mode in MODES:
        direction = MODES[mode]
    elif mode == 0:
        direction = _toward(target_position, cell)
    elif mode in (6, 7, 10):
        direction = _direction(caster_direction)
        if mode == 7:
            direction = (
                (direction + 4) % 8
                if direction < 8 and direction >= 0
                else 9
                if direction == 8
                else 8
                if direction == 9
                else -1
            )
        elif mode == 10:
            if direction < 0:
                direction = -1
            else:
                x, y = VECTORS[direction]
                direction = -1 if (x, y) == (0, 0) else VECTORS.index((y, x))
    elif mode in (8, 9):
        if caster_position is None:
            raise ValueError("Missing native eWF caster position")
        direction = (
            _toward(caster_position, target_position)
            if rebind
            else _toward(target_position, caster_position)
        )
    elif mode == 11:
        direction = _direction(target_direction)
        direction = (
            (direction + 4) % 8
            if direction < 8 and direction >= 0
            else 9
            if direction == 8
            else 8
            if direction == 9
            else -1
        )
    else:
        direction = -1
    return rebind, direction


class NativeOrientationHandler:
    native_runner_value_verified = True

    def __init__(
        self, fight, packets, *, action_id, allocate_uid, context, authority, draw_mode
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.authority, self.draw_mode = context, authority, draw_mode

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 303 or not values["parameters"]:
            raise ValueError("Unsupported native eWF parameters")
        # Original eWF.C reads parameter0 only; extra pairs are unused.
        caster = self.fight.actors.get(invocation.caster_id)
        target = self.fight.actors.get(invocation.target_id)
        if invocation.target_id is not None and target is None:
            raise ValueError("Unknown native orientation PV target")
        rebind, direction = orientation_transition(
            values["parameters"][0],
            caster_position=None if caster is None else caster.position,
            caster_direction=None
            if caster is None
            else getattr(caster, "direction", None),
            target_position=None if target is None else target.position,
            target_direction=None
            if target is None
            else getattr(target, "direction", None),
            cell=invocation.cell,
            draw_mode=lambda: self.draw_mode(effect, invocation),
        )
        actor = caster if rebind else target
        if actor is None or direction == -1:
            return False  # Native mu(true): null/NONE, not a fabricated facing.
        current = _direction(getattr(actor, "direction", None))
        provider = getattr(self.authority, "property_counts", None)
        if not callable(provider):
            raise ValueError("Missing native orientation property authority")
        counts = provider(self.fight, actor)
        if not isinstance(counts, dict) or any(
            type(k) is not int or type(v) is not int for k, v in counts.items()
        ):
            raise ValueError("Missing native PB orientation counters")
        if counts.get(51, 0) != 0 or direction == current:
            return False  # eWF.sev guard and no-change failure.
        # C rebinds bfs before application/ownership; never rotate the original
        # target in mode8 or leave the retained effect in its manager.
        selected = replace(invocation, target_id=actor.id)
        ctx = self.context(effect, selected)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
        ):
            raise ValueError("Missing native orientation execution authority")
        if not ctx.executable:
            return False
        uid = self.allocate_uid()
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=actor.id,
            value=direction,
            timing_payload=ctx.timing_payload,
            execution_status=0,
            executed=True,
        )
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=303,
            target_id=actor.id,
            uid=uid,
            running_effect_payload=payload,
        )
        actor.direction = direction
        self.fight._event(
            "orientation",
            actor_id=actor.id,
            direction=direction,
            source_id=invocation.caster_id,
            effect_reference=invocation.reference,
        )
        if ctx.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                effect_class=303,
                family="eWF",
                target_id=actor.id,
                caster_id=invocation.caster_id,
                stat_id=None,
                actual=direction,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
            )
        # aTR/cvY only observes/registers: it never invokes eWF.c. The client
        # must complete aVo/cvX with eIK=false to apply the evaluated direction.
        self.packets.append((12613, evaluated_application_from_observation(packet)))
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, direction)
        return True


def remove_orientation(handler, uid):
    # eWF has no bbR override: Qe removal never restores the previous facing.
    return remove_forced_characteristic(handler, uid)
