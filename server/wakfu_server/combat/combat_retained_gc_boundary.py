"""Private, quiescent shared-publication seam for terminal effect collection.

The bounded weak cursor is a scheduling hint only. Every collection proves
terminal lifecycle and fresh full graph coherence again, on the preview.
"""
from weakref import WeakKeyDictionary
import logging
import os
import sys
import threading
from collections import OrderedDict
from types import GetSetDescriptorType


_CURSORS = WeakKeyDictionary()
_GC_DIAGNOSTICS = os.environ.get("WAKFU_RETIRED_GC_DIAGNOSTICS") == "1"
_GC_DIAGNOSTIC_LOG = logging.getLogger(__name__)
_GC_DIAGNOSTIC_LOCK = threading.Lock()
_GC_DIAGNOSTIC_SEEN = OrderedDict()
_GC_DIAGNOSTIC_LIMIT = 256


def _gc_diagnostic(fight, event, **fields):
    """Emit at most one row per scalar decision signature; retain no fight refs."""
    try:
        if not _GC_DIAGNOSTICS:
            return
        fight_id = turn_id = None
        if fight is not None:
            # Public package layout owns the canonical module identity; there
            # is no nested wakfu_server.combat alias in production.
            state_module = sys.modules.get("wakfu_server.combat_state")
            fight_type = (
                state_module.__dict__.get("Fight")
                if type(state_module) is type(sys)
                else None
            )
            if fight_type is not None and type(fight) is fight_type:
                # Read only CPython's native instance-dict descriptor. Never
                # call a user property named __dict__ on an untrusted object.
                descriptor = fight_type.__dict__.get("__dict__")
                if type(descriptor) is GetSetDescriptorType:
                    state = descriptor.__get__(fight, fight_type)
                else:
                    state = None
                if type(state) is dict:
                    fight_id = state.get("id")
                    turn_id = state.get("turn_id")
                    collections_module = sys.modules.get(
                        "wakfu_server.combat_retained_collections"
                    )
                    owned_map_type = (
                        collections_module.__dict__.get("OwnedMap")
                        if type(collections_module) is type(sys)
                        else None
                    )
                    for source_name, count_name in (
                        ("actors", "actor_count"),
                        ("native_retained_records", "retained_record_count"),
                    ):
                        value = dict.get(state, source_name)
                        if type(value) is dict or (
                            owned_map_type is not None and type(value) is owned_map_type
                        ):
                            fields[count_name] = dict.__len__(value)

        if type(fight_id) is not int:
            fight_id = None
        if type(turn_id) is not int:
            turn_id = None
        safe = tuple(
            sorted(
                (key, value)
                for key, value in fields.items()
                if type(key) is str and type(value) in (str, int, bool, type(None))
            )
        )
        if type(event) is not str:
            event = "invalid_event"
        signature = (fight_id, turn_id, event, safe)
        with _GC_DIAGNOSTIC_LOCK:
            if signature in _GC_DIAGNOSTIC_SEEN:
                return
            _GC_DIAGNOSTIC_SEEN[signature] = None
            if len(_GC_DIAGNOSTIC_SEEN) > _GC_DIAGNOSTIC_LIMIT:
                _GC_DIAGNOSTIC_SEEN.popitem(last=False)
        rendered = " ".join(f"{key}={value}" for key, value in safe)
        _GC_DIAGNOSTIC_LOG.warning(
            "retired_gc_diagnostic fight_id=%s turn_id=%s event=%s %s",
            fight_id,
            turn_id,
            event,
            rendered,
        )
    except BaseException:
        # Observability must never affect candidate publication.
        pass


_MAPS = (
    "owned_stat_effects",
    "native_owned_group_effects",
    "native_owned_area_effects",
    "native_owned_spatial_effects",
    "native_owned_state_containers",
    "state_wire_payloads",
    "native_retained_records",
    "native_effect_areas",
    "native_retired_area_managers",
)


def _storage_owner(fight, *, coherent=False):
    from .combat_retained_collections import bound_collections

    owner = bound_collections(vars(fight))
    return (
        owner
        if owner is not None and (not coherent or owner.consistent(pending=()))
        else None
    )


def _native_map(value, field, owner):
    if type(value) is dict:
        return True
    if owner is None:
        return False
    if field == "native_owned_state_containers":
        from weakref import ReferenceType
        from .combat_retained_collections import RetainedCollections
        from .combat_retired_area_tracking import RetiredAreaTracking
        from .combat_owned_container_facts import OwnedContainerFacts

        tracking = (
            owner.retired_tracking if type(owner) is RetainedCollections else None
        )
        owner_ref = None if tracking is None else tracking.owner
        return (
            type(value) is OwnedContainerFacts
            and type(tracking) is RetiredAreaTracking
            and tracking.facts is value
            and type(owner_ref) is ReferenceType
            and owner_ref() is owner
        )
    from .combat_retained_collections import (
        OwnedMap,
        SOURCE_NAMES,
        AREA_SOURCE_NAMES,
        bound_area_collections,
    )

    expected = (
        owner.actors
        if field == "actors"
        else owner.records
        if field == "native_retained_records"
        else owner.sources.get(field)
        if field in SOURCE_NAMES
        else owner.area_sources.get(field)
        if field in AREA_SOURCE_NAMES and type(owner.area_sources) is dict
        else None
    )
    return type(value) is OwnedMap and value is expected


