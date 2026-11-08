"""Atomic due-clock removal of owned effects, including state-owned children."""
from wakfu_server import native_catalog as protocol_catalog
from copy import deepcopy
import json
from .combat_state_timing import StateTimer
from .combat_state_managers import state_manager, state_managers
from .combat_stat_handler import NativeStatHandler
from .combat_effect_removal import running_effect_removal
from wakfu_server.paths import DATA_ROOT
from .combat_retained_runtime import remove_owned_group, remove_owned_stat


def _due(timer, actor_id, round_number, phase, round_cleanup):
    return timer is not None and (
        timer.expires_at_round_cleanup(round_number)
        if round_cleanup
        else timer.expires_on(actor_id=actor_id, round_number=round_number, phase=phase)
    )


def _native_expiration_retention(preview, retention):
    from types import MethodType
    from .combat_retained_runtime import (
        NativeRetainedRuntime,
        _SOURCE_VIEW,
        _SOURCE_REMOVAL,
        _SOURCE_SYNCHRONIZE,
        _SOURCE_LIVE,
    )
    from .combat_stat_handler import _SOURCE_REMOVE
    from . import combat_state_managers as manager_source

    if (
        state_managers is not _EXPIRATION_STATE_MANAGERS
        or manager_source.state_managers is not _EXPIRATION_STATE_MANAGERS
        or type(retention) is not NativeRetainedRuntime
        or NativeRetainedRuntime.__getattribute__ is not object.__getattribute__
        or retention.fight is not preview
        or type(retention.stat_handler) is not NativeStatHandler
        or NativeStatHandler.__getattribute__ is not object.__getattribute__
        or retention.stat_handler.fight is not preview
    ):
        return False
    for name, original in (
        ("view", _SOURCE_VIEW),
        ("removal", _SOURCE_REMOVAL),
        ("synchronize", _SOURCE_SYNCHRONIZE),
        ("_live", _SOURCE_LIVE),
    ):
        provider = getattr(retention, name)
        if (
            type(provider) is not MethodType
            or provider.__self__ is not retention
            or provider.__func__ is not original
        ):
            return False
    remove = retention.stat_handler.remove
    return (
        type(remove) is MethodType
        and remove.__self__ is retention.stat_handler
        and remove.__func__ is _SOURCE_REMOVE
    )


def _reconcile_expiration_records(preview, retention):
    """The old final union includes pending carriers; preserve that distinction."""
    from . import combat_state_managers as manager_source

    if (
        not _native_expiration_retention(preview, retention)
        or state_managers is not _EXPIRATION_STATE_MANAGERS
        or manager_source.state_managers is not _EXPIRATION_STATE_MANAGERS
    ):
        return False
    from .combat_retained_registration_scope import native_membership_owner
    from .combat_retained_reconciliation import reconcile_registered_uids

    owner = native_membership_owner(preview)
    return owner is not None and reconcile_registered_uids(owner, frozenset())


