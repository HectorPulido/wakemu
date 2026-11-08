"""Lossless data graph for complete native context, without executing objects.

All instance fields and slot values are included. Reference nodes preserve
shared identity and cycles. Callables are descriptors: native execution stays
behind the world's oracle, never through eval/import of received code.
"""
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from collections import deque
from collections.abc import Sequence
import base64
import gzip
import json
import math
import inspect
import _thread
import zlib

from ..native.native_deadline import check

_CONTAINER_KINDS = {
    list: "list",
    tuple: "tuple",
    set: "set",
    frozenset: "frozenset",
    deque: "deque",
}
_LOCK_TYPES = (_thread.LockType, type(_thread.RLock()))


def _lock_fields(item):
    return dict(
        nativeAuthority=True,
        transferable=False,
        locked=item.locked() if hasattr(item, "locked") else None,
        ownedByCurrentThread=item._is_owned() if hasattr(item, "_is_owned") else None,
    )


def _instance_fields(item):
    values = dict(vars(item)) if hasattr(item, "__dict__") else {}
    if is_dataclass(item):
        values.update((field.name, getattr(item, field.name)) for field in fields(item))
    for cls in type(item).__mro__:
        slots = getattr(cls, "__slots__", ())
        if isinstance(slots, str):
            slots = (slots,)
        for name in slots:
            if name.startswith("__") and not name.endswith("__"):
                name = "_" + cls.__name__.lstrip("_") + name
            if name not in ("__dict__", "__weakref__") and hasattr(item, name):
                values[name] = getattr(item, name)
    # Factory backreferences expose their logical target, not weakref internals.
    if "_reference" in values or "_dispatcher_owner" in values:
        from weakref import ReferenceType
        from wakfu_server.combat_runtime_backrefs import FactoryOwnerReference

        if type(item) is FactoryOwnerReference and set(values) == {
            "_reference",
            "_escaped_owner",
        }:
            reference = values["_reference"]
            if type(reference) is ReferenceType and reference.__callback__ is None:
                owner = reference()
                if (
                    values["_escaped_owner"] is None
                    or values["_escaped_owner"] is owner
                ):
                    values = {"owner": owner}
        elif "_dispatcher_owner" in values:
            from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
            from wakfu_server.combat_event_replay import NativeEventReplay
            from wakfu_server.combat_condition_cell_batch import NativeCellBatchFactory
            from wakfu_server.combat_native_delayed_effects import NativeDelayedEffects

            if any(
                type(item) is kind
                for kind in (
                    NativeAreaEventRuntime,
                    NativeEventReplay,
                    NativeCellBatchFactory,
                    NativeDelayedEffects,
                )
            ):
                owner = values["_dispatcher_owner"]
                if type(owner) is FactoryOwnerReference:
                    owner = owner._reference()
                values = {
                    ("dispatcher" if key == "_dispatcher_owner" else key): (
                        owner if key == "_dispatcher_owner" else value
                    )
                    for key, value in values.items()
                }
    if "_stat_handler_owner" in values:
        from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
        from wakfu_server.combat_runtime_backrefs import FactoryOwnerReference

        if type(item) is NativeRetainedRuntime:
            owner = values["_stat_handler_owner"]
            if type(owner) is FactoryOwnerReference:
                owner = owner._reference()
            values = {
                ("stat_handler" if key == "_stat_handler_owner" else key): (
                    owner if key == "_stat_handler_owner" else value
                )
                for key, value in values.items()
            }
    # Owned storage projects its historical logical owner edge. Weak indexes
    # and the Fight's lifetime anchor are derived implementation details.
    if any(name in values for name in ("_owner_ref", "_native_retained_owner")):
        from weakref import ReferenceType
        from wakfu_server.combat_retained_collections import (
            OwnedMap,
            OwnedOrder,
            TrackedRow,
            RetainedCollections,
            bound_collections,
        )
        from wakfu_server.combat_state import Fight

        kind = type(item)
        if kind is OwnedMap or kind is OwnedOrder or kind is TrackedRow:
            reference = values.get("_owner_ref")
            if (
                "owner" not in values
                and "_owner_ref" in values
                and (
                    reference is None
                    or type(reference) is ReferenceType
                    and reference.__callback__ is None
                )
            ):
                owner = None if reference is None else reference()
                if owner is None or type(owner) is RetainedCollections:
                    # Replace at the same ordinal; appending owner would change
                    # the complete native fingerprint's ordered field stream.
                    values = {
                        ("owner" if name == "_owner_ref" else name): (
                            owner if name == "_owner_ref" else value
                        )
                        for name, value in values.items()
                    }
                    if (
                        type(owner) is RetainedCollections
                        and values.get("_owner_anchor") is owner
                    ):
                        values.pop("_owner_anchor")
        elif kind is Fight:
            owner = values.get("_native_retained_owner")
            if (
                type(owner) is RetainedCollections
                and bound_collections(values) is owner
            ):
                values.pop("_native_retained_owner")
    if "_fight_ref" in values:
        from weakref import ReferenceType
        from wakfu_server.combat_characteristic_link import (
            ObservableCharacteristicStats,
        )
        from wakfu_server.combat_pointer_qi_actor import ActualActorQI
        from wakfu_server.combat_state import Fight

        kind = type(item)
        if kind is ObservableCharacteristicStats or kind is ActualActorQI:
            logical = "_fight" if kind is ObservableCharacteristicStats else "fight"
            reference = values["_fight_ref"]
            if (
                logical not in values
                and type(reference) is ReferenceType
                and reference.__callback__ is None
            ):
                fight = reference()
                if type(fight) is Fight:
                    values = {
                        (logical if name == "_fight_ref" else name): (
                            fight if name == "_fight_ref" else value
                        )
                        for name, value in values.items()
                    }
                    if values.get("_fight_anchor") is fight:
                        values.pop("_fight_anchor")
    # Exact native row eligibility is derived, never part of authority bytes.
    if "_selected_scalar_proofs" in values:
        from wakfu_server.combat_retained_collections import RetainedCollections
        from wakfu_server.combat_selected_scalar_proof import SelectedScalarProofs

        if (
            type(item) is RetainedCollections
            and type(values["_selected_scalar_proofs"]) is SelectedScalarProofs
        ):
            values.pop("_selected_scalar_proofs")
    if "_scalar_eligibility" in values:
        from wakfu_server.combat_retained_collections import TrackedRow
        from wakfu_server.combat_source_parent_index import OwnedStateSourceRow

        if type(item) is TrackedRow or type(item) is OwnedStateSourceRow:
            proof = values["_scalar_eligibility"]
            if proof is None or type(proof) is bool:
                values.pop("_scalar_eligibility")
    if "_retained_value" in values:
        from wakfu_server.combat_retained_collections import TrackedRow
        from wakfu_server.combat_retained_effects import RetainedEffect

        if type(item) is TrackedRow:
            cached = values["_retained_value"]
            if cached is None or type(cached) is RetainedEffect:
                values.pop("_retained_value")
    return values


