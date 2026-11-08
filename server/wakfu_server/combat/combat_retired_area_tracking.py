"""Mutation-gateway adapter for local retired-Qq reachability."""
from weakref import ref
from .combat_retired_area_index import RetiredAreaIndex


class RetiredAreaTracking:
    def __init__(self, owner):
        self.owner = ref(owner)
        self.graph = RetiredAreaIndex()
        self.records_dirty = set()
        self.areas_dirty = set()
        self.facts = None
        self.valid = True

    def record_changed(self, uid):
        if type(uid) is int:
            self.records_dirty.add(uid)
        else:
            self.valid = False

    def area_changed(self, uid):
        if type(uid) is int:
            self.areas_dirty.add(uid)
        else:
            self.valid = False

    def bind_facts(self, facts):
        """Fresh/decoded graph boundary only; never repair binding in a query."""
        if self.facts is not None and self.facts is not facts:
            raise ValueError("Retired root graph facts require a fresh owner")
        self.facts = facts

    def copy_record_roots_from(self, source):
        """Transfer only clean roots for metadata present in the fresh clone.

        Dirty, opaque and absent source records retain fresh-clone semantics:
        present rows are validated normally and deleted history is not copied.
        """
        from collections import Counter

        graph = source.graph
        owner = self.owner()
        if (
            type(graph) is not RetiredAreaIndex
            or type(graph.tokens) is not dict
            or type(graph.opaque) is not set
            or type(source.records_dirty) is not set
            or owner is None
        ):
            return False
        tokens, roots, transferred = {}, Counter(), set()
        for uid in owner.records:
            if uid in source.records_dirty:
                continue
            token = ("record", uid)
            if token in graph.opaque:
                continue
            values = graph.tokens.get(token)
            if type(values) is not Counter:
                continue
            copied = Counter(values)
            tokens[token] = copied
            for identity, count in copied.items():
                if type(identity) is not int or type(count) is not int or count <= 0:
                    return False
                roots[identity] = roots.get(identity, 0) + count
            transferred.add(uid)
        self.graph.tokens = tokens
        self.graph.roots = roots
        self.graph.dirty.update(roots)
        self.records_dirty.difference_update(transferred)
        return True

    def _record(self, owner, uid):
        from .combat_retained_collections import owned_metadata_row

        row = owner.records.get(uid)
        if row is None:
            self.graph.root(("record", uid), ())
            return
        if (
            not owned_metadata_row(owner, uid, row)
            or type(row).get is not dict.get
            or "get" in vars(row)
        ):
            self.graph.root(("record", uid), None)
            return
        manager, caster = dict.get(row, "manager_id"), dict.get(row, "caster_id")
        kind, container = dict.get(row, "container_kind"), dict.get(row, "container_id")
        values = [manager, caster]
        if kind is not None and type(kind) is not str:
            self.graph.root(("record", uid), None)
            return
        if kind == "effect_area":
            values.append(container)
        if any(value is not None and type(value) is not int for value in values):
            self.graph.root(("record", uid), None)
            return
        self.graph.root(
            ("record", uid), (value for value in values if value is not None)
        )

    def _area(self, owner, uid):
        from .combat_area_membership import OwnedAreaRow
        from .combat_state_ledger import StateLedger

        active_map = owner.area_sources["native_effect_areas"]
        retired_map = owner.area_sources["native_retired_area_managers"]
        active, retired = uid in active_map, uid in retired_map
        row = active_map.get(uid) if active else retired_map.get(uid)
        if not active and not retired:
            self.graph.area(uid, None, active=False, retired=False, protected=False)
            return
        if type(row) is not OwnedAreaRow or type(row).get is not dict.get:
            self.graph.area(
                uid,
                None,
                active=active,
                retired=retired,
                protected=False,
                verified=False,
            )
            return
        parent = dict.get(row, "owner_id")
        executing, removing = dict.get(row, "executing", False), dict.get(
            row, "removing", False
        )
        ledger = dict.get(row, "state_ledger")
        verified = (
            type(executing) is bool
            and type(removing) is bool
            and (
                ledger is None
                or (type(ledger) is StateLedger and type(ledger._entries) is tuple)
            )
        )
        protected = (
            bool(executing or removing or (ledger is not None and ledger._entries))
            if verified
            else False
        )
        self.graph.area(
            uid,
            parent,
            active=active,
            retired=retired,
            protected=protected,
            verified=verified,
        )

    def _descriptor(self, uid, users):
        from .combat_owned_container_row import OwnedContainerRow

        row = dict.get(self.facts, uid)
        if row is None or uid not in users:
            self.graph.root(("descriptor", uid), ())
            return
        if (
            type(row) is not OwnedContainerRow
            or type(row).get is not dict.get
            or "get" in vars(row)
            or type(dict.get(row, "uid")) is not int
            or dict.get(row, "uid") != uid
        ):
            self.graph.root(("descriptor", uid), None)
            return
        values = (dict.get(row, "target_id"), dict.get(row, "caster_id"))
        if any(value is not None and type(value) is not int for value in values):
            self.graph.root(("descriptor", uid), None)
            return
        self.graph.root(
            ("descriptor", uid), (value for value in values if value is not None)
        )

    def plan(self, fight):
        from .combat_owned_container_facts import OwnedContainerFacts
        from .combat_state_membership import caster_roots, retired_ledger_dirty
        from .combat_source_parent_index import SOURCE_MAPS

        owner = self.owner()
        facts = self.facts
        if (
            not self.valid
            or owner is None
            or type(facts) is not OwnedContainerFacts
            or vars(fight).get("native_owned_state_containers") is not facts
            or not facts._valid
            or facts._root_opaque
        ):
            return None
        casters = caster_roots(owner)
        if casters is None:
            return None
        caster_dirty, area_dirty = retired_ledger_dirty(owner)
        users = owner.source_parents.parents(
            {name: owner.sources[name] for name in SOURCE_MAPS}
        )
        if users is None:
            return None
        for uid in tuple(self.records_dirty):
            self._record(owner, uid)
        self.records_dirty.clear()
        for uid in self.areas_dirty | area_dirty:
            self._area(owner, uid)
        self.areas_dirty.clear()
        area_dirty.clear()
        for identity in tuple(caster_dirty):
            count = casters.get(identity, 0)
            self.graph.root(("ledger", identity), {identity: count} if count else ())
        caster_dirty.clear()
        parents = owner.source_parents.root_changed_parents
        for uid in facts._roots_dirty | parents:
            if type(uid) is int:
                self._descriptor(uid, users)
        facts._roots_dirty.clear()
        parents.clear()
        return self.graph.plan()


