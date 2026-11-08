"""Owned retained storage gateways; arbitrary supplied metadata stays opaque.

Payload rows in source maps remain actual caller objects. Only freshly produced
metadata passed to install_owned is copied into a tracked row. This module does
not certify state-ledger membership or replace native ownership validation.
"""
from copy import deepcopy
from weakref import ref, ReferenceType
from .combat_source_parent_index import SourceParentIndex, SOURCE_MAPS


AREA_SOURCE_NAMES = ("native_effect_areas", "native_retired_area_managers")


SOURCE_NAMES = (
    "owned_stat_effects",
    "state_wire_payloads",
    "native_owned_group_effects",
    "native_owned_area_effects",
    "native_owned_spatial_effects",
)


_ROOTED_COPY = object()


class _WeakOwner:
    """Weak routing edge; the Fight owns the registry's lifetime."""

    @property
    def owner(self):
        fields = vars(self)
        if "_owner_ref" not in fields:
            return fields.get("owner")
        reference = fields["_owner_ref"]
        return reference() if type(reference) is ReferenceType else None

    @owner.setter
    def owner(self, value):
        fields = vars(self)
        if type(self) in (OwnedMap, OwnedOrder, TrackedRow) and (
            value is None or type(value) is RetainedCollections
        ):
            fields.pop("owner", None)
            object.__setattr__(
                self, "_owner_ref", None if value is None else ref(value)
            )
        else:
            fields.pop("_owner_ref", None)
            fields["owner"] = value


def bind_fight_owner(fight, owner):
    fight._native_retained_owner = owner


def _copy_owner(value, memo):
    owner = value.owner
    # A detached standalone copy historically keeps its copied registry alive.
    # The actual Fight clone already supplies a strong root, even when actors
    # are visited before the explicit root attribute.
    anchor = (
        owner is not None
        and id(owner) not in memo
        and ((_ROOTED_COPY, id(owner)) not in memo)
    )
    return deepcopy(owner, memo), anchor


def _copied_owner(value, owner, anchor):
    if anchor:
        object.__setattr__(value, "_owner_anchor", owner)
    return value


class TrackedRow(_WeakOwner, dict):
    def _invalidate_owner_index(self):
        fields = vars(self)
        reference = fields.get("_owner_ref")
        owner = reference() if type(reference) is ReferenceType else fields.get("owner")
        uid = fields.get("uid")
        if (
            type(owner) is RetainedCollections
            and type(uid) is int
            and dict.get(owner.records, uid) is self
        ):
            owner.owner_opaque.add(uid)

    def _invalidate_scalar(self):
        TrackedRow._invalidate_owner_index(self)
        object.__setattr__(self, "_scalar_eligibility", None)
        from .combat_selected_scalar_proof import invalidate_record

        invalidate_record(self)

    def __init__(self, owner, uid, value):
        TrackedRow._invalidate_scalar(self)
        object.__setattr__(self, "_retained_value", None)
        dict.__init__(self, value)
        self.owner, self.uid = owner, uid

    def __setattr__(self, name, value):
        if (
            type(name) is str
            and name in ("owner", "uid", "_owner_ref") + _OWNER_ROW_READERS
        ):
            TrackedRow._invalidate_owner_index(self)
        if type(name) is str and name in ("owner", "uid", "_owner_ref"):
            from .combat_selected_scalar_proof import invalidate_record

            invalidate_record(self)
        object.__setattr__(self, name, value)
        if type(name) is str and name in ("owner", "uid", "_owner_ref"):
            invalidate_record(self)
        if type(name) is str and name in (
            "get",
            "values",
            "items",
            "keys",
            "__iter__",
            "__getitem__",
            "__len__",
        ):
            TrackedRow._invalidate_scalar(self)
            object.__setattr__(self, "_retained_value", None)
        if name == "get":
            fields = vars(self)
            owner, uid = self.owner, fields.get("uid")
            if (
                type(owner) is RetainedCollections
                and type(uid) is int
                and owner.records.get(uid) is self
            ):
                owner.retired_tracking.record_changed(uid)

    def __delattr__(self, name):
        if (
            type(name) is str
            and name in ("owner", "uid", "_owner_ref") + _OWNER_ROW_READERS
        ):
            TrackedRow._invalidate_owner_index(self)
        if type(name) is str and name in ("owner", "uid", "_owner_ref"):
            from .combat_selected_scalar_proof import invalidate_record

            invalidate_record(self)
        object.__delattr__(self, name)
        if type(name) is str and name in (
            "get",
            "values",
            "items",
            "keys",
            "__iter__",
            "__getitem__",
            "__len__",
        ):
            TrackedRow._invalidate_scalar(self)
            object.__setattr__(self, "_retained_value", None)
        if name == "get":
            fields = vars(self)
            owner, uid = self.owner, fields.get("uid")
            if (
                type(owner) is RetainedCollections
                and type(uid) is int
                and owner.records.get(uid) is self
            ):
                owner.retired_tracking.record_changed(uid)
                owner._owner_record_changed(uid)

    def _changed(self):
        TrackedRow._invalidate_scalar(self)
        object.__setattr__(self, "_retained_value", None)
        if (
            self.owner is not None
            and type(self.uid) is int
            and self.owner.records.get(self.uid) is self
        ):
            self.owner._record_changed(self.uid)

    def __setitem__(self, key, value):
        TrackedRow._invalidate_scalar(self)
        object.__setattr__(self, "_retained_value", None)
        dict.__setitem__(self, key, value)
        self._changed()

    def __delitem__(self, key):
        TrackedRow._invalidate_scalar(self)
        object.__setattr__(self, "_retained_value", None)
        dict.__delitem__(self, key)
        self._changed()

    def clear(self):
        TrackedRow._invalidate_scalar(self)
        object.__setattr__(self, "_retained_value", None)
        dict.clear(self)
        self._changed()

    def pop(self, key, *default):
        TrackedRow._invalidate_scalar(self)
        object.__setattr__(self, "_retained_value", None)
        result = dict.pop(self, key, *default)
        self._changed()
        return result

    def popitem(self):
        TrackedRow._invalidate_scalar(self)
        object.__setattr__(self, "_retained_value", None)
        result = dict.popitem(self)
        self._changed()
        return result

    def update(self, *args, **kwargs):
        TrackedRow._invalidate_scalar(self)
        object.__setattr__(self, "_retained_value", None)
        for key, value in dict(*args, **kwargs).items():
            self[key] = value

    def setdefault(self, key, value=None):
        TrackedRow._invalidate_scalar(self)
        object.__setattr__(self, "_retained_value", None)
        if key not in self:
            self[key] = value
        return self[key]

    def __ior__(self, value):
        TrackedRow._invalidate_scalar(self)
        object.__setattr__(self, "_retained_value", None)
        self.update(value)
        return self

    def __deepcopy__(self, memo):
        owner, anchor = _copy_owner(self, memo)
        if id(self) in memo:
            return _copied_owner(memo[id(self)], owner, anchor)
        # A caller may retain an old row after replacement or deletion.
        # Its historical value must not turn into the current registered row.
        result = TrackedRow(owner, self.uid, deepcopy(dict(self), memo))
        memo[id(self)] = result
        return _copied_owner(result, owner, anchor)


