"""Regional chief wishes are the sole authority for ecological equilibrium.

These ranges score player actions; they never cap spawning or reproduction.
The native client reads the same installed protector wishes for its display.
"""
from functools import lru_cache
from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def catalog():
    return native_catalog.load(DATA_ROOT / "territory-protector-bonuses.json")


def limits(map_id, region_id, kind, family_id):
    """Return verified chief bounds, foreign-monster tolerance, or unmanaged."""
    if kind not in ("monster", "plant"):
        raise ValueError("Invalid ecological population kind")
    territory = catalog()["territories"].get(str(region_id))
    if territory is not None and territory["map_id"] != map_id:
        raise ValueError("Native chief belongs to a different map")
    wishes = () if territory is None else territory[kind + "_wishes"]
    matching = [wish for wish in wishes if wish["family_id"] == family_id]
    if len(matching) > 1:
        raise ValueError("Duplicate native chief family wish")
    if matching:
        wish = matching[0]
        low, high = wish["minimum"], wish["maximum"]
        if (
            type(low) is not int
            or type(high) is not int
            or not 0 <= low <= high < 2**31
        ):
            raise ValueError("Invalid native chief equilibrium range")
        return dict(
            minimum=low, maximum=high, source="native_chief_wish", revision=None
        )
    if kind == "monster":
        return dict(minimum=0, maximum=10, source="no_native_wish", revision=None)
    return dict(
        minimum=None, maximum=None, source="unmanaged_native_family", revision=None
    )
