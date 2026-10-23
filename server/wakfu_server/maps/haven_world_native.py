"""Recovered cwk12957 codec and original patch0 base-geometry fixture.

The initial patch layout is an explicit server content choice using an actual
installed template, not a claim about original guild-world purchase layouts.
"""
from hashlib import sha256
import json
from pathlib import Path
import struct


CLIENT_SHA256 = "e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd"
HM_SHA256 = "83d32ce93198d3d71d95a97697662a7c945e1f5db5f2e5ad9f045375afff1fed"


def _integer(value, minimum, maximum, label):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"Invalid native Haven World {label}")
    return value


def partition_bytes(rows):
    """cen.ed: repeated six signed shorts, without count/header inside blob.

    Logical partitionXY expands to2x2 nine-cell patches. The remaining four
    shorts are original packed patch IDs, ordered(0,0),(1,0),(0,1),(1,1).
    """
    if not isinstance(rows, (tuple, list)) or len(rows) > 32767 // 12:
        raise ValueError("Invalid native Haven World partition list")
    result = []
    used = set()
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != 6:
            raise ValueError("Invalid native Haven World partition record")
        values = tuple(
            _integer(value, -32768, 32767, "partition field") for value in row
        )
        if values[:2] in used:
            raise ValueError("Duplicate native Haven World partition location")
        used.add(values[:2])
        result.append(struct.pack(">6h", *values))
    return b"".join(result)


def building_bytes(rows):
    """ceC.ff: repeated UID:i64, definition:i16, value:i32, X:i16,Y:i16.

    This is the transport only. Callers must resolve actual definitions through
    original buildings.lib and own their gameplay/application metadata.
    """
    if not isinstance(rows, (tuple, list)) or len(rows) > 32767 // 18:
        raise ValueError("Invalid native Haven World building list")
    result = []
    used = set()
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != 5:
            raise ValueError("Invalid native Haven World building record")
        uid, definition, value, x, y = row
        _integer(uid, -(2**63), 2**63 - 1, "building UID")
        _integer(definition, -32768, 32767, "building definition")
        _integer(value, -(2**31), 2**31 - 1, "building value")
        _integer(x, -32768, 32767, "building X")
        _integer(y, -32768, 32767, "building Y")
        if uid in used:
            raise ValueError("Duplicate native Haven World building UID")
        used.add(uid)
        result.append(struct.pack(">qhi2h", uid, definition, value, x, y))
    return b"".join(result)


def metadata(guild_id, name, hp_value, m_ai, llx, lnq):
    """Exact fiB.fQ layout; opaque fields retain original accessor names.

    Ya=guildID and arM=-guildID. HP is a second native long, not an actor HP
    characteristic. eJp/mAi is an editable world pool (build UI subtracts cost).
    No gameplay meaning for either boolean is inferred by this codec.
    """
    _integer(guild_id, 1, 2**63 - 1, "guild ID")
    _integer(hp_value, -(2**63), 2**63 - 1, "HP value")
    _integer(m_ai, -(2**31), 2**31 - 1, "mAi value")
    if type(name) is not str or type(llx) is not bool or type(lnq) is not bool:
        raise ValueError("Invalid native Haven World metadata")
    encoded = name.encode("utf-8")
    if len(encoded) > 2**31 - 1:
        raise ValueError("Native Haven World name exceeds wire length")
    return (
        struct.pack(">qqi", guild_id, hp_value, len(encoded))
        + encoded
        + struct.pack(">iBB", m_ai, llx, lnq)
    )


def bootstrap(
    guild_id,
    name,
    hp_value,
    *,
    partitions,
    buildings=(),
    linked_ids=(),
    m_ai=0,
    llx=False,
    lnq=False,
):
    """12957 must precede world actor/scene transition that invokes ciu.nl."""
    parts = partition_bytes(partitions)
    built = building_bytes(buildings)
    if not isinstance(linked_ids, (tuple, list)) or len(linked_ids) > 32767:
        raise ValueError("Invalid native Haven World linked IDs")
    links = b"".join(
        struct.pack(">q", _integer(value, -(2**63), 2**63 - 1, "linked ID"))
        for value in linked_ids
    )
    body = (
        struct.pack(">h", len(parts))
        + parts
        + struct.pack(">h", len(built))
        + built
        + struct.pack(">h", len(linked_ids))
        + links
        + metadata(guild_id, name, hp_value, m_ai, llx, lnq)
    )
    return 12957, body


def base_geometry():
    """324 original free ground cells from four genuine patch0 quadrants."""
    path = Path(__file__).with_name("base-partition-geometry.json")
    raw = path.read_bytes()
    if (
        sha256(raw).hexdigest()
        != "45b3d677a03884fa4e360f404e0e76ebb7987cd458e6112a20bf4e8227996f6e"
    ):
        raise ValueError("Conflicting original Haven World base geometry")
    data = json.loads(raw)
    return tuple(tuple(row) for row in data["cells"])


def interior_geometry():
    """Original ground inside the native buildable interior, part(0,-5)."""
    path = Path(__file__).with_name("interior-base-partition-geometry.json")
    raw = path.read_bytes()
    if (
        sha256(raw).hexdigest()
        != "cf13fa55f2478702ed4403381d9637b13299cd18396a4d824c205dcfd229d0f2"
    ):
        raise ValueError("Conflicting original Haven World interior geometry")
    return tuple(tuple(row) for row in json.loads(raw)["cells"])