class OwnedMap(_WeakOwner, dict):
    def __init__(self, owner, name):
        self.owner, self.name = owner, name

    def _active(self):
        owner = self.owner
        if owner is None:
            return False
        current = (
            owner.records
            if self.name == "records"
            else owner.actors
            if self.name == "actors"
            else owner.area_sources[self.name]
            if self.name in AREA_SOURCE_NAMES
            else owner.sources[self.name]
        )
        return current is self

    def _notify(self, uid):
        if self._active():
            if type(uid) is not int:
                self.owner.valid = False
                return
            self.owner._map_changed(self.name, uid)

    def __setitem__(self, uid, row):
        # Never convert a mutable external alias into an apparently owned row.
        if self.name == "records" and self._active():
            self.owner.valid = False
        dict.__setitem__(self, uid, row)
        self._notify(uid)

    def install_owned(self, uid, row, *, _clone=False):
        if self.name != "records" or type(row) is not dict:
            raise ValueError("Fresh exact metadata dictionary required")
        # Retained metadata is scalar-only; reject a shallow nested alias.
        if any(type(key) is not str for key in row):
            raise ValueError("Retained metadata keys must be exact strings")
        if any(
            value is not None
            and not (type(value) is int or type(value) is str or type(value) is bool)
            for value in row.values()
        ):
            raise ValueError("Retained metadata must contain owned scalar facts")
        owned = TrackedRow(self.owner, uid, row)
        dict.__setitem__(self, uid, owned)
        if (
            _clone
            and type(uid) is int
            and type(self) is OwnedMap
            and type(self.owner) is RetainedCollections
            and self.owner.records is self
            and TrackedRow.__iter__ is dict.__iter__
            and TrackedRow.__getattribute__ is dict.__getattribute__
            and TrackedRow.__init__ is _CLONE_ROW_INIT
            and TrackedRow.__setattr__ is _CLONE_ROW_SETATTR
            and OwnedMap._notify is _CLONE_NOTIFY
            and RetainedCollections._map_changed is _CLONE_MAP_CHANGED
            and RetainedCollections._record_changed is _CLONE_RECORD_CHANGED
        ):
            # This fresh exact dictionary was checked immediately above. No
            # callback runs between that check and native index publication.
            self.owner._record_changed(uid, _keys_checked=True)
            self.owner._membership_changed(uid)
        else:
            self._notify(uid)
        return owned

    def __delitem__(self, uid):
        dict.__delitem__(self, uid)
        self._notify(uid)

    def clear(self):
        for uid in tuple(self):
            del self[uid]

    def pop(self, uid, *default):
        if type(uid) is not int:
            result = dict.pop(self, uid, *default)
            self._notify(uid)
            return result
        if uid not in self:
            return dict.pop(self, uid, *default)
        value = self[uid]
        del self[uid]
        return value

    def popitem(self):
        if not self:
            raise KeyError("popitem(): dictionary is empty")
        uid = next(reversed(self))
        return uid, self.pop(uid)

    def update(self, *args, **kwargs):
        for uid, row in dict(*args, **kwargs).items():
            self[uid] = row

    def setdefault(self, uid, row=None):
        if uid not in self:
            self[uid] = row
        return self[uid]

    def __ior__(self, value):
        self.update(value)
        return self

    def __deepcopy__(self, memo):
        owner, anchor = _copy_owner(self, memo)
        if id(self) in memo:
            return _copied_owner(memo[id(self)], owner, anchor)
        result = OwnedMap(owner, self.name)
        memo[id(self)] = result
        for uid, row in self.items():
            dict.__setitem__(result, deepcopy(uid, memo), deepcopy(row, memo))
        return _copied_owner(result, owner, anchor)