def _static_catalog_descriptor(value):
    """Recognize only the sealed published type, without inspecting its reader."""
    kind = type(value)
    if kind.__name__ != "PublishedStaticMapping" or kind.__module__ not in (
        "wakfu_server.combat_published_catalogs",
        "wakfu_server.combat.combat_published_catalogs",
    ):
        return None
    try:
        from wakfu_server.combat_published_catalogs import static_catalog_descriptor
    except ModuleNotFoundError as error:
        if error.name != "wakfu_server.combat_published_catalogs":
            raise
        # The host-mounted SDK can precede a complete World image rebuild.
        # Legacy images have no published views to encode; nested import
        # failures in an installed implementation must still propagate.
        return None

    return static_catalog_descriptor(value)


def _encode(value, *, serialize_nodes=False, _geometry_cache=True, _parts=None):
    check()
    if _parts is not None and not serialize_nodes:
        raise ValueError("Native parts encoding requires serialized nodes")
    nodes, identities = [], {}
    visits = 0
    node_encoder = (
        json.JSONEncoder(separators=(",", ":"), allow_nan=False)
        if serialize_nodes
        else None
    )
    fragment_lookup = None
    fragment_publish = None
    fragment_rebase = None
    tuple_node_bytes = None
    tuple_value_bytes = None
    if serialize_nodes and _geometry_cache:
        from .native_geometry_fragments import (
            get_fragment,
            cache_fragment_from_encoded,
            cached_int_tuple_node,
            cached_int_tuple_values,
        )

        from .native_geometry_render_cache import rebase_fragment

        fragment_rebase = rebase_fragment
        fragment_lookup = get_fragment
        fragment_publish = cache_fragment_from_encoded
        tuple_node_bytes = cached_int_tuple_node
        tuple_value_bytes = cached_int_tuple_values

    def visit(item):
        nonlocal visits
        # Primitive values and repeated references do not allocate graph nodes.
        # Count traversal work rather than node allocation so long scalar
        # arrays and heavily aliased authority graphs remain interruptible.
        visits += 1
        if visits & 255 == 0:
            check()
        kind = type(item)
        if item is None or kind is str or kind is int or kind is bool:
            return {"value": item}
        if kind is float:
            if not math.isfinite(item):
                raise ValueError("Non-finite native context value")
            return {"value": item}
        identity = id(item)
        existing = identities.get(identity)
        if existing is not None:
            return {"ref": existing}
        index = len(nodes)
        if index % 1024 == 0:
            check()
        identities[identity] = index
        node = {}
        nodes.append(node)
        if (
            fragment_lookup is not None
            and isinstance(item, frozenset)
            and type(item) is not frozenset
        ):
            fragment = fragment_lookup(
                item,
                lambda terrain: _encode(
                    terrain, serialize_nodes=True, _geometry_cache=False
                ),
                _instance_fields,
                build=_parts is not None,
            )
            if fragment is not None:
                if _parts is not None:
                    following, assignments = _parts.add(
                        fragment, identities, len(nodes)
                    )
                    nodes[index] = None
                    nodes.extend([None] * (following - len(nodes)))
                    identities.update(assignments)
                    check()
                    return {"ref": index}
                root_index, following, assignments, rows = fragment_rebase(
                    fragment, identities, len(nodes)
                )
                if root_index != index:
                    raise ValueError("Native geometry fragment root identity mismatch")
                nodes.extend([None] * (following - len(nodes)))
                identities.update(assignments)
                for row_index, serialized in rows:
                    if row_index % 1024 == 0:
                        check()
                    nodes[row_index] = serialized
                check()
                return {"ref": index}
        # Exact integer tuples have no identity-bearing children or custom
        # fields. Preserve the already-reserved tuple node ID, but avoid
        # allocating one scalar-reference dictionary per integer.
        if (
            serialize_nodes
            and tuple_value_bytes is not None
            and type(item) is tuple
            and _CONTAINER_KINDS.get(tuple) == "tuple"
        ):
            serialized_tuple = tuple_value_bytes(item)
            if serialized_tuple is not None:
                nodes[index] = serialized_tuple
                return {"ref": index}
        static_descriptor = _static_catalog_descriptor(item)
        if static_descriptor is not None:
            node.update(type="staticCatalog", descriptor=static_descriptor)
        elif isinstance(item, (bytes, bytearray, memoryview)):
            node.update(
                type=type(item).__name__,
                value=base64.b64encode(bytes(item)).decode("ascii"),
            )
        elif isinstance(item, (datetime, date)):
            node.update(type=type(item).__name__, value=item.isoformat())
            if isinstance(item, datetime):
                node["fold"] = item.fold
        elif isinstance(item, Decimal):
            if not item.is_finite():
                raise ValueError("Non-finite native decimal")
            node.update(type="decimal", value=str(item))
        elif isinstance(item, dict):
            node.update(
                type="dict", entries=[[visit(k), visit(v)] for k, v in dict.items(item)]
            )
        elif isinstance(item, (list, tuple, set, frozenset, deque)):
            sequence = item
            if isinstance(item, (set, frozenset)):
                # Native terrain and registries have deterministic comparable
                # keys. A mixed set still retains all items through type keys.
                try:
                    sequence = sorted(item)
                except TypeError:
                    sequence = list(item)
            kind = _CONTAINER_KINDS.get(type(item))
            if kind is None:
                kind = next(
                    name
                    for cls, name in _CONTAINER_KINDS.items()
                    if isinstance(item, cls)
                )
            node.update(type=kind, items=[visit(v) for v in sequence])
            if isinstance(item, deque):
                node["maxlen"] = item.maxlen
        elif isinstance(item, _LOCK_TYPES):
            node.update(
                type="object",
                module=type(item).__module__,
                name=type(item).__qualname__,
                fields={name: visit(v) for name, v in _lock_fields(item).items()},
            )
        elif inspect.isroutine(item):
            node.update(
                type="callable",
                module=getattr(item, "__module__", type(item).__module__),
                name=getattr(item, "__qualname__", type(item).__qualname__),
            )
        else:
            values = _instance_fields(item)
            if not values and not hasattr(item, "__dict__") and not is_dataclass(item):
                raise ValueError(
                    "Unsupported native context type: " + type(item).__qualname__
                )
            node.update(
                type="object",
                module=type(item).__module__,
                name=type(item).__qualname__,
                fields={name: visit(v) for name, v in values.items()},
            )
        if isinstance(item, (dict, list, tuple, set, frozenset, deque)) and type(
            item
        ) not in (dict, list, tuple, set, frozenset, deque):
            node["nativeClass"] = dict(
                module=type(item).__module__, name=type(item).__qualname__
            )
            node["fields"] = {
                name: visit(v) for name, v in _instance_fields(item).items()
            }
        if serialize_nodes:
            # References already point to stable indices. A completed node
            # can become JSON immediately instead of retaining thousands of
            # tracked Python containers until the entire arena is encoded.
            serialized = (
                tuple_node_bytes(item, node)
                if tuple_node_bytes is not None and type(item) is tuple
                else None
            )
            nodes[index] = (
                node_encoder.encode(node) if serialized is None else serialized
            )
            if (
                _parts is None
                and fragment_publish is not None
                and isinstance(item, frozenset)
                and type(item) is not frozenset
            ):
                # Seed from the complete nodes already encoded above. A cold
                # terrain does not need a second graph serialization/parse.
                fragment_publish(item, identities, nodes, _instance_fields)
        return {"ref": index}

    try:
        root = visit(value)
    finally:
        # A recursive closure otherwise retains itself, its memo and every
        # encoded node until cyclic GC. Repeated complete arena snapshots
        # then retain entire discarded graphs and trigger long collections.
        # Break only this local function cycle; retain all returned data.
        visit = None
    if _parts is not None:
        return _parts.finish(root, nodes)
    if serialize_nodes:
        return (
            '{"encoding":"wakfu-native-graph-1","root":'
            + json.dumps(root, separators=(",", ":"), allow_nan=False)
            + ',"nodes":['
            + ",".join(nodes)
            + "]}"
        ).encode()
    return dict(encoding="wakfu-native-graph-1", root=root, nodes=nodes)


