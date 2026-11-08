"""Versioned offline combat graphs; never a live checkpoint recovery format.

Preserve aliases, dictionary key types, collection order and canonical QI
pointers. Only named data types are accepted; no pickle, evaluated source or
payload-selected imports. Runtime services must be rebuilt by a trusted recipe.
"""
import base64
import datetime as _datetime
import importlib
import json
import math
from weakref import ref, ReferenceType

SCHEMA = "wakemu-combat-reproduction-state-v1"
MAX_NODES = 100000
MAX_DEPTH = 160
MAX_BYTES = 64 * 1024 * 1024

_TYPES = {
    "Actor": ("combat_state", "Actor"),
    "Fight": ("combat_state", "Fight"),
    "RuntimeMessages": ("combat_runtime_messages", "RuntimeMessages"),
    "StateLedger": ("combat_state_ledger", "StateLedger"),
    "RunningState": ("combat_state_ledger", "RunningState"),
    "StateTimer": ("combat_state_timing", "StateTimer"),
    "NativeCarryPair": ("combat_carrying", "NativeCarryPair"),
    "InstanceDifficultySnapshot": (
        "combat_instance_level_group",
        "InstanceDifficultySnapshot",
    ),
    "PublishedInstanceContext": (
        "combat_instance_context",
        "PublishedInstanceContext",
    ),
    "PublicationLease": ("combat_instance_publication", "PublicationLease"),
    "PartyPublicationLease": (
        "combat_instance_publication",
        "PartyPublicationLease",
    ),
    "InstancePublicationTracker": (
        "combat_instance_publication",
        "InstancePublicationTracker",
    ),
    "CopyBookAction": ("combat_character_copy_book", "CopyBookAction"),
    "ActorSnapshot": ("combat_actor_snapshot", "ActorSnapshot"),
    "NativeActorAuthority": ("combat_runtime_adapter", "NativeActorAuthority"),
    "SummonRegistration": ("combat_summon", "SummonRegistration"),
    "SummonSpecification": ("combat_summon", "SummonSpecification"),
    "NativeTroveByteSet": ("combat_trove_byte_set", "NativeTroveByteSet"),
    "NativeTroveLongMap": ("combat_trove_long_map", "NativeTroveLongMap"),
    "NativeTroveIntMap": ("combat_trove_int_map", "NativeTroveIntMap"),
    "NativePointerCheckpoint": (
        "combat_pointer_qi_checkpoint",
        "NativePointerCheckpoint",
    ),
    "ActualActorQI": ("combat_pointer_qi_actor", "ActualActorQI"),
    "ActorQK": ("combat_pointer_qi_actor", "ActorQK"),
    "AreaQK": ("combat_pointer_qi_actor", "AreaQK"),
    "ActualRetained937": ("combat_pointer_qi_actor", "ActualRetained937"),
    "RetainedContext": ("combat_pointer_qi_actor", "RetainedContext"),
    "ImmutableTerrainSet": ("combat_geometry_snapshot", "ImmutableTerrainSet"),
    "ImmutableQIMasks": ("combat_qi_snapshot", "ImmutableQIMasks"),
    "NativeDelivery": ("combat_native_action_ids", "NativeDelivery"),
    "AckBarrier": ("combat_ack_barrier", "AckBarrier"),
    "Session": ("combat_shared", "Session"),
    "Batch": ("combat_shared", "Batch"),
    "ObservableCharacteristicStats": (
        "combat_characteristic_link",
        "ObservableCharacteristicStats",
    ),
    "RetainedEffect": ("combat_retained_effects", "RetainedEffect"),
    "CapturedCreature": ("characters.captured_roster", "CapturedCreature"),
    "NativeCapturedRoster": ("characters.captured_roster", "NativeCapturedRoster"),
    "OwnedCapturedRoster": ("characters.captured_roster", "OwnedCapturedRoster"),
    "OwnedSocialContext": ("characters.owned_social_context", "OwnedSocialContext"),
    "ImmutableCatalog": ("combat_static_catalogs", "ImmutableCatalog"),
}
_MAPPING_TYPES = frozenset(
    {"NativePointerCheckpoint", "ObservableCharacteristicStats", "ImmutableCatalog"}
)
_RUNTIME_SERVICES = frozenset(
    {
        "stats_serializer",
        "runtime_stats_serializer",
        "turn_end_provider",
        "turn_start_provider",
        "expiration_runtime_factory",
        "clock",
        # Trusted diagnostic recipe restores the exact callback certificate.
        "_retained_gc_callbacks",
    }
)


class UnsupportedReproductionState(ValueError):
    """An unsupported fact is never silently removed from a reproduction."""


def _type_name(value):
    cls = type(value)
    for name, (module, symbol) in _TYPES.items():
        if cls.__name__ == symbol and cls.__module__ in (
            "wakfu_server." + module,
            "wakfu_server.combat." + module,
        ):
            return name
    raise UnsupportedReproductionState(
        "Unsupported reproduction type: " + cls.__module__ + "." + cls.__name__
    )


def _class(name):
    if name not in _TYPES:
        raise UnsupportedReproductionState("Unknown reproduction type: " + str(name))
    module, symbol = _TYPES[name]
    return getattr(importlib.import_module("wakfu_server." + module), symbol)


def _publication_scope(value):
    return (
        type(value) is tuple
        and len(value) == 5
        and all(type(value[index]) is int for index in (0, 2, 3, 4))
        and value[0] > 0
        and type(value[1]) is str
        and bool(value[1])
        and value[2] > 0
        and value[3] > 0
        and value[4] >= 0
    )


