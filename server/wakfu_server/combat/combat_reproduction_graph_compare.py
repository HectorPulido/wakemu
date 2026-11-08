"""Ordered graph isomorphism ignoring only exact string-node identity.

This compares codec evidence without reconstructing domain objects or rewriting
nodes. Every non-string node participates in a bijection, including bytes.
"""
import base64
import datetime as _datetime
import math
import json

from .combat_reproduction_state import SCHEMA, MAX_NODES, _TYPES


class _Invalid(ValueError):
    pass


def _validate(graph):
    if (
        type(graph) is not dict
        or set(graph) != {"schema", "root", "nodes", "services"}
        or graph["schema"] != SCHEMA
        or type(graph["nodes"]) is not list
        or len(graph["nodes"]) > MAX_NODES
        or type(graph["services"]) is not list
    ):
        raise _Invalid()
    # Transport must be acyclic JSON even though encoded domain refs can cycle.
    json.dumps(graph, allow_nan=False)
    nodes = graph["nodes"]

    def ref(value):
        return (
            type(value) is dict
            and set(value) == {"ref"}
            and type(value["ref"]) is int
            and 0 <= value["ref"] < len(nodes)
        )

    def value(item):
        if item is None or type(item) in (bool, int, str):
            return
        if type(item) is float and math.isfinite(item):
            return
        if ref(item):
            return
        if type(item) is dict and set(item) == {"bytes"} and type(item["bytes"]) is str:
            base64.b64decode(item["bytes"], validate=True)
            return
        raise _Invalid()

    def pairs(items):
        if type(items) is not list:
            raise _Invalid()
        for pair in items:
            if type(pair) is not list or len(pair) != 2:
                raise _Invalid()
            value(pair[0])
            value(pair[1])

    def sequence(items):
        if type(items) is not list:
            raise _Invalid()
        for item in items:
            value(item)

    value(graph["root"])
    for node in nodes:
        if type(node) is not dict or type(node.get("kind")) is not str:
            raise _Invalid()
        kind = node["kind"]
        if kind in ("str", "bytes"):
            if set(node) != {"kind", "value"} or type(node["value"]) is not str:
                raise _Invalid()
            if kind == "bytes":
                base64.b64decode(node["value"], validate=True)
        elif kind == "temporal":
            temporal_type, parts = node.get("type"), node.get("value")
            if type(parts) is not list:
                raise _Invalid()
            try:
                if temporal_type == "datetime":
                    if (
                        set(node) != {"kind", "type", "value", "tzinfo"}
                        or len(parts) != 8
                        or any(type(part) is not int for part in parts)
                        or parts[7] not in (0, 1)
                    ):
                        raise _Invalid()
                    _datetime.datetime(*parts[:7], fold=parts[7])
                    zone = node["tzinfo"]
                    if zone is not None and (
                        not ref(zone)
                        or nodes[zone["ref"]].get("kind") != "temporal"
                        or nodes[zone["ref"]].get("type") != "timezone"
                    ):
                        raise _Invalid()
                elif temporal_type == "date":
                    if (
                        set(node) != {"kind", "type", "value"}
                        or len(parts) != 3
                        or any(type(part) is not int for part in parts)
                    ):
                        raise _Invalid()
                    _datetime.date(*parts)
                elif temporal_type == "time":
                    if (
                        set(node) != {"kind", "type", "value", "tzinfo"}
                        or len(parts) != 5
                        or any(type(part) is not int for part in parts)
                        or parts[4] not in (0, 1)
                    ):
                        raise _Invalid()
                    _datetime.time(*parts[:4], fold=parts[4])
                    zone = node["tzinfo"]
                    if zone is not None and (
                        not ref(zone)
                        or nodes[zone["ref"]].get("kind") != "temporal"
                        or nodes[zone["ref"]].get("type") != "timezone"
                    ):
                        raise _Invalid()
                elif temporal_type == "timedelta":
                    if (
                        set(node) != {"kind", "type", "value"}
                        or len(parts) != 3
                        or any(type(part) is not int for part in parts)
                    ):
                        raise _Invalid()
                    _datetime.timedelta(*parts)
                elif temporal_type == "timezone":
                    if (
                        set(node) != {"kind", "type", "value", "canonical_utc"}
                        or len(parts) != 4
                        or any(type(part) is not int for part in parts[:3])
                        or parts[3] is not None
                        and type(parts[3]) is not str
                        or type(node["canonical_utc"]) is not bool
                    ):
                        raise _Invalid()
                    _datetime.timezone(_datetime.timedelta(*parts[:3]), parts[3])
                    if node["canonical_utc"] and (
                        parts[:3] != [0, 0, 0] or parts[3] != "UTC"
                    ):
                        raise _Invalid()
                else:
                    raise _Invalid()
            except (OverflowError, TypeError, ValueError) as error:
                raise _Invalid() from error
        elif kind == "opaque":
            if set(node) != {"kind"}:
                raise _Invalid()
        elif kind in ("staticCatalog", "staticProjection"):
            if (
                set(node) != {"kind", "descriptor"}
                or type(node["descriptor"]) is not dict
            ):
                raise _Invalid()
            from .combat_published_catalogs import validate_static_catalog_descriptor

            descriptor = node["descriptor"]
            if kind == "staticCatalog":
                validate_static_catalog_descriptor(descriptor)
            else:
                if (
                    set(descriptor) != {"policy", "catalog", "record", "path"}
                    or descriptor["policy"] != "wakemu.published-projection.v1"
                    or type(descriptor["record"]) is not str
                    or type(descriptor["path"]) is not list
                ):
                    raise _Invalid()
                validate_static_catalog_descriptor(descriptor["catalog"])
                for step in descriptor["path"]:
                    if (
                        type(step) is not list
                        or len(step) != 2
                        or type(step[0]) is not str
                    ):
                        raise _Invalid()
                    if step[0] == "key" and type(step[1]) in (str, int):
                        continue
                    if step[0] == "item" and type(step[1]) is int and step[1] >= 0:
                        continue
                    raise _Invalid()
        elif kind in ("dict", "list", "tuple", "set", "frozenset"):
            allowed = {
                "kind",
                "items",
                "native_retained_storage",
                "native_retained_owner",
                "native_retained_uid",
                "native_area_row",
                "native_provenance_keys",
            }
            if not {"kind", "items"} <= set(node) or set(node) - allowed:
                raise _Invalid()
            (pairs if kind == "dict" else sequence)(node["items"])
            for name in ("native_retained_owner", "native_retained_uid"):
                if name in node:
                    value(node[name])
            if (
                "native_retained_storage" in node
                and type(node["native_retained_storage"]) is not str
            ):
                raise _Invalid()
            for name in ("native_area_row", "native_provenance_keys"):
                if name in node and type(node[name]) is not bool:
                    raise _Invalid()
        elif kind == "object":
            allowed = {
                "kind",
                "type",
                "attrs",
                "items",
                "mapping",
                "attribute_order",
                "service_keys",
                "blocking",
            }
            if (
                set(node) - allowed
                or type(node.get("type")) is not str
                or node["type"] not in _TYPES
            ):
                raise _Invalid()
            if node["type"] not in (
                "ImmutableTerrainSet",
                "ImmutableQIMasks",
            ) and not ref(node.get("attrs")):
                raise _Invalid()
            if "attrs" in node and nodes[node["attrs"]["ref"]].get("kind") != "dict":
                raise _Invalid()
            for name in ("items", "attribute_order"):
                if name in node:
                    sequence(node[name])
            for name in ("service_keys", "blocking"):
                if name in node:
                    pairs(node[name])
            if "mapping" in node and not ref(node["mapping"]):
                raise _Invalid()
            if (
                node["type"] in ("ImmutableTerrainSet", "ImmutableQIMasks")
                and "items" not in node
            ):
                raise _Invalid()
        else:
            raise _Invalid()
    seen_services = set()
    for service in graph["services"]:
        if (
            type(service) is not dict
            or set(service) != {"node", "field"}
            or type(service["node"]) is not int
            or not 0 <= service["node"] < len(nodes)
            or nodes[service["node"]]["kind"] != "object"
            or type(service["field"]) is not str
        ):
            raise _Invalid()
        key = (service["node"], service["field"])
        if key in seen_services:
            raise _Invalid()
        seen_services.add(key)
    return nodes


