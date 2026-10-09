"""Source-attested nested summons of class2 captured creatures, never generic NPCs."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def nested_profiles():
    source = protocol_catalog.load(
        DATA_ROOT / "native-class-captured-nested-profiles.json"
    )
    seeds = source.get("seed_identity", {})
    if (
        source.get("schema") != "owned-captured-native-profiles-v1"
        or seeds.get("schema") != "native-class-summon-dependency-seeds-v1"
        or seeds.get("class_id") != 2
    ):
        raise ValueError("Unattested class capture nested profile domain")
    profiles = source["profiles"]
    expected = {str(reference) for reference in seeds["profile_ids"]}
    proven = {str(row["profile_id"]) for row in seeds["effect_profile_edges"]}
    if set(profiles) != expected or proven != expected:
        raise ValueError("Incomplete original class-capture nested profile proofs")
    for reference, profile in profiles.items():
        if (
            profile.get("profile_id") != int(reference)
            or len(profile["initial_state_triples"]) % 3
        ):
            raise ValueError("Invalid original nested profile metadata")
    return profiles


def merge_profile_component(existing, component):
    """Extend only explicitly source-closed class dependencies; preserve old rows."""
    merged = dict(existing)
    for reference, profile in nested_profiles().items():
        if reference in merged:
            if merged[reference][component] != profile[component]:
                raise ValueError("Conflicting native class nested profile component")
        else:
            merged[reference] = profile
    return merged


@lru_cache(maxsize=1)
def captured_effect_catalog():
    source = protocol_catalog.load(
        DATA_ROOT / "native-class-captured-effect-closure.json"
    )
    if (
        source.get("schema") != "native-class-captured-effect-closure-v1"
        or source.get("class_id") != 2
    ):
        raise ValueError("Unattested original captured effect closure")
    if {int(key) for key in source["effects"]} != set(
        source["effect_reference_closure"]
    ):
        raise ValueError("Incomplete original captured effect closure")
    return source


@lru_cache(maxsize=1)
def captured_zero_catalog():
    source = protocol_catalog.load(DATA_ROOT / "native-class-captured-level-zero.json")
    if set(source["spells"]) != set(source["casting"]):
        raise ValueError("Incomplete original captured zero-level casting authority")
    return source


def merge_zero_component(existing, captured):
    merged = dict(existing)
    for key, value in captured.items():
        if key in merged and merged[key] != value:
            raise ValueError("Conflicting original captured level-zero component")
        merged[key] = value
    return merged


def merge_captured_effects(existing):
    from .combat_effect_runtime import _merge_effects

    captured = captured_effect_catalog()
    merged = _merge_effects(existing, captured)
    for reference, source in captured["effects"].items():
        effect = merged[reference]
        active = source["native_active_effect"]
        if (
            "native_active_effect" in effect
            and effect["native_active_effect"] != active
        ):
            raise ValueError("Conflicting original captured active-effect metadata")
        if "native_active_effect" not in effect:
            merged[reference] = {**effect, "native_active_effect": active}
    return merged