def prune_indexed_retired(fight):
    """Abstain before deletion unless every current native root is indexed."""
    from .combat_retained_registration_scope import native_membership_owner
    from .combat_area_membership import OwnedAreaRow
    from .combat_owned_container_row import OwnedContainerRow
    from .combat_owned_container_facts import OwnedContainerFacts
    from .combat_source_parent_index import OwnedStateSourceRow
    from .combat_pointer_qi_spatialowned import NativeSpatialRecord
    from .combat_retained_collections import OwnedMap, TrackedRow
    from .combat_state import Fight
    from .combat_state_ledger import RunningState, StateLedger

    owner = native_membership_owner(fight)
    if (
        owner is None
        or "native_owned_state_containers" in Fight.__dict__
        or type(owner.retired_tracking) is not RetiredAreaTracking
        or type(owner.retired_tracking.facts) is not OwnedContainerFacts
        or RunningState.__getattribute__ is not object.__getattribute__
        or "__getattr__" in RunningState.__dict__
        or "caster_id" in RunningState.__dict__
        or "actor_id" in StateLedger.__dict__
        or any(
            cls.get is not dict.get or cls.__getattribute__ is not dict.__getattribute__
            for cls in (
                OwnedAreaRow,
                OwnedContainerRow,
                OwnedContainerFacts,
                OwnedStateSourceRow,
                NativeSpatialRecord,
                OwnedMap,
                TrackedRow,
            )
        )
    ):
        return False
    maps = (
        owner.records,
        owner.actors,
        owner.retired_tracking.facts,
        *owner.sources.values(),
        *owner.area_sources.values(),
    )
    if any(
        "get" in vars(rows) or "values" in vars(rows) or "items" in vars(rows)
        for rows in maps
    ):
        return False
    planned = owner.retired_tracking.plan(fight)
    if planned is None:
        return False
    retired = owner.area_sources["native_retired_area_managers"]
    for identity in planned:
        del retired[identity]
    return True
