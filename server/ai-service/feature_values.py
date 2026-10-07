"""Shared validation for explicitly supplied native outcome measurements."""
import math
import re


def validate_features(raw, label, maximum):
    if not isinstance(raw, dict) or len(raw) > 64:
        raise ValueError("Invalid " + label)
    result = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", key):
            raise ValueError("Invalid feature name")
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not -maximum <= value <= maximum
        ):
            raise ValueError("Invalid " + label)
        result[key] = value
    return result
