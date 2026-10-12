"""Native eXl934/eGj.dnu retirement; HP and fdt registration stay intact."""
from contextlib import contextmanager
from contextvars import ContextVar

from .combat_global_pv_collections import (
    global_fighter_registered,
    global_fighter_guards,
    set_global_fighter_status,
)
from .combat_trove_long_map import NativeTroveLongMap

SOURCE = "native.eXl934.eGj_dnu.v1"
_TRANSITIONS = ContextVar("native_eGj_dnu_transitions", default=())


@contextmanager
def _transition(fight, actor):
    token = _TRANSITIONS.set(
        (*_TRANSITIONS.get(), (fight, actor, actor.native_obstacle_id))
    )
    try:
        yield
    finally:
        _TRANSITIONS.reset(token)


def forced_retirement_transition(fight, identity, slot):
    """Actual reentrant dnu window, never a persistent status exemption."""
    return any(
        owner is fight
        and actor.id == identity
        and fight.actors.get(identity) is actor
        and actor.native_obstacle_id == previous_slot == slot
        for owner, actor, previous_slot in _TRANSITIONS.get()
    )


def retired_forced_fighter_ids(fight):
    records = getattr(fight, "native_forced_retirements", {})
    if not isinstance(records, dict):
        raise ValueError("Malformed native forced-retirement history")
    result = set()
    for key, row in records.items():
        actor = fight.actors.get(int(key))
        if (
            actor is None
            or not isinstance(row, dict)
            or row.get("source") != SOURCE
            or row.get("actor_id") != actor.id
            or type(row.get("uid")) is not int
            or row["uid"] <= 0
            or actor.native_obstacle_id != -1
            or getattr(actor, "native_forced_retirement", None) != row
            or not global_fighter_registered(fight, actor.id)
            or (
                global_fighter_guards(fight, actor.id)
                != dict(baF=False, baG=False, baK=True)
                and not forced_retirement_transition(fight, actor.id, -1)
            )
        ):
            raise ValueError("Missing actual native eXl retirement authority")
        result.add(actor.id)
    return frozenset(result)


def linked_fighter_order(fight, retiring_id):
    """fcb.dLy after aO: native fdt order, IN_PLAY OR OFF_PLAY only."""
    state = fight.native_global_pv_collections
    return tuple(
        identity
        for identity in NativeTroveLongMap(state["fighters"]).order()
        if identity != retiring_id and not global_fighter_guards(fight, identity)["baK"]
    )


def cleanup_runner_order(view, linked, target_id, identities):
    """eZV.i/Qn: departing manager, caster OR target links, native exemptions."""
    selected = []
    for identity in linked:
        for entry in view.entries:
            if entry.uid in selected or entry.manager_id != target_id:
                continue
            if entry.effect_class == 310:
                continue  # eVi.rpJ state carrier is explicitly excluded.
            if type(entry.container_present) is not bool:
                raise ValueError("Missing actual native runner container presence")
            if entry.container_present and entry.container_type is None:
                raise ValueError("Missing actual native runner container type")
            if entry.container_present and entry.container_type == 1:
                continue
            caster, target = identities(entry)
            if caster == identity or target == identity:
                selected.append(entry.uid)
    return tuple(selected)


class NativeForcedRetirementCleanup:
    """Actual shared Qs/Qf callback owners on the same detached preview."""

    def __init__(self, retention):
        self.retention = retention
        self.fight = retention.fight

    def _identities(self, entry):
        from .combat_effect_removal import _identity_fields

        for name in (
            "owned_stat_effects",
            "native_owned_group_effects",
            "native_owned_area_effects",
            "native_owned_spatial_effects",
        ):
            row = getattr(self.fight, name, {}).get(entry.uid)
            if row is not None:
                fields = _identity_fields(bytes.fromhex(row["payload"]))

                def signed(value):
                    return value - (1 << 64) if value >= 1 << 63 else value

                if 6 not in fields:
                    raise ValueError("Missing native runner caster identity")
                return signed(fields[6]), signed(fields[7]) if 7 in fields else None
        raise ValueError("Missing owned native linked-runner payload")

    def preflight(self, actor):
        from .combat_effect_area_queries import _rows
        from .combat_global_pv_collections import global_area_order
        from .combat_effect_area_events import NativeAreaEventRuntime

        rows = {row["uid"]: row for row in _rows(self.fight)}
        self.areas = tuple(
            uid
            for uid in global_area_order(self.fight)
            if rows[uid]["owner_id"] == actor.id
        )
        self.area_events = getattr(self.retention, "area_events", None)
        if self.areas:
            if (
                not isinstance(self.area_events, NativeAreaEventRuntime)
                or self.area_events.fight is not self.fight
            ):
                raise ValueError("Missing actual native Qs callback owner")
            for uid in self.areas:
                self.area_events._definition(rows[uid])
        view = self.retention.view()
        selected = cleanup_runner_order(
            view, linked_fighter_order(self.fight, actor.id), actor.id, self._identities
        )
        self.retention.removal(view).plan(selected)

    def remove_areas(self, actor):
        from .combat_effect_area import remove_owned_hour_area

        for uid in self.areas:
            remove_owned_hour_area(self.fight, uid, callbacks=self.area_events)
        self.retention.synchronize()

    def remove_linked_runners(self, actor):
        # Area callbacks can change the complete Qf population: obtain a fresh
        # authoritative view at the native point, after status/controller/carry.
        view = self.retention.view()
        selected = cleanup_runner_order(
            view, linked_fighter_order(self.fight, actor.id), actor.id, self._identities
        )
        self.retention.removal(view).remove(selected)
        self.retention.synchronize()


