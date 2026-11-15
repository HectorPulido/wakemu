"""Native Celestial Dojo floor markers (family 330 cell presentations).

NOT WIRED: the packet envelope below is a hand-built guess. The official
13497/12613/13560 presentations start with the fight id, not with the family
number, so these bytes are ignored by the installed client. The native route is
to apply the real class-330 carrier effects through the retained effect engine,
which is still unverified for these references. Do not publish from here.

The official dojo lessons publish cell-bound 330 presentations: the bound sack
carries its own marks and the exercise guidance (rear cell, range row, blocked
shot line, area mirror, state rings) appears on the floor. Those are what the
player sees as red/green tiles. Without them the lesson looks and plays like a
fight against an ordinary potato sack.

Graphic references and cells come from the official 2026-11-12 session through
`tools/quest-reconstruction/extract_dojo_scene_markers.py`; only the observed
target and guidance marks are reproduced, never the hero's own bootstrap
carriers. Identities are ours: the presentation binds this owner's lesson
actor, so a client cannot inject a target, cell or graphic.
"""

import collections
import struct

# objective -> {cell: (graphics observed on that cell at lesson start)}
MARKERS = {
    # objective -> cell -> graphics observed within the first frames of that
    # lesson fight (2026-11-12 capture). Graphics on the hero's own bootstrap
    # cell (0,-10) are not lesson geometry and are excluded.
    10574: {(0, -13, 0): (361144, 353144, 353150, 353152)},
    10575: {(0, -13, 0): (361164, 361169)},
    10576: {(0, -13, 0): (361199, 357586)},
    10608: {(0, -13, 0): (367089,)},
    # The area lesson marks each bound sack cell as that sack appears.
    10609: {
        (1, -13, 0): (367092, 367096, 367098),
        (0, -14, 0): (367092, 367096, 367098),
        (0, -12, 0): (367092, 367096, 367098),
        (-1, -13, 0): (367092, 367096, 367098),
    },
    10610: {},
    10611: {(0, -13, 0): (367283, 367323, 367348, 367329)},
}
# Rear-approach guidance. The official session shows these only after the
# hero's first repositioning (frames 8678/8700/8704 against a bootstrap at
# 8514), so publishing them at fight start is an explicit local deviation that
# keeps the rule visible before the hit; retiring them with the fight ends it.
REAR_GUIDANCE = {10574: {(0, -14, 0): (175871, 175342, 348076)}}
FAMILY = 330
PRESENTATION, RETIREMENT = 13497, 13560
_UID_BASE = 1 << 30


def _varint(value):
    value &= (1 << 64) - 1
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        out.append(byte | (0x80 if value else 0))
        if not value:
            return bytes(out)


def _tag(number):
    return _varint((number << 3) | 0)


def _length_delimited(number, raw):
    return _varint((number << 3) | 2) + _varint(len(raw)) + raw


def _position(cell):
    return (
        _tag(1)
        + _varint(cell[0])
        + _tag(2)
        + _varint(cell[1])
        + _tag(3)
        + _varint(cell[2])
    )


def _carrier(uid, graphic, cell, owner, action_id):
    """One official-shaped 330 presentation bound to one cell."""
    body = bytearray()
    body += _tag(1) + _varint(uid)
    body += _tag(2) + _varint(uid)
    body += _tag(3) + _varint(graphic)
    body += _tag(4) + _varint(0)
    body += _length_delimited(5, _position(cell))
    body += _tag(6) + _varint(owner)
    body += _tag(7) + _varint(owner)
    body += _tag(9) + _varint(1)
    body += _tag(10) + _varint((action_id & 0xFFFF) << 16 | 0x0101)
    inner = _tag(1) + _varint(0) + _tag(2) + _varint(-1 & ((1 << 64) - 1))
    body += _length_delimited(11, inner + _length_delimited(3, inner))
    tail = (
        _tag(1)
        + _varint(1)
        + _tag(2)
        + _varint(0)
        + _tag(4)
        + _varint(-1 & ((1 << 64) - 1))
        + _tag(5)
        + _varint(1)
        + _tag(6)
        + _varint(0)
        + _tag(7)
        + _varint(1)
    )
    body += _length_delimited(13, tail)
    return struct.pack(">i", FAMILY) + _varint(len(body)) + bytes(body)


