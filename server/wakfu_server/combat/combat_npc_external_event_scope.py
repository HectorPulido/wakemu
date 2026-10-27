"""Owned ordinary NPC sources at reconstructed round/wave boundaries.

This is source provenance, not recipient affiliation: an NPC-created carrier
may live on a player or Qq. Qf still decides masks, lifetime and corpse guards.
No new event, fabricated Qe, alive predicate or species allowlist is supplied.
"""
from collections.abc import Mapping


def _source_closure(fight, entries, provenance, roots):
    """Source ancestry is independent from native removal ownership."""
    result = set(roots)
    areas = {
        **getattr(fight, "native_retired_area_managers", {}),
        **getattr(fight, "native_effect_areas", {}),
    }

    def area_parent(container):
        if (
            container.get("container_kind") != "effect_area"
            and container.get("container_type") != 3
        ):
            return None
        area = areas.get(container.get("container_id"))
        return None if area is None else area.get("effect_uid")

    while True:
        count = len(result)
        for entry in entries:
            if entry.owner_uid in result or area_parent(vars(entry)) in result:
                result.add(entry.uid)
        for uid, record in provenance.items():
            if (
                record["parent_known"] and record["parent_state_uid"] in result
            ) or area_parent(record) in result:
                result.add(uid)
        if len(result) == count:
            return frozenset(result)


def _non_npc_sources(fight, entries, provenance):
    """Exclude actual item custody, even after native actor rebinding."""
    from .combat_equipment_finish import _qualified_sources

    initialized = getattr(fight, "native_owned_equipment_initializations", {}) or {}
    containers = set()
    if any(marker.get("sources") for marker in initialized.values()):
        # This validates all original owners' pins and initialized sources.
        # It is custody, not the recipient-filtered equipment event scope.
        for _owner, source, _states in _qualified_sources(fight):
            container = source["native_retained_container"]
            if (
                container.get("present") is True
                and container.get("type") == 12
                and container.get("native_kind") == "item"
            ):
                containers.add(container["id"])

    def item(record):
        return (
            record.get("container_present") is True
            and record.get("container_type") == 12
            and record.get("container_id") in containers
        )

    seeds = {entry.uid for entry in entries if item(vars(entry))}
    seeds.update(uid for uid, record in provenance.items() if item(record))
    seeds.update(
        binding["combat_uid"]
        for bindings in getattr(fight, "native_consumable_initializations", {}).values()
        for binding in bindings
    )
    for entry in entries:
        if entry.effect_class != 310:
            continue
        record = provenance.get(entry.uid)
        if (entry.container_kind == "state" or entry.container_type == 1) and (
            record is None or record["parent_known"] is not True
        ):
            # Legacy PL stores the state definition/grade, not its running UID.
            # Never guess which same-reference carrier was the actual source.
            seeds.add(entry.uid)
    for uid, record in provenance.items():
        if (
            record["container_known"] is not True
            or (record["container_kind"] == "state" or record["container_type"] == 1)
            and record["parent_known"] is not True
        ):
            seeds.add(uid)
    return _source_closure(fight, entries, provenance, seeds)


def has_npc_round_interest(fight):
    """Cheap queue interest only; delivery independently verifies authority."""
    for row in getattr(fight, "native_owned_group_effects", {}).values():
        invocation = row.get("invocation", {})
        actor = fight.actors.get(invocation.get("caster_id"))
        masks = row.get("native_subscription_masks")
        if (
            actor is not None
            and actor.controlled is False
            and isinstance(masks, (tuple, list))
            and len(masks) == 7
            and any(1004 in (masks[index] or ()) for index in (2, 5))
        ):
            return True
    return False


def qualified_npc_uids(dispatcher):
    """Verify real ordinary construction and registered retained source IDs."""
    from .combat_event_replay import NativeCloneAuthority
    from .combat_ordinary_events import OrdinaryHealingEvents
    from .combat_summon import ordinary_roster_authority
    from .combat_state_managers import state_managers
    from .combat_effect_removal import _readonly_hex_identity_fields
    from .combat_retained_source_provenance import state_source_provenance

    retention = dispatcher.native_retention
    fight = retention.fight
    authority = getattr(dispatcher, "native_clone_authority", None)
    if not isinstance(authority, NativeCloneAuthority):
        return frozenset()
    lifecycle = getattr(authority.executable, "__self__", None)
    if (
        not isinstance(lifecycle, OrdinaryHealingEvents)
        or getattr(authority.condition_context, "__self__", None) is not lifecycle
        or lifecycle.preview is not fight
        or lifecycle.retention is not retention
        or lifecycle.replay is not dispatcher.replay_event
        or not ordinary_roster_authority(lifecycle.adapter.actor_authority)
    ):
        return frozenset()
    entries = tuple(retention.view().entries)
    provenance = state_source_provenance(fight)
    excluded = _non_npc_sources(fight, entries, provenance)
    actors = lifecycle.adapter.actor_authority
    verified = {}

    def npc(identity):
        if identity not in verified:
            actor = fight.actors.get(identity)
            if actor is None or actor.controlled is not False:
                verified[identity] = False
            else:
                source = actors(fight, actor)
                verified[identity] = (
                    source.is_player is False
                    and source.is_summon is False
                    and source.native_actor_type == 1
                    and type(source.native_npc_prototype_ref) is int
                    and source.native_npc_prototype_ref > 0
                )
        return verified[identity]

    carriers = {
        state.uid: state
        for manager in state_managers(fight)
        for state in manager.state_ledger.entries
    }
    seeds = set()
    for entry in entries:
        # A physical item is equipment authority, never an NPC-source shortcut.
        if (
            entry.uid in excluded
            or entry.container_kind == "item"
            or entry.container_type == 12
        ):
            continue
        if entry.effect_class == 310:
            state = carriers.get(entry.uid)
            if state is not None and npc(state.caster_id):
                fields = _readonly_hex_identity_fields(
                    fight.state_wire_payloads[entry.uid]
                )
                if fields.get(6) != state.caster_id & ((1 << 64) - 1):
                    raise ValueError(
                        "NPC boundary carrier differs from its native caster"
                    )
                seeds.add(entry.uid)
            continue
        row = getattr(fight, "native_owned_group_effects", {}).get(entry.uid)
        if row is None:
            row = getattr(fight, "owned_stat_effects", {}).get(entry.uid)
        if not isinstance(row, Mapping):
            continue
        invocation = row.get("invocation")
        caster = (
            invocation.get("caster_id")
            if isinstance(invocation, Mapping)
            else row.get("caster_id")
        )
        if npc(caster):
            fields = _readonly_hex_identity_fields(row["payload"])
            if fields.get(6) != caster & ((1 << 64) - 1):
                raise ValueError("NPC boundary effect differs from its native caster")
            # The complete retained view has already checked this UID's real
            # payload, original generic definition, family and PL identities.
            seeds.add(entry.uid)
    return (_source_closure(fight, entries, provenance, seeds) - excluded) & frozenset(
        entry.uid for entry in entries
    )