def _area_row_known(row, owner):
    """Accept native detached Qq aliases without following weak observer graphs."""
    from weakref import ReferenceType
    from .combat_retained_collections import (
        RetainedCollections,
        OwnedMap,
        AREA_SOURCE_NAMES,
    )
    from .combat_area_membership import OwnedAreaRow
    from .combat_source_parent_index import OwnedStateSourceRow

    if (
        type(row) is not OwnedAreaRow
        or type(owner) is not RetainedCollections
        or type(owner.area_sources) is not dict
    ):
        return False
    observers = row._membership_owners
    if type(observers) is not list:
        return False
    for entry in observers:
        if (
            type(entry) is not tuple
            or len(entry) != 3
            or type(entry[0]) is not ReferenceType
            or type(entry[1]) is not str
            or entry[1] not in AREA_SOURCE_NAMES
            or type(entry[2]) is not int
        ):
            return False
        current = entry[0]()
        if current is None:
            continue
        if current is not owner:
            return False
        # A removed area's stale native observer is legitimate; _changed drops
        # it on the next write. It must still address this owner's native map.
        rows = owner.area_sources.get(entry[1])
        if type(rows) is not OwnedMap or rows.owner is not owner:
            return False
    return True


def _source_row_known(row, owner):
    from weakref import WeakKeyDictionary
    from .combat_source_parent_index import SourceParentIndex, SOURCE_MAPS

    fields = vars(row)
    if any(
        type(key) is not str or key not in ("_parent_watchers", "_scalar_eligibility")
        for key in fields
    ):
        return False
    proof = fields.get("_scalar_eligibility")
    if proof is not None and type(proof) is not bool:
        return False
    watchers = fields.get("_parent_watchers")
    if watchers is None:
        return not fields or set(fields) == {"_scalar_eligibility"}
    if type(watchers) is not WeakKeyDictionary or owner is None:
        return False
    for index, tokens in watchers.items():
        if (
            type(index) is not SourceParentIndex
            or index is not owner.source_parents
            or type(tokens) is not set
            or type(index.maps) is not dict
            or type(index.bindings) is not dict
            or type(index.dirty) is not set
            or any(
                index.maps.get(name) is not owner.sources[name] for name in SOURCE_MAPS
            )
        ):
            return False
        for token in tokens:
            if (
                type(token) is not tuple
                or len(token) != 2
                or type(token[0]) is not str
                or token[0] not in SOURCE_MAPS
                or type(token[1]) is not int
                or index.bindings.get(token) is not row
                or dict.get(index.maps[token[0]], token[1]) is not row
            ):
                return False
    return True


def _container_facts_known(value, fight):
    from .combat_owned_container_facts import OwnedContainerFacts
    from .combat_owned_container_row import OwnedContainerRow

    if (
        type(value) is not OwnedContainerFacts
        or OwnedContainerFacts.__getattribute__ is not dict.__getattribute__
        or vars(fight).get("native_owned_state_containers") is not value
    ):
        return False
    fields = vars(value)
    if any(type(key) is not str for key in fields) or set(fields) != {
        "_dirty",
        "_valid",
        "_roots_dirty",
        "_root_opaque",
        "_root_bindings",
    }:
        return False
    if type(fields["_valid"]) is not bool:
        return False
    for name in ("_dirty", "_roots_dirty", "_root_opaque"):
        keys = fields[name]
        if type(keys) is not set or any(
            type(key) is not int for key in set.__iter__(keys)
        ):
            return False
    bindings = fields["_root_bindings"]
    return (
        type(bindings) is dict
        and all(type(key) is int for key in dict.__iter__(value))
        and all(type(key) is int for key in dict.__iter__(bindings))
        and all(
            type(key) is int
            and type(row) is OwnedContainerRow
            and dict.get(value, key) is row
            for key, row in dict.items(bindings)
        )
    )


def _container_row_known(value, facts):
    from weakref import ReferenceType
    from .combat_owned_container_row import OwnedContainerRow
    from .combat_owned_container_facts import OwnedContainerFacts

    if (
        type(value) is not OwnedContainerRow
        or OwnedContainerRow.__getattribute__ is not dict.__getattribute__
    ):
        return False
    fields = vars(value)
    if any(type(key) is not str for key in fields) or set(fields) != {"_root_maps"}:
        return False
    observers = fields["_root_maps"]
    if type(observers) is not list:
        return False
    for token in list.__iter__(observers):
        if (
            type(token) is not tuple
            or len(token) != 2
            or type(token[0]) is not ReferenceType
            or type(token[1]) is not int
        ):
            return False
        current = token[0]()
        if current is None:
            continue
        if current is not facts:
            return False
        roots = vars(facts)["_root_bindings"]
        if (
            dict.get(facts, token[1]) is not value
            or dict.get(roots, token[1]) is not value
        ):
            return False
    return True