def _publication_receipt(value):
    return (
        type(value) is tuple
        and len(value) == 5
        and type(value[0]) is str
        and len(value[0]) == 32
        and all(character in "0123456789abcdef" for character in value[0])
        and _publication_scope(value[1])
        and type(value[2]) is int
        and value[2] > 0
        and type(value[3]) is str
        and len(value[3]) == 64
        and all(character in "0123456789abcdef" for character in value[3])
        and type(value[4]) is int
    )


def _validate_publication_state(objects, nodes):
    """Validate reconstructed publication state without reconnecting owners."""
    publication_names = {
        "PublishedInstanceContext",
        "PublicationLease",
        "PartyPublicationLease",
        "InstancePublicationTracker",
    }
    present = {node.get("type") for node in nodes if node.get("kind") == "object"}
    if not present.intersection(publication_names):
        return
    publication_lease = (
        _class("PublicationLease")
        if present.intersection(
            {"PublicationLease", "PartyPublicationLease", "InstancePublicationTracker"}
        )
        else None
    )
    party_lease = (
        _class("PartyPublicationLease") if "PartyPublicationLease" in present else None
    )
    tracker_type = (
        _class("InstancePublicationTracker")
        if present.intersection({"InstancePublicationTracker", "PartyPublicationLease"})
        else None
    )
    context_type = (
        _class("PublishedInstanceContext")
        if present.intersection(
            {"PublishedInstanceContext", "InstancePublicationTracker"}
        )
        else None
    )
    for index, node in enumerate(nodes):
        name = node.get("type")
        if name not in publication_names:
            continue
        obj = objects[index]
        fields = vars(obj)
        if name == "PublishedInstanceContext":
            if set(fields) != {"session_actor_id", "instance_id", "payload"}:
                raise UnsupportedReproductionState(
                    "Invalid published instance context fields"
                )
            try:
                obj.__post_init__()
            except (TypeError, ValueError) as error:
                raise UnsupportedReproductionState(
                    "Invalid published instance context"
                ) from error
        elif name == "PublicationLease":
            if set(fields) not in ({"current"}, {"current", "owner_bindings"}):
                raise UnsupportedReproductionState("Invalid publication lease fields")
            if fields["current"] is not None and not _publication_receipt(
                fields["current"]
            ):
                raise UnsupportedReproductionState("Invalid publication lease receipt")
            if "owner_bindings" in fields:
                bindings = fields["owner_bindings"]
                if (
                    type(bindings) is not tuple
                    or len(bindings) != 1
                    or type(bindings[0]) is not tuple
                    or len(bindings[0]) != 2
                    or type(bindings[0][0]) is not tracker_type
                    or not _publication_scope(bindings[0][1])
                    or bindings[0][0].lease is not obj
                ):
                    raise UnsupportedReproductionState(
                        "Invalid publication lease owner alias"
                    )
        elif name == "InstancePublicationTracker":
            if set(fields) != {
                "connection_nonce",
                "lease",
                "scope",
                "published",
                "sequence",
            }:
                raise UnsupportedReproductionState("Invalid publication tracker fields")
            nonce, lease, scope = (
                fields["connection_nonce"],
                fields["lease"],
                fields["scope"],
            )
            published, sequence = fields["published"], fields["sequence"]
            if (
                type(nonce) is not str
                or len(nonce) != 32
                or any(character not in "0123456789abcdef" for character in nonce)
                or type(lease) is not publication_lease
                or scope is not None
                and not _publication_scope(scope)
                or published is not None
                and type(published) is not context_type
                or type(sequence) is not int
                or sequence < 0
            ):
                raise UnsupportedReproductionState("Invalid publication tracker state")
            current = lease.current
            if current is not None and (
                current[0] != nonce
                or current[1] != scope
                or current[2] != sequence
                or published is None
                or current[3] != published.sha256
            ):
                raise UnsupportedReproductionState(
                    "Publication tracker and lease differ"
                )
            if (published is None) != (current is None):
                raise UnsupportedReproductionState(
                    "Publication tracker publication differs"
                )
        else:
            if set(fields) != {"leases", "owner_bindings"}:
                raise UnsupportedReproductionState(
                    "Invalid party publication lease fields"
                )
            leases, bindings = fields["leases"], fields["owner_bindings"]
            if (
                type(leases) is not tuple
                or not leases
                or any(type(lease) is not publication_lease for lease in leases)
                or type(bindings) is not tuple
                or bindings
                and len(bindings) != len(leases)
            ):
                raise UnsupportedReproductionState(
                    "Invalid party publication lease sources"
                )
            for lease, binding in zip(leases, bindings):
                if (
                    type(binding) is not tuple
                    or len(binding) != 2
                    or type(binding[0]) is not tracker_type
                    or not _publication_scope(binding[1])
                    or binding[0].lease is not lease
                ):
                    raise UnsupportedReproductionState(
                        "Invalid party publication owner alias"
                    )


def _sort_key(value):
    if value is None or type(value) in (
        str,
        int,
        bool,
        float,
        bytes,
        _datetime.datetime,
        _datetime.date,
        _datetime.time,
        _datetime.timedelta,
        _datetime.timezone,
    ):
        return (type(value).__name__, repr(value))
    if type(value) is tuple:
        return ("tuple", tuple(_sort_key(item) for item in value))
    raise UnsupportedReproductionState("Unordered collection has unsupported elements")


