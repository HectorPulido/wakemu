"""Installed bag templates; specialized item-type filters await native evaluation."""
from wakfu_server import native_catalog as protocol_catalog
from .paths import DATA_ROOT
import json
from pathlib import Path

RULES = {
    entry["reference"]: entry
    for entry in protocol_catalog.load(DATA_ROOT / "inventory-bag-rules.json")["bags"]
}


def ordinary(reference):
    rule = RULES.get(reference)
    if (
        rule is None
        or reference == 2175
        or rule["accepted_types"]
        or rule["has_equip_criteria"]
        or not 1 <= rule["capacity"] <= 32767
    ):
        raise ValueError("Unsupported specialized bag or native equip criteria")
    return rule