class OwnedOrder(_WeakOwner, list):
    def __init__(self, owner):
        self.owner = owner

    def _changed(self):
        self.owner.order_dirty = True

    def append(self, uid):
        list.append(self, uid)
        if (
            not self.owner.order_dirty
            and type(uid) is int
            and uid not in self.owner.ordinals
        ):
            self.owner.ordinals[uid] = len(self) - 1
            self.owner._order_membership_changed(uid)
        else:
            self._changed()

    def extend(self, values):
        if values is self:
            values = tuple(values)
        for uid in values:
            self.append(uid)

    def __setitem__(self, key, value):
        list.__setitem__(self, key, value)
        self._changed()

    def __delitem__(self, key):
        list.__delitem__(self, key)
        self._changed()

    def insert(self, index, value):
        list.insert(self, index, value)
        self._changed()

    def pop(self, index=-1):
        result = list.pop(self, index)
        self._changed()
        return result

    def remove(self, value):
        list.remove(self, value)
        self._changed()

    def clear(self):
        list.clear(self)
        self.owner.ordinals.clear()
        self.owner.order_mismatch = set(self.owner.records)
        self.owner.order_dirty = False

    def reverse(self):
        list.reverse(self)
        self._changed()

    def sort(self, *args, **kwargs):
        try:
            list.sort(self, *args, **kwargs)
        finally:
            self._changed()

    def __iadd__(self, values):
        self.extend(values)
        return self

    def __imul__(self, count):
        list.__imul__(self, count)
        self._changed()
        return self

    def __deepcopy__(self, memo):
        owner, anchor = _copy_owner(self, memo)
        return _copied_owner(owner.order, owner, anchor)