def _canonical_graph(
    fight,
    *,
    pending_roots=None,
    diagnostic=None,
    reference_schemas=None,
    projection_opaque=None,
):
    """Unknown/custom values cannot lose hidden outbound references to GC."""
    from .combat_state_ledger import StateLedger, RunningState, StateTimer
    from .combat_character_copy_book import CopyBookAction
    from .combat_carrying import NativeCarryPair
    from .combat_instance_level_group import InstanceDifficultySnapshot
    from .combat_geometry_snapshot import ImmutableTerrainSet
    from .combat_qi_snapshot import ImmutableQIMasks
    from .combat_static_catalogs import ImmutableCatalog
    from .combat_characteristic_link import ObservableCharacteristicStats
    from .combat_retained_collections import (
        OwnedMap,
        OwnedOrder,
        TrackedRow,
        owned_metadata_row,
        SOURCE_NAMES,
        AREA_SOURCE_NAMES,
        bound_area_collections,
    )
    from .combat_state import Actor
    from .combat_area_membership import OwnedAreaRow
    from .combat_source_parent_index import OwnedStateSourceRow
    from .combat_owned_container_facts import OwnedContainerFacts
    from .combat_owned_container_row import OwnedContainerRow
    from .combat_source_provenance_entries import SourceProvenanceEntries
    from .combat_pointer_qi_checkpoint import NativePointerCheckpoint
    from .combat_retained_gc_pointer import pointer_sources
    from wakfu_server.characters.owned_social_context import OwnedSocialContext

    records = (
        StateLedger,
        RunningState,
        StateTimer,
        CopyBookAction,
        NativeCarryPair,
        InstanceDifficultySnapshot,
        OwnedSocialContext,
    )
    completed, visiting = set(), set()
    storage = _storage_owner(fight, coherent=True)
    if storage is not None and not bound_area_collections(vars(fight), storage):
        if diagnostic is not None:
            diagnostic.append(
                (
                    "native_owned_area_effects",
                    type(vars(fight).get("native_owned_area_effects")).__name__,
                    "area_collection_owner_mismatch",
                )
            )
        return False
    maps = (
        ()
        if storage is None
        else (
            storage.actors,
            storage.records,
            *(storage.sources[name] for name in SOURCE_NAMES),
            *(storage.area_sources[name] for name in AREA_SOURCE_NAMES),
        )
    )

    facts = vars(fight).get("native_owned_state_containers")
    known_facts = facts if _container_facts_known(facts, fight) else None

    from .combat_retained_gc import reference_schema_value_known

    schemas_known = [True]

    def plain(value, reference_key=None):
        if (
            reference_schemas is not None
            and schemas_known[0]
            and reference_key in ("native_context_hex", "child_effect_uids")
            and not reference_schema_value_known(value, reference_key)
        ):
            schemas_known[0] = False
        kind = type(value)
        if (
            kind is str
            or kind is int
            or kind is bool
            or kind is float
            or kind is type(None)
        ):
            return True
        if projection_opaque is not None and kind not in (dict, list, tuple):
            from .combat_retained_gc_readers import serialization_reads_plain

            if not serialization_reads_plain(value):
                projection_opaque.add(None)
        if id(value) in visiting:
            return False  # snapshot._plain cannot serialize a recursive graph.
        if id(value) in completed:
            return True
        visiting.add(id(value))
        try:
            if kind is dict:
                valid = all(
                    (type(key) is str or type(key) is int) and plain(item, key)
                    for key, item in dict.items(value)
                )
            elif kind is SourceProvenanceEntries:
                # Only primitive key-proof bookkeeping is hidden in this map.
                # Rows are still traversed normally, including alias/cycle checks.
                native_getter = (
                    SourceProvenanceEntries.__getattribute__ is dict.__getattribute__
                )
                attrs = vars(value) if native_getter else None
                valid = (
                    native_getter
                    and all(type(key) is str for key in attrs)
                    and set(attrs) == {"_native_keys", "_native_key_serial"}
                    and type(attrs["_native_keys"]) is bool
                    and type(attrs["_native_key_serial"]) is int
                    and all(
                        type(key) is str and plain(item, key)
                        for key, item in dict.items(value)
                    )
                )
            elif kind is OwnedMap:
                valid = any(value is current for current in maps) and all(
                    type(key) is int and plain(item, key)
                    for key, item in dict.items(value)
                )
            elif kind is OwnedContainerFacts:
                valid = value is known_facts and all(
                    type(key) is int and plain(item, key)
                    for key, item in dict.items(value)
                )
            elif kind is OwnedContainerRow:
                valid = _container_row_known(value, known_facts) and all(
                    type(key) is str and plain(item, key)
                    for key, item in dict.items(value)
                )
            elif kind is OwnedStateSourceRow:
                valid = _source_row_known(value, storage) and all(
                    type(key) is str and plain(item, key)
                    for key, item in dict.items(value)
                )
            elif kind is OwnedAreaRow:
                valid = _area_row_known(value, storage) and all(
                    type(key) is str and plain(item, key)
                    for key, item in dict.items(value)
                )
            elif kind is OwnedOrder:
                valid = (
                    storage is not None
                    and value is storage.order
                    and all(type(uid) is int for uid in list.__iter__(value))
                )
            elif kind is TrackedRow:
                uid = vars(value).get("uid")
                valid = owned_metadata_row(storage, uid, value) and all(
                    type(key) is str and plain(item, key)
                    for key, item in dict.items(value)
                )
            elif kind is tuple or kind is list or kind is set or kind is frozenset:
                valid = all(plain(item, reference_key) for item in value)
            elif kind is ImmutableTerrainSet:
                valid = all(plain(item) for item in frozenset.__iter__(value))
            elif kind is ImmutableQIMasks:
                valid = all(type(item) is int for item in tuple.__iter__(value))
            elif kind is ImmutableCatalog:
                bindings = vars(value)
                source, views = bindings.get("_source"), bindings.get("_views")
                valid = (
                    set(bindings) == {"_source", "_views"}
                    and type(source) is dict
                    and type(views) is dict
                    and len(views) == 0
                    and plain(source)
                )
            elif kind is NativePointerCheckpoint:
                roots = pointer_sources(value, fight, plain)
                valid = roots is not None
                if valid and pending_roots is not None:
                    pending_roots.extend(roots)
            elif kind is ObservableCharacteristicStats:
                binding = vars(value)
                identity = binding.get("_identity")
                actors = vars(fight).get("actors")
                actor = (
                    dict.get(actors, identity)
                    if type(identity) is int and _native_map(actors, "actors", storage)
                    else None
                )
                from weakref import ReferenceType

                reference = binding.get("_fight_ref")
                valid = (
                    set(binding) == {"_fight_ref", "_identity"}
                    and type(reference) is ReferenceType
                    and reference.__callback__ is None
                    and reference() is fight
                    and type(actor) is Actor
                    and vars(actor).get("effect_stats") is value
                    and all(
                        type(key) is int and type(item) is int
                        for key, item in dict.items(value)
                    )
                )
            elif any(kind is record for record in records):
                valid = kind.__getattribute__ is object.__getattribute__ and plain(
                    vars(value)
                )
            else:
                valid = False
            if not valid and diagnostic is not None and not diagnostic:
                reason = (
                    "owned_map_identity_or_entries"
                    if kind is OwnedMap
                    else "owned_order_owner_or_uids"
                    if kind is OwnedOrder
                    else "tracked_row_owner_or_fields"
                    if kind is TrackedRow
                    else "area_row_owner_or_observers"
                    if kind is OwnedAreaRow
                    else "source_row_owner_or_watchers"
                    if kind is OwnedStateSourceRow
                    else "record_getattribute_or_fields"
                    if any(kind is record for record in records)
                    else "characteristic_owner_or_values"
                    if kind is ObservableCharacteristicStats
                    else "pointer_source_or_payload"
                    if kind is NativePointerCheckpoint
                    else "catalog_source_or_views"
                    if kind is ImmutableCatalog
                    else "immutable_qi_item_type"
                    if kind is ImmutableQIMasks
                    else "mapping_key_or_value"
                    if kind is dict
                    else "unsupported_or_nonplain_value"
                )
                diagnostic.append((root_field, type(value).__name__, reason))
            if valid:
                completed.add(id(value))
            return valid
        finally:
            visiting.remove(id(value))

    try:
        for root_field, value in vars(fight).items():
            if root_field == "_native_retained_owner":
                if storage is None or value is not storage:
                    return False
                continue
            if root_field == "native_rift_creation_deliveries" and type(value) is dict:
                # Native birth packets are immutable historical delivery bytes,
                # not executable references. This field is excluded by _HISTORY
                # before projection; aliases in active fields still run plain().
                # Preserve legacy/custom row validation instead of accepting
                # arbitrary binary values anywhere in the fight graph.
                for identity, delivery in dict.items(value):
                    frozen = (
                        type(identity) is int
                        and type(delivery) is tuple
                        and len(delivery) == 2
                        and all(
                            type(packet) is tuple
                            and len(packet) == 2
                            and type(packet[0]) is int
                            and packet[0] == opcode
                            and type(packet[1]) is bytes
                            for packet, opcode in zip(delivery, (12608, 13091))
                        )
                    )
                    if frozen:
                        continue
                    if type(identity) not in (str, int) or not plain(
                        delivery, identity
                    ):
                        return False
                continue
            if root_field in (
                "actors",
                "native_rail_movement_authority",
                "native_instance_publication_lease",
            ):
                continue
            if not plain(value):
                return False
        root_field = "actors"
        for actor in fight.actors.values():
            if projection_opaque is not None:
                from .combat_retained_gc_readers import serialization_reads_plain

                if type(actor) is not Actor or not serialization_reads_plain(actor):
                    projection_opaque.add(None)
            if not plain(vars(actor)):
                return False
        return True
    finally:
        # Break the recursive closure on acceptance, rejection and exceptions.
        plain = None
        if reference_schemas is not None:
            reference_schemas.append(schemas_known[0])


