"""Local ecological level bands over the immutable native growth catalog.

Nearby native levels are alternatives, not compulsory successive sexes/forms.
Bands are anchored at their first level; overlap never chains across a family.
Native special forms retain their own bands and classification.
"""
from copy import deepcopy
from functools import lru_cache
import struct
from wakfu_server import native_catalog as protocol_catalog
from .paths import DATA_ROOT


def _kind(candidate):
    classification = candidate["boss_classification"]
    if classification != "regular":
        return classification
    return "dominant" if 115 in candidate.get("world_properties", ()) else "regular"


def normalize_catalog(catalog):
    result = deepcopy(catalog)
    for family in result["families"]:
        candidates = sorted(
            (candidate for tier in family["tiers"] for candidate in tier["candidates"]),
            key=lambda row: (row["min_level"], row["reference"]),
        )
        tiers = []
        latest_by_kind = {}
        for candidate in candidates:
            level = candidate["min_level"]
            kind = _kind(candidate)
            previous = latest_by_kind.get(kind)
            if previous is None or level - previous["min_level"] > max(
                3, previous["min_level"] // 20
            ):
                previous = dict(min_level=level, candidates=[], kind=kind)
                tiers.append(previous)
                latest_by_kind[kind] = previous
            previous["candidates"].append(candidate)
        tiers.sort(
            key=lambda tier: (
                tier["min_level"],
                tier["kind"] != "regular",
                tier["candidates"][0]["reference"],
            )
        )
        for rank, tier in enumerate(tiers):
            tier["rank"] = rank
            tier.pop("kind")
        family["tiers"] = tiers
        family["terminal"] = len(tiers) <= 1
    return result


CATALOG = normalize_catalog(
    protocol_catalog.load(DATA_ROOT / "monster-growth-catalog.json")
)
FAMILIES = {family["family_id"]: family for family in CATALOG["families"]}
STAGES = {
    candidate["reference"]: (family, tier["rank"])
    for family in CATALOG["families"]
    for tier in family["tiers"]
    for candidate in tier["candidates"]
}


def _valid_name(name):
    if not isinstance(name, str) or not name.strip():
        return False
    try:
        return len(name.encode("utf-8")) <= 65535
    except UnicodeError:
        return False


@lru_cache(maxsize=None)
def publication_viable(reference, min_level):
    """Prove a release-pinned native form can become a complete world packet."""
    from .monsters import owned_instance
    from .combat_monster_world import spawn_group
    from .monster_minigame_policy import effective_ordinary_summon_only_references

    if reference in effective_ordinary_summon_only_references():
        return False

    try:
        member = owned_instance(reference, min_level, -1, map_id=1, x=0, y=0, z=0)
        spawn_group([member], group_id=1)
    except (ValueError, TypeError, KeyError, OverflowError, UnicodeError, struct.error):
        return False
    return True


@lru_cache(maxsize=None)
def _initial_references(family_id):
    """Immutable process/release-pinned pool; no repeated native action scan."""
    from .monsters import REFERENCES
    from .monster_collect import _actions
    from .planting import SEEDS

    family = FAMILIES.get(family_id)
    if family is None or not family["tiers"]:
        return ()
    candidates = tuple(
        candidate["reference"]
        for candidate in family["tiers"][0]["candidates"]
        if candidate["boss_classification"] == "regular"
        and _valid_name(REFERENCES[candidate["reference"]].get("name"))
        and publication_viable(candidate["reference"], candidate["min_level"])
    )
    seeds = {
        seed["item_reference"]
        for seed in SEEDS.values()
        if seed["resource_reference"] in family.get("resource_references", ())
    }
    fertile = {
        reference
        for (reference, _), action in _actions().items()
        if action["csP"] in seeds
        and action["clT"].strip() in ("", 'not IsDead("target")')
    }
    preferred = tuple(reference for reference in candidates if reference in fertile)
    return preferred or candidates


def initial_candidates(family_id, *, eligible_references=None):
    """Return fresh native initial rows, preferring native seed producers.

    Non-harvestable tutorial forms are excluded when farming forms exist.
    Explicit planting eligibility is intersected without modifying the cache.
    """
    references = _initial_references(family_id)
    if eligible_references is not None:
        references = tuple(ref for ref in references if ref in eligible_references)
    family = FAMILIES.get(family_id)
    if family is None or not family["tiers"]:
        return []
    allowed = set(references)
    return [
        dict(candidate)
        for candidate in family["tiers"][0]["candidates"]
        if candidate["reference"] in allowed
    ]
