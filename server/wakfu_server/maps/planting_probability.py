"""Verified fyi/dev probability arithmetic, independent of context acquisition.

This mirrors the installed client's calculation; it does not claim the
official server uses this implementation or invent missing actor/climate data.
"""
from wakfu_server import native_catalog as protocol_catalog
import math
import json
import struct
from .paths import DATA_ROOT

RESOURCE_CLIMATES = {
    row["resource_reference"]: row
    for row in protocol_catalog.load(DATA_ROOT / "resource-climates.json")
}


def resolver(store, *, profession_bonus, open_test_policy=False):
    """Build an occupation resolver using territory authority and actor bonus.

    The bonus provider receives the prepared owned actor/profession, never a
    client-supplied percentage. Both contexts are frozen by Plantings.begin.
    """
    if not callable(profession_bonus):
        raise ValueError("Missing authoritative planting bonus provider")
    if type(open_test_policy) is not bool:
        raise ValueError("Invalid open planting probability policy")

    def resolve(prepared):
        character, request = prepared["character"], prepared["request"]
        if character["map_id"] == 1440:
            from .haven_bag_garden import is_private_garden, validate_target

            if not is_private_garden(character):
                raise ValueError("Merkalugar planting requires an active private Ranch")
            validate_target(character, request["x"], request["y"], z=prepared["z"])
            # A Ranch retains native terrain and the configured world planting
            # policy; ground28 is synthesized only for map9 garden gem rooms.
        if character["map_id"] == 9:
            from .haven_bag_garden import validate_target

            validate_target(character, request["x"], request["y"], z=prepared["z"])
            if prepared["definition"]["monster_resource"]:
                raise ValueError(
                    "Monster reproduction is unavailable inside private gardens"
                )
            from .planting_cells import GROUNDS

            ground = GROUNDS.get(28)
            if ground is None:
                raise ValueError("Native Haven Bag garden ground is unavailable")
            resource = prepared["definition"]
            threshold = ground["resources"].get(str(resource["resource_reference"]))
            if threshold is None:
                threshold = ground["families"].get(str(resource["family_id"]), 0)
            chance = calculate(
                ground_percent=threshold,
                climate_compatible=True,
                profession_bonus_percent=profession_bonus(prepared),
            )["probability"]
            if chance <= 0:
                raise ValueError("This resource cannot grow on native garden ground")
            return chance
        if open_test_policy:
            # The open profile intentionally bypasses native ground/territory
            # restrictions. Its visible1% must not secretly succeed100%.
            with store.connection() as db:
                row = db.execute(
                    "SELECT value FROM settings WHERE name='open_planting_probability'"
                ).fetchone()
            probability = None if row is None else row["value"]
            succeeds(probability, 0.0)
            return probability
        from .territory_weather import context

        weather = context(
            store, character, x=request["x"], y=request["y"], z=prepared["z"]
        )
        return for_cell(
            character,
            request,
            prepared["definition"],
            z=prepared["z"],
            weather=weather["weather"],
            profession_bonus_percent=profession_bonus(prepared),
        )["probability"]

    return resolve


def for_cell(character, request, resource, *, z, weather, profession_bonus_percent):
    """Resolve an exact native surface; weather/bonus must come from authority."""
    from .planting_cells import cells, GROUNDS

    if type(z) is not int:
        raise ValueError("Invalid authoritative planting height")
    if type(weather) is not str or weather not in ("ABSENT", "LIGHT", "HEAVY", "STORM"):
        raise ValueError("Unknown authoritative planting weather")
    surfaces = [
        row
        for row in cells(character["map_id"]).get((request["x"], request["y"]), ())
        if row["z"] == z
    ]
    if len(surfaces) != 1:
        raise ValueError("Unknown or ambiguous planting probability surface")
    surface = surfaces[0]
    ground = GROUNDS.get(surface["ground_id"])
    climate = RESOURCE_CLIMATES.get(resource["resource_reference"])
    if ground is None or climate is None:
        raise ValueError("Unknown native planting probability context")
    threshold = ground["resources"].get(str(resource["resource_reference"]))
    if threshold is None:
        threshold = ground["families"].get(str(resource["family_id"]), 0)
    compatible = (
        weather == "ABSENT"
        or climate["climate"] == "NONE"
        or weather in climate["allowed_weather"]
    )
    return dict(
        calculate(
            ground_percent=threshold,
            climate_compatible=compatible,
            profession_bonus_percent=profession_bonus_percent,
        ),
        ground_id=surface["ground_id"],
        region_id=surface["region_id"],
    )


def calculate(*, ground_percent, climate_compatible, profession_bonus_percent):
    if type(ground_percent) is not int or not 0 <= ground_percent <= 100:
        raise ValueError("Invalid native planting ground threshold")
    if type(climate_compatible) is not bool:
        raise ValueError("Unknown planting climate compatibility")
    if (
        type(profession_bonus_percent) not in (int, float)
        or not math.isfinite(profession_bonus_percent)
        or not -(1 << 31) <= profession_bonus_percent < (1 << 31)
    ):
        raise ValueError("Invalid authoritative planting profession bonus")
    climate_factor = 1.0 if climate_compatible else 0.8
    # eGj.PS converts the integer effect2000 bonus to float, divides by
    # float100, then widens to double. Preserve that intermediate rounding.
    native_bonus = struct.unpack(">f", struct.pack(">f", profession_bonus_percent))[0]
    native_bonus = struct.unpack(">f", struct.pack(">f", native_bonus / 100.0))[0]
    probability = (ground_percent / 100.0) * climate_factor * (1.0 + native_bonus)
    probability = max(0.0, min(1.0, probability))
    # dev.am uses -1 for forbidden (X), not 0%; JVM Math.round is floor(x+.5).
    displayed = -1 if probability <= 0 else math.floor(probability * 100 + 0.5)
    return dict(probability=probability, displayed_percent=displayed)


def succeeds(probability, draw):
    """Compare one server-owned uniform draw, without rounding the chance."""
    if (
        any(
            type(value) not in (int, float)
            or not 0 <= value <= 1
            or not math.isfinite(value)
            for value in (probability, draw)
        )
        or draw == 1
    ):
        raise ValueError("Invalid authoritative planting roll")
    return draw < probability
