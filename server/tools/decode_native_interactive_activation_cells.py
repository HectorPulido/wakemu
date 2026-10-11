"""Read literal Re.bkT activation positions from installed interactive payloads.

Evidence: bEH client-content decoder reads a short point count and exact i32,
i32, i16 positions into Re.bkT; Re.h(aBn) tests exact set membership. These
positions are activation cells, never polygon vertices or collision footprints.
"""
import struct
import json
from functools import lru_cache
from pathlib import Path


def decode(record):
    raw = bytes.fromhex(record["payload_hex"])
    identity = struct.pack(
        ">hiih", record["map_id"], int(record["x"]), int(record["y"]), int(record["z"])
    )
    starts = [index for index in range(len(raw)) if raw.startswith(identity, index)]
    if len(starts) != 1:
        raise ValueError("Native interactive map/position frame is not unique")
    start = starts[0]
    if len(raw) < start + 21:
        raise ValueError("Truncated native interactive content frame")
    count = struct.unpack_from(">h", raw, start + 19)[0]
    if not 0 <= count <= 4096 or len(raw) < start + 21 + count * 10 + 2:
        raise ValueError("Invalid native activation-position count")
    return [
        list(struct.unpack_from(">iih", raw, start + 21 + index * 10))
        for index in range(count)
    ]


@lru_cache(maxsize=1)
def payload_catalog():
    path = Path(
        ".runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-map-objects.json"
    )
    if not path.exists():
        return {}
    return {(row["map_id"], row["id"]): row for row in json.loads(path.read_text())}


def literal_positions(record):
    """Accept only native center and byte-decoded exact membership coordinates."""
    center = tuple(int(record[key]) for key in ("x", "y", "z"))
    raw = (
        record
        if "payload_hex" in record
        else payload_catalog().get((record["map_id"], record["id"]))
    )
    result = {center}
    if raw is not None:
        if (
            raw.get("type") != record.get("type")
            or tuple(int(raw[key]) for key in ("x", "y", "z")) != center
        ):
            raise ValueError("Native activation payload contradicts object identity")
        result.update(map(tuple, decode(raw)))
    return result
