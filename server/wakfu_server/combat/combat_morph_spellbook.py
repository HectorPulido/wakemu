"""big.a/bPu: a separate temporary fyR, with actual raw-reference UIDs."""
from wakfu_server import native_catalog as protocol_catalog
from dataclasses import replace
from functools import lru_cache
import json
import hashlib
from pathlib import Path
from wakfu_server.paths import DATA_ROOT
from .combat_spell_level import NativeSpellBook


_REVIEWED_MORPH_SHA256 = (
    "a946da7bc228938aa016df78a2a207089dcc4f7c8358e5727f4549a073110bf6"
)


def _morph_digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


@lru_cache(maxsize=1)
def _reviewed_morph_profiles():
    raw = Path(__file__).with_name("reviewed_native_morph_profiles.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != _REVIEWED_MORPH_SHA256:
        raise ValueError("Reviewed native morphology supplement changed")
    data = json.loads(raw)
    if data.get("schema") != "wakemu-reviewed-native-morph-profile-supplement-v1":
        raise ValueError("Unknown reviewed native morphology contract")
    return data


def _merge_reviewed_morph_profiles(document):
    data = _reviewed_morph_profiles()
    if protocol_catalog.release() != data["native_catalog_revision"]:
        return document  # Other releases retain only their own native profiles.
    if _morph_digest(document) != data["base_canonical_sha256"]:
        raise ValueError("Reviewed morphology base native source changed")
    profiles = dict(document["profiles"])
    additions = data["profiles"]
    edges = data["effect_profile_edges"]
    if (
        type(additions) is not dict
        or type(edges) is not list
        or {str(e.get("profile_id")) for e in edges} != set(additions)
    ):
        raise ValueError("Incomplete reviewed native morphology edges")
    source_edges = []
    for edge in edges:
        source = protocol_catalog.record(
            DATA_ROOT / "combat-state-definitions.json",
            "effects",
            edge["effect_reference"],
        )
        parameters = source.get("parameters", []) if isinstance(source, dict) else []
        if (
            not isinstance(source, dict)
            or _morph_digest(source) != edge["source_effect_canonical_sha256"]
            or source.get("effect_class") != 933
            or len(parameters) != 2
            or parameters != [edge["profile_id"], 0]
        ):
            raise ValueError("Reviewed morphology lacks its exact native933 edge")
        key = str(edge["profile_id"])
        profile = additions[key]
        if profile.get("profile_id") != edge["profile_id"]:
            raise ValueError("Reviewed morphology profile identity changed")
        if key in profiles and profiles[key] != profile:
            raise ValueError("Reviewed morphology conflicts with native profile")
        profiles[key] = profile
        source_edges.append(
            {
                "effect_reference": edge["effect_reference"],
                "profile_id": edge["profile_id"],
            }
        )
    seeds = dict(document["seed_identity"])
    seeds["profile_ids"] = sorted(set(seeds["profile_ids"]) | set(map(int, additions)))
    seeds["effect_profile_edges"] = [*seeds["effect_profile_edges"], *source_edges]
    return dict(
        document,
        profiles=profiles,
        seed_identity=seeds,
        native_book_checks=document["native_book_checks"] + data["native_book_checks"],
    )


@lru_cache(maxsize=1)
def _native_class_morph_document():
    path = DATA_ROOT / "native-class-morph-profiles.json"
    if not protocol_catalog.exists(path):
        raise ValueError("Missing scoped native transformation profile export")
    document = protocol_catalog.load(path)
    _validate_morph_profiles(document)
    return document


@lru_cache(maxsize=1)
def native_class_morph_profiles():
    """Original class-only domain, independent of reviewed captured profiles."""
    return _native_class_morph_document()["profiles"]


@lru_cache(maxsize=1)
def native_morph_profiles():
    """All validated profiles usable by the native transformation constructor."""
    return _validate_morph_profiles(
        _merge_reviewed_morph_profiles(_native_class_morph_document())
    )


def _validate_morph_profiles(document):
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