def planning_snapshot(fight):
    """Project only proven scalar QI encoding; keep the durable snapshot intact.

    Canonical pointer aliases are identity/scalar storage, not a Qf invocation.
    The exact pointer proof separately returns pending/area execution sources.
    Unknown graphs return None rather than receive a field-name exemption.
    """
    roots = []
    if not _canonical_graph(fight, pending_roots=roots):
        return None
    return _project_snapshot(fight, roots)


_PLANNER_ROOT_HISTORY = frozenset(
    (
        "native_state_source_provenance",
        "native_global_pv_collections",
        "rift_wave_state",
    )
)

_RIFT_WAVE_PLANNER_FIELDS = frozenset(
    (
        "seed",
        "wave",
        "policy",
        "catalog",
        "instance_id",
        "turn_budget",
        "pending_wave",
        "actor_id_pool",
        "persisted_wave",
        "wave_actor_ids",
        "world_group_id",
        "staged_receipts",
        "current_actor_ids",
        "wave_species_refs",
        "native_wave_entries",
        "native_artifact_groups",
        "equipment_wave_boundaries",
        "native_artifact_generation",
        "native_artifact_inheritance",
        "native_company_compensation",
        "outcome",
        "last_cleared_wave",
    )
)
_RIFT_ARTIFACT_GROUP_FIELDS = frozenset(
    (
        "wave",
        "original",
        "remaining",
        "assignments",
        "choices_allowed",
        "choices_made",
        "pending_pairs",
    )
)


