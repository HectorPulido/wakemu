"""Registry-driven eWQ/eWR current-characteristic and null400 handlers.

All callbacks and outboxes belong to a transaction preview. Native guards,
retention and timing are explicit; RESISTANCE_CAP requires a separate engine.
Owned removal reverses actual clamped deltas, never requested amounts.
"""
from dataclasses import dataclass
from .combat_stat_effects import (
    stat_parameters,
    apply_current_stat,
    remove_current_stat,
    owned_effect_payload,
    owned_effect_application,
    current_stat_initial_eligible,
    null_execution_status,
)
from .combat_effect_removal import running_effect_removal


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
        actor.effect_stats[stat] = value


class NativeStatHandler:
    def __init__(self, fight, packets, registry, *, action_id, allocate_uid, context):
        self.fight, self.packets, self.registry = fight, packets, registry["effects"]
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )
        self.event_lifecycle = None

    def __call__(self, effect, values, invocation):
        row = self.registry.get(str(effect["effect_class"]))
        if row is None:
            raise ValueError("Missing native current-stat registry entry")
        target = self.fight.actors.get(invocation.target_id)
        if (
            self.fight.phase != "active"
            or self.fight.current is None
            or target is None
            or (target.hp <= 0 and row["runner"] != "eXE")
            or invocation.caster_id not in self.fight.actors
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
        if not context.executable:
            return False
        stat = None
        actual = requested = 0
        after = None
        execution_status = None
        if row["runner"] == "eXE":
            execution_status = null_execution_status(effect["parameters"])
        elif row["runner"] in ("eWQ", "eWR"):
            plan = stat_parameters(
                effect["parameters"],
                invocation.level,
                registered_stat_id=row["fixed_stat_id"],
                percent_default=row["percent_default"],
                trigger_value=context.trigger_value,
            )
            if not current_stat_initial_eligible(
                plan["requested"],
                zero_initial_amount_rejected=row["zero_initial_amount_rejected"],
            ):
                return False
            stat = plan["stat_id"]
            minimum, maximum = _bounds(target, stat)
            result = apply_current_stat(
                family=row["runner"],
                current=_current(target, stat),
                minimum=minimum,
                maximum=maximum,
                requested=plan["requested"],
                percent=plan["percent"],
                executable=context.executable,
                frozen=stat in target.effect_frozen,
                source_guards_verified=context.source_guards_verified,
                limit_policy=row["limit_policy"],
            )
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
        if clone and self.event_lifecycle is not None:
            for channel in (1, 2):
                self.event_lifecycle.phase(
                    effect,
                    invocation,
                    uid=uid,
                    value=0,
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
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
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
        self.packets.append((13497, packet))
        if clone and self.event_lifecycle is not None:
            for channel in (3, 4):
                self.event_lifecycle.phase(
                    effect,
                    invocation,
                    uid=uid,
                    value=0,
                    channel=channel,
                    _event_ids=tuple(sorted({0, *(effect["target_masks"][6] or ())})),
                )
        return True  # Qe.a records an application even when the actual delta is zero.

    def remove(self, uid):
        entry = self.fight.owned_stat_effects.get(uid)
        if entry is None:
            raise ValueError("Missing owned current-stat effect")
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
        if entry.get("family") == "eWN":
            from .combat_maximum_resource import remove_maximum_resource

            return remove_maximum_resource(self, uid)
        if entry.get("family") == "eZe":
            from .combat_spell_cost_effect import remove_spell_cost

            return remove_spell_cost(self, uid)
        actor = self.fight.actors.get(entry["target_id"])
        if actor is None:
            raise ValueError("Missing native effect owner")
        stat = entry["stat_id"]
        after = None
        if stat is not None:
            minimum, maximum = _bounds(actor, stat)
            after = remove_current_stat(
                family=entry["family"],
                current=_current(actor, stat),
                minimum=minimum,
                maximum=maximum,
                actual=entry["actual"],
                frozen=stat in actor.effect_frozen,
                limit_policy=entry["limit_policy"],
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
            _write(self.fight, entry["caster_id"], actor, stat, after)
        del self.fight.owned_stat_effects[uid]
        self.packets.append((13560, packet))
