#!/usr/bin/env python3
"""Export the three protector satisfaction states used by the native client."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "server/protocol/combat-state-definitions.json"
PROTECTORS = ROOT / "server/protocol/monster-encyclopedia.json"
REGIONS = ROOT / "server/protocol/ecology-regions.json"
OUTPUT = ROOT / "server/protocol/territory-protector-bonuses.json"
STATE_IDS = (1915, 1916, 1917)


def export() -> dict:
    source_bytes = SOURCE.read_bytes()
    with open(SOURCE, "rt", encoding="utf-8") as stream:
        catalog = json.load(stream)
    with open(PROTECTORS, "rt", encoding="utf-8") as stream:
        protector_catalog = json.load(stream)
    regions = json.loads(REGIONS.read_text(encoding="utf-8"))
    region_to_map = {
        region["region_id"]: map_row["map_id"]
        for map_row in regions
        for region in map_row["regions"]
    }

    states = {}
    for state_id in STATE_IDS:
        state = catalog["states"][str(state_id)]
        effects = []
        for effect_id in state["effect_ids"]:
            row = catalog["effects"][str(effect_id)]
            effects.append(
                {
                    "id": effect_id,
                    "effect_class": row["effect_class"],
                    "variant": row["variant"],
                    "criteria": row["criteria"],
                    "parameters": row["parameters"][: row["parameter_count"]],
                }
            )
        states[str(state_id)] = {
            "name": state["name"],
            "description": state["description"],
            "effects": effects,
        }

    territories = {}
    for protector in protector_catalog["territories"]:
        territory_id = protector["territory_id"]
        raw = protector["raw_native"]
        territories[str(territory_id)] = {
            "territory_id": territory_id,
            "map_id": region_to_map.get(territory_id),
            "monster_wishes": [
                {"family_id": row["aIc"], "minimum": row["ctP"], "maximum": row["ctQ"]}
                for row in raw["ctN"]
            ],
            "plant_wishes": [
                {"family_id": row["aIc"], "minimum": row["ctP"], "maximum": row["ctQ"]}
                for row in raw["ctO"]
            ],
        }

    return {
        "source": "native client protector catalog aMD/aME/aMF joined to map regions; native state definitions",
        "source_sha256": {
            "combat_state_definitions": hashlib.sha256(source_bytes).hexdigest(),
            "protector_catalog": hashlib.sha256(PROTECTORS.read_bytes()).hexdigest(),
            "map_regions": hashlib.sha256(REGIONS.read_bytes()).hexdigest(),
        },
        "states": states,
        "territories": territories,
        "satisfaction": {
            "empty": None,
            "unsatisfied": 1917,
            "partially_satisfied": 1915,
            "satisfied": 1916,
            "rule": "zero satisfied => unsatisfied; all satisfied => satisfied; otherwise partial",
        },
    }


def main() -> None:
    OUTPUT.write_text(
        json.dumps(export(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
