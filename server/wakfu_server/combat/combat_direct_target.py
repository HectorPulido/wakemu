"""Native eVE.cym and Qe.a explicit PV target policy, backed by all aNw rows."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def native_direct_target_policies():
    metadata = protocol_catalog.load(DATA_ROOT / "native-direct-target-policies.json")
    if metadata.get("schema") != 1 or metadata.get("source_count") != len(
        metadata.get("effects", {})
    ):
        raise ValueError("Incomplete native direct-target policy population")
    return metadata["effects"]


def explicit_native_target(effect, invocation, *, metadata=None):
    """Return explicit PV identity or None when native aZX asks for area selection."""
    metadata = native_direct_target_policies() if metadata is None else metadata
    row = metadata.get(str(invocation.reference))
    if (
        not isinstance(row, (list, tuple))
        or len(row) != 3
        or row[0] != effect["effect_class"]
        or any(type(value) is not bool for value in row[1:])
    ):
        raise ValueError("Missing/conflicting native explicit-target definition")
    recalculate, caster_is_target = row[1:]
    target = invocation.caster_id if caster_is_target else invocation.target_id
    return None if recalculate else target