def _static_catalog_descriptor(value):
    kind = type(value)
    if kind.__name__ != "PublishedStaticMapping" or kind.__module__ not in (
        "wakfu_server.combat_published_catalogs",
        "wakfu_server.combat.combat_published_catalogs",
    ):
        return None
    from .combat_published_catalogs import static_catalog_descriptor

    return static_catalog_descriptor(value)


def encode_state(value, *, preserve_scalars=False):
    """Capture data and service requirements without invoking any providers."""
    if type(preserve_scalars) is not bool:
        raise UnsupportedReproductionState("Invalid scalar identity policy")
    nodes, seen, services = [], {}, []
    from .combat_reproduction_static_bindings import StaticProjectionBindings

    static_bindings = StaticProjectionBindings()

    def encode(current, depth=0):
        if depth > MAX_DEPTH:
            raise UnsupportedReproductionState("Reproduction nesting limit exceeded")
        if (
            current is None
            or type(current) in (int, bool)
            or type(current) is str
            and not preserve_scalars
        ):
            return current
        if type(current) is float:
            if not math.isfinite(current):
                raise UnsupportedReproductionState("Nonfinite reproduction number")
            return current
        if type(current) is bytes and not preserve_scalars:
            return {"bytes": base64.b64encode(current).decode("ascii")}
        identity = id(current)
        if identity in seen:
            original, index = seen[identity]
            if original is not current:
                raise UnsupportedReproductionState(
                    "Reproduction object identity changed"
                )
            return {"ref": index}
        if len(nodes) >= MAX_NODES:
            raise UnsupportedReproductionState("Reproduction node limit exceeded")
        index = len(nodes)
        # Keep synthetic attribute/mapping dictionaries alive too. Retaining
        # only their integer ids lets Python reuse an id for the next object.
        seen[identity] = (current, index)
        node = {}
        nodes.append(node)
        reference = {"ref": index}
        kind = type(current)
        from .combat_retained_collections import OwnedMap, OwnedOrder, TrackedRow
        from .combat_area_membership import OwnedAreaRow
        from .combat_source_parent_index import OwnedStateSourceRow
        from .combat_source_provenance_entries import SourceProvenanceEntries
        from .combat_owned_container_facts import OwnedContainerFacts
        from .combat_owned_container_row import OwnedContainerRow

        projection = static_bindings.descriptor(current)
        static_descriptor = _static_catalog_descriptor(current)
        if projection is not None:
            node.update(kind="staticProjection", descriptor=projection)
        elif static_descriptor is not None:
            node.update(kind="staticCatalog", descriptor=static_descriptor)
        elif kind is str:
            node.update(kind="str", value=current)
        elif kind is bytes:
            node.update(kind="bytes", value=base64.b64encode(current).decode("ascii"))
        elif kind is _datetime.datetime:
            node.update(
                kind="temporal",
                type="datetime",
                value=[
                    current.year,
                    current.month,
                    current.day,
                    current.hour,
                    current.minute,
                    current.second,
                    current.microsecond,
                    current.fold,
                ],
                tzinfo=encode(current.tzinfo, depth + 1),
            )
        elif kind is _datetime.date:
            node.update(
                kind="temporal",
                type="date",
                value=[current.year, current.month, current.day],
            )
        elif kind is _datetime.time:
            node.update(
                kind="temporal",
                type="time",
                value=[
                    current.hour,
                    current.minute,
                    current.second,
                    current.microsecond,
                    current.fold,
                ],
                tzinfo=encode(current.tzinfo, depth + 1),
            )
        elif kind is _datetime.timedelta:
            node.update(
                kind="temporal",
                type="timedelta",
                value=[current.days, current.seconds, current.microseconds],
            )
        elif kind is _datetime.timezone:
            offset = current.utcoffset(None)
            if type(offset) is not _datetime.timedelta:
                raise UnsupportedReproductionState("Invalid fixed timezone offset")
            name = current.tzname(None)
            if name is not None and type(name) is not str:
                raise UnsupportedReproductionState("Invalid fixed timezone name")
            node.update(
                kind="temporal",
                type="timezone",
                value=[offset.days, offset.seconds, offset.microseconds, name],
                canonical_utc=current is _datetime.timezone.utc,
            )
        elif (
            kind is dict
            or kind is OwnedMap
            or kind is TrackedRow
            or kind is OwnedAreaRow
            or kind is OwnedStateSourceRow
            or kind is OwnedContainerFacts
            or kind is OwnedContainerRow
            or kind is SourceProvenanceEntries
        ):
            node.update(
                kind="dict",
                items=[
                    [encode(k, depth + 1), encode(v, depth + 1)]
                    for k, v in current.items()
                ],
            )
            if kind is SourceProvenanceEntries:
                if type(current._native_keys) is not bool:
                    raise UnsupportedReproductionState(
                        "Invalid native provenance admission"
                    )
                node["native_retained_storage"] = "source_provenance_entries"
                node["native_provenance_keys"] = current._native_keys
            elif kind is OwnedContainerRow:
                node["native_retained_storage"] = "container_row"
            elif kind is OwnedContainerFacts:
                node["native_retained_storage"] = "container_facts"
            elif kind is OwnedStateSourceRow:
                node["native_retained_storage"] = "source_row"
            elif kind is OwnedAreaRow:
                node["native_area_row"] = True
            elif kind is OwnedMap:
                node["native_retained_storage"] = current.name
                node["native_retained_owner"] = encode(current.owner.records, depth + 1)
            elif kind is TrackedRow:
                node["native_retained_storage"] = "row"
                node["native_retained_owner"] = encode(current.owner.records, depth + 1)
                node["native_retained_uid"] = encode(current.uid, depth + 1)
        elif kind in (list, tuple, set, frozenset) or kind is OwnedOrder:
            items = (
                sorted(current, key=_sort_key) if kind in (set, frozenset) else current
            )
            node.update(
                kind="list" if kind is OwnedOrder else kind.__name__,
                items=[encode(v, depth + 1) for v in items],
            )
            if kind is OwnedOrder:
                node["native_retained_storage"] = "order"
                node["native_retained_owner"] = encode(current.owner.records, depth + 1)
        elif kind is object:
            node.update(kind="opaque")
        else:
            name = _type_name(current)
            node.update(kind="object", type=name)
            if name == "ImmutableTerrainSet":
                node["items"] = [encode(v, depth + 1) for v in sorted(current)]
            elif name == "ImmutableQIMasks":
                # Preserve mask order and shared immutable owner identity.
                _class(name)(list(current))
                node["items"] = [encode(v, depth + 1) for v in current]
            elif name == "NativeDelivery":
                node["items"] = [encode(v, depth + 1) for v in current]
                node["attrs"] = encode(vars(current), depth + 1)
            else:
                attrs = dict(vars(current))
                if name == "Fight" and "_native_retained_owner" in attrs:
                    from .combat_retained_collections import bound_collections

                    if bound_collections(attrs) is not attrs["_native_retained_owner"]:
                        raise UnsupportedReproductionState(
                            "Unbound retained owner root"
                        )
                    attrs.pop("_native_retained_owner")
                if name in ("ActualActorQI", "ObservableCharacteristicStats"):
                    logical = "fight" if name == "ActualActorQI" else "_fight"
                    observer_ref = attrs.get("_fight_ref")
                    if (
                        logical in attrs
                        or type(observer_ref) is not ReferenceType
                        or observer_ref.__callback__ is not None
                        or type(observer_ref()) is not _class("Fight")
                    ):
                        raise UnsupportedReproductionState(
                            "Unbound native Fight observer"
                        )
                    owner = observer_ref()
                    if "_fight_anchor" in attrs:
                        if attrs["_fight_anchor"] is not owner:
                            raise UnsupportedReproductionState(
                                "Foreign native Fight anchor"
                            )
                        attrs.pop("_fight_anchor")
                    attrs = {
                        logical
                        if key == "_fight_ref"
                        else key: owner
                        if key == "_fight_ref"
                        else value
                        for key, value in attrs.items()
                    }
                if preserve_scalars:
                    node["attribute_order"] = [encode(key, depth + 1) for key in attrs]
                if name == "RuntimeMessages":
                    if attrs.get("_retained_gc_callbacks") is not None:
                        from .combat_retained_gc_authority import native_callbacks_known

                        if not native_callbacks_known(current):
                            raise UnsupportedReproductionState(
                                "Unqualified native runtime callback certificate"
                            )
                    if preserve_scalars:
                        node["service_keys"] = [
                            [
                                field,
                                encode(
                                    next(key for key in attrs if key == field),
                                    depth + 1,
                                ),
                            ]
                            for field in sorted(_RUNTIME_SERVICES)
                            if field in attrs
                        ]
                    for field in sorted(_RUNTIME_SERVICES):
                        service = attrs.pop(field, None)
                        if service is not None:
                            services.append({"node": index, "field": field})
                if name == "Fight" and "native_rail_movement_authority" in attrs:
                    if preserve_scalars:
                        node["service_keys"] = [
                            [
                                "native_rail_movement_authority",
                                encode(
                                    next(
                                        key
                                        for key in attrs
                                        if key == "native_rail_movement_authority"
                                    ),
                                    depth + 1,
                                ),
                            ]
                        ]
                    attrs.pop("native_rail_movement_authority")
                    services.append(
                        {"node": index, "field": "native_rail_movement_authority"}
                    )
                if name == "ActualActorQI":
                    blockers = attrs.pop("movement_blocking")
                    objects = (
                        *current.objects.values(),
                        *current.area_objects.values(),
                    )
                    if set(blockers) != {id(obj) for obj in objects}:
                        raise UnsupportedReproductionState(
                            "Unbound QI blocking authority"
                        )
                    node["blocking"] = [
                        [encode(obj, depth + 1), encode(blockers[id(obj)], depth + 1)]
                        for obj in objects
                    ]
                node["attrs"] = encode(attrs, depth + 1)
                if name in _MAPPING_TYPES:
                    node["mapping"] = encode(dict(current), depth + 1)
        return reference

    try:
        root = encode(value)
        result = dict(schema=SCHEMA, root=root, nodes=nodes, services=services)
        if len(json.dumps(result, allow_nan=False).encode()) > MAX_BYTES:
            raise UnsupportedReproductionState("Reproduction state size limit exceeded")
        return result
    finally:
        # Break the recursive closure without changing the captured graph.
        encode = None