def compare_graphs(expected, actual):
    """Return False for unequal/malformed graphs; preserve all non-str aliases.

    Input must be codec graphs, not gameplay objects. Both graphs must contain
    only nodes reachable from the root or explicit service-owner references.
    """
    try:
        left, right = _validate(expected), _validate(actual)
        forward, reverse, reached_left, reached_right = {}, {}, set(), set()
        pending = [(expected["root"], actual["root"])]
        if len(expected["services"]) != len(actual["services"]):
            return False
        for first, second in zip(expected["services"], actual["services"]):
            if first["field"] != second["field"]:
                return False
            pending.append(({"ref": first["node"]}, {"ref": second["node"]}))
        while pending:
            first, second = pending.pop()
            first_ref = type(first) is dict and set(first) == {"ref"}
            second_ref = type(second) is dict and set(second) == {"ref"}
            if first_ref or second_ref:
                if not first_ref or not second_ref:
                    return False
                a, b = first["ref"], second["ref"]
                if (
                    type(a) is not int
                    or type(b) is not int
                    or not 0 <= a < len(left)
                    or not 0 <= b < len(right)
                ):
                    return False
                reached_left.add(a)
                reached_right.add(b)
                x, y = left[a], right[b]
                if x["kind"] == "str" or y["kind"] == "str":
                    if (
                        x["kind"] != "str"
                        or y["kind"] != "str"
                        or x["value"] != y["value"]
                    ):
                        return False
                    continue
                if a in forward or b in reverse:
                    if forward.get(a) != b or reverse.get(b) != a:
                        return False
                    continue
                forward[a], reverse[b] = b, a
                pending.append((x, y))
            elif type(first) is not type(second):
                return False
            elif type(first) is dict:
                if list(first) != list(second):
                    return False
                pending.extend((first[key], second[key]) for key in first)
            elif type(first) is list:
                if len(first) != len(second):
                    return False
                pending.extend(zip(first, second))
            elif first is None or type(first) in (str, int, bool):
                if first != second:
                    return False
            elif type(first) is float:
                if (
                    not math.isfinite(first)
                    or not math.isfinite(second)
                    or first.hex() != second.hex()
                ):
                    return False
            else:
                return False
        return len(reached_left) == len(left) and len(reached_right) == len(right)
    except (
        ValueError,
        TypeError,
        KeyError,
        IndexError,
        AttributeError,
        RecursionError,
    ):
        return False