def encode(value):
    return _encode(value)


def encode_bytes(value):
    """The identical complete graph as JSON, without a retained Python tree."""
    return _encode(value, serialize_nodes=True)


class NativeGraph:
    """Read a validated native data graph, retaining types and every field."""

    def __init__(self, encoded, *, _validation_nodes=None):
        if isinstance(encoded, bytes):
            try:
                check()
                if encoded.startswith(b"\x1f\x8b"):
                    encoded = gzip.decompress(encoded)
                check()
                encoded = json.loads(encoded)
            except TimeoutError:
                raise
            except (OSError, EOFError, ValueError, UnicodeError, zlib.error) as error:
                raise ValueError("Invalid native graph bytes") from error
        if (
            not isinstance(encoded, dict)
            or set(encoded) != {"encoding", "root", "nodes"}
            or encoded["encoding"] != "wakfu-native-graph-1"
            or not isinstance(encoded["nodes"], list)
            and not (
                _validation_nodes is not None and isinstance(encoded["nodes"], Sequence)
            )
        ):
            raise ValueError("Invalid native graph")
        self.data = encoded
        self.nodes = encoded["nodes"]
        references = 0

        def reference(ref):
            nonlocal references
            references += 1
            if references % 256 == 0:
                check()
            if not isinstance(ref, dict) or len(ref) != 1:
                raise ValueError("Invalid native graph reference")
            if "value" in ref:
                value = ref["value"]
                if value is not None and type(value) not in (str, int, float, bool):
                    raise ValueError("Invalid native primitive")
                if type(value) is float and not math.isfinite(value):
                    raise ValueError("Non-finite native primitive")
            elif (
                "ref" not in ref
                or type(ref["ref"]) is not int
                or not 0 <= ref["ref"] < len(self.nodes)
            ):
                raise ValueError("Invalid native graph reference")

        reference(encoded["root"])
        # Internal parts readers supply only dynamic nodes here AFTER every
        # immutable fragment has been validated and its reference map sealed.
        # Ordinary untrusted flat graphs always validate every node.
        for node_index, node in enumerate(
            self.nodes if _validation_nodes is None else _validation_nodes
        ):
            if node_index % 1024 == 0:
                check()
            if not isinstance(node, dict):
                raise ValueError("Invalid native graph node")
            kind = node.get("type")
            extra = set()
            if (
                kind in ("dict", "list", "tuple", "set", "frozenset", "deque")
                and "nativeClass" in node
            ):
                descriptor = node["nativeClass"]
                if (
                    not isinstance(descriptor, dict)
                    or set(descriptor) != {"module", "name"}
                    or any(
                        not isinstance(descriptor[k], str) or not descriptor[k]
                        for k in descriptor
                    )
                    or not isinstance(node.get("fields"), dict)
                    or any(not isinstance(key, str) for key in node["fields"])
                ):
                    raise ValueError("Invalid native container class")
                for ref in node["fields"].values():
                    reference(ref)
                extra = {"nativeClass", "fields"}
            if kind in ("object", "callable") and any(
                not isinstance(node.get(key), str) or not node[key]
                for key in ("module", "name")
            ):
                raise ValueError("Invalid native type descriptor")
            if kind == "staticCatalog":
                if set(node) != {"type", "descriptor"}:
                    raise ValueError("Invalid native static catalog node")
                from wakfu_server.combat_published_catalogs import (
                    validate_static_catalog_descriptor,
                )

                validate_static_catalog_descriptor(node["descriptor"])
            elif kind == "dict":
                if set(node) != {"type", "entries"} | extra or not isinstance(
                    node["entries"], list
                ):
                    raise ValueError("Invalid native mapping")
                for entry in node["entries"]:
                    if not isinstance(entry, list) or len(entry) != 2:
                        raise ValueError("Invalid native mapping entry")
                    reference(entry[0])
                    reference(entry[1])
            elif kind in (
                "list",
                "tuple",
                "set",
                "frozenset",
                "deque",
                "ImmutableTerrainSet",
            ):
                expected = (
                    {"type", "items", "maxlen"}
                    if kind == "deque"
                    else {"type", "items"}
                )
                if set(node) != expected | extra or not isinstance(node["items"], list):
                    raise ValueError("Invalid native sequence")
                if (
                    kind == "deque"
                    and node["maxlen"] is not None
                    and (type(node["maxlen"]) is not int or node["maxlen"] < 0)
                ):
                    raise ValueError("Invalid native deque maximum length")
                for item in node["items"]:
                    reference(item)
            elif kind == "object":
                if set(node) != {"type", "module", "name", "fields"} or not isinstance(
                    node["fields"], dict
                ):
                    raise ValueError("Invalid native object")
                if not all(isinstance(key, str) for key in node["fields"]):
                    raise ValueError("Invalid native field name")
                for item in node["fields"].values():
                    reference(item)
            elif kind == "callable":
                if set(node) != {"type", "module", "name"}:
                    raise ValueError("Invalid native callable descriptor")
            elif kind in (
                "bytes",
                "bytearray",
                "memoryview",
                "date",
                "datetime",
                "decimal",
            ):
                expected = (
                    {"type", "value", "fold"}
                    if kind == "datetime"
                    else {"type", "value"}
                )
                if set(node) != expected or not isinstance(node["value"], str):
                    raise ValueError("Invalid native scalar")
                try:
                    if kind in ("bytes", "bytearray", "memoryview"):
                        base64.b64decode(node["value"], validate=True)
                    elif kind == "date":
                        date.fromisoformat(node["value"])
                    elif kind == "datetime":
                        datetime.fromisoformat(node["value"])
                        if type(node["fold"]) is not int or node["fold"] not in (0, 1):
                            raise ValueError("Invalid datetime fold")
                    elif not Decimal(node["value"]).is_finite():
                        raise ValueError("Non-finite decimal")
                except (ValueError, TypeError, ArithmeticError) as error:
                    raise ValueError("Invalid native scalar value") from error
            else:
                raise ValueError("Unknown native graph node type")

    def resolve(self, reference):
        return (
            reference["value"] if "value" in reference else self.nodes[reference["ref"]]
        )

    @property
    def root(self):
        return self.resolve(self.data["root"])

    def static_catalog(self, reference):
        """Resolve an explicit published pin; plain conversion never loads rows."""
        node = self.resolve(reference)
        if not isinstance(node, dict) or node.get("type") != "staticCatalog":
            raise ValueError("Native value is not a published static catalog")
        from wakfu_server.combat_published_catalogs import (
            resolve_static_catalog_descriptor,
        )

        return resolve_static_catalog_descriptor(node["descriptor"])

    def field(self, reference, key):
        """Return a field reference without projecting away other information."""
        node = self.resolve(reference)
        if isinstance(node, dict) and node.get("type") == "object":
            if key not in node["fields"]:
                raise KeyError(key)
            return node["fields"][key]
        if isinstance(node, dict) and node.get("type") == "dict":
            for name, value in node["entries"]:
                if self.plain(name) == key:
                    return value
            raise KeyError(key)
        raise ValueError("Native value has no instance fields")

    def plain(self, reference, *, _visiting=None, _progress=None):
        """Decode data containers/scalars only; never instantiate native classes.

        Cycles remain available through field/reference navigation. Explicit plain
        conversion rejects cycles and objects instead of silently losing their data."""
        progress = [0] if _progress is None else _progress
        progress[0] += 1
        if progress[0] % 256 == 0:
            check()
        if "value" in reference:
            return reference["value"]
        visiting = set() if _visiting is None else _visiting
        identity = reference["ref"]
        if identity in visiting:
            raise ValueError("Cyclic native value requires reference navigation")
        node = self.nodes[identity]
        kind = node["type"]
        visiting.add(identity)
        try:
            if kind in ("list", "tuple", "set", "frozenset", "deque"):
                result = [
                    self.plain(v, _visiting=visiting, _progress=progress)
                    for v in node["items"]
                ]
                if kind == "deque":
                    return deque(result, maxlen=node["maxlen"])
                return {
                    "list": list,
                    "tuple": tuple,
                    "set": set,
                    "frozenset": frozenset,
                }[kind](result)
            if kind == "dict":
                return {
                    self.plain(k, _visiting=visiting, _progress=progress): self.plain(
                        v, _visiting=visiting, _progress=progress
                    )
                    for k, v in node["entries"]
                }
            if kind in ("bytes", "bytearray", "memoryview"):
                value = base64.b64decode(node["value"], validate=True)
                return {
                    "bytes": bytes,
                    "bytearray": bytearray,
                    "memoryview": memoryview,
                }[kind](value)
            if kind == "date":
                return date.fromisoformat(node["value"])
            if kind == "datetime":
                return datetime.fromisoformat(node["value"]).replace(fold=node["fold"])
            if kind == "decimal":
                return Decimal(node["value"])
            raise ValueError("Native object requires field/reference navigation")
        finally:
            visiting.remove(identity)
