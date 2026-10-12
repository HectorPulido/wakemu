"""Plain checkpoint encoding over an already qualified canonical pointer owner.

Decoding never constructs actor/area authority from a roster. A caller must bind
an existing qualified owner; loading a new arbitrary persisted fight is excluded.
"""
from copy import deepcopy
import json
from .combat_trove_byte_set import NativeTroveByteSet

SCHEMA = "native.QI.pointer_QL_history937.bound_plain.v1"


def encode(qi):
    objects = [*qi.objects.values(), *qi.area_objects.values()]
    keys = {id(obj): (obj.kind, obj.identity) for obj in objects}
    return dict(
        schema=SCHEMA,
        canonical=[
            dict(
                kind=obj.kind,
                identity=obj.identity,
                byte=obj.byte,
                position=[obj.x, obj.y],
                radius=obj.radius,
                movement_blocking=qi.movement_blocking[id(obj)],
            )
            for obj in objects
        ],
        slots=[None if obj is None else list(keys[id(obj)]) for obj in qi.slots],
        cells=[
            dict(cell=list(cell), trove=deepcopy(value.state))
            for cell, value in sorted(qi.cells.items())
        ],
        anchors=[
            dict(byte=byte, cell=list(cell))
            for byte, cell in sorted(qi.anchors.items())
        ],
    )


def decode_bound(qi, payload):
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError("Missing actual bound pointer checkpoint schema")
    objects = [*qi.objects.values(), *qi.area_objects.values()]
    owned = {(obj.kind, obj.identity): obj for obj in objects}
    current = encode(qi)
    if set(payload) != set(current):
        raise ValueError("Incomplete pointer checkpoint fields")
    if json.dumps(payload.get("canonical"), sort_keys=True) != json.dumps(
        current["canonical"], sort_keys=True
    ):
        raise ValueError("Checkpoint canonical facts differ from actual QK authority")
    slots = payload.get("slots")
    if not isinstance(slots, list) or len(slots) != 127:
        raise ValueError("Missing complete native slot pointer population")
    resolved = []
    for key in slots:
        if key is None:
            resolved.append(None)
        elif (
            not isinstance(key, list)
            or len(key) != 2
            or type(key[0]) is not str
            or type(key[1]) is not int
            or tuple(key) not in owned
        ):
            raise ValueError("Unknown canonical slot pointer")
        else:
            resolved.append(owned[tuple(key)])
    cells = {}
    for row in payload.get("cells", []):
        cell = tuple(row["cell"])
        if (
            len(cell) != 2
            or any(type(n) is not int for n in cell)
            or not qi.inside(*cell)
            or cell in cells
        ):
            raise ValueError("Invalid explicit native QL cell")
        value = NativeTroveByteSet(deepcopy(row["trove"]))
        if any(not 0 <= byte < 127 for byte in value.order()):
            raise ValueError("Invalid native QL byte")
        cells[cell] = value
    anchors = {}
    for row in payload.get("anchors", []):
        byte, cell = row["byte"], tuple(row["cell"])
        if (
            type(byte) is not int
            or not 0 <= byte < 127
            or len(cell) != 2
            or any(type(n) is not int for n in cell)
            or not qi.inside(*cell)
            or byte in anchors
        ):
            raise ValueError("Invalid native latest anchor")
        anchors[byte] = cell
    # Binding proves object identity, not arbitrary caller-supplied alias history.
    # Only the current owned producer's exact checkpoint can be republished here.
    if json.dumps(payload, sort_keys=True) != json.dumps(current, sort_keys=True):
        raise ValueError(
            "Unproved pointer topology mutation during checkpoint rebinding"
        )
    qi.slots, qi.cells, qi.anchors = resolved, cells, anchors