def _planner_rift_wave_state(value):
    """Keep only future-area roots read by the GC planner; unknown shapes stay full."""
    if type(value) is not dict or any(
        type(key) is not str or key not in _RIFT_WAVE_PLANNER_FIELDS
        for key in dict.keys(value)
    ):
        return value
    if "native_artifact_groups" not in value:
        return value
    groups = value["native_artifact_groups"]
    if type(groups) is not dict:
        return value
    projected = {}
    for key, group in dict.items(groups):
        if (
            type(key) is not str
            or type(group) is not dict
            or any(
                type(name) is not str or name not in _RIFT_ARTIFACT_GROUP_FIELDS
                for name in dict.keys(group)
            )
        ):
            return value
        remaining = dict.get(group, "remaining", None)
        if "remaining" not in group:
            projected[key] = {}
        elif type(remaining) is list or type(remaining) is tuple:
            if any(type(identity) is not int for identity in remaining):
                return value
            projected[key] = {"remaining": remaining}
        else:
            return value
    return {"native_artifact_groups": projected}


def _planner_snapshot_fields(fields):
    """Exclude only _HISTORY fields the planner never explicitly reads."""
    from .combat_retained_gc import _HISTORY

    omitted = _HISTORY - _PLANNER_ROOT_HISTORY
    result = {key: value for key, value in fields.items() if key not in omitted}
    if "rift_wave_state" in result:
        result["rift_wave_state"] = _planner_rift_wave_state(result["rift_wave_state"])
    return result


def _project_snapshot(fight, roots):
    # Internal: the caller just proved this exact graph in the synchronous
    # quiescent boundary. Only planner-relevant fields are serialized; the
    # durable snapshot API and all other consumers still receive full state.
    from .fight_checkpoint_store import snapshot, _plain
    from .combat_pointer_qi_checkpoint import NativePointerCheckpoint
    from types import SimpleNamespace

    planning_fight = SimpleNamespace(**_planner_snapshot_fields(vars(fight)))
    result = snapshot(planning_fight)
    for field, value in vars(fight).items():
        if type(value) is NativePointerCheckpoint:
            result.pop(field, None)
    return result, _plain(roots)


def _retryable_runners(fight, terminal):
    # All carrier310 rows are permanent query roots, even on OUT fighters.
    # A descriptor alone is managed by native parent/user synchronization.
    # Neither justifies a new whole-graph collection at every later turn.
    return any(
        row["manager_id"] in terminal and row["effect_class"] != 310
        for row in fight.native_retained_records.values()
    )


def _quiescent(fight, runtime, *, diagnostic=None):
    from .combat_pending_state import pending_state_uids
    from .combat_event_replay import _READ_PASS_CONTEXTS
    from .combat_structural_qf_scope import _FRAMES

    execution, fields = vars(runtime), vars(fight)
    pending = execution.get("pending")
    if execution.get("awaiting_ack") is not None:
        if diagnostic is not None:
            diagnostic.append(("runtime.awaiting_ack", None, "present"))
        return False
    if type(pending) is not list and type(pending) is not tuple:
        if diagnostic is not None:
            diagnostic.append(
                ("runtime.pending", type(pending).__name__, "wrong_container_type")
            )
        return False
    if len(pending) != 0:
        if diagnostic is not None:
            diagnostic.append(
                ("runtime.pending", "list_or_tuple", "nonempty", len(pending))
            )
        return False
    if fields.get("_resolution_depth") != 0:
        value = fields.get("_resolution_depth")
        if diagnostic is not None:
            diagnostic.append(
                ("_resolution_depth", type(value).__name__, "nonzero_or_missing")
            )
        return False
    if execution.get("_native_delivery_depth", 0) != 0:
        value = execution.get("_native_delivery_depth", 0)
        if diagnostic is not None:
            diagnostic.append(
                ("runtime._native_delivery_depth", type(value).__name__, "nonzero")
            )
        return False
    pending_uids = pending_state_uids(fight)
    if pending_uids:
        if diagnostic is not None:
            diagnostic.append(
                ("pending_state_uids", "frozenset", "nonempty", len(pending_uids))
            )
        return False
    if _READ_PASS_CONTEXTS.get():
        if diagnostic is not None:
            diagnostic.append(("_READ_PASS_CONTEXTS", "tuple", "nonempty"))
        return False
    if _FRAMES.get():
        if diagnostic is not None:
            diagnostic.append(("_FRAMES", "tuple", "nonempty"))
        return False
    delays = fields.get("native_delay_queue", {})
    if type(delays) is not dict:
        if diagnostic is not None:
            diagnostic.append(
                ("native_delay_queue", type(delays).__name__, "wrong_container_type")
            )
        return False
    entries = delays.get("entries", ())
    if (
        type(entries) is not dict
        and type(entries) is not list
        and type(entries) is not tuple
    ):
        if diagnostic is not None:
            diagnostic.append(
                (
                    "native_delay_queue.entries",
                    type(entries).__name__,
                    "wrong_container_type",
                )
            )
        return False
    if len(entries):
        if diagnostic is not None:
            diagnostic.append(
                (
                    "native_delay_queue.entries",
                    type(entries).__name__,
                    "nonempty",
                    len(entries),
                )
            )
        return False
    for actor in fields["actors"].values():
        status = vars(actor).get("native_death_status")
        if status is not None and type(status) is not dict:
            if diagnostic is not None:
                diagnostic.append(
                    (
                        "actor.native_death_status",
                        type(status).__name__,
                        "wrong_container_type",
                    )
                )
            return False
        if status is not None and status.get("pending_restoration") is not None:
            if diagnostic is not None:
                diagnostic.append(
                    (
                        "actor.native_death_status.pending_restoration",
                        "present",
                        "pending",
                    )
                )
            return False
    return True