class RetainedCollections:
    def __init__(self):
        from .combat_selected_scalar_proof import SelectedScalarProofs

        self._selected_scalar_proofs = SelectedScalarProofs()
        self.valid = True
        self.by_owner_uid = {}
        self.record_owners = {}
        self.owner_opaque = set()
        self.by_manager = {}
        self.managers = {}
        self.live_keys = {name: set() for name in SOURCE_NAMES}
        self.source_counts = {}
        self.source_ordinals = {name: {} for name in SOURCE_NAMES}
        self.source_next = {name: 0 for name in SOURCE_NAMES}
        self.unmatched = set()
        self.duplicate_sources = set()
        self.ordinals = {}
        self.order_mismatch = set()
        self.order_dirty = False
        self.records = OwnedMap(self, "records")
        self.order = OwnedOrder(self)
        self.actors = OwnedMap(self, "actors")
        self.sources = {name: OwnedMap(self, name) for name in SOURCE_NAMES}
        self.source_parents = SourceParentIndex(
            {name: self.sources[name] for name in SOURCE_MAPS}
        )
        self.area_sources = {name: OwnedMap(self, name) for name in AREA_SOURCE_NAMES}
        self.area_conflicts = set()
        # Constructor scopes are synchronous, ephemeral, and never cloned or
        # serialized with a Fight. They do not enter the actual fighter roster.
        self.detached_actors = {}
        from .combat_state_membership import reset_membership

        reset_membership(self)
        from .combat_retired_area_tracking import RetiredAreaTracking

        self.retired_tracking = RetiredAreaTracking(self)

    def _notify_live_before(self, uid):
        for scope in tuple(getattr(self, "_live_scopes", ())):
            scope.touch(uid)

    def _invalidate_live_scopes(self):
        for scope in tuple(getattr(self, "_live_scopes", ())):
            scope.freeze_membership()

    def _owner_record_changed(self, uid, *, _keys_checked=False):
        if type(uid) is not int:
            self.valid = False
            return
        previous = self.record_owners.pop(uid, None)
        if previous is not None:
            bucket = self.by_owner_uid[previous]
            bucket.discard(uid)
            if not bucket:
                del self.by_owner_uid[previous]
        self.owner_opaque.discard(uid)
        row = dict.get(self.records, uid)
        if row is None:
            return
        if (
            type(row) is not TrackedRow
            or row.owner is not self
            or type(row.uid) is not int
            or row.uid != uid
            or type(dict.get(row, "uid")) is not int
            or dict.get(row, "uid") != uid
            or any(name in vars(row) for name in _OWNER_ROW_READERS)
            or (
                not _keys_checked
                and any(type(key) is not str for key in dict.keys(row))
            )
        ):
            self.owner_opaque.add(uid)
            return
        parent = dict.get(row, "owner_uid")
        if parent is None:
            return
        if type(parent) is not int:
            self.owner_opaque.add(uid)
            return
        self.record_owners[uid] = parent
        self.by_owner_uid.setdefault(parent, set()).add(uid)

    def owned_children(self, uid):
        """Fresh inverse owner edges, in native retained order; None is opaque."""
        if (
            type(uid) is not int
            or not self.valid
            or self.owner_opaque
            or self.order_dirty
            or any(
                getattr(cls, name) is not method for cls, name, method in _OWNER_METHODS
            )
            or type(self.records) is not OwnedMap
            or any(name in vars(self.records) for name in _OWNER_ROW_READERS)
        ):
            return None
        if self.order_mismatch:
            return None
        return tuple(
            sorted(self.by_owner_uid.get(uid, ()), key=self.ordinals.__getitem__)
        )

    def _record_changed(self, uid, *, _keys_checked=False):
        self._owner_record_changed(uid, _keys_checked=_keys_checked)
        self._selected_scalar_proofs.invalidate(uid)
        self.retired_tracking.record_changed(uid)
        if type(uid) is not int:
            self.valid = False
            return
        previous = self.managers.pop(uid, None)
        if previous is not None:
            bucket = self.by_manager[previous]
            bucket.discard(uid)
            if not bucket:
                del self.by_manager[previous]
        row = self.records.get(uid)
        if row is None:
            return
        if (
            type(uid) is not int
            or type(row) is not TrackedRow
            or row.owner is not self
            or row.uid != uid
            or (not _keys_checked and any(type(key) is not str for key in row))
            or type(row.get("uid")) is not int
            or row.get("uid") != uid
            or type(row.get("manager_id")) is not int
        ):
            self.valid = False
            return
        manager = row["manager_id"]
        self.managers[uid] = manager
        self.by_manager.setdefault(manager, set()).add(uid)

    def _area_conflict_changed(self, uid):
        active = uid in self.area_sources["native_effect_areas"]
        retired = uid in self.area_sources["native_retired_area_managers"]
        if (active and retired) or ((active or retired) and uid in self.actors):
            self.area_conflicts.add(uid)
        else:
            self.area_conflicts.discard(uid)

    def _map_changed(self, name, uid):
        self._selected_scalar_proofs.invalidate(uid)
        if name in SOURCE_MAPS:
            self.source_parents.bind(name, uid)
        if type(uid) is not int:
            self.valid = False
            return
        if name == "actors":
            self._area_conflict_changed(uid)
            from .combat_state_membership import attach_actor, detach_actor

            if uid in self.actors:
                attach_actor(self, uid, self.actors[uid])
            else:
                detach_actor(self, uid)
            return
        if name in AREA_SOURCE_NAMES:
            self.retired_tracking.area_changed(uid)
            from .combat_state_membership import attach_area, detach_area

            self._area_conflict_changed(uid)
            if uid in self.area_sources[name]:
                attach_area(self, uid, self.area_sources[name][uid], role=name)
            else:
                detach_area(self, uid, role=name)
            return
        if name == "records":
            self._record_changed(uid)
        else:
            was_present = uid in self.live_keys[name]
            present = uid in self.sources[name]
            if present and type(uid) is not int:
                self.valid = False
            if present != was_present:
                self._notify_live_before(uid)
                count = self.source_counts.get(uid, 0) + (1 if present else -1)
                if count:
                    self.source_counts[uid] = count
                else:
                    self.source_counts.pop(uid, None)
                if present:
                    self.live_keys[name].add(uid)
                    self.source_ordinals[name][uid] = self.source_next[name]
                    self.source_next[name] += 1
                else:
                    self.live_keys[name].discard(uid)
                    self.source_ordinals[name].pop(uid, None)
                if count > 1:
                    self.duplicate_sources.add(uid)
                else:
                    self.duplicate_sources.discard(uid)
        self._membership_changed(uid)

    def _membership_changed(self, uid):
        self._order_membership_changed(uid)
        if (uid in self.records) != (uid in self.source_counts):
            self.unmatched.add(uid)
        else:
            self.unmatched.discard(uid)

    def consistent(self, pending=()):
        self._refresh_order()
        if not self.valid or self.duplicate_sources or self.order_mismatch:
            return False
        pending = frozenset(pending)
        # A pending carrier can be removed by its own child callbacks before
        # the registration scope exits. Such an absent UID contributes nothing
        # to the live population; only present sources need pending exclusion.
        return (
            len(self.unmatched) <= len(pending)
            and all(
                uid in pending and uid in self.source_counts and uid not in self.records
                for uid in self.unmatched
            )
            and all(uid not in self.records for uid in pending)
        )

    def source_uids(self, name, selected_uids=None):
        if selected_uids is None:
            return self.sources[name].keys()
        order = self.source_ordinals[name]
        return tuple(
            sorted(
                (uid for uid in selected_uids if uid in order), key=order.__getitem__
            )
        )

    def manager_uids(self, identity):
        return self.ordered_uids(identity)

    def ordered_uids(self, manager):
        self._refresh_order()
        if not self.valid or self.order_mismatch:
            raise ValueError("Retained collection authority requires fallback")
        selected = self.by_manager.get(manager, ())
        return tuple(sorted(selected, key=self.ordinals.__getitem__))

    def _order_membership_changed(self, uid):
        if (uid in self.records) != (uid in self.ordinals):
            self.order_mismatch.add(uid)
        else:
            self.order_mismatch.discard(uid)

    def _refresh_order(self):
        if not self.valid:
            return
        if self.order_dirty:
            self.ordinals = {}
            for position, uid in enumerate(self.order):
                if type(uid) is not int or uid in self.ordinals:
                    self.valid = False
                    break
                self.ordinals[uid] = position
            self.order_dirty = False
            self.order_mismatch = set(self.records).symmetric_difference(self.ordinals)

    def __deepcopy__(self, memo):
        result = type(self)()
        memo[id(self)] = result
        memo[id(self.records)] = result.records
        memo[id(self.order)] = result.order
        memo[id(self.actors)] = result.actors
        for name, source in self.sources.items():
            memo[id(source)] = result.sources[name]
        for name, source in self.area_sources.items():
            memo[id(source)] = result.area_sources[name]
        if self.retired_tracking.facts is not None:
            result.retired_tracking.bind_facts(
                deepcopy(self.retired_tracking.facts, memo)
            )
        transfer_roots = _native_record_clone_batch(self, result)
        fresh_rows = transfer_roots and TrackedRow.__new__ is dict.__new__
        seed_indexes = fresh_rows and not any(
            (
                result.by_manager,
                result.managers,
                result.by_owner_uid,
                result.record_owners,
                result.owner_opaque,
            )
        )
        for uid, row in self.records.items():
            if transfer_roots and not (
                type(uid) is int
                and type(row) is TrackedRow
                and row.owner is self
                and type(row.uid) is int
                and row.uid == uid
                and not any(name in vars(row) for name in _OWNER_ROW_READERS)
                and (
                    uid in self.retired_tracking.records_dirty
                    or ("record", uid) in self.retired_tracking.graph.tokens
                    or ("record", uid) in self.retired_tracking.graph.opaque
                )
            ):
                transfer_roots = False
            fresh_rows = fresh_rows and transfer_roots
            if type(row) is TrackedRow and row.owner is self:
                if (
                    fresh_rows
                    and type(uid) is int
                    and type(row.uid) is int
                    and row.uid == uid
                    and not any(name in vars(row) for name in _OWNER_ROW_READERS)
                ):
                    # No arbitrary callback runs in this certified metadata-only
                    # segment. The fresh row has no prior binding to invalidate.
                    payload = dict(row)
                    if any(type(key) is not str for key in payload):
                        raise ValueError("Retained metadata keys must be exact strings")
                    if any(
                        value is not None
                        and not (
                            type(value) is int
                            or type(value) is str
                            or type(value) is bool
                        )
                        for value in payload.values()
                    ):
                        raise ValueError(
                            "Retained metadata must contain owned scalar facts"
                        )
                    cloned = dict.__new__(TrackedRow)
                    dict.__init__(cloned, payload)
                    object.__setattr__(cloned, "_scalar_eligibility", None)
                    object.__setattr__(cloned, "_retained_value", None)
                    object.__setattr__(cloned, "_owner_ref", ref(result))
                    object.__setattr__(cloned, "uid", uid)
                    dict.__setitem__(result.records, uid, cloned)
                    if seed_indexes:
                        _seed_fresh_record_indexes(result, uid, payload)
                    else:
                        result._record_changed(uid, _keys_checked=True)
                        result._membership_changed(uid)
                elif (
                    getattr(result.records.install_owned, "__func__", None)
                    is _CLONE_INSTALL
                ):
                    fresh_rows = False
                    cloned = result.records.install_owned(uid, dict(row), _clone=True)
                else:
                    fresh_rows = False
                    cloned = result.records.install_owned(uid, dict(row))
                memo[id(row)] = cloned
            else:
                fresh_rows = False
                result.records[deepcopy(uid, memo)] = deepcopy(row, memo)
        if transfer_roots and _native_record_clone_batch(self, result, finished=True):
            result.retired_tracking.copy_record_roots_from(self.retired_tracking)
        result.order.extend(deepcopy(list(self.order), memo))
        for name, source in self.sources.items():
            for uid, row in source.items():
                result.sources[name][deepcopy(uid, memo)] = deepcopy(row, memo)
        for uid, actor in self.actors.items():
            result.actors[deepcopy(uid, memo)] = deepcopy(actor, memo)
        for name, source in self.area_sources.items():
            for uid, row in source.items():
                result.area_sources[name][deepcopy(uid, memo)] = deepcopy(row, memo)
        result.valid = result.valid and self.valid
        return result


