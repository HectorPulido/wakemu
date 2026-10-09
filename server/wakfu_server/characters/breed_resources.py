"""Native aKe resources exported from the installed client; no fallback breed."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from .paths import DATA_ROOT


@lru_cache(maxsize=1)
def _catalog():
    return {
        row["breed"]: row["resources"]
        for row in protocol_catalog.load(DATA_ROOT / "breed-innate-definitions.json")[
            "breeds"
        ]
    }


def base_resources(character):
    breed = character.get("breed")
    if type(breed) is not int or breed not in _catalog():
        raise ValueError("Unknown native breed resources")
    values = _catalog()[breed]
    if any(
        type(values.get(key)) is not int or values[key] < 0
        for key in ("AP", "MP", "WP", "HP_base")
    ):
        raise ValueError("Invalid native breed resources")
    return dict(values)


def playable_breeds():
    """Exact native player classes, excluding the nonplayable SOUL enum."""
    return frozenset(_catalog())


def live_wp(fight, actor_id):
    actor = fight.actors[actor_id]
    if actor.effect_stats is None or actor.effect_maxima is None:
        raise ValueError("Missing authoritative combat WP snapshot")
    current, maximum = actor.effect_stats.get(4), actor.effect_maxima.get(4)
    if (
        type(current) is not int
        or type(maximum) is not int
        or not 0 <= current <= maximum
    ):
        raise ValueError("Invalid authoritative combat WP snapshot")
    return current, maximum