def plan(fight, objective, *, target_id, owner_id, cells, action_id=0):
    """Presentations for one lesson: each marker binds to the lesson roster.

    A marker cell is skipped when it is not part of the published arena, so a
    reconstruction can never invent geometry the client cannot draw.
    """
    if objective not in MARKERS or type(target_id) is not int or target_id >= 0:
        return []
    if type(owner_id) is not int or owner_id <= 0:
        return []
    walkable = {tuple(cell) for cell in cells}
    packets, bindings = [], []
    uid = _UID_BASE + (abs(target_id) % (1 << 24))
    marks = dict(MARKERS.get(objective) or {})
    marks.update(REAR_GUIDANCE.get(objective) or {})
    for offset, (cell, graphics) in enumerate(sorted(marks.items())):
        cell = tuple(cell)
        if cell not in walkable:
            continue
        for graphic in graphics:
            packets.append(
                (
                    PRESENTATION,
                    _carrier(uid + offset, graphic, cell, owner_id, action_id),
                )
            )
            bindings.append(
                {"uid": uid + offset, "graphic": graphic, "cell": list(cell)}
            )
    return packets, bindings


def retire(bindings, action_id):
    """Retire exactly the presentations this lesson published."""
    return [
        (
            RETIREMENT,
            struct.pack(">i", FAMILY)
            + _varint(1)
            + _tag(1)
            + _varint(row["uid"])
            + _tag(2)
            + _varint(action_id),
        )
        for row in bindings
    ]


def decode(body):
    """Read one 330 presentation back. Used by tests and by the live probe."""
    from tools.extract_rii_los_areas import _fields, _signed

    (family,) = struct.unpack_from(">i", body, 0)
    if family != FAMILY:
        raise ValueError("Not a dojo marker packet")
    length, offset = 0, 4
    shift = 0
    while True:
        byte = body[offset]
        offset += 1
        length |= (byte & 0x7F) << shift
        shift += 7
        if byte < 0x80:
            break
    data = _fields(body[offset : offset + length])
    position = _fields(data[5])
    return dict(
        family=family,
        uid=_signed(data[1]),
        graphic=_signed(data[3]),
        cell=(_signed(position[1]), _signed(position[2]), position[3]),
        owner=_signed(data[6]),
    )


CONTRACTS = (
    ("rii_orientation_contract", 10574),
    ("rii_element_lesson_contract", 10575),
    ("rii_distance_lesson_contract", 10576),
    ("rii_los_lesson_contract", 10608),
    ("rii_area_lesson_contract", 10609),
    ("rii_movement_lesson_contract", 10610),
    ("rii_states_lesson_contract", 10611),
)


def lesson_of(fight):
    """(objective, contract) for the single bound lesson of this fight."""
    found = [
        (objective, getattr(fight, attribute, None))
        for attribute, objective in CONTRACTS
        if isinstance(getattr(fight, attribute, None), dict)
    ]
    if len(found) > 1:
        raise ValueError("A lesson fight cannot carry multiple lesson contracts")
    return found[0] if found else (None, None)


def publish(fight, owner_id, cells):
    """Markers for the bound lesson, read from its own contract roster."""
    objective, contract = lesson_of(fight)
    if objective is None or not isinstance(contract, dict):
        return []
    target = contract.get("target")
    if not isinstance(target, int) or target >= 0:
        return []
    planned = plan(fight, objective, target_id=target, owner_id=owner_id, cells=cells)
    if not isinstance(planned, tuple):
        return []
    fight.native_dojo_markers = planned[1]
    return planned[0]