_FIELDS = {
    "native_retained_records": "records",
    "actors": "actors",
    **{name: name for name in SOURCE_NAMES},
}


def bound_collections(fields):
    """Prove exact storage binding without traversing any retained population."""
    if type(fields) is not dict:
        return None
    records = fields.get("native_retained_records")
    if (
        type(records) is not OwnedMap
        or type(records.name) is not str
        or records.name != "records"
        or type(records.owner) is not RetainedCollections
    ):
        return None
    owner = records.owner
    if fields.get("_native_retained_owner") is not owner:
        return None
    if owner.records is not records or type(owner.sources) is not dict:
        return None
    order = fields.get("native_retained_order")
    if (
        type(order) is not OwnedOrder
        or order is not owner.order
        or order.owner is not owner
    ):
        return None
    for field, name in _FIELDS.items():
        rows = fields.get(field)
        expected = (
            owner.records
            if name == "records"
            else owner.actors
            if name == "actors"
            else owner.sources.get(name)
        )
        if (
            type(rows) is not OwnedMap
            or rows is not expected
            or rows.owner is not owner
            or type(rows.name) is not str
            or rows.name != name
        ):
            return None
    return owner


def owned_metadata_row(owner, uid, row):
    """Certify one current row, excluding detached aliases and opaque keys."""
    return (
        type(owner) is RetainedCollections
        and type(uid) is int
        and type(row) is TrackedRow
        and row.owner is owner
        and type(row.uid) is int
        and row.uid == uid
        and owner.records.get(uid) is row
    )