def _release_carried(fight, actor):
    """eGj.fqz -> carrier.dnF -> R(current cell), after OUT_OF_PLAY."""
    from .combat_carrying import _pairs, carrying_relations, release_registered

    if not carrying_relations(fight, actor)["is_carried"]:
        return
    pair = next(pair for pair in _pairs(fight).values() if pair.carried_id == actor.id)
    carrier = fight.actors[pair.carrier_id]
    release_registered(fight, carrier, carrier.position, direction=actor.direction)


def force_retire_fighter(fight, actor, *, uid, cleanup, property_counts=None):
    """Apply dnu on an already detached transaction; callers own atomic delivery."""
    from .combat_controller_registry import _row, restore_native_controller
    from .combat_qi_fight import current_registry
    from .combat_qi_registry import NativeQIRegistry
    from .combat_timeline_snapshot import counters, remove
    from .combat_carrying import carrying_relations
    from .combat_property_stack import property_present

    if (
        fight.actors.get(actor.id) is not actor
        or type(uid) is not int
        or uid <= 0
        or cleanup.fight is not fight
        or not global_fighter_registered(fight, actor.id)
    ):
        raise ValueError("Actual registered native retirement recipient required")
    current_registry(fight)  # Full physical topology before native transition.
    _row(fight, actor.id)  # Actual constructor controller originals.
    counters(fight)
    carrying_relations(fight, actor)
    counts = getattr(actor, "native_fight_property_counts", None)
    bind_counts = counts is None
    if bind_counts:
        if not callable(property_counts):
            raise ValueError(
                "Missing registered native retirement PB counter authority"
            )
        counts = property_counts(fight, actor)
    property_present(counts, 114)
    cleanup.preflight(actor)
    if bind_counts:
        # The registered creation authority proves the complete PB population;
        # attach its own copy only to this detached recipient after preflight.
        actor.native_fight_property_counts = dict(counts)
    hp = actor.hp
    slot = actor.native_obstacle_id
    trace = []
    with _transition(fight, actor):
        set_global_fighter_status(fight, actor.id, "OFF_PLAY")
        trace.append("OFF_PLAY")
        cleanup.remove_areas(actor)
        trace.append("Qs.k")
        # fem.eT snapshots SY/position, adjusts previously saved positions, and
        # removes Tc membership. The outer resolution boundary reconciles order.
        # Several removals may happen before the outer resolution reconciles
        # fight.order. Tc has already removed their SY identities.
        if not property_present(actor.native_fight_property_counts, 114):
            active_order = [
                identity for identity in fight.order if str(identity) in counters(fight)
            ]
            index = active_order.index(actor.id) if actor.id in active_order else -1
            remove(fight, actor.id)
            if index >= 0:
                for row in fight.native_timeline_removed:
                    if row["actor_id"] != actor.id and index < row["position"]:
                        row["position"] -= 1  # fem.eN -> feu.TG.
        trace.append("SU.eT")
        set_global_fighter_status(fight, actor.id, "OUT_OF_PLAY")
        trace.append("OUT_OF_PLAY")
        restore_native_controller(fight, actor.id)
        trace.append("restore_controller")
        _release_carried(fight, actor)
        cleanup.remove_linked_runners(actor)
        # fem.eu permanently removes the saved initiative entry, distinct from
        # ordinary OFF_PLAY's reversible snapshot. Keep unrelated snapshots.
        if not property_present(actor.native_fight_property_counts, 114):
            fight.native_timeline_removed[:] = [
                row
                for row in fight.native_timeline_removed
                if row["actor_id"] != actor.id
            ]
        trace.append("SU.eu")
        if hasattr(fight, "native_pointer_checkpoint"):
            registry = current_registry(fight)
        else:
            registry = NativeQIRegistry(
                fight.native_qi_snapshot,
                fight.native_qi_slots,
                touched_cells=fight.native_qi_touched_cells,
                byte_topology=fight.native_qi_byte_topology,
            )
        if slot != -1:
            registry.remove(actor.native_obstacle_id, ("actor", actor.id))
        actor.native_obstacle_id = -1
        if hasattr(fight, "native_pointer_checkpoint"):
            from .combat_carrying import _publish_registry

            _publish_registry(fight, registry)
        else:
            fight.native_qi_slots = registry.serialized_slots()
            fight.native_qi_touched_cells = registry.serialized_cells()
            fight.native_qi_byte_topology = registry.serialized_byte_topology()
        trace.append("QI.g")
        history = getattr(fight, "native_forced_retirement_order", [])
        fight.native_forced_retirement_order = [
            *history,
            actor.id,
        ]  # rRO.add, no dedup.
        trace.append("removed_history")
        row = dict(
            source=SOURCE,
            actor_id=actor.id,
            uid=uid,
            previous_slot=slot,
            trace=trace,
            hp_before=hp,
            hp_after=actor.hp,
        )
        records = getattr(fight, "native_forced_retirements", {})
        fight.native_forced_retirements = dict(records, **{str(actor.id): row})
        actor.native_forced_retirement = row
        return row