def _retained_restore_roles(nodes):
    """Own canonical legacy storage only inside this unpublished decoded graph.

    Nodes are private shallow copies. Allocation still uses the original node
    identities, so every internal alias points to the same new gateway.
    Custom mapping/object schemas and incomplete Fight storage are untouched.
    """
    from .combat_retained_collections import SOURCE_NAMES, AREA_SOURCE_NAMES

    missing = object()

    def literal(value):
        if (
            value is None
            or type(value) is str
            or type(value) is int
            or type(value) is bool
        ):
            return value
        if type(value) is dict and set(value) == {"ref"} and type(value["ref"]) is int:
            index = value["ref"]
            if 0 <= index < len(nodes) and nodes[index].get("kind") == "str":
                return nodes[index].get("value", missing)
        return missing

    def reference(value, kind):
        if (
            type(value) is not dict
            or set(value) != {"ref"}
            or type(value["ref"]) is not int
        ):
            return None
        index = value["ref"]
        return (
            index
            if 0 <= index < len(nodes) and nodes[index].get("kind") == kind
            else None
        )

    fields = {
        "actors": "actors",
        "native_retained_records": "records",
        "native_retained_order": "order",
        **{name: name for name in SOURCE_NAMES},
    }
    for node in nodes:
        if node.get("kind") != "object" or node.get("type") != "Fight":
            continue
        attr_index = reference(node.get("attrs"), "dict")
        if attr_index is None:
            continue
        attrs = {
            literal(key): value
            for key, value in nodes[attr_index].get("items", ())
            if type(literal(key)) is str
        }
        if literal(attrs.get("native_retained_tracking", missing)) is not True:
            continue
        selected = {}
        for field, role in fields.items():
            index = reference(attrs.get(field), "list" if role == "order" else "dict")
            if index is None or index in selected:
                break
            selected[index] = role
        else:
            rows = []
            valid = True
            records_index = next(
                index for index, role in selected.items() if role == "records"
            )
            for index, role in selected.items():
                if role == "order":
                    valid = all(
                        type(literal(uid)) is int
                        for uid in nodes[index].get("items", ())
                    )
                else:
                    for key, value in nodes[index].get("items", ()):
                        uid = literal(key)
                        if type(uid) is not int:
                            valid = False
                            break
                        if role == "records":
                            row_index = reference(value, "dict")
                            if row_index is None:
                                valid = False
                                break
                            metadata = {
                                literal(k): literal(v)
                                for k, v in nodes[row_index].get("items", ())
                            }
                            if (
                                any(
                                    type(k) is not str or v is missing
                                    for k, v in metadata.items()
                                )
                                or type(metadata.get("uid")) is not int
                                or metadata["uid"] != uid
                                or type(metadata.get("manager_id")) is not int
                            ):
                                valid = False
                                break
                            rows.append((row_index, uid))
                if not valid:
                    break
            if not valid:
                continue
            for index, role in selected.items():
                nodes[index].setdefault("native_retained_storage", role)
            for index, uid in rows:
                nodes[index].setdefault("native_retained_storage", "row")
                nodes[index].setdefault("native_retained_owner", {"ref": records_index})
                nodes[index].setdefault("native_retained_uid", uid)
            # Fresh graph allocation preserves all aliases while certifying
            # legacy membership rows; this never converts live mappings.
            area_maps = {}
            for field in AREA_SOURCE_NAMES:
                area_index = reference(attrs.get(field), "dict")
                if (
                    area_index is None
                    or area_index in selected
                    or area_index in area_maps
                ):
                    break
                area_node = nodes[area_index]
                if area_node.get("native_retained_storage", field) != field or not all(
                    type(literal(key)) is int for key, _ in area_node.get("items", ())
                ):
                    break
                area_maps[area_index] = field
            else:
                for area_index, field in area_maps.items():
                    nodes[area_index].setdefault("native_retained_storage", field)
                area_rows = {}
                for area_index in area_maps:
                    for key, value in nodes[area_index].get("items", ()):
                        row_index = reference(value, "dict")
                        if row_index is None:
                            continue
                        row_node = nodes[row_index]
                        metadata = {literal(k): v for k, v in row_node.get("items", ())}
                        uid = literal(key)
                        valid = (
                            "native_retained_storage" not in row_node
                            and all(type(k) is str for k in metadata)
                            and type(literal(metadata.get("uid", missing))) is int
                            and literal(metadata["uid"]) == uid
                        )
                        if valid and "state_ledger" in metadata:
                            ledger_index = reference(metadata["state_ledger"], "object")
                            valid = (
                                ledger_index is not None
                                and nodes[ledger_index].get("type") == "StateLedger"
                            )
                            if valid:
                                ledger_attrs = reference(
                                    nodes[ledger_index].get("attrs"), "dict"
                                )
                                ledger_fields = (
                                    {}
                                    if ledger_attrs is None
                                    else {
                                        literal(k): literal(v)
                                        for k, v in nodes[ledger_attrs].get("items", ())
                                    }
                                )
                                valid = (
                                    type(ledger_fields.get("actor_id")) is int
                                    and ledger_fields["actor_id"] == uid
                                )
                        area_rows[row_index] = area_rows.get(row_index, True) and valid
                for row_index, valid in area_rows.items():
                    if valid:
                        nodes[row_index].setdefault("native_area_row", True)


