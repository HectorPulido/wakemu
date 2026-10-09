"""big.a/bPu: a separate temporary fyR, with actual raw-reference UIDs."""
from wakfu_server import native_catalog as protocol_catalog
from dataclasses import replace
from functools import lru_cache
import json
from wakfu_server.paths import DATA_ROOT
from .combat_spell_level import NativeSpellBook


@lru_cache(maxsize=1)
def native_morph_profiles():
    path = DATA_ROOT / "native-class-morph-profiles.json"
    if not protocol_catalog.exists(path):
        raise ValueError("Missing scoped native transformation profile export")
    document = protocol_catalog.load(path)
    if (
        document.get("schema") != "native-class-morph-profiles-v1"
        or document.get("seed_identity", {}).get("schema")
        != "native-class-morph-profile-seeds-v1"
    ):
        raise ValueError("Unverified native transformation profile source")
    profiles = document.get("profiles")
    seeds = document["seed_identity"]
    expected = seeds.get("profile_ids")
    edges = seeds.get("effect_profile_edges")
    if (
        not isinstance(profiles, dict)
        or not isinstance(expected, list)
        or any(type(value) is not int for value in expected)
        or set(profiles) != {str(value) for value in expected}
        or not isinstance(edges, list)
        or {edge.get("profile_id") for edge in edges} != set(expected)
        or type(document.get("native_book_checks")) is not int
        or document["native_book_checks"] <= 0
    ):
        raise ValueError("Incomplete scoped native transformation profile proof")
    for key, profile in profiles.items():
        if profile.get("profile_id") != int(key):
            raise ValueError("Mismatched native transformation profile identity")
        build_morph_book(profile, profile["minimum_level"])
    return profiles


def build_morph_book(profile, level):
    """Keep native dvR order; direct bPO ignores captured override-level pairs."""
    if (
        not isinstance(profile, dict)
        or type(profile.get("minimum_level")) is not int
        or not isinstance(profile.get("abilities"), list)
        or type(level) is not int
        or not -32768 <= level <= 32767
    ):
        raise ValueError("Missing native transformation book constructor source")
    levels = {}
    for row in profile["abilities"]:
        reference, uid, maximum = (
            row.get("reference"),
            row.get("casting_uid"),
            row.get("maximum_level"),
        )
        if (
            type(reference) is not int
            or type(uid) is not int
            or uid != reference
            or type(maximum) is not int
            or not 0 <= maximum <= 32767
        ):
            raise ValueError("Missing exact native transformation bPO identity")
        # fyR rejects duplicate UIDs and capacity overflow; bPu catches both.
        if reference not in levels and len(levels) < 80:
            levels[reference] = min(level, maximum)
    return levels


def install_morph_book(fight, actor, profile, *, own_level, uid):
    if fight.actors.get(actor.id) is not actor or type(own_level) is not bool:
        raise ValueError("Actual registered transformation target required")
    level = actor.effective_level if own_level else profile["minimum_level"]
    levels = build_morph_book(profile, level)
    if not hasattr(fight, "native_morph_spellbooks"):
        fight.native_morph_spellbooks = {}
    # Replacement creates a fresh native fyR; no copied base/grant snapshot.
    fight.native_morph_spellbooks[actor.id] = dict(
        profile_id=profile["profile_id"],
        own_level=own_level,
        book_uid=uid,
        levels=levels,
        grants={},
        removed_raw_uids=set(),
        source="big.a -> direct bPO -> bPu.S/fyR(80)",
    )


def remove_morph_book(fight, actor_id):
    # eWG.bbR/PR removes CURRENT temporary book, irrespective of its profile.
    getattr(fight, "native_morph_spellbooks", {}).pop(actor_id, None)


def morph_record(fight, actor_id):
    row = getattr(fight, "native_morph_spellbooks", {}).get(actor_id)
    if row is not None and (
        not isinstance(row, dict)
        or type(row.get("book_uid")) is not int
        or not isinstance(row.get("levels"), dict)
        or not isinstance(row.get("grants"), dict)
        or not isinstance(row.get("removed_raw_uids"), (set, frozenset))
        or any(
            type(k) is not int or type(v) is not int for k, v in row["levels"].items()
        )
    ):
        raise ValueError("Invalid native temporary transformation book identity")
    return row


def active_morph_book(fight, actor_id, basebook):
    row = morph_record(fight, actor_id)
    if row is None:
        return basebook
    if not isinstance(basebook, NativeSpellBook):
        raise ValueError("Missing actual base-book/player progression authority")
    # PLAYER_CHARACTER/dsx remains independent from switched dok().
    levels = {
        ref: level
        for ref, level in row["levels"].items()
        if ref not in row["removed_raw_uids"]
    }
    return replace(basebook, levels=levels)


def resolve_morph_action(fight, actor_id, uid):
    row = morph_record(fight, actor_id)
    if row is None:
        return None
    from .combat_spell_grant_book import grant_record

    granted = grant_record(fight, actor_id, uid)
    if granted is not None:
        return uid, granted["level"]
    if (
        type(uid) is not int
        or uid not in row["levels"]
        or uid in row["removed_raw_uids"]
    ):
        raise ValueError("Spell is absent from actual temporary transformation book")
    return uid, row["levels"][uid]
