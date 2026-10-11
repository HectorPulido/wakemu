"""Native region ecology initialization; populations are owned local counts.

Installed region definitions specify families, not captured account data.
The caller must supply the actual region from map partition state: choosing
an arbitrary region would enable seeds in the wrong ecosystem.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
import struct
from .paths import DATA_ROOT

MAPS = {
    row["map_id"]: row
    for row in protocol_catalog.load(DATA_ROOT / "ecology-regions.json")
}


def region(map_id, region_id):
    match = next(
        (
            r
            for r in MAPS.get(map_id, {}).get("regions", [])
            if r["region_id"] == region_id
        ),
        None,
    )
    if match is None:
        raise ValueError("Unknown native map region")
    return match


def display_families(definition, kind):
    """Native bRN exposes three named slots per kind; -1 is an empty slot."""
    families = []
    for row in definition[kind + "_families"]:
        family = row["family_id"]
        if type(family) is not int or family >= 2**31:
            raise ValueError("Invalid native ecosystem family")
        if family <= 0:
            continue
        if family not in families:
            families.append(family)
    if len(families) > 3:
        raise ValueError("Native ecosystem exceeds three display slots")
    return families


def bootstrap(
    map_id,
    region_id,
    *,
    monster_counts=None,
    plant_counts=None,
    test_monster_families=()
):
    """12789/cuE → chl → bRR.Jo + bRT.dT/bRU.dT.

    Absent counts mean an empty LOCAL population, never official population.
    Family rows must remain present even when population is zero; dev.am uses
    bRT.Jp(family) existence as a planting gate. Open planting permissions must
    never append display rows: the native receiver has only three typed slots.
    """
    definition = region(map_id, region_id)

    def encode(kind, counts):
        counts = {} if counts is None else counts
        families = display_families(definition, kind)
        if kind == "monster" and any(
            type(family) is not int or family not in families
            for family in test_monster_families
        ):
            raise ValueError("Foreign test ecosystem family")
        if any(k not in families for k in counts):
            raise ValueError("Foreign ecosystem family")
        rows = []
        for family in families:
            count = counts.get(family, 0)
            if type(count) is not int or not 0 <= count < 2**31:
                raise ValueError("Invalid local population")
            rows.append(struct.pack(">ii", family, count))
        return struct.pack(">i", len(rows)) + b"".join(rows)

    monsters = encode("monster", monster_counts)
    plants = encode("plant", plant_counts)
    return (
        12789,
        struct.pack(">ii", region_id, len(monsters))
        + monsters
        + struct.pack(">i", len(plants))
        + plants,
    )


def authorize_family(map_id, region_id, resource):
    """Check the native ecosystem family gate; ground/profession still required."""
    definition = region(map_id, region_id)
    if resource["monster_resource"]:
        available = {r["family_id"] for r in definition["monster_families"]}
        if not set(resource["monster_family_ids"]).issubset(available):
            raise ValueError("Monster family is unavailable in this native region")
    elif resource["family_id"] not in {
        r["family_id"] for r in definition["plant_families"]
    }:
        raise ValueError("Plant family is unavailable in this native region")
