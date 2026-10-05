"""Audited fresh eVE/eZk timing contexts for the fixed local fight timeline.

No fallback execution modes, realtime clocks, delayed effects or trigger values.
"""
from .combat_effects import _integer, _varint
from .combat_parameters import parameter_value, _float32, _integer as java_integer
import math
from .combat_state_parameters import interpret_state_parameters
from .combat_state_application import (
    existing_state_from_definition,
    plan_state_application,
)
from .combat_definitions import state_profile
from .combat_state_ledger import StateTimeline
from .combat_state_timing import StateTimingDefinition, schedule_state_timer
from .combat_state_handler import StateCarrierContext
from .combat_stat_handler import StatExecutionContext
from .combat_effect_timing import schedule_effect_timer
from .combat_native_container import resolve_state_container


def native_time_payload(timer=None, *, realtime_remaining=-1):
    """eZR.QH -> iB, including native Ts.biM sentinel (0,-1,false)."""
    actor, round_number, end = (
        (0, -1, False)
        if timer is None
        else (timer.actor_id, timer.expiration_round, timer.phase == "end")
    )
    deadline = b"".join(
        _integer(k, v) for k, v in ((1, actor), (2, round_number), (3, int(end)))
    )
    return (
        _integer(1, 0)
        + _integer(2, -1)
        + b"\x1a"
        + _varint(len(deadline))
        + deadline
        + _integer(4, realtime_remaining)
        + _integer(5, 0)
    )


def native_definition_timing(effect, level):
    """Exact eVy.en/eo and eVH.ep arithmetic, using native exported fields."""
    mode = effect.get("native_execution_mode")
    fields = effect.get("native_timing_definition")
    if mode == 0:
        return {"retained": True, "delay": False, "duration": None}
    if not isinstance(fields, dict):
        raise ValueError("Missing native timing definition")

    def amount(base, growth, short):
        product = _float32(_float32(fields[growth]) * level)
        delta = (
            java_integer(math.floor(product))
            if math.isfinite(product)
            else java_integer(product)
        )
        value = ((fields[base] + delta + 2**31) % 2**32) - 2**31
        return ((value + 32768) % 65536) - 32768 if short else value

    # eVI is the audited synthetic collision subclass; it inherits eVy.en/eo.
    if mode == 2 and effect.get("native_definition_class") in ("eVy", "eVI"):
        duration = amount("ryE", "ryF", True)
        delay = amount("ryH", "ryI", True)
        if delay > 0:
            raise ValueError("Delayed effect execution requires a verified queue")
        return {"retained": duration != 0, "delay": False, "duration": duration}
    if mode == 1 and effect.get("native_definition_class") == "eVH":
        duration = amount("rzv", "rzw", False)
        if duration > 0:
            raise ValueError("Realtime effect timer requires a verified scheduler")
        return {"retained": duration < 0, "delay": False, "duration": duration}
    raise ValueError("Unknown native execution mode or definition class")


def native_state_timeline(fight, clock_actor_id):
    if fight.phase != "active" or fight.current is None:
        raise ValueError("Native timing requires an active actor turn")
    order = tuple(fight.order)
    records = getattr(fight, "native_summon_registrations", {})
    excluded = set()
    for identity, row in records.items():
        if identity not in fight.actors or row.get("actor_id") != identity:
            raise ValueError("Stale native summoned timeline registration")
        # fbX.C excludes NOT_PRESENT_IN_TIMELINE114 from fem/Tc insertion.
        if 114 in row["fight_properties"]:
            excluded.add(identity)
    eligible = {
        identity
        for identity, member in fight.actors.items()
        if member.hp > 0 and identity not in excluded
    }
    deferred = getattr(fight, "_resolution_depth", 0) > 0
    if (
        len(set(order)) != len(order)
        or not eligible <= set(order)
        or not set(order) <= set(fight.actors)
        or (not deferred and set(order) != eligible)
    ):
        raise ValueError("Inconsistent eligible fixed actor timeline")
    actor = fight.current
    if type(actor.turn_count) is not int or not 1 <= actor.turn_count < 32768:
        raise ValueError("Missing authoritative native round")
    if not 0 <= fight.turn_index < len(order) or order[fight.turn_index] != actor.id:
        raise ValueError("Inconsistent native current actor index")
    if clock_actor_id not in order and clock_actor_id not in excluded:
        raise ValueError("Missing state clock actor")
    return StateTimeline(
        actor.turn_count,
        actor.id,
        fight.turn_index,
        order.index(clock_actor_id) if clock_actor_id in order else -1,
        "active",
    )