def _native_callback_mismatch(runtime):
    """Name the first callback field that revoked proof; never render values."""
    from .combat_retained_gc_authority import _FIELDS, _NativeCallbacks
    from .combat_expiration_provider import OwnedExpirationFactory
    import time

    fields = vars(runtime)
    proof = fields.get("_retained_gc_callbacks")
    if proof is None:
        for name in _FIELDS[:-1]:
            if fields.get(name) is not None:
                return name
        if fields.get("clock") is not time.monotonic:
            return "clock"
        return "_retained_gc_callbacks"
    if type(proof) is not _NativeCallbacks:
        return "_retained_gc_callbacks"
    if len(proof.providers) != len(_FIELDS):
        return "_retained_gc_callbacks.providers"
    for name, provider in zip(_FIELDS, proof.providers):
        if fields.get(name) is not provider:
            return name
    if type(fields.get("expiration_runtime_factory")) is not OwnedExpirationFactory:
        return "expiration_runtime_factory"
    return "_retained_gc_callbacks"


def _complete_view(fight):
    from .combat_retained_effects import NativeRetainedEffectView
    from .combat_retained_runtime import _retained_read_population

    records, order = fight.native_retained_records, fight.native_retained_order
    if len(order) != len(records) or set(order) != set(records):
        raise ValueError("GC boundary requires complete retained insertion order")
    view = NativeRetainedEffectView(
        fight,
        _retained_read_population(fight),
        population_verified_complete=fight.native_retained_tracking,
    )
    if set(view.known) != set(records):
        raise ValueError("GC boundary contains unowned retained entries")


def _native_retry_round(fight):
    value = vars(fight).get("native_timeline_round")
    return value if type(value) is int and value >= 0 else None


def _terminal_retired_ids(fight):
    """Reuse native QI/fdy retirement proofs; HP zero alone is reversible."""
    from .combat_ordinary_qi_retirement import retired_ordinary_qi_ids
    from .combat_summon_retirement import retired_summon_ids
    from .combat_native_death_status import native_is_dead

    ordinary = retired_ordinary_qi_ids(fight)
    summons = retired_summon_ids(fight)
    result = set()
    for identity in ordinary | summons:
        actor = fight.actors[identity]
        status = getattr(actor, "native_death_status", None)
        if identity in summons or (
            actor.controlled is False
            and getattr(actor, "native_summon_source", None) is None
        ):
            if (
                type(status) is dict
                and status.get("last_writer") == "owned.aTS.F.type2"
                and native_is_dead(actor) is True
            ):
                result.add(identity)
    return result


def _native_group_replay_known():
    """Fixed-size consumer proof; never import SDK/catalogs or scan a Fight."""
    for name, marker in (
        ("combat_event_replay", "_GROUP_HISTORY_METHODS"),
        ("combat_retained_runtime", "_GROUP_HISTORY_METHODS"),
        ("combat_effect_dispatch", "_GROUP_HISTORY_METHODS"),
        ("combat_encounter_scene_external_participant", "_GROUP_HISTORY_FUNCTIONS"),
        ("combat_encounter_owned_start_binding", "_GROUP_HISTORY_FUNCTIONS"),
        ("combat_encounter_movement_binding", "_GROUP_HISTORY_FUNCTIONS"),
        ("combat_encounter_npc_start_binding", "_GROUP_HISTORY_FUNCTIONS"),
        ("rift_ko_cleanup", "_GROUP_HISTORY_FUNCTIONS"),
    ):
        module = sys.modules.get("wakfu_server." + name)
        if type(module) is not type(sys):
            return False
        original = vars(module).get(marker)
        if type(original) is not tuple or not original:
            return False
        if marker == "_GROUP_HISTORY_METHODS":
            for kind, field, method in original:
                if (
                    vars(module).get(kind.__name__) is not kind
                    or getattr(kind, field, None) is not method
                ):
                    return False
        elif any(
            vars(module).get(field) is not function for field, function in original
        ):
            return False
    return True


