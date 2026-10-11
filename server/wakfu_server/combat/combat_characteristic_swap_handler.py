"""Native eZy1049 with captured PA values and ordered reversible shifts."""
from dataclasses import replace

from .combat_characteristic_swap import swap_characteristics, swap_additional_payload
from .combat_parameters import parameter_value
from .combat_stat_handler import StatExecutionContext, _current, _bounds, _write
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_effect_removal import running_effect_removal
from .combat_character_copy_metadata import native_copy_characteristics
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_value_transfer import apply_context_value


def pa_operations(fight, actor, source_id, first, second):
    definitions = native_copy_characteristics()["fresh_characteristics"]
    copied = getattr(actor, "native_copy_pa_source", None) is not None
    for stat in (first, second):
        definition = definitions.get(str(stat))
        if not isinstance(definition, dict):
            raise ValueError("Missing actual native eZy characteristic authority")
        minimum, maximum = _bounds(actor, stat)
        value = _current(actor, stat)
        if (
            any(type(v) is not int for v in (minimum, maximum, value))
            or not minimum <= value <= maximum
        ):
            raise ValueError("Invalid native eZy current PA snapshot")
        if copied:
            from .combat_copied_pa import copied_raw_current

            copied_raw_current(actor, stat)
        elif (
            definition.get("expandable") is not False
            or definition.get("over_max_current") is not False
            or stat in actor.effect_frozen
            or minimum != definition["hard_minimum"]
            or maximum != definition["hard_maximum"]
        ):
            raise ValueError("Native eZy PA requires hidden raw-current authority")

    def shift(stat, amount, subtract):
        if copied:
            from .combat_copied_pa import shift_copied_current

            shift_copied_current(fight, actor, stat, amount, subtract=subtract)
            return
        minimum, maximum = _bounds(actor, stat)
        from .combat_casting_range import int32

        value = _current(actor, stat)
        requested = (
            (minimum if amount > int32(value - minimum) else int32(value - amount))
            if subtract
            else (maximum if amount > int32(maximum - value) else int32(value + amount))
        )
        after = max(minimum, min(maximum, requested))
        _write(fight, source_id, actor, stat, after)

    return lambda stat: _current(actor, stat), shift


class NativeCharacteristicSwapHandler:
    def __init__(self, fight, packets, *, action_id, allocate_uid, context, rng):
        self.fight, self.packets, self.action_id = fight, packets, action_id
        self.allocate_uid, self.context, self.rng = allocate_uid, context, rng
        self.event_lifecycle = None
        self.prepared = {}

    def _context(self, effect, invocation):
        if effect.get("effect_class") != 1049 or len(effect.get("parameters", ())) != 4:
            raise ValueError("Missing native eZy definition")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
        ):
            raise ValueError("Missing native eZy execution authority")
        return context

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            masks = effect.get("target_masks")
            if not isinstance(masks, (list, tuple)) or len(masks) != 7:
                raise ValueError("Missing native eZy event masks")
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
        self._context(effect, invocation)
        uid = invocation.native_running_uid or self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, 1049, rng=self.rng)
        self._phase(effect, invocation, runner, 1)
        ids = tuple(
            ((parameter_value(effect["parameters"], i, invocation.level) + 128) % 256)
            - 128
            for i in (0, 1)
        )
        runner.set_calculated(
            apply_context_value(
                0,
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
        )
        self.prepared[uid] = runner, ids
        return invocation

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)

    def __call__(self, effect, values, invocation):
        context = self._context(effect, invocation)
        if not context.executable:
            self.cancel_prepared(invocation)
            return False
        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        item = self.prepared.pop(invocation.native_running_uid, None)
        if item is None:
            raise ValueError("Missing prepared native eZy runner")
        runner, (first, second) = item
        self._phase(effect, invocation, runner, 2)
        context = self._context(effect, invocation)
        if not context.executable:
            return False
        actor = self.fight.actors.get(invocation.target_id)
        if actor is None:
            raise ValueError("Missing actual native eZy target PA authority")
        current, shift = pa_operations(
            self.fight, actor, invocation.caster_id, first, second
        )
        captured = swap_characteristics(first, second, current=current, shift=shift)
        runner.finish_application()
        payload = owned_effect_payload(
            uid=runner.uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=actor.id,
            value=runner.value,
            timing_payload=context.timing_payload,
        ) + swap_additional_payload(first, second, captured)
        if context.retained:
            self.fight.owned_stat_effects[runner.uid] = dict(
                uid=runner.uid,
                effect_class=1049,
                family="eZy",
                stat_id=None,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                actual=runner.value,
                native_characteristic_ids=[first, second],
                native_captured_currents=list(captured),
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
                    effect_class=1049,
                    target_id=actor.id,
                    uid=runner.uid,
                    running_effect_payload=payload,
                ),
            )
        )
        if context.retained and self.event_lifecycle is not None:
            register = getattr(self.event_lifecycle, "register_applied", None)
            if callable(register):
                register(effect, invocation, runner.uid)
        for channel in (3, 4):
            self._phase(effect, invocation, runner, channel)
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, runner.value)
        return True


def remove_characteristic_swap(handler, uid):
    row = handler.fight.owned_stat_effects[uid]
    if row.get("effect_class") != 1049 or row.get("family") != "eZy":
        raise ValueError("Missing retained native eZy identity")
    first, second = row["native_characteristic_ids"]
    actor = handler.fight.actors[row["target_id"]]
    current, shift = pa_operations(
        handler.fight, actor, row["caster_id"], first, second
    )
    swap_characteristics(
        first,
        second,
        current=current,
        shift=shift,
        captured=row["native_captured_currents"],
        remove=True,
    )
    handler.packets.append(
        (
            13560,
            running_effect_removal(
                handler.fight.id,
                handler.action_id,
                effect_class=1049,
                target_id=actor.id,
                uid=uid,
                running_effect_payload=bytes.fromhex(row["payload"]),
            ),
        )
    )
    del handler.fight.owned_stat_effects[uid]
