"""Operation-local selected-Qf validation; never a complete/removal view."""
from .combat_retained_effects import (
    RetainedEffect,
    _RetainedManagerPass,
    validate_retained_entry_identity,
)
from .combat_effect_removal import _identity_fields, _readonly_hex_identity_fields
from .combat_summon_initialization import registered_or_detached_actor


class NativeRetainedEventView:
    def __init__(
        self, fight, entries, *, manager_id, _manager_pass, _rows, _parents=()
    ):
        self.fight = fight
        self.entries = tuple(entries)
        self.by_uid = {}
        # Resolve each target once for this construction. Several retained Qf
        # entries commonly share a manager; area-manager resolution refreshes
        # and validates its native PV geometry, so repeating it per entry is
        # both redundant and needlessly expensive. Keep this index local to the
        # immutable view construction: later views must observe current fight
        # state and re-run the authority checks.
        if (
            type(_manager_pass) is not _RetainedManagerPass
            or _manager_pass.fight is not fight
            or not _manager_pass._consumed
        ):
            raise ValueError("Invalid private selected-manager proof")
        for entry in self.entries:
            validate_retained_entry_identity(entry, _manager_pass, self.by_uid)
        from .combat_pending_state import pending_state_uids

        pending = pending_state_uids(fight)
        known = {}
        for uid, row in _rows("owned_stat_effects"):
            if uid not in self.by_uid:
                continue
            fields = _readonly_hex_identity_fields(row["payload"])
            generic = fields.get(3)
            known[uid] = (
                row["target_id"],
                row["effect_class"],
                generic,
                row.get("state_uid"),
            )
        for actor in (_manager_pass.resolve(manager_id),):
            for state in actor.state_ledger.entries:
                if state.uid in pending:
                    continue  # Actual eZk iterator precedes its Qf registration.
                payload = fight.state_wire_payloads.get(state.uid)
                if payload is None:
                    raise ValueError("Missing native carrier wire ownership")
                fields = _readonly_hex_identity_fields(payload)
                generic = fields.get(3)
                if generic == (1 << 64) - 1:
                    generic = -1
                known[state.uid] = (actor.id, 310, generic, None)
        for uid, row in _rows("native_owned_group_effects"):
            if uid not in self.by_uid:
                continue
            fields = _readonly_hex_identity_fields(row["payload"])
            if row["target_id"] is None:
                from .combat_subscription_runners import GROUP_SUBSCRIPTION_FAMILIES

                entry = self.by_uid.get(uid)
                caster = fields.get(6)
                if caster is not None and caster >= (1 << 63):
                    caster -= 1 << 64
                if (
                    entry is None
                    or row["effect_class"] not in GROUP_SUBSCRIPTION_FAMILIES + (307,)
                    or 7 in fields
                    or registered_or_detached_actor(fight, caster) is None
                    or entry.manager_id != caster
                ):
                    raise ValueError("Unverified native cell group manager")
            if row["effect_class"] == 307:
                messages = {}
                _identity_fields(bytes.fromhex(row["payload"]), messages=messages)
                from .combat_retained_summon import retained_summon_actor

                native_actor_id = retained_summon_actor(bytes.fromhex(row["payload"]))
                if row.get(
                    "native_creation_source"
                ) != "eZl.c/eZR.d" or native_actor_id != row.get(
                    "native_summon_actor_id"
                ):
                    raise ValueError("Unverified native retained summon actor identity")
            known[uid] = (
                row["target_id"],
                row["effect_class"],
                fields.get(3),
                row.get("state_uid"),
            )
        for uid, row in _rows("native_owned_area_effects"):
            if uid not in self.by_uid:
                continue
            from .combat_private_target_aura import validate_private_target_aura

            validate_private_target_aura(fight, row)
            fields = _readonly_hex_identity_fields(row["payload"])
            entry = self.by_uid.get(uid)
            manager = row["caster_id"]
            if row["effect_class"] == 338:
                if row.get(
                    "native_manager_source"
                ) != "eYJ.PK.owner_on_caster" or row.get("native_manager_id") not in (
                    row["caster_id"],
                    row["target_id"],
                ):
                    raise ValueError("Missing native eYJ Qf manager provenance")
                manager = row["native_manager_id"]
            if (
                entry is None
                or entry.manager_id != manager
                or fields.get(6) != row["caster_id"] & ((1 << 64) - 1)
                or (
                    fields.get(7) != (row["target_id"] & ((1 << 64) - 1))
                    if row.get("target_id") is not None
                    else 7 in fields
                )
            ):
                raise ValueError("Unverified native area effect manager")
            known[uid] = (
                row["target_id"],
                row["effect_class"],
                fields.get(3),
                row.get("state_uid"),
            )
        for uid, row in _rows("native_owned_spatial_effects"):
            if uid not in self.by_uid:
                continue
            from .combat_pointer_qi_spatialowned import validate_spatial_record

            entry = self.by_uid.get(uid)
            if entry is None:
                raise ValueError("Complete Qf view omitted actual spatial runner")
            validate_spatial_record(fight, row, entry)
            known[uid] = (
                row["target_id"],
                937,
                row["generic_effect"],
                row["state_uid"],
            )
        if (
            {uid for uid in self.by_uid if uid in fight.state_wire_payloads}
            - set(known)
            - pending
        ):
            raise ValueError("Orphan native state payload")
        for uid, identity in known.items():
            entry = self.by_uid.get(uid)
            if entry is None:
                raise ValueError(
                    "Complete native view omitted an owned retained effect"
                )
            if (
                entry.target_id,
                entry.effect_class,
                entry.generic_effect,
                entry.owner_uid,
            ) != identity:
                raise ValueError(
                    "Native retained metadata disagrees with owned identity"
                )
        for entry in self.entries:
            if (
                entry.target_id is None
                and entry.uid not in getattr(fight, "native_owned_group_effects", {})
                and entry.uid not in getattr(fight, "native_owned_area_effects", {})
            ):
                raise ValueError("Target-less retained entry lacks owned cell group")
            if (
                entry.owner_uid is not None
                and entry.owner_uid not in self.by_uid
                and entry.owner_uid not in pending
                and entry.owner_uid not in _parents
            ):
                from .combat_native_container import owned_state_container

                owner = owned_state_container(fight, entry.owner_uid)
                if entry.container_present is not True or entry.container_type != 1:
                    raise ValueError(
                        "Native retained child owner lacks actual PL authority"
                    )
        self.known = known