def decode_state(payload):
    """Reconstruct an isolated graph using an explicit data type allowlist."""
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise UnsupportedReproductionState("Unknown reproduction state schema")
    if set(payload) != {"schema", "root", "nodes", "services"}:
        raise UnsupportedReproductionState("Unexpected reproduction state fields")
    if len(json.dumps(payload, allow_nan=False).encode()) > MAX_BYTES:
        raise UnsupportedReproductionState("Reproduction state size limit exceeded")
    nodes = payload["nodes"]
    if not isinstance(nodes, list) or len(nodes) > MAX_NODES:
        raise UnsupportedReproductionState("Invalid reproduction nodes")
    if any(type(node) is not dict for node in nodes):
        raise UnsupportedReproductionState("Invalid reproduction node")
    nodes = [dict(node) for node in nodes]
    _retained_restore_roles(nodes)
    from .combat_retained_collections import (
        OwnedMap,
        OwnedOrder,
        TrackedRow,
        SOURCE_NAMES,
        AREA_SOURCE_NAMES,
        restore_collections,
        restore_area_collections,
    )
    from .combat_area_membership import OwnedAreaRow
    from .combat_source_parent_index import OwnedStateSourceRow
    from .combat_owned_container_facts import OwnedContainerFacts
    from .combat_owned_container_row import OwnedContainerRow
    from .combat_source_provenance_entries import SourceProvenanceEntries

    objects, building = {}, set()
    scalar_owners = {}
    preserve_scalars = any(
        node.get("kind") in ("str", "bytes") for node in nodes if isinstance(node, dict)
    )
    # Allocate all mutable owners first so cyclic actor/QI references remain exact.
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise UnsupportedReproductionState("Invalid reproduction node")
        kind = node.get("kind")
        if kind == "staticProjection":
            if set(node) != {"kind", "descriptor"}:
                raise UnsupportedReproductionState("Invalid static projection node")
            from .combat_reproduction_static_bindings import resolve_static_projection

            objects[index] = resolve_static_projection(node["descriptor"])
        elif kind == "staticCatalog":
            if set(node) != {"kind", "descriptor"}:
                raise UnsupportedReproductionState("Invalid static catalog node")
            from .combat_published_catalogs import resolve_static_catalog_descriptor

            objects[index] = resolve_static_catalog_descriptor(node["descriptor"])
        elif kind == "dict":
            role = node.get("native_retained_storage")
            if "native_area_row" in node:
                if node["native_area_row"] is not True or role is not None:
                    raise UnsupportedReproductionState("Invalid native area row")
                objects[index] = OwnedAreaRow()
            elif role is None:
                objects[index] = {}
            elif role == "container_row":
                objects[index] = OwnedContainerRow()
            elif role == "container_facts":
                objects[index] = OwnedContainerFacts()
            elif role == "source_provenance_entries":
                if type(node.get("native_provenance_keys")) is not bool:
                    raise UnsupportedReproductionState(
                        "Invalid native provenance admission"
                    )
                objects[index] = SourceProvenanceEntries()
            elif role == "source_row":
                objects[index] = OwnedStateSourceRow()
            elif role == "row":
                obj = dict.__new__(TrackedRow)
                obj.owner, obj.uid = None, None
                objects[index] = obj
            elif role in ("actors", "records", *SOURCE_NAMES, *AREA_SOURCE_NAMES):
                obj = dict.__new__(OwnedMap)
                obj.owner, obj.name = None, role
                objects[index] = obj
            else:
                raise UnsupportedReproductionState("Unknown retained storage role")
        elif kind == "list":
            role = node.get("native_retained_storage")
            if role is None:
                objects[index] = []
            elif role == "order":
                obj = list.__new__(OwnedOrder)
                obj.owner = None
                objects[index] = obj
            else:
                raise UnsupportedReproductionState("Unknown retained storage role")
        elif kind == "set":
            objects[index] = set()
        elif kind == "opaque":
            objects[index] = object()
        elif kind == "object":
            name = node.get("type")
            cls = _class(name)
            if name not in (
                "ImmutableTerrainSet",
                "ImmutableQIMasks",
                "NativeDelivery",
            ):
                objects[index] = (
                    dict.__new__(cls) if name in _MAPPING_TYPES else object.__new__(cls)
                )
        elif kind not in ("tuple", "frozenset", "str", "bytes", "temporal"):
            raise UnsupportedReproductionState("Unknown reproduction node kind")

    def decode(value, depth=0):
        if depth > MAX_DEPTH:
            raise UnsupportedReproductionState("Reproduction nesting limit exceeded")
        if value is None or type(value) in (str, int, bool):
            return value
        if type(value) is float and math.isfinite(value):
            return value
        if not isinstance(value, dict):
            raise UnsupportedReproductionState("Invalid reproduction value")
        if set(value) == {"bytes"}:
            try:
                return base64.b64decode(value["bytes"], validate=True)
            except (TypeError, ValueError) as error:
                raise UnsupportedReproductionState(
                    "Invalid reproduction bytes"
                ) from error
        if (
            set(value) != {"ref"}
            or type(value["ref"]) is not int
            or not 0 <= value["ref"] < len(nodes)
        ):
            raise UnsupportedReproductionState("Invalid reproduction reference")
        index = value["ref"]
        if index not in objects:
            if index in building:
                raise UnsupportedReproductionState(
                    "Unsupported immutable reference cycle"
                )
            building.add(index)
            node = nodes[index]
            kind = node["kind"]
            if kind == "temporal":
                temporal_type = node.get("type")
                value = node.get("value")
                if temporal_type == "datetime" and set(node) == {
                    "kind",
                    "type",
                    "value",
                    "tzinfo",
                }:
                    if (
                        type(value) is not list
                        or len(value) != 8
                        or any(type(part) is not int for part in value)
                    ):
                        raise UnsupportedReproductionState(
                            "Invalid reproduction datetime"
                        )
                    tzinfo = decode(node["tzinfo"], depth + 1)
                    if tzinfo is not None and type(tzinfo) is not _datetime.timezone:
                        raise UnsupportedReproductionState(
                            "Unsupported reproduction timezone"
                        )
                    objects[index] = _datetime.datetime(
                        *value[:7], tzinfo=tzinfo, fold=value[7]
                    )
                elif temporal_type == "date" and set(node) == {"kind", "type", "value"}:
                    if (
                        type(value) is not list
                        or len(value) != 3
                        or any(type(part) is not int for part in value)
                    ):
                        raise UnsupportedReproductionState("Invalid reproduction date")
                    objects[index] = _datetime.date(*value)
                elif temporal_type == "time" and set(node) == {
                    "kind",
                    "type",
                    "value",
                    "tzinfo",
                }:
                    if (
                        type(value) is not list
                        or len(value) != 5
                        or any(type(part) is not int for part in value)
                    ):
                        raise UnsupportedReproductionState("Invalid reproduction time")
                    tzinfo = decode(node["tzinfo"], depth + 1)
                    if tzinfo is not None and type(tzinfo) is not _datetime.timezone:
                        raise UnsupportedReproductionState(
                            "Unsupported reproduction timezone"
                        )
                    objects[index] = _datetime.time(
                        *value[:4], tzinfo=tzinfo, fold=value[4]
                    )
                elif temporal_type == "timedelta" and set(node) == {
                    "kind",
                    "type",
                    "value",
                }:
                    if (
                        type(value) is not list
                        or len(value) != 3
                        or any(type(part) is not int for part in value)
                    ):
                        raise UnsupportedReproductionState(
                            "Invalid reproduction duration"
                        )
                    objects[index] = _datetime.timedelta(*value)
                elif temporal_type == "timezone" and set(node) == {
                    "kind",
                    "type",
                    "value",
                    "canonical_utc",
                }:
                    if (
                        type(value) is not list
                        or len(value) != 4
                        or any(type(part) is not int for part in value[:3])
                        or value[3] is not None
                        and type(value[3]) is not str
                        or type(node["canonical_utc"]) is not bool
                    ):
                        raise UnsupportedReproductionState(
                            "Invalid reproduction timezone"
                        )
                    offset = _datetime.timedelta(*value[:3])
                    if node["canonical_utc"]:
                        if offset != _datetime.timedelta(0) or value[3] != "UTC":
                            raise UnsupportedReproductionState(
                                "Invalid canonical UTC timezone"
                            )
                        objects[index] = _datetime.timezone.utc
                    else:
                        objects[index] = _datetime.timezone(offset, value[3])
                else:
                    raise UnsupportedReproductionState(
                        "Invalid reproduction temporal node"
                    )
                building.remove(index)
                return objects[index]
            if kind in ("str", "bytes"):
                if set(node) != {"kind", "value"} or type(node["value"]) is not str:
                    raise UnsupportedReproductionState(
                        "Invalid reproduction scalar node"
                    )
                if kind == "str":
                    scalar = "".join((node["value"], ""))
                else:
                    try:
                        decoded = base64.b64decode(node["value"], validate=True)
                        scalar = b"".join((decoded, b""))
                    except (TypeError, ValueError) as error:
                        raise UnsupportedReproductionState(
                            "Invalid reproduction scalar bytes"
                        ) from error
                if id(scalar) in scalar_owners:
                    raise UnsupportedReproductionState(
                        "Distinct scalar identities cannot be preserved"
                    )
                scalar_owners[id(scalar)] = index
                objects[index] = scalar
                building.remove(index)
                return scalar
            items = [decode(item, depth + 1) for item in node["items"]]
            if kind == "tuple":
                objects[index] = tuple(items)
            elif kind == "frozenset":
                objects[index] = frozenset(items)
            elif node["type"] in ("ImmutableTerrainSet", "ImmutableQIMasks"):
                objects[index] = _class(node["type"])(items)
            else:
                objects[index] = tuple.__new__(_class(node["type"]), items)
            building.remove(index)
        return objects[index]

    try:
        # Resolve immutable nodes, then populate mutable references and attributes.
        for index in range(len(nodes)):
            decode({"ref": index})
        for index, node in enumerate(nodes):
            obj, kind = objects[index], node["kind"]
            if kind == "dict":
                for key, value in node["items"]:
                    key = decode(key)
                    if key in obj:
                        raise UnsupportedReproductionState(
                            "Duplicate reproduction mapping key"
                        )
                    # Controlled fresh graph construction: routing is rebuilt
                    # once after all actual Fight/row aliases have been restored.
                    dict.__setitem__(obj, key, decode(value))
                if node.get("native_retained_storage") == "source_provenance_entries":
                    # A revoked map stays revoked even after foreign keys were
                    # removed. Operation-local mutation fences start afresh.
                    obj._native_keys = node["native_provenance_keys"] and all(
                        type(key) is str for key in dict.__iter__(obj)
                    )
            elif kind == "list":
                list.extend(obj, (decode(item) for item in node["items"]))
            elif kind == "set":
                obj.update(decode(item) for item in node["items"])
        for index, node in enumerate(nodes):
            if node["kind"] != "object" or "attrs" not in node:
                continue
            attrs = decode(node["attrs"])
            if type(attrs) is not dict or any(type(k) is not str for k in attrs):
                raise UnsupportedReproductionState(
                    "Invalid reproduction object attributes"
                )
            if preserve_scalars:
                # Assign the restored dictionary itself; update() on a split
                # instance dictionary can substitute cached attribute key objects.
                object.__setattr__(objects[index], "__dict__", attrs)
            else:
                objects[index].__dict__.update(attrs)
            if "service_keys" in node:
                allowed = (
                    _RUNTIME_SERVICES
                    if node["type"] == "RuntimeMessages"
                    else {"native_rail_movement_authority"}
                    if node["type"] == "Fight"
                    else set()
                )
                if type(node["service_keys"]) is not list:
                    raise UnsupportedReproductionState("Invalid scalar service keys")
                restored_keys = set()
                for row in node["service_keys"]:
                    if (
                        type(row) is not list
                        or len(row) != 2
                        or row[0] not in allowed
                        or row[0] in restored_keys
                    ):
                        raise UnsupportedReproductionState("Invalid scalar service key")
                    key = decode(row[1])
                    if type(key) is not str or key != row[0]:
                        raise UnsupportedReproductionState("Scalar service key differs")
                    objects[index].__dict__[key] = None
                    restored_keys.add(key)
            elif node["type"] == "RuntimeMessages":
                objects[index].__dict__.update(
                    {field: None for field in _RUNTIME_SERVICES}
                )
            if node["type"] == "OwnedSocialContext":
                objects[index].validate()
            if node["type"] in _MAPPING_TYPES:
                dict.update(objects[index], decode(node["mapping"]))
            if node["type"] == "ActualActorQI":
                objects[index].movement_blocking = {
                    id(decode(key)): decode(value) for key, value in node["blocking"]
                }
        for index, node in enumerate(nodes):
            if "attribute_order" not in node:
                continue
            if (
                node.get("kind") != "object"
                or type(node["attribute_order"]) is not list
            ):
                raise UnsupportedReproductionState(
                    "Invalid reproduction attribute order"
                )
            keys = [decode(key) for key in node["attribute_order"]]
            attrs = vars(objects[index])
            if (
                any(type(key) is not str for key in keys)
                or len(keys) != len(set(keys))
                or set(keys) != set(attrs)
            ):
                raise UnsupportedReproductionState("Reproduction attribute keys differ")
            object.__setattr__(
                objects[index], "__dict__", {key: attrs[key] for key in keys}
            )
        # Attribute-order validation uses the historical logical fields. Only
        # now restore the physical weak edges, retaining that same field order.
        for index, node in enumerate(nodes):
            if node.get("type") not in (
                "ActualActorQI",
                "ObservableCharacteristicStats",
            ):
                continue
            logical = "fight" if node["type"] == "ActualActorQI" else "_fight"
            obj = objects[index]
            attrs = vars(obj)
            owner = attrs.get(logical)
            if type(owner) is not _class("Fight"):
                raise UnsupportedReproductionState("Invalid restored Fight observer")
            object.__setattr__(
                obj,
                "__dict__",
                {
                    "_fight_ref"
                    if key == logical
                    else key: ref(owner)
                    if key == logical
                    else value
                    for key, value in attrs.items()
                },
            )
        services = payload["services"]
        if not isinstance(services, list):
            raise UnsupportedReproductionState("Invalid reproduction service manifest")
        for row in services:
            if not isinstance(row, dict) or set(row) != {"node", "field"}:
                raise UnsupportedReproductionState(
                    "Invalid reproduction service requirement"
                )
            index, field = row["node"], row["field"]
            if (
                type(index) is not int
                or index not in objects
                or not (
                    nodes[index].get("type") == "RuntimeMessages"
                    and field in _RUNTIME_SERVICES
                    or nodes[index].get("type") == "Fight"
                    and field == "native_rail_movement_authority"
                )
            ):
                raise UnsupportedReproductionState(
                    "Unknown reproduction service requirement"
                )
        for index, node in enumerate(nodes):
            if node.get("native_retained_storage") == "container_facts":
                objects[index]._touch_all()
        for index, node in enumerate(nodes):
            if (
                node.get("type") == "Fight"
                and type(getattr(objects[index], "native_retained_records", None))
                is OwnedMap
            ):
                fight = objects[index]
                restore_collections(fight)
                if any(
                    type(getattr(fight, name, None)) is OwnedMap
                    and getattr(fight, name).name == name
                    for name in AREA_SOURCE_NAMES
                ):
                    restore_area_collections(fight)
        for index, node in enumerate(nodes):
            if node.get("native_retained_storage") == "row":
                records = decode(node["native_retained_owner"])
                uid = decode(node["native_retained_uid"])
                if (
                    type(records) is not OwnedMap
                    or records.name != "records"
                    or records.owner is None
                ):
                    raise UnsupportedReproductionState(
                        "Retained row lacks its restored registry"
                    )
                row = objects[index]
                if row.owner is not None and row.owner is not records.owner:
                    raise UnsupportedReproductionState("Retained row registry differs")
                row.owner, row.uid = records.owner, uid
        for index, node in enumerate(nodes):
            if "native_retained_storage" not in node or node[
                "native_retained_storage"
            ] in (
                "source_row",
                "container_facts",
                "container_row",
                "source_provenance_entries",
            ):
                continue
            current = objects[index]
            if current.owner is None and "native_retained_owner" in node:
                records = decode(node["native_retained_owner"])
                if type(records) is OwnedMap and records.name == "records":
                    current.owner = records.owner
            if current.owner is None:
                raise UnsupportedReproductionState(
                    "Retained storage has no restored Fight owner"
                )
        for index, node in enumerate(nodes):
            if node.get("type") == "NativePointerCheckpoint":
                objects[index].validate(objects[index]._qi.fight)
        _validate_publication_state(objects, nodes)
        return decode(payload["root"])
    finally:
        # Do not retain restored objects through the local recursive function.
        decode = None
