"""Native eWs451 mutates faV.rzt property membership, never fighter PB counters."""
from .combat_area_contracts import SUPPORTED_AREA_CONTRACTS
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_effect_removal import running_effect_removal
from dataclasses import replace
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_value_transfer import apply_context_value


def area_properties(row, definition):
    if definition.get("type") == "ARTIFACT" or row.get("native_area_contract") == "faM":
        from .combat_artifact_area import verify_artifact_area

        verify_artifact_area(row, definition)
    values = row.get("native_current_area_properties")
    if values is None:
        values = definition.get("native_area_properties")
    elif row.get("native_area_property_source") != "faV.rzt.eWs":
        raise ValueError("Missing current native area property provenance")
    if not isinstance(values, (list, tuple, set, frozenset)) or any(
        type(value) is not int or not 0 <= value <= 14 for value in values
    ):
        raise ValueError("Missing complete native faV property set")
    return frozenset(values)


def _target(fight, identity):
    active = getattr(fight, "native_effect_areas", {})
    retired = getattr(fight, "native_retired_area_managers", {})
    if identity in active and identity in retired:
        raise ValueError("Area property target is active and retired")
    row = active.get(identity, retired.get(identity))
    if row is None:
        return None, None
    from .combat_effect_area import native_effect_areas

    definition = native_effect_areas().get(str(row.get("reference")))
    if (
        row.get("uid") != identity
        or row.get("native_area_contract") not in SUPPORTED_AREA_CONTRACTS
        or not isinstance(definition, dict)
    ):
        raise ValueError("Missing actual native faV property target")
    return row, definition


def _write(row, values):
    row["native_current_area_properties"] = tuple(sorted(values))
    row["native_area_property_source"] = "faV.rzt.eWs"


class NativeAreaPropertyHandler:
    native_runner_value_verified = True

    def __init__(
        self, fight, packets, *, action_id, allocate_uid, context, rng=lambda: 0.5
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )
        self.rng, self.event_lifecycle = rng, None
        self.prepared, self.runners = {}, {}

    def _events(self, effect):
        masks = effect.get("target_masks")
        if not isinstance(masks, (list, tuple)) or len(masks) < 7:
            raise ValueError("Missing native area property events")
        return tuple(sorted({0, *(masks[6] or ())}))

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)
        self.runners.pop(invocation.native_running_uid, None)

    def prepare(self, effect, values, invocation):
        if self.event_lifecycle is None:
            return invocation
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        try:
            runner = NativeRunnerAmount(uid, 451, rng=self.rng)
            self.runners[uid] = runner
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=0,
                channel=1,
                _event_ids=self._events(effect),
                runner_modifier=runner,
                _nullable_target=True,
            )
            parameters = values.get("parameters")
            if not parameters or type(parameters[0]) is not int:
                raise ValueError("Missing native evaluated area property")
            # eWs.C writes inherited Qe.aSg, then the actual PS value applies.
            amount = apply_context_value(
                parameters[0],
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
            self.prepared[uid] = amount
            runner.set_calculated(amount)
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def __call__(self, effect, values, invocation):
        try:
            return self._apply(effect, values, invocation)
        finally:
            self.cancel_prepared(invocation)

    def _apply(self, effect, values, invocation):
        if effect["effect_class"] != 451:
            raise ValueError("Wrong native area property runner")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
        ):
            raise ValueError("Missing native area property execution authority")
        if not ctx.executable:
            return False
        parameters = values.get("parameters")
        if not parameters or type(parameters[0]) is not int:
            raise ValueError("Missing native evaluated area property")
        prop = parameters[0]
        uid = invocation.native_running_uid
        if uid is not None:
            if uid not in self.prepared:
                raise ValueError("Missing prepared native area property runner")
            prop = self.prepared[uid]
        uid = uid or self.allocate_uid()
        amount = apply_context_value(
            parameters[0],
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        if invocation.native_running_uid is not None:
            amount = self.prepared[uid]
        runner = self.runners.get(uid)
        if self.event_lifecycle is not None:
            if runner is None:
                runner = NativeRunnerAmount(uid, 451, rng=self.rng, value=amount)
                self.event_lifecycle.phase(
                    effect,
                    invocation,
                    uid=uid,
                    value=amount,
                    channel=1,
                    _event_ids=self._events(effect),
                    runner_modifier=runner,
                    _nullable_target=True,
                )
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=runner.value,
                channel=2,
                _event_ids=self._events(effect),
                runner_modifier=runner,
                _nullable_target=True,
            )
            live = self.context(effect, invocation)
            if not live.executable:
                return False
            if live.retained != ctx.retained:
                raise ValueError("Native area property retention changed during L2")
            amount = runner.value
        prop = amount
        row, definition = _target(self.fight, invocation.target_id)
        # eWs.c: null/non-Qq target or fbo.Tn=null calls mu(true).
        if row is None or not 0 <= prop <= 14:
            return False
        current = area_properties(row, definition)
        if prop == 12:
            raise ValueError(
                "Dynamic faV Qf construction requires native manager authority"
            )
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=invocation.target_id,
            value=amount,
            timing_payload=ctx.timing_payload,
        )
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=451,
            target_id=invocation.target_id,
            uid=uid,
            running_effect_payload=payload,
        )
        _write(row, current | {prop})
        if ctx.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=invocation.target_id,
                caster_id=invocation.caster_id,
                effect_class=451,
                family="eWs",
                property_id=prop,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
            )
        from .combat_observation_delivery import evaluated_application_from_observation

        # eWs.c writes the real Qq property set; aTR only observes this runner.
        # Immediate effects execute directly; retained runners keep native Qf.
        self.packets.append(
            (
                12613,
                evaluated_application_from_observation(
                    packet, execute=not ctx.retained
                ),
            )
        )
        if ctx.retained and self.event_lifecycle is not None:
            self.event_lifecycle.register_applied(effect, invocation, uid)
        if self.event_lifecycle is not None:
            runner.finish_application()
            for channel in (3, 4):
                self.event_lifecycle.phase(
                    effect,
                    invocation,
                    uid=uid,
                    value=runner.value,
                    channel=channel,
                    _event_ids=self._events(effect),
                    runner_modifier=runner,
                    _nullable_target=True,
                )
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, amount if runner is None else runner.value)
        return True


def remove_area_property(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    row, definition = _target(handler.fight, entry["target_id"])
    if row is None:
        raise ValueError("Missing actual retained area property target")
    if entry["property_id"] == 12:
        raise ValueError(
            "Dynamic faV null-Qf transition requires native manager authority"
        )
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=451,
        target_id=entry["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    _write(row, area_properties(row, definition) - {entry["property_id"]})
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