def prepare_retired_gc(previous, candidate, runtime, packets):
    """Collect only on an unadopted native preview; failure prevents publication.

    Immutable output packets are not executable callbacks and do not block GC.
    Pending runtime presentation/ACK and native execution scopes do block it.
    No actor, accounting receipt, native action or reward is removed here.
    """
    from .combat_state import Fight, Actor
    from .combat_runtime_messages import RuntimeMessages
    from .combat_retained_gc_authority import native_callbacks_known
    from .combat_retained_gc_ephemeral import ephemeral_sources_known

    for value, label, expected in (
        (candidate, "candidate", Fight),
        (previous, "previous", Fight),
        (runtime, "runtime", RuntimeMessages),
    ):
        if type(value) is not expected:
            _gc_diagnostic(
                candidate if type(candidate) is Fight else None,
                "guard_rejected",
                reason="exact_type",
                field=label,
                value_type=type(value).__name__,
            )
            return
    if candidate is previous:
        _gc_diagnostic(
            candidate, "guard_rejected", reason="same_candidate_and_previous"
        )
        return
    for cls, label in (
        (Fight, "Fight"),
        (Actor, "Actor"),
        (RuntimeMessages, "RuntimeMessages"),
    ):
        if cls.__getattribute__ is not object.__getattribute__:
            _gc_diagnostic(
                candidate, "guard_rejected", reason="custom_getattribute", field=label
            )
            return
    if not native_callbacks_known(runtime):
        callback_field = None
        if _GC_DIAGNOSTICS:
            callback_field = _native_callback_mismatch(runtime)
        _gc_diagnostic(
            candidate,
            "guard_rejected",
            reason="runtime_callbacks_unknown",
            field=callback_field,
        )
        return
    if not ephemeral_sources_known(candidate):
        _gc_diagnostic(candidate, "guard_rejected", reason="ephemeral_sources_unknown")
        return
    fields = vars(candidate)
    storage = _storage_owner(candidate)
    if runtime.fight is not candidate:
        _gc_diagnostic(candidate, "guard_rejected", reason="runtime_fight_mismatch")
        return
    if fields.get("native_retained_tracking") is not True:
        _gc_diagnostic(
            candidate,
            "guard_rejected",
            reason="retained_tracking_disabled",
            field="native_retained_tracking",
        )
        return
    if not _native_map(fields.get("actors"), "actors", storage):
        _gc_diagnostic(
            candidate,
            "guard_rejected",
            reason="collection_owner_mismatch",
            field="actors",
            value_type=type(fields.get("actors")).__name__,
        )
        return
    for actor in fields["actors"].values():
        if type(actor) is not Actor:
            _gc_diagnostic(
                candidate,
                "guard_rejected",
                reason="actor_exact_type",
                field="actors",
                value_type=type(actor).__name__,
            )
            return
    for name in _MAPS:
        value = fields.get(name, {})
        if not _native_map(value, name, storage):
            _gc_diagnostic(
                candidate,
                "guard_rejected",
                reason="collection_owner_mismatch",
                field=name,
                value_type=type(value).__name__,
            )
            return
    retirements = fields.get("native_ordinary_qi_retirements", {})
    summon_retirements = fields.get("native_summon_retirements", {})
    if (
        type(retirements) is not dict
        or type(summon_retirements) is not dict
        or not (retirements or summon_retirements)
    ):
        _gc_diagnostic(
            candidate,
            "guard_rejected",
            reason="no_ordinary_qi_retirements",
            retirement_type=type(retirements).__name__,
        )
        return
    if type(packets) is not tuple and type(packets) is not list:
        # NativeDelivery is a tuple subclass with immutable native metadata.
        from .combat_native_action_ids import NativeDelivery

        if type(packets) is not NativeDelivery:
            _gc_diagnostic(
                candidate,
                "guard_rejected",
                reason="delivery_type",
                delivery_type=type(packets).__name__,
            )
            return
    old = _CURSORS.get(previous)
    count = len(retirements) + len(summon_retirements)
    prior_storage = _storage_owner(previous)
    shrink = any(
        _native_map(vars(previous).get(name, {}), name, prior_storage)
        and len(fields.get(name, {})) < len(vars(previous).get(name, {}))
        for name in _MAPS
    )
    # Only exact native packet rows permit deferred application scheduling.
    # Opaque opcodes retain the old membership test and immediate behavior.
    native_packet_iteration = (
        type(packets) is tuple
        or type(packets) is list
        or NativeDelivery.__iter__ is tuple.__iter__
    )
    native_packet_rows = native_packet_iteration and all(
        type(row) is tuple and len(row) == 2 and type(row[0]) is int for row in packets
    )
    effect_packet = any(opcode in (13497, 13560) for opcode, _ in packets)
    # Batch unreachable-history reclamation within an exact active native
    # round. No reachability result is cached; the next attempt proves again.
    # Pending drains, finalization and unknown round provenance retain retries.
    current_round = _native_retry_round(candidate)
    previous_round = _native_retry_round(previous)
    checked_round = old[3] if old is not None and len(old) == 4 else None
    retry_boundary = (
        current_round != checked_round
        if current_round is not None
        and previous_round is not None
        and type(checked_round) is int
        and checked_round >= 0
        else candidate.turn_id != previous.turn_id
    )
    application_retry_scheduled = (
        native_packet_rows
        and effect_packet
        and old is not None
        and old[2]
        and current_round is not None
        and previous_round is not None
        and type(checked_round) is int
        and checked_round >= 0
        and current_round == previous_round == checked_round
        and not any(opcode == 13560 for opcode, _ in packets)
    )
    immediate_effect_packet = effect_packet and not application_retry_scheduled
    finalization_retry = (
        old is not None
        and old[2]
        and previous.phase == "active"
        and candidate.phase != "active"
    )
    dirty = (
        old is None
        or old[0] != count
        or old[1]
        or shrink
        or immediate_effect_packet
        or old[2]
        and retry_boundary
        or finalization_retry
    )
    if (
        dirty
        and old is not None
        and not old[1]
        and native_packet_rows
        and previous.phase == candidate.phase == "active"
        and current_round is not None
        and previous_round is not None
        and type(checked_round) is int
        and checked_round >= 0
        and current_round == previous_round == checked_round
    ):
        # Reclamation only: retain the newly unreachable graph until the next
        # native round instead of rescanning the whole history for each death
        # or removal. Never reuse reachability or mutate actors/packets here.
        # Pending drains, finalization and unknown provenance remain immediate.
        _CURSORS[candidate] = (count, False, True, checked_round)
        _gc_diagnostic(
            candidate,
            "deferred",
            reason="native_round_reclamation_scheduled",
            retirement_count=count,
        )
        return
    if not dirty:
        _gc_diagnostic(
            candidate,
            "deferred",
            reason=(
                "application_retry_already_scheduled"
                if application_retry_scheduled
                else "cursor_clean"
            ),
            retirement_count=count,
        )
        _CURSORS[candidate] = old
        return
    quiescence_detail = [] if _GC_DIAGNOSTICS else None
    if not _quiescent(candidate, runtime, diagnostic=quiescence_detail):
        detail = (
            quiescence_detail[0] if quiescence_detail else (None, None, "not_quiescent")
        )
        _gc_diagnostic(
            candidate,
            "deferred",
            reason="not_quiescent",
            field=detail[0],
            value_type=detail[1],
            detail=detail[2],
            detail_count=detail[3] if len(detail) > 3 else None,
            retirement_count=count,
        )
        _CURSORS[candidate] = (count, True, True, checked_round)
        return
    from .combat_retained_gc import plan_retired_effects, sweep_retired_effects

    pointer_roots = []
    reference_schemas = []
    projection_opaque = set()
    canonical_failure = [] if _GC_DIAGNOSTICS else None
    if not _canonical_graph(
        candidate,
        pending_roots=pointer_roots,
        diagnostic=canonical_failure,
        reference_schemas=reference_schemas,
        projection_opaque=projection_opaque,
    ):
        # No snapshot coercion of custom mappings/objects: their references
        # are opaque. Reconsider at the next root-changing boundary.
        details = (
            canonical_failure[0]
            if canonical_failure
            else (None, None, "canonical_rejected")
        )
        _gc_diagnostic(
            candidate,
            "deferred",
            reason="canonical_graph_rejected",
            field=details[0],
            value_type=details[1],
            detail=details[2],
        )
        _CURSORS[candidate] = (count, False, True, current_round)
        return
    terminal = _terminal_retired_ids(candidate)
    if not terminal:
        _gc_diagnostic(
            candidate,
            "deferred",
            reason="no_terminal_actor",
            retirement_count=count,
            actor_count=len(fields["actors"]),
        )
        _CURSORS[candidate] = (count, False, False, current_round)
        return
    _complete_view(candidate)
    projected_snapshot, pointer_roots = _project_snapshot(candidate, pointer_roots)
    plan = plan_retired_effects(
        projected_snapshot,
        terminal,
        pending_roots=pointer_roots,
        _reference_schemas_valid=(
            reference_schemas == [True] and None not in projection_opaque
        ),
        _native_group_trigger_history=(
            reference_schemas == [True]
            and not projection_opaque
            and native_callbacks_known(runtime)
            and _native_group_replay_known()
        ),
    )
    _gc_diagnostic(
        candidate,
        "plan",
        reason="complete",
        retirement_count=count,
        terminal_actors=len(terminal),
        actor_ids=len(plan.actor_ids),
        effect_uids=len(plan.effect_uids),
        marked_actor_ids=len(plan.marked_actor_ids),
        opaque_sources=len(plan.opaque_sources),
        orphan_container_uids=len(plan.orphan_container_uids),
        orphan_provenance_uids=len(plan.orphan_provenance_uids),
    )
    if plan.effect_uids or plan.orphan_provenance_uids:
        _gc_diagnostic(
            candidate,
            "sweep_started",
            reason="retained_or_provenance_uids_present",
            effect_uids=len(plan.effect_uids),
            actor_ids=len(plan.actor_ids),
            orphan_container_uids=len(plan.orphan_container_uids),
            orphan_provenance_uids=len(plan.orphan_provenance_uids),
        )
        sweep_retired_effects(candidate, plan)
        _complete_view(candidate)
        if (
            storage is not None
            and _storage_owner(candidate, coherent=True) is not storage
        ):
            raise ValueError("GC sweep changed owned collection coherence")
        _gc_diagnostic(
            candidate,
            "sweep_complete",
            reason="postconditions_passed",
            effect_uids=len(plan.effect_uids),
            actor_ids=len(plan.actor_ids),
            orphan_container_uids=len(plan.orphan_container_uids),
            orphan_provenance_uids=len(plan.orphan_provenance_uids),
        )
    else:
        _gc_diagnostic(candidate, "sweep_skipped", reason="empty_effect_plan")
    # A manager may lose one inert UID while another still has a live user.
    # Manager-level membership in the plan does not mean it was fully swept.
    remaining = bool(plan.orphan_provenance_uids) or _retryable_runners(
        candidate, terminal
    )
    _CURSORS[candidate] = (count, False, remaining, current_round)
