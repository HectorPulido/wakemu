"""eMW world property predicate with original eHQ -> ffe fallback."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from collections.abc import Mapping
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def registry():
    return protocol_catalog.load(DATA_ROOT / "native-world-properties.json")[
        "properties"
    ]


def has_world_property(actor, identity, *, duration_seconds=None, now_ms=None):
    if type(identity) is not int:
        raise ValueError("Native world property requires an integral ID")
    identity = (identity + 128) % 256 - 128
    row = registry().get(str(identity))
    if row is None:
        return False
    world = getattr(actor, "world_properties", None)
    fight = getattr(actor, "fight_properties", None)
    if world is None or not isinstance(world, frozenset):
        raise ValueError("Missing complete native actor world properties")
    fallback = row["fight_property"]
    if fallback != -1 and (fight is None or not isinstance(fight, frozenset)):
        raise ValueError("Missing native world property fight fallback authority")
    present = identity in world or fallback != -1 and fallback in fight
    if not present or duration_seconds is None:
        return bool(present)
    times = getattr(actor, "world_property_since_ms", None)
    if (
        not isinstance(times, Mapping)
        or type(now_ms) is not int
        or type(duration_seconds) is not int
    ):
        raise ValueError("Missing complete native world property age ledger/clock")
    # A missing key is zero only after the caller attests a complete eHC ledger.
    since = times.get(identity, 0)
    if type(since) is not int:
        raise ValueError("Invalid native world property activation timestamp")
    signed = lambda n: (n + (1 << 63)) % (1 << 64) - (1 << 63)
    return signed(now_ms - since) >= signed(duration_seconds * 1000)