def bind_adopted_actors(fight, actors):
    """Rebind an adopted actor map while preserving its outer object and actors."""
    fight.actors = actors
    records = getattr(fight, "native_retained_records", None)
    if (
        type(records) is not OwnedMap
        or type(records.owner) is not RetainedCollections
        or type(records.name) is not str
        or records.name != "records"
        or records.owner.records is not records
        or type(actors) is not OwnedMap
        or type(actors.name) is not str
        or actors.name != "actors"
    ):
        return actors
    owner = records.owner
    bind_fight_owner(fight, owner)
    from .combat_state_membership import detach_actor

    previous_keys = tuple(owner.actors)
    actors.owner = owner
    owner.actors = actors
    for uid in previous_keys:
        if type(uid) is int and uid not in actors:
            detach_actor(owner, uid)
            owner._area_conflict_changed(uid)
    for uid in actors:
        owner._map_changed("actors", uid)
    return actors


def _rebuild(owner):
    owner.source_parents = SourceParentIndex(
        {name: owner.sources[name] for name in SOURCE_MAPS}
    )
    """Explicit storage replacement/restore boundary, never a query-time scan."""
    owner.by_owner_uid.clear()
    owner.record_owners.clear()
    owner.owner_opaque.clear()
    owner.by_manager.clear()
    owner.managers.clear()
    owner.source_counts.clear()
    owner.unmatched.clear()
    owner.duplicate_sources.clear()
    for name in SOURCE_NAMES:
        owner.live_keys[name].clear()
        owner.source_ordinals[name].clear()
        owner.source_next[name] = 0
    owner.order_dirty = True
    owner._refresh_order()
    from .combat_state_membership import reset_membership

    reset_membership(owner)
    for uid in owner.actors:
        owner._map_changed("actors", uid)
    for uid in owner.records:
        owner._map_changed("records", uid)
    for name, rows in owner.sources.items():
        for uid in rows:
            owner._map_changed(name, uid)


def restore_collections(fight):
    """Bind codec-tagged unbound storage without replacing any aliased object."""
    maps = {field: getattr(fight, field, None) for field in _FIELDS}
    order = getattr(fight, "native_retained_order", None)
    if (
        type(order) is not OwnedOrder
        or getattr(order, "owner", None) is not None
        or any(
            type(rows) is not OwnedMap
            or rows.owner is not None
            or rows.name != _FIELDS[field]
            for field, rows in maps.items()
        )
    ):
        raise ValueError("Restore requires exact unbound native retained storage")
    owner = RetainedCollections()
    owner.records = maps["native_retained_records"]
    owner.actors = maps["actors"]
    owner.sources = {name: maps[name] for name in SOURCE_NAMES}
    owner.order = order
    for rows in maps.values():
        rows.owner = owner
    order.owner = owner
    for uid, row in owner.records.items():
        if type(row) is TrackedRow and row.owner is None:
            if row.uid is not None and (type(row.uid) is not int or row.uid != uid):
                owner.valid = False
            row.owner, row.uid = owner, uid
        else:
            owner.valid = False
    bind_fight_owner(fight, owner)
    _rebuild(owner)
    owner.retired_tracking.bind_facts(
        getattr(fight, "native_owned_state_containers", None)
    )
    return owner


