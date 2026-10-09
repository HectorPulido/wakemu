"""Native eVE.a PT allocation preflight; exclusion geometry remains explicit."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def null_exclusion_references():
    data = protocol_catalog.load(DATA_ROOT / "native-pt-preflight.json")
    if (
        len(data["null_exclusion_references"]) + len(data["nonnull_exclusions"])
        != data["definitions_checked"]
    ):
        raise ValueError("Incomplete native PT preflight export")
    return frozenset(data["null_exclusion_references"])


def native_pt_preflight(effect, invocation):
    if invocation.reference not in null_exclusion_references():
        raise ValueError("Native PT exclusion-area preflight is not implemented")
    # eVE.a returns true immediately when fKX is null. Native registry existence
    # is verified by dispatch; unsupported server handlers reject the transaction.
    return True