def _remove_owned_areas(preview, packets, handler, action_id, uids, retention=None):
    """Remove actual owned area runners through their native Qf callbacks."""
    from .combat_retained_effects import (
        RetainedEffect,
        NativeRetainedEffectView,
        NativeRetainedRemoval,
        register_owned_removals,
    )

    if (
        _native_expiration_retention(preview, retention)
        and type(uids) is tuple
        and all(type(uid) is int for uid in uids)
    ):
        # Native synchronize already reconciles source/ledger membership and
        # prunes retired managers. Do not build and discard a second full view.
        retention.synchronize()
        removal_provider = retention.removal
        from types import SimpleNamespace
        from .combat_retained_removal_query import removal_view
        from .combat_retained_runtime import remove_now

        # These are requested identities, not authority: removal_view resolves
        # and validates their actual transitive, cross-manager removal closure.
        view = removal_view(retention, tuple(SimpleNamespace(uid=uid) for uid in uids))
        if view is None:
            view = retention.view()
        remove_now(
            retention, view, uids, _snapshot_uids=True, _provider=removal_provider
        )
        return

    # Earlier due carriers can already have removed their child
    # runners. Preserve a complete view of the remaining Qf rows.
    live = (
        set(preview.owned_stat_effects)
        | set(preview.state_wire_payloads)
        | set(preview.native_owned_group_effects)
        | set(getattr(preview, "native_owned_area_effects", {}))
        | set(getattr(preview, "native_owned_spatial_effects", {}))
        | {
            entry.uid
            for manager in state_managers(preview)
            for entry in manager.state_ledger.entries
        }
    )
    from .combat_retained_collections import replace_collection

    replace_collection(
        preview,
        "native_retained_records",
        {
            key: row
            for key, row in preview.native_retained_records.items()
            if key in live
        },
    )
    preview.native_retained_order[:] = [
        key for key in preview.native_retained_order if key in live
    ]
    view = NativeRetainedEffectView(
        preview,
        [
            RetainedEffect(**preview.native_retained_records[key])
            for key in preview.native_retained_order
        ],
        population_verified_complete=preview.native_retained_tracking,
    )
    if retention is not None:
        retention.synchronize()
        from .combat_retained_runtime import remove_now

        removal_provider = retention.removal
        remove_now(
            retention,
            retention.view(),
            uids,
            _snapshot_uids=True,
            _provider=removal_provider,
        )
    else:
        removal = NativeRetainedRemoval(view)
        register_owned_removals(
            removal, stat_handler=handler, packets=packets, action_id=action_id
        )
        removal.remove(tuple(uids))


def _prepare_timed_expiration_shared(
    fight,
    *,
    actor_id,
    round_number,
    phase,
    action_id,
    round_cleanup=False,
    registry=None,
    runtime_factory=None,
    _owned_runtime=None,
):
    """Return successful preview/outbox without publishing partial effects.

    Standalone callers retain atomic previews. An explicitly attested native
    delivery may reuse its private fight; its outer owner discards it on error.
    Call round_cleanup once on a new round, then start/end for the actual actor.
    No timer is inferred from durations or from a missing owned metadata record.
    """
    if (
        phase not in ("start", "end")
        or type(round_number) is not int
        or not 1 <= round_number < 32768
    ):
        raise ValueError("Explicit native clock phase/round required")
    if actor_id not in fight.actors or fight.phase != "active":
        raise ValueError("Invalid native expiration actor/fight")
    preview = (
        fight
        if _owns_expiration_preview(fight, _owned_runtime, runtime_factory)
        else deepcopy(fight)
    )
    packets = []
    if registry is None:
        registry = protocol_catalog.load(
            DATA_ROOT / "effect-characteristic-registry.json"
        )
    handler = NativeStatHandler(
        preview,
        packets,
        registry,
        action_id=action_id,
        allocate_uid=lambda: None,
        context=lambda *a: None,
    )
    retention = None
    if runtime_factory is not None:
        factory = runtime_factory(action_id=action_id)
        dispatcher, runtime_packets = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        retention = dispatcher.native_retention
        if retention.fight is not preview:
            raise ValueError("Expiration callbacks belong to another preview")
        packets = runtime_packets
        handler = retention.stat_handler
        delayed = getattr(dispatcher, "native_delays", None)
        if delayed is not None:
            delayed.boundary(
                actor_id=actor_id,
                round_number=round_number,
                phase=phase,
                round_cleanup=round_cleanup,
            )
    elif getattr(fight, "native_delay_queue", {}).get("entries"):
        raise ValueError("Delayed Qe boundary requires actual runtime factory")
    from .combat_expiration_boundary import collect_expiration_due, order_expiration_due

    due = collect_expiration_due(
        preview,
        actor_id=actor_id,
        round_number=round_number,
        phase=phase,
        round_cleanup=round_cleanup,
    )
    # Native TC stores callbacks in application order. The local owned UID
    # sequence follows application order; state carriers precede their children.
    with preview.effect_resolution():
        expiration = order_expiration_due(preview, due)
        for uid, kind, target_id in expiration.entries:
            if kind == "area":
                if uid not in getattr(preview, "native_owned_area_effects", {}):
                    continue
                _remove_owned_areas(
                    preview, packets, handler, action_id, (uid,), retention
                )
                continue
            if kind == "group":
                if uid in preview.native_owned_group_effects:
                    remove_owned_group(preview, packets, action_id=action_id, uid=uid)
                continue
            if kind == "stat":
                if uid in preview.owned_stat_effects:
                    remove_owned_stat(handler, uid)
                continue
            actor = state_manager(preview, target_id)
            if actor is None:
                raise ValueError("Missing actual expiring state manager")
            entries = [
                entry for entry in actor.state_ledger.entries if entry.uid == uid
            ]
            if not entries:
                continue
            payload = preview.state_wire_payloads.get(uid)
            if payload is None:
                raise ValueError("Missing owned expiring state carrier payload")
            area_children = tuple(
                child_uid
                for child_uid, child in getattr(
                    preview, "native_owned_area_effects", {}
                ).items()
                if child.get("state_uid") == uid
            )
            if area_children:
                # The parent PL remains present while child Qf callbacks run.
                # Their own duration may be indefinite; ownership still ends
                # with the carrier, subject to native keep-after removal.
                _remove_owned_areas(
                    preview, packets, handler, action_id, area_children, retention
                )
            for child_uid, child in tuple(preview.owned_stat_effects.items()):
                if child.get("state_uid") == uid:
                    remove_owned_stat(handler, child_uid)
            for child_uid, child in tuple(preview.native_owned_group_effects.items()):
                if child.get("state_uid") == uid:
                    remove_owned_group(
                        preview, packets, action_id=action_id, uid=child_uid
                    )
            packet = running_effect_removal(
                preview.id,
                action_id,
                effect_class=310,
                target_id=target_id,
                uid=uid,
                running_effect_payload=bytes.fromhex(payload),
            )
            actor.state_ledger.remove(uid)
            del preview.state_wire_payloads[uid]
            preview._event(
                "state_removed",
                actor_id=target_id,
                uid=uid,
                state_id=entries[0].reference,
                reason="expiration",
            )
            packets.append((13560, packet))
    if not _reconcile_expiration_records(preview, retention):
        live = (
            set(preview.owned_stat_effects)
            | set(preview.state_wire_payloads)
            | set(preview.native_owned_group_effects)
            | set(getattr(preview, "native_owned_area_effects", {}))
            | set(getattr(preview, "native_owned_spatial_effects", {}))
            | {
                entry.uid
                for manager in state_managers(preview)
                for entry in manager.state_ledger.entries
            }
        )
        from .combat_retained_collections import replace_collection

        replace_collection(
            preview,
            "native_retained_records",
            {
                uid: row
                for uid, row in preview.native_retained_records.items()
                if uid in live
            },
        )
        preview.native_retained_order[:] = [
            uid for uid in preview.native_retained_order if uid in live
        ]
    return preview, packets


