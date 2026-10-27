"""Native fdA/fdz controller records in cvx12514's final eHZ byte array.

ckv.eh decodes this map and fdt.b replaces only each supplied fighter row.
This is a codec, not permission to transfer control: scene assembly must supply
the actual original/current identities, status, team and constructor flags.
"""
from dataclasses import dataclass
import struct


_STATUS = {"NONE": 0, "IN_PLAY": 1, "OFF_PLAY": 2, "OUT_OF_PLAY": 3}


@dataclass(frozen=True)
class NativeControllerRecord:
    actor_id: int
    status: str
    current_team: int
    original_team: int
    is_summon: bool
    original_controller_id: int
    is_team_leader: bool
    current_controller_id: int


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Invalid native controller snapshot integer")
    return value


def controller_snapshot(records):
    """Encode a supplied ordered subset; the native consumer does not clear it."""
    if not isinstance(records, tuple) or len(records) > 32767:
        raise ValueError("Explicit native controller snapshot tuple required")
    result, seen = [struct.pack(">h", len(records))], set()
    for row in records:
        if not isinstance(row, NativeControllerRecord):
            raise ValueError("Typed native controller snapshot record required")
        actor_id = _integer(row.actor_id, -(1 << 63), (1 << 63) - 1)
        if actor_id in seen:
            raise ValueError("Duplicate native controller snapshot fighter")
        seen.add(actor_id)
        if type(row.status) is not str or row.status not in _STATUS:
            raise ValueError("Unknown native fdx controller snapshot status")
        if type(row.is_summon) is not bool or type(row.is_team_leader) is not bool:
            raise ValueError("Actual native fdy constructor flags required")
        body = struct.pack(
            ">bbbBqBq",
            _STATUS[row.status],
            _integer(row.current_team, -128, 127),
            _integer(row.original_team, -128, 127),
            row.is_summon,
            _integer(row.original_controller_id, -(1 << 63), (1 << 63) - 1),
            row.is_team_leader,
            _integer(row.current_controller_id, -(1 << 63), (1 << 63) - 1),
        )
        result.extend((struct.pack(">qi", actor_id, len(body)), body))
    return b"".join(result)