class NativeRetainedEventPopulation:
    def __init__(self, retention, index, managers, frame):
        self.retention, self.fight = retention, retention.fight
        self.index, self.managers, self.frame = index, managers, frame
        managers.consume(self.fight)
        frame.counts["event_populations"] += 1

    def for_manager(self, identity):
        from .combat_structural_qf_scope import event_frame
        from .combat_global_pv_read_view import NativeGlobalPVReadView
        from .combat_pending_state import pending_state_uids
        from .combat_retained_runtime import _retained_record

        frame = event_frame(self.retention)
        if (
            frame is not self.frame
            or not self.index.valid
            or type(identity) is not int
            or identity not in self.fight.actors
        ):
            self.frame.counts["full_fallbacks"] += 1
            return self.retention.view()
        pv = NativeGlobalPVReadView(self.fight)
        try:
            registered = pv.registered(self.fight, identity)
            guards = pv.guards(self.fight, identity) if registered else None
        except ValueError:
            registered, guards = False, None
        if not registered or guards["baF"] is not True:
            frame.counts["full_fallbacks"] += 1
            return self.retention.view()
        ids = self.index.by_manager.get(identity, ())
        entries = tuple(
            frame.frozen_rows.read(
                self.fight, uid, self.fight.native_retained_records[uid]
            )
            for uid in ids
        )
        frame.counts["selected_conversions"] += len(entries)
        uids = set(ids)
        pending = pending_state_uids(self.fight)
        parents = self._root_carrier_witnesses(entries, uids, pending)
        if parents is None:
            frame.counts["cross_manager_fallbacks"] += 1
            return self.retention.view()
        result = NativeRetainedEventView(
            self.fight,
            entries,
            manager_id=identity,
            _manager_pass=self.managers,
            _rows=lambda name: self.index.rows(name, ids),
            _parents=parents,
        )
        frame.counts["selected_views"] += 1
        return result

    def _root_carrier_witnesses(self, entries, selected, pending):
        return root_carrier_witnesses(
            self.fight,
            self.index,
            self.managers,
            self.frame.frozen_rows,
            self.frame.counts,
            entries,
            selected,
            pending,
        )


def root_carrier_witnesses(
    fight, index, managers, frozen_rows, counts, entries, selected, pending
):
    from .combat_retained_runtime import _retained_record
    from .combat_state_ledger import RunningState, StateLedger

    witnesses = {}
    for child in entries:
        uid = child.owner_uid
        if uid is None or uid in selected or uid in pending or uid in witnesses:
            continue
        if type(uid) is not int:
            return None
        located = index.carriers.get(uid)
        record = fight.native_retained_records.get(uid)
        from .combat_retained_collections import TrackedRow

        if located is None or (
            type(record) is not dict and type(record) is not TrackedRow
        ):
            return None
        actor, state = located
        if (
            type(state) is not RunningState
            or type(actor.state_ledger) is not StateLedger
            or managers.resolve(actor.id) is not actor
            or not any(current is state for current in actor.state_ledger.entries)
            or state.uid != uid
            or type(record.get("uid")) is not int
            or record["uid"] != uid
            or record.get("effect_class") != 310
            or record.get("owner_uid") is not None
            or record.get("target_id") != actor.id
        ):
            return None
        # The witness is a live canonical carrier, never an owned row from
        # another source kind or a retired PL snapshot.
        if any(uid in getattr(fight, name, {}) for name in index.ordinals):
            return None
        payload = fight.state_wire_payloads.get(uid)
        if payload is None:
            raise ValueError("Missing native carrier wire ownership")
        entry = frozen_rows.read(fight, uid, record)
        counts["parent_conversions"] += 1
        validate_retained_entry_identity(entry, managers, witnesses)
        fields = _readonly_hex_identity_fields(payload)
        generic = fields.get(3)
        if generic == (1 << 64) - 1:
            generic = -1
        if (
            entry.target_id,
            entry.effect_class,
            entry.generic_effect,
            entry.owner_uid,
        ) != (actor.id, 310, generic, None):
            raise ValueError("Native retained metadata disagrees with owned identity")
        counts["root_carrier_witnesses"] += 1
    return witnesses
