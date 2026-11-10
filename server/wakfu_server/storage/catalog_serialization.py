"""Stable catalog record encoding, preserving dictionary insertion order."""

import json


def ordered_bytes(value):
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), allow_nan=False
    ).encode()