def prepare_timed_expiration(fight, **clock):
    """Prepare the owned expiration boundary before adoption."""
    return _prepare_timed_expiration_shared(fight, **clock)


def expire_timed_effects(fight, **clock):
    previous_ids = set(fight.actors)
    preview, packets = prepare_timed_expiration(fight, **clock)
    if previous_ids != set(preview.actors):
        raise ValueError("Expiration changed actor roster")
    from .combat_area_boundary import adopt_fight

    adopt_fight(fight, preview)
    return packets


def _owns_expiration_preview(fight, runtime, factory):
    """Borrow only the exact fight already covered by native delivery rollback."""
    from .combat_runtime_messages import RuntimeMessages
    from .combat_state import Fight
    from .combat_expiration_provider import OwnedExpirationFactory
    from .combat_retained_gc_authority import capture_native_callbacks
    from .combat_native_action_ids import owned_native_delivery_fight

    if (
        type(runtime) is not RuntimeMessages
        or type(fight) is not Fight
        or RuntimeMessages.__getattribute__ is not object.__getattribute__
        or "fight" in vars(RuntimeMessages)
        or vars(runtime).get("fight") is not fight
        or type(factory) is not OwnedExpirationFactory
        or vars(runtime).get("expiration_runtime_factory") is not factory
        or vars(runtime).get("_native_delivery_depth") != 1
        or capture_native_callbacks(runtime) is None
    ):
        return False
    return owned_native_delivery_fight(runtime, fight) is fight


_EXPIRATION_STATE_MANAGERS = state_managers
