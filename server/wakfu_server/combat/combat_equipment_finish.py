"""Explicit Wakemu terminal1030 policy for actual owned equipment effects.

The installed client proves subscriptions, not the official server publisher.
This extends the existing documented outcome policy without broadcasting to
consumable counters or manufacturing a triggering running-effect context.
"""
from collections.abc import Mapping
from copy import deepcopy


def preflight_equipment_finish(factory, retained_container):
    """Attest the ordinary factory used by the installed terminal policy.

    The same original adapter construction supplies retention, external event
    replay and clone authority. This checks construction only; it does not run
    an event or claim that1030's original server publisher was recovered.
    """
    from .combat_equipment_retained_lifecycle import preflight

    return preflight(factory, retained_container)


def _closure(entries, roots):
    result = set(roots)
    while True:
        previous = len(result)
        result.update(entry.uid for entry in entries if entry.owner_uid in result)
        if len(result) == previous:
            return result


def _qualified_sources(fight):
    from .combat_owned_equipment_pin import (
        preparation_for_actor,
        execution_state_references,
    )
    from .combat_server_spell import compiled_runtime_catalog

    initialized = getattr(fight, "native_owned_equipment_initializations", {})
    result = []
    for actor_id, marker in initialized.items():
        if not marker.get("sources"):
            continue
        preparation = preparation_for_actor(fight, actor_id, compiled_runtime_catalog())
        actual = {
            (
                source["uid"],
                source["reference"],
                source["source_reference"],
                source["attachment_field"],
                tuple(source["roots"]),
            )
            for source in marker["sources"]
        }
        for source in preparation["sources"]:
            identity = (
                source["uid"],
                source["reference"],
                source["source_reference"],
                source["attachment_field"],
                tuple(source["roots"]),
            )
            if identity in actual:
                result.append(
                    (
                        actor_id,
                        source,
                        execution_state_references(
                            source,
                            preparation["compiled"],
                        ),
                    )
                )
    return tuple(result)


def _scope(fight, entries, sources):
    food = _closure(
        entries,
        {
            binding["combat_uid"]
            for bindings in getattr(
                fight, "native_consumable_initializations", {}
            ).values()
            for binding in bindings
        },
    )
    seeds = set()
    for owner_id, source, states in sources:
        container = source["native_retained_container"]
        if (
            container.get("present") is not True
            or container.get("type") != 12
            or container.get("native_kind") != "item"
            or container.get("is_spell") is not False
        ):
            raise ValueError("Equipment finish requires actual native item container")
        effects = source["effects"]
        definitions = {int(key): value for key, value in effects.items()}
        for entry in entries:
            if (
                entry.container_present is not True
                or entry.container_type != 12
                or entry.container_kind != "item"
                or entry.container_is_spell is not False
                or entry.container_id != container["id"]
            ):
                continue
            actor = fight.actors.get(owner_id)
            if actor is None:
                raise ValueError("Equipment finish source lost its owned actor")
            if entry.effect_class == 310:
                carrier = next(
                    (
                        row
                        for manager in fight.actors.values()
                        for row in manager.state_ledger.entries
                        if row.uid == entry.uid
                    ),
                    None,
                )
                if (
                    carrier is not None
                    and carrier.reference in states
                    and carrier.caster_id == owner_id
                ):
                    seeds.add(entry.uid)
            elif entry.generic_effect in definitions:
                # The retained PL belongs to the original owned caster. A
                # foreign source with the same gear reference cannot qualify.
                payload = next(
                    (
                        getattr(fight, name, {}).get(entry.uid)
                        for name in (
                            "owned_stat_effects",
                            "native_owned_group_effects",
                            "native_owned_area_effects",
                            "native_owned_spatial_effects",
                        )
                        if entry.uid in getattr(fight, name, {})
                    ),
                    None,
                )
                invocation = (
                    payload.get("invocation") if isinstance(payload, Mapping) else None
                )
                caster = (
                    invocation.get("caster_id")
                    if isinstance(invocation, Mapping)
                    else payload.get("caster_id")
                    if isinstance(payload, Mapping)
                    else None
                )
                if caster == owner_id:
                    seeds.add(entry.uid)
    return frozenset(_closure(entries, seeds) - food)


def prepare_equipment_finish(fight, runtime_factory, *, action_id):
    """Return a detached once-only terminal preview and its ordinary packets.

    Call after reward/progression settlement, before its final checkpoint, in
    the same guarded transaction. The caller adopts only on that transaction's
    successful publication and restores its old Fight on rollback.
    """
    from .combat_event_replay import NativeExternalEvent
    from .combat_retained_effects import NativeRetainedEffectView, RetainedEffect

    if (
        fight.phase != "finished"
        or type(fight.winner) is not int
        or fight.winner not in (0, 1)
    ):
        raise ValueError("Equipment finish requires a settled terminal fight")
    if getattr(fight, "native_equipment_finish_delivered", False):
        return fight, ()
    if not getattr(fight, "native_owned_equipment_initializations", None):
        return fight, ()
    # Most finished fights have no equipment finish listener. Do not construct
    # another native runtime or copy the fight for those unchanged outcomes.
    possible = set()
    for uid, row in getattr(fight, "native_owned_group_effects", {}).items():
        masks = row.get("native_subscription_masks")
        if (
            not isinstance(masks, (tuple, list))
            or len(masks) != 7
            or any(
                mask is not None
                and (
                    not isinstance(mask, (tuple, list))
                    or any(type(event) is not int for event in mask)
                )
                for mask in masks
            )
        ):
            raise ValueError("Malformed equipment finish subscription")
        if 1030 in (masks[5] or ()):
            possible.add(uid)
    if not possible:
        return fight, ()
    sources = _qualified_sources(fight)
    if not sources:
        return fight, ()
    live_entries = NativeRetainedEffectView(
        fight,
        (RetainedEffect(**row) for row in fight.native_retained_records.values()),
        population_verified_complete=getattr(fight, "native_retained_tracking", False),
    ).entries
    qualified = _scope(fight, live_entries, sources)
    if not possible.intersection(qualified):
        return fight, ()
    preview = deepcopy(fight)
    dispatcher, packets = runtime_factory(action_id=action_id)(
        preview,
        {"native_retained_container": {"present": False}},
    )
    retention = dispatcher.native_retention
    if retention.fight is not preview:
        raise ValueError("Equipment finish runtime belongs to another fight")
    entries = retention.view().entries
    eligible = _scope(preview, entries, sources)
    if eligible != qualified:
        raise ValueError("Equipment finish ownership changed during preparation")
    managers = sorted({entry.manager_id for entry in entries if entry.uid in eligible})
    phase, winner = preview.phase, preview.winner
    preview.phase = "active"
    try:
        with preview.effect_resolution():
            for manager_id in managers:
                dispatcher.replay_event(
                    NativeExternalEvent(manager_id, (1030,), 61),
                    authority=dispatcher.native_clone_authority,
                    eligible_uids=eligible,
                )
    finally:
        preview.phase, preview.winner = phase, winner
    preview.native_equipment_finish_delivered = True
    return preview, tuple(packets)