def replace_collection(fight, field, values):
    """Explicit native replacement preserves values and detached outer aliases."""
    if field not in _FIELDS:
        raise ValueError("Unsupported retained collection replacement")
    records = getattr(fight, "native_retained_records", None)
    if type(records) is not OwnedMap or type(records.owner) is not RetainedCollections:
        setattr(fight, field, values)
        return values  # Legacy/opaque storage keeps the generic consumer path.
    owner, name = records.owner, _FIELDS[field]
    replacement = OwnedMap(owner, name)
    previous_records = owner.records
    incremental_records = (
        name == "records"
        and owner.valid
        and type(values) is dict
        and type(previous_records) is OwnedMap
        and previous_records.owner is owner
        and previous_records.name == "records"
        and TrackedRow.__getattribute__ is dict.__getattribute__
        and TrackedRow.get is dict.get
    )
    unchanged = set()
    for uid, row in values.items():
        dict.__setitem__(replacement, uid, row)
        if incremental_records:
            if (
                type(uid) is not int
                or type(row) is not TrackedRow
                or row.owner is not owner
                or type(row.uid) is not int
                or row.uid != uid
                or "get" in vars(row)
            ):
                incremental_records = False
            elif dict.get(previous_records, uid) is row:
                unchanged.add(uid)
    if name == "records":
        previous_records = owner.records
        old_keys = set(owner.managers)
        owner.records = replacement
        if not incremental_records:
            owner.by_manager.clear()
            owner.managers.clear()
    elif name == "actors":
        old_keys = tuple(owner.actors)
        owner.actors = replacement
    else:
        old_keys = set(owner.live_keys[name])
        owner.sources[name] = replacement
        owner.source_parents = SourceParentIndex(
            {key: owner.sources[key] for key in SOURCE_MAPS}
        )
    setattr(fight, field, replacement)
    if name == "actors":
        from .combat_state_membership import detach_actor

        for uid in old_keys:
            if type(uid) is int and uid not in replacement:
                detach_actor(owner, uid)
                owner._area_conflict_changed(uid)
        for uid in replacement:
            owner._map_changed("actors", uid)
    else:
        new_keys = set()
        for uid in replacement:
            if type(uid) is not int:
                owner.valid = False
                continue
            new_keys.add(uid)
        for uid in old_keys | new_keys:
            if incremental_records and uid in unchanged:
                # Mutation gateways already maintain this row's manager/root.
                # Preserve existing dirty roots and source/order bookkeeping.
                owner._membership_changed(uid)
            else:
                owner._map_changed(name, uid)
        if name != "records":
            # Replacing a source can reorder surviving keys. Rebuild only its
            # own ordinal vector, not metadata or any other source population.
            owner.source_ordinals[name] = {
                uid: ordinal
                for ordinal, uid in enumerate(replacement)
                if type(uid) is int
            }
            owner.source_next[name] = len(replacement)
    return replacement


def bound_area_collections(fields, owner):
    """Prove current area namespace bindings without reading historical rows."""
    if (
        type(fields) is not dict
        or type(owner) is not RetainedCollections
        or type(owner.area_sources) is not dict
        or owner.area_conflicts
    ):
        return False
    for name in AREA_SOURCE_NAMES:
        rows = fields.get(name)
        if (
            type(rows) is not OwnedMap
            or rows.owner is not owner
            or type(rows.name) is not str
            or rows.name != name
            or owner.area_sources.get(name) is not rows
        ):
            return False
    return True


def restore_area_collections(fight):
    """Bind freshly decoded area maps at the explicit graph restore boundary."""
    owner = bound_collections(vars(fight))
    if owner is None:
        raise ValueError("Area restore requires bound native retained storage")
    maps = {name: getattr(fight, name, None) for name in AREA_SOURCE_NAMES}
    if any(
        type(rows) is not OwnedMap
        or rows.owner is not None
        or type(rows.name) is not str
        or rows.name != name
        for name, rows in maps.items()
    ):
        raise ValueError("Area restore requires exact unbound area storage")
    owner.area_sources = maps
    owner.area_conflicts.clear()
    for rows in maps.values():
        rows.owner = owner
    for name, rows in maps.items():
        for uid in rows:
            owner._map_changed(name, uid)
    return owner


# Captured native methods fence the clone-only publication shortcut.
_CLONE_NOTIFY = OwnedMap._notify
_CLONE_MAP_CHANGED = RetainedCollections._map_changed
_CLONE_RECORD_CHANGED = RetainedCollections._record_changed

_CLONE_INSTALL = OwnedMap.install_owned
_CLONE_ROW_INIT = TrackedRow.__init__
_CLONE_ROW_SETATTR = TrackedRow.__setattr__


_OWNER_ROW_READERS = (
    "get",
    "values",
    "items",
    "keys",
    "__iter__",
    "__getitem__",
    "__len__",
    "__getattribute__",
)
_OWNER_METHODS = tuple(
    (cls, name, getattr(cls, name))
    for cls, names in (
        (
            TrackedRow,
            _OWNER_ROW_READERS
            + (
                "__setattr__",
                "__delattr__",
                "__setitem__",
                "__delitem__",
                "clear",
                "pop",
                "popitem",
                "update",
                "setdefault",
                "__ior__",
                "_invalidate_owner_index",
                "_invalidate_scalar",
                "_changed",
                "__init__",
            ),
        ),
        (
            OwnedMap,
            _OWNER_ROW_READERS
            + (
                "install_owned",
                "__setitem__",
                "__delitem__",
                "clear",
                "pop",
                "popitem",
                "update",
                "setdefault",
                "__ior__",
            ),
        ),
        (
            RetainedCollections,
            ("_owner_record_changed", "_record_changed", "_map_changed"),
        ),
    )
    for name in names
)


