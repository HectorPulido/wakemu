"""Versioned offline combat graphs; never a live checkpoint recovery format.

Preserve aliases, dictionary key types, collection order and canonical QI
pointers. Only named data types are accepted; no pickle, evaluated source or
payload-selected imports. Runtime services must be rebuilt by a trusted recipe.
"""
import base64
import importlib
import json
import math

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


def _sort_key(value):
    if value is None or type(value) in (str, int, bool, float, bytes):
        return (type(value).__name__, repr(value))
    if type(value) is tuple:
        return ("tuple", tuple(_sort_key(item) for item in value))
    raise UnsupportedReproductionState("Unordered collection has unsupported elements")


def encode_state(value, *, preserve_scalars=False):
    """Capture data and service requirements without invoking any providers."""
    if type(preserve_scalars) is not bool:
        raise UnsupportedReproductionState("Invalid scalar identity policy")
    nodes, seen, services = [], {}, []

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
        if kind is str:
            node.update(kind="str", value=current)
        elif kind is bytes:
            node.update(kind="bytes", value=base64.b64encode(current).decode("ascii"))
        elif kind is dict:
            node.update(
                kind="dict",
                items=[
                    [encode(k, depth + 1), encode(v, depth + 1)]
                    for k, v in current.items()
                ],
            )
        elif kind in (list, tuple, set, frozenset):
            items = (
                sorted(current, key=_sort_key) if kind in (set, frozenset) else current
            )
            node.update(kind=kind.__name__, items=[encode(v, depth + 1) for v in items])
        elif kind is object:
            node.update(kind="opaque")
        else:
            name = _type_name(current)
            node.update(kind="object", type=name)
            if name == "ImmutableTerrainSet":
                node["items"] = [encode(v, depth + 1) for v in sorted(current)]
            elif name == "NativeDelivery":
                node["items"] = [encode(v, depth + 1) for v in current]
                node["attrs"] = encode(vars(current), depth + 1)
            else:
                attrs = dict(vars(current))
                if preserve_scalars:
                    node["attribute_order"] = [encode(key, depth + 1) for key in attrs]
                if name == "RuntimeMessages":
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

    root = encode(value)
    result = dict(schema=SCHEMA, root=root, nodes=nodes, services=services)
    if len(json.dumps(result, allow_nan=False).encode()) > MAX_BYTES:
        raise UnsupportedReproductionState("Reproduction state size limit exceeded")
    return result


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
        if kind == "dict":
            objects[index] = {}
        elif kind == "list":
            objects[index] = []
        elif kind == "set":
            objects[index] = set()
        elif kind == "opaque":
            objects[index] = object()
        elif kind == "object":
            name = node.get("type")
            cls = _class(name)
            if name not in ("ImmutableTerrainSet", "NativeDelivery"):
                objects[index] = (
                    dict.__new__(cls) if name in _MAPPING_TYPES else object.__new__(cls)
                )
        elif kind not in ("tuple", "frozenset", "str", "bytes"):
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
            elif node["type"] == "ImmutableTerrainSet":
                objects[index] = _class(node["type"])(items)
            else:
                objects[index] = tuple.__new__(_class(node["type"]), items)
            building.remove(index)
        return objects[index]

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
                obj[key] = decode(value)
        elif kind == "list":
            obj.extend(decode(item) for item in node["items"])
        elif kind == "set":
            obj.update(decode(item) for item in node["items"])
    for index, node in enumerate(nodes):
        if node["kind"] != "object" or "attrs" not in node:
            continue
        attrs = decode(node["attrs"])
        if type(attrs) is not dict or any(type(k) is not str for k in attrs):
            raise UnsupportedReproductionState("Invalid reproduction object attributes")
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
            objects[index].__dict__.update({field: None for field in _RUNTIME_SERVICES})
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
        if node.get("kind") != "object" or type(node["attribute_order"]) is not list:
            raise UnsupportedReproductionState("Invalid reproduction attribute order")
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
        if node.get("type") == "NativePointerCheckpoint":
            objects[index].validate(objects[index]._qi.fight)
    return decode(payload["root"])
