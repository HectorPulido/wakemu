"""Extract boss-aware local rosters without assuming the largest reference is a boss."""
from collections import Counter

BOSS_WORLD_PROPERTY = 43


def identify(pool):
    """Return native BOSS references, excluding unrelated optional guest families.

    A unique flagged boss may legitimately have another family (Nox/Bilby Queen).
    Multiple flagged families are disambiguated only against ordinary members.
    """
    bosses = [m for m in pool if native_role(m) == "boss"]
    ordinary_families = Counter(
        m["family_id"] for m in pool if native_role(m) == "ordinary"
    )
    excluded = []
    if len({m["family_id"] for m in bosses}) > 1:
        matching = [m for m in bosses if m["family_id"] in ordinary_families]
        if matching:
            excluded = [m["ref"] for m in bosses if m not in matching]
            bosses = matching
    return {
        "boss_references": [m["ref"] for m in bosses],
        "family_pool_references": [
            m["ref"]
            for m in pool
            if m["ref"] not in excluded and native_role(m) == "ordinary"
        ],
        "excluded_role_references": [
            m.get("ref")
            for m in pool
            if native_role(m) in {"archmonster", "dominant", "unknown"}
        ],
        "excluded_nonfamily_references": excluded,
        "status": "native_boss_property" if bosses else "unresolved_no_native_boss",
    }


ARCH_WORLD_PROPERTY = 45
DOMINANT_WORLD_PROPERTY = 115


def native_role(monster):
    """Fail closed on absent/malformed native metadata; forbidden roles win."""
    if not isinstance(monster, dict):
        return "unknown"
    arrays = monster.get("raw_visual_arrays")
    properties = arrays.get("csc") if isinstance(arrays, dict) else None
    if not isinstance(properties, list) or any(
        type(value) is not int for value in properties
    ):
        return "unknown"
    if ARCH_WORLD_PROPERTY in properties:
        return "archmonster"
    if DOMINANT_WORLD_PROPERTY in properties:
        return "dominant"
    if BOSS_WORLD_PROPERTY in properties:
        return "boss"
    return "ordinary"


def role_allowed(monster, *, final_room=False, allowed_boss_references=()):
    """Permit ordinary actors; permit selected bosses only in the final room."""
    role = native_role(monster)
    if role == "ordinary":
        return True
    return (
        role == "boss" and final_room and monster.get("ref") in allowed_boss_references
    )


def load_role_catalog(path):
    """Load an explicit native export for offline preparation, never a runtime hook."""
    import json
    from pathlib import Path

    records = json.loads(Path(path).read_text())["monsters"]
    return {record["ref"]: record for record in records}
