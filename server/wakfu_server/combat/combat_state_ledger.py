"""Ordered authoritative running states, independent of class and wire format.

This collection owns application/replacement and source identity. It does not
execute child effects or advance clocks: those operations require the effect
dispatcher. In particular, duration zero is returned to the dispatcher for
instant execution only when all native persistence rules permit it.
"""
from dataclasses import dataclass
from .combat_definitions import state_profile
from .combat_state_application import (
    existing_state_from_definition,
    plan_state_application,
)
from .combat_conditions import ConditionActor
from .combat_state_timing import (
    state_requires_retention,
    StateTimer,
    StateTimingDefinition,
    schedule_state_timer,
)


@dataclass(frozen=True)
class StateTimeline:
    round_number: int
    current_actor_id: int
    current_actor_index: int
    clock_actor_index: int
    current_phase: str


@dataclass(frozen=True)
class RunningState:
    uid: int
    reference: int
    level: int
    caster_id: int
    target_id: int
    duration: int
    clock_actor: str
    tick_at_turn_end: bool
    effect_ids: tuple[int, ...]
    realtime_duration: int
    retained: bool
    timer: StateTimer | None
    protected: bool | None = None


@dataclass(frozen=True)
class StateChange:
    applied: RunningState | None
    removed: tuple[RunningState, ...] = ()


class StateLedger:
    def __init__(self, actor_id):
        if type(actor_id) is not int or actor_id == 0:
            raise ValueError("Missing state owner")
        self.actor_id = actor_id
        self._entries = ()

    @property
    def entries(self):
        return self._entries

    def apply(
        self,
        catalog,
        reference,
        level,
        *,
        caster_id,
        uid,
        applying_effect_has_delay=None,
        timeline=None,
        protected=None
    ):
        if type(caster_id) is not int or caster_id == 0:
            raise ValueError("Missing state caster")
        if type(uid) is not int or not 0 < uid < (1 << 63):
            raise ValueError("Invalid state effect UID")
        if any(entry.uid == uid for entry in self._entries):
            raise ValueError("State effect UID is already running")
        definition = catalog["states"].get(str(reference))
        if definition is None:
            raise ValueError("Unknown state definition")
        if protected is not None and type(protected) is not bool:
            raise ValueError("Invalid native carrier protection")
        instance_protected = definition["protected"] if protected is None else protected
        matching = tuple(
            entry for entry in self._entries if entry.reference == reference
        )
        plan = plan_state_application(
            level,
            definition["maximum_level"],
            [
                existing_state_from_definition(
                    dict(
                        definition,
                        protected=definition["protected"]
                        if entry.protected is None
                        else entry.protected,
                    ),
                    entry.level,
                )
                for entry in matching
            ],
        )
        if not plan.accepted:
            return StateChange(None)
        # Validate the full resulting profile before changing any collection.
        # Signed-short overflow is not silently converted to a positive level.
        profile = state_profile(catalog, reference, plan.level)
        native_persistent = state_requires_retention(
            turn_duration=profile["duration"],
            realtime_duration=profile["realtime_duration"],
            permanent_flag=profile["skip_turn_timer"],
            applying_effect_has_delay=False,
        )
        if (
            applying_effect_has_delay is not None
            and type(applying_effect_has_delay) is not bool
        ):
            raise ValueError("Invalid applying-effect delay context")
        if not native_persistent and applying_effect_has_delay is None:
            raise ValueError(
                "Applying-effect delay is required to classify a temporary state"
            )
        retained = native_persistent or applying_effect_has_delay is True
        timer = None
        if timeline is not None:
            if not isinstance(timeline, StateTimeline):
                raise ValueError("Authoritative native timeline required")
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
                level=profile["level"],
                caster_id=caster_id,
                target_id=self.actor_id,
                **vars(timeline),
            )
        applied = RunningState(
            uid,
            reference,
            profile["level"],
            caster_id,
            self.actor_id,
            profile["duration"],
            profile["clock_actor"],
            profile["tick_at_turn_end"],
            tuple(profile["effects"]),
            profile["realtime_duration"],
            retained,
            timer,
            instance_protected,
        )
        removed = tuple(matching[index] for index in plan.remove_indices)
        removed_uids = {entry.uid for entry in removed}
        survivors = tuple(
            entry for entry in self._entries if entry.uid not in removed_uids
        )
        self._entries = survivors + ((applied,) if applied.retained else ())
        return StateChange(applied, removed)

    def remove(self, uid):
        removed = next((entry for entry in self._entries if entry.uid == uid), None)
        if removed is not None:
            self._entries = tuple(entry for entry in self._entries if entry.uid != uid)
        return removed

    def expire(self, *, actor_id, round_number, phase, round_cleanup=False):
        """Return exact native-clock removals for the wire/effect dispatcher.

        Unscheduled states stay intact. This never guesses a timer from their
        duration or decrements every state on every fighter's turn.
        """
        removed = tuple(
            entry
            for entry in self._entries
            if entry.timer is not None
            and (
                entry.timer.expires_at_round_cleanup(round_number)
                if round_cleanup
                else entry.timer.expires_on(
                    actor_id=actor_id, round_number=round_number, phase=phase
                )
            )
        )
        ids = {entry.uid for entry in removed}
        self._entries = tuple(entry for entry in self._entries if entry.uid not in ids)
        return removed

    def condition_actor(self, **context):
        """Expose actual ordered states; deck/type/carry context stays explicit."""
        return ConditionActor(
            actor_id=self.actor_id,
            state_ids=frozenset(entry.reference for entry in self._entries),
            state_levels=tuple(
                (entry.reference, entry.level) for entry in self._entries
            ),
            state_sources=tuple(
                (entry.reference, entry.caster_id) for entry in self._entries
            ),
            **context,
        )