# One proof per scalar metadata batch, not one reflective proof per record.
# Facts have already been copied; later source/actor/area callbacks retain all
# normal dirty notifications against the independently copied primitive graph.
def _native_record_clone_batch(source, target, *, finished=False):
    from .combat_retired_area_tracking import RetiredAreaTracking
    from .combat_retired_area_index import RetiredAreaIndex
    from . import combat_selected_scalar_proof as scalar_proof

    SelectedScalarProofs = scalar_proof.SelectedScalarProofs
    if (
        type(source) is not RetainedCollections
        or type(target) is not RetainedCollections
        or not source.valid
        or not target.valid
        or any(getattr(cls, name) is not method for cls, name, method in _BATCH_METHODS)
        or scalar_proof.invalidate_record is not _BATCH_INVALIDATE_RECORD
        or scalar_proof.invalidate_owner is not _BATCH_INVALIDATE_OWNER
        or owned_metadata_row is not _BATCH_METADATA_ROW
        or any(
            name in vars(TrackedRow)
            for name in ("uid", "_retained_value", "_scalar_eligibility", "_owner_ref")
        )
        or _WeakOwner.owner is not _BATCH_OWNER_PROPERTY
        or any(name in vars(target) for name in _BATCH_OWNER_NAMES)
        or type(target._selected_scalar_proofs) is not SelectedScalarProofs
        or vars(target._selected_scalar_proofs).keys()
        != {"managers", "dependents", "event_recipes"}
        or any(
            type(getattr(target._selected_scalar_proofs, name)) is not dict
            for name in ("managers", "dependents", "event_recipes")
        )
        or target._selected_scalar_proofs.managers
        or target._selected_scalar_proofs.dependents
        or target._selected_scalar_proofs.event_recipes
    ):
        return False
    for owner in (source, target):
        if (
            type(owner.records) is not OwnedMap
            or owner.records.owner is not owner
            or owner.records.name != "records"
            or any(
                name in vars(owner.records)
                for name in _OWNER_ROW_READERS + ("install_owned", "_notify")
            )
            or type(owner.retired_tracking) is not RetiredAreaTracking
            or not owner.retired_tracking.valid
            or type(owner.retired_tracking.graph) is not RetiredAreaIndex
            or type(owner.retired_tracking.graph.tokens) is not dict
            or type(owner.retired_tracking.graph.opaque) is not set
            or type(owner.retired_tracking.records_dirty) is not set
            or "record_changed" in vars(owner.retired_tracking)
        ):
            return False
    if not finished:
        graph = target.retired_tracking.graph
        if (
            any(
                type(getattr(target, name)) is not dict
                for name in (
                    "by_owner_uid",
                    "record_owners",
                    "by_manager",
                    "managers",
                    "source_counts",
                    "ordinals",
                )
            )
            or any(
                type(getattr(target, name)) is not set
                for name in ("owner_opaque", "unmatched", "order_mismatch")
            )
            or graph.tokens
            or graph.owners
            or graph.roots
            or graph.opaque
            or target.records
            or target.retired_tracking.records_dirty
        ):
            return False
    return True


_BATCH_OWNER_NAMES = (
    "_owner_record_changed",
    "_record_changed",
    "_map_changed",
    "_membership_changed",
    "_order_membership_changed",
)
_BATCH_OWNER_PROPERTY = _WeakOwner.owner
_BATCH_METADATA_ROW = owned_metadata_row
from .combat_retired_area_tracking import RetiredAreaTracking as _BatchTracking
from .combat_selected_scalar_proof import (
    SelectedScalarProofs as _BatchScalarProofs,
    invalidate_record as _BATCH_INVALIDATE_RECORD,
    invalidate_owner as _BATCH_INVALIDATE_OWNER,
)

_BATCH_METHODS = _OWNER_METHODS + tuple(
    (cls, name, getattr(cls, name))
    for cls, names in (
        (
            RetainedCollections,
            ("__getattribute__", "_membership_changed", "_order_membership_changed"),
        ),
        (_BatchTracking, ("record_changed", "_record")),
        (_BatchScalarProofs, ("invalidate",)),
    )
    for name in names
)


def _seed_fresh_record_indexes(owner, uid, payload):
    """Initialize unpublished native metadata, not mutate an existing binding.

    The caller's batch proof guarantees fresh empty indexes and original native
    gateways. No payload callback occurs in this scalar-only construction loop.
    Later source/actor/area copies retain their usual mutation notifications.
    """
    owner.retired_tracking.records_dirty.add(uid)
    if uid not in owner.source_counts:
        owner.unmatched.add(uid)
    else:
        owner.unmatched.discard(uid)
    if uid not in owner.ordinals:
        owner.order_mismatch.add(uid)
    else:
        owner.order_mismatch.discard(uid)
    payload_uid = payload.get("uid")
    valid_uid = type(payload_uid) is int and payload_uid == uid
    parent = payload.get("owner_uid")
    if not valid_uid or (parent is not None and type(parent) is not int):
        owner.owner_opaque.add(uid)
    elif parent is not None:
        owner.record_owners[uid] = parent
        owner.by_owner_uid.setdefault(parent, set()).add(uid)
    manager = payload.get("manager_id")
    if not valid_uid or type(manager) is not int:
        owner.valid = False
    else:
        owner.managers[uid] = manager
        owner.by_manager.setdefault(manager, set()).add(uid)
