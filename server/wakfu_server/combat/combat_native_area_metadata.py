"""Compact native point areas shared by spell, state, and relative resolvers."""
from wakfu_server import native_catalog as protocol_catalog
from functools import lru_cache
import json
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def native_point_area_metadata():
    return protocol_catalog.load(DATA_ROOT / "native-point-areas.json")


def merge_native_point_areas(effects, metadata=None):
    metadata = native_point_area_metadata() if metadata is None else metadata
    merged = dict(effects)
    for reference, effect in effects.items():
        if effect.get("area_class") not in ("anE", "anJ"):
            continue
        row = metadata.get(str(reference))
        if row is None:
            if "native_area_points" in effect:
                continue
            raise ValueError("Missing native point area metadata")
        if any(
            row.get(key) != effect.get(key)
            for key in ("area_class", "area_native", "effect_class")
        ):
            raise ValueError("Conflicting native point area identity")
        if (
            "native_area_points" in effect
            and effect["native_area_points"] != row["native_area_points"]
        ):
            raise ValueError("Conflicting native point area offsets")
        merged[reference] = dict(effect, native_area_points=row["native_area_points"])
    return merged