class NativeEffectTimingProvider:
    def __init__(self, catalog):
        self.catalog = catalog

    def state(self, preview, plan, effect, invocation):
        count = effect["parameter_count"]
        values = [
            parameter_value(effect["parameters"], i, invocation.level)
            for i in range(count)
        ]
        params = interpret_state_parameters(values)
        return self.state_reference(
            preview, plan, effect, invocation, params["reference"], params["level"]
        )

    def state_reference(
        self, preview, plan, effect, invocation, reference, requested_level
    ):
        native_definition_timing(effect, invocation.level)
        return self.direct_state_reference(
            preview,
            invocation,
            reference,
            requested_level,
            critical=bool(effect["variant"] & 1),
        )

    def direct_state_reference(
        self, preview, invocation, reference, requested_level, *, critical
    ):
        """eWu direct carrier application, with explicit applicator critical flag.

        Its state clock comes from fyW, independent of the applicator's PK clock.
        The caller must attest its native synthetic PK and PL separately.
        """
        if type(critical) is not bool:
            raise ValueError("Explicit native direct applicator critical flag required")
        definition = self.catalog["states"][str(reference)]
        from .combat_state_managers import state_manager

        target = state_manager(preview, invocation.target_id)
        if target is None:
            raise ValueError("Missing actual native state target manager")
        matching = [
            existing_state_from_definition(
                dict(
                    definition,
                    protected=definition["protected"]
                    if e.protected is None
                    else e.protected,
                ),
                e.level,
            )
            for e in target.state_ledger.entries
            if e.reference == reference
        ]
        application = plan_state_application(
            requested_level, definition["maximum_level"], matching
        )
        # A rejected application produces no carrier; use the requested level only
        # to validate its definition. The handler repeats this pure decision.
        level = application.level if application.accepted else requested_level
        profile = state_profile(self.catalog, reference, level)
        if profile["realtime_duration"] > 0:
            raise ValueError("Realtime state clock requires a verified scheduler")
        clock = (
            invocation.caster_id
            if definition["clock_actor"] == "caster"
            else invocation.target_id
        )
        if getattr(target, "native_is_area", False) and clock == target.id:
            if profile["duration"] > 0:
                raise ValueError("Timed area state clock is unaudited")
            # Zero/indefinite carriers retain no turn timer (fyW duration<=0).
            # The active boundary exists, but no area timeline slot is invented.
            timeline = native_state_timeline(preview, invocation.caster_id)
        else:
            timeline = native_state_timeline(preview, clock)
        timing = StateTimingDefinition(
            definition["duration_base"],
            definition["duration_per_level"],
            definition["maximum_level"],
            definition["tick_at_turn_end"],
            definition["clock_actor"] == "caster",
            definition["skip_turn_timer"],
        )
        timer = schedule_state_timer(
            timing,
            level=level,
            caster_id=invocation.caster_id,
            target_id=invocation.target_id,
            **vars(timeline)
        )
        # eZk.a/aWr initialize rHv=-1,dPa=0,rHy/rHz=false. eWu.D
        # propagates the chosen applying effect's dd(1) critical variant.
        return StateCarrierContext(
            -1,
            profile["realtime_duration"],
            False,
            timeline,
            invocation.base_uid,
            critical,
            False,
            False,
            0,
            native_time_payload(timer, realtime_remaining=profile["realtime_duration"]),
        )

    def stat(self, preview, plan, effect, invocation):
        native = native_definition_timing(effect, invocation.level)
        retained = native["retained"]
        timer = None
        if effect["native_execution_mode"] == 2 and native["duration"] > 0:
            fields = effect["native_timing_definition"]
            for key in ("clock_on_caster", "clock_on_target"):
                if type(fields.get(key)) is not bool:
                    raise ValueError("Missing native clock routing")
            clock = (
                invocation.caster_id
                if fields["clock_on_caster"]
                else invocation.target_id
            )
            if clock not in preview.actors:
                clock = invocation.caster_id
            timeline = native_state_timeline(preview, clock)
            timer = schedule_effect_timer(
                duration=native["duration"],
                expire_at_end=fields["esr"],
                extend_on_clock_turn=fields["ryG"],
                clock_actor_id=clock,
                timeline=timeline,
            )
        if invocation.state_uid:
            # Qe.bfq retains the actual fyW owner during its synchronous
            # iterator, including instant states and replaced sibling states.
            # Use the same execution-local resolver as damage and retention;
            # it still rejects unknown UIDs after the call has returned.
            resolve_state_container(preview, invocation.state_uid)
        # Qe.bfq preserves PL identity but does not override eZR.Ty.
        # Instant Ty=false state children must not be undone when the carrier
        # is replaced (e.g. Concentration grants PW before decreasing itself).
        return StatExecutionContext(
            True, True, None, retained, native_time_payload(timer), timer
        )
