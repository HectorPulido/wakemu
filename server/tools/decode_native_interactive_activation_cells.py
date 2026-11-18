"""Read literal Re.bkT activation positions from installed interactive payloads.

Evidence: bEH client-content decoder reads a short point count and exact i32,
i32, i16 positions into Re.bkT; Re.h(aBn) tests exact set membership. These
positions are activation cells, never polygon vertices or collision footprints.
"""
import struct
import json
from functools import lru_cache
from pathlib import Path


# The same typed decoder is used by live owned scene triggers.
import sys

_SERVER = Path(__file__).resolve().parents[1]
if str(_SERVER) not in sys.path:
    sys.path.insert(0, str(_SERVER))
from wakfu_server.native_interactive_activation import decode


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
