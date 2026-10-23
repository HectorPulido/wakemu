"""Exact original environmental location predicates over occupied live scopes.

This adapter supplies criterion truth, not profile admission, spawn composition,
reward policy, or event timing. The caller owns the scope lock and transaction.
"""
import re

from . import environmental_presence as presence
from .environmental_runtime import integer


_SATISFACTION = re.compile(r"GetSatisfactionLevel\(\)[ \t\r\n]*>=[ \t\r\n]*3")


def _kind(criterion):
    if type(criterion) is not str:
        return None
    text = criterion.strip(" \t\r\n")
    if not text:
        return "empty"
    if text == "IsNeoServer()":
        return "neo"
    if _SATISFACTION.fullmatch(text) is not None:
        return "satisfaction"
    return None


def supports(criterion):
    """Recognize only the three qualified forms without reading world or SQL."""
    return _kind(criterion) is not None


def profile_eligible(db, profile, *, world_instance_id):
    """Check only admission of a new window against its sealed source policy."""
    map_id, region_id = profile["map_id"], profile["region_id"]
    occupied = presence.capture(map_id, world_instance_id)
    if occupied is None:
        return False
    if profile["family"] not in ("monster_defeat", "group_defeat"):
        return presence.current(occupied, map_id, world_instance_id)
    from .environmental_storage import _transaction

    _transaction(db)
    policy = db.execute(
        "SELECT * FROM environmental_profile_location_policy WHERE profile_key=%s AND version=%s",
        (profile["profile_key"], profile["version"]),
    ).fetchone()
    if policy is None:
        # Schema validation permits an absent child only for a verified blank
        # original location. Existing resource profiles need no new child.
        return presence.current(occupied, map_id, world_instance_id)
    if (
        not profile["sealed"]
        or policy["native_scenario_id"] != profile["native_scenario_id"]
    ):
        raise ValueError("Environmental admission policy differs from sealed profile")
    return eligible(
        db,
        criterion=policy["native_criteria"],
        map_id=map_id,
        world_instance_id=world_instance_id,
        region_id=region_id,
    )


def eligible(db, *, criterion, map_id, world_instance_id, region_id):
    """Evaluate a source location in its exact occupied map/region/instance.

    Missing territory authority or incomplete population is ineligible, never a
    fabricated satisfaction value. Unsupported syntax and malformed authority
    raise rather than silently authorizing a broader expression.
    """
    kind = _kind(criterion)
    if kind is None:
        raise ValueError("Unsupported environmental location criterion")
    integer(map_id, "criterion map", minimum=1)
    if map_id >= 2**31:
        raise ValueError("Invalid environmental criterion map")
    integer(world_instance_id, "criterion world instance")
    if region_id is not None:
        integer(region_id, "criterion region", minimum=1)
        if region_id >= 2**31:
            raise ValueError("Invalid environmental criterion region")
    occupied = presence.capture(map_id, world_instance_id)
    if occupied is None:
        return False
    if kind == "empty":
        return presence.current(occupied, map_id, world_instance_id)
    if kind == "satisfaction" and region_id is None:
        return False

    from .environmental_storage import _transaction

    _transaction(db)
    if kind == "neo":
        from wakfu_server.neo_regeneration import mode_from_database

        result = mode_from_database(db)
    else:
        from wakfu_server import ecology_context, ecology_population
        from wakfu_server.characters import territory_bonuses

        # Validate the original map/territory join before reading population.
        # Empty counts here only resolve the binding; their status is unused.
        try:
            binding = territory_bonuses.evaluate_population(region_id, {}, {})
        except ValueError as error:
            if str(error) != "Native territory has no verified map-region mapping":
                raise
            return False
        if binding["map_id"] != map_id:
            return False
        population = ecology_population.snapshot(
            db,
            map_id,
            world_instance_id,
            locate=ecology_context.population_region,
            exclude_unassigned=True,
        )
        if not population["complete"]:
            return False
        counts = population["regions"].get(region_id, {"monster": {}, "plant": {}})
        evaluated = territory_bonuses.evaluate_population(
            region_id,
            dict(counts.get("monster", {})),
            dict(counts.get("plant", {})),
        )
        # fwX SATISFIED has byte 3; use the existing native state mapping rather
        # than treating a number of fulfilled wishes as the criterion value.
        result = evaluated["state_id"] == territory_bonuses.state_id(1, 1)
    return result and presence.current(occupied, map_id, world_instance_id)
