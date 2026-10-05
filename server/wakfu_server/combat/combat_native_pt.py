"""Native eVE.a PT allocation preflight; exclusion geometry remains explicit."""
import gzip
import json
from functools import lru_cache
from .paths import DATA_ROOT


@lru_cache(maxsize=1)
def null_exclusion_references():
    with gzip.open(DATA_ROOT / "native-pt-preflight.json.gz", "rt") as stream:
        data = json.load(stream)
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
