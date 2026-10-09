"""Original class transformation profile ability dependency closures."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def effect_catalog():
    source = protocol_catalog.load(
        DATA_ROOT / "native-class-morph933-effect-closure.json"
    )
    from .combat_morph_spellbook import native_morph_profiles

    references = {
        row["reference"]
        for profile in native_morph_profiles().values()
        for row in profile["abilities"]
    }
    if (
        source.get("schema") != "native-class-morph933-effect-closure-v1"
        or source.get("class_dependency_domain") != "morph933"
        or source.get("class_id") != 11
        or set(source["spell_reference_closure"]) != references
        or set(map(int, source["effects"])) != set(source["effect_reference_closure"])
    ):
        raise ValueError("Unattested original class morph dependency closure")
    return source


def merge_effects(existing):
    from .combat_effect_runtime import _merge_effects

    source = effect_catalog()
    merged = _merge_effects(existing, source)
    for reference, effect in source["effects"].items():
        present = merged[reference]
        if (
            "native_active_effect" in present
            and present["native_active_effect"] != effect["native_active_effect"]
        ):
            raise ValueError("Conflicting original class morph active-effect metadata")
        if "native_active_effect" not in present:
            merged[reference] = {
                **present,
                "native_active_effect": effect["native_active_effect"],
            }
    return merged


@lru_cache(maxsize=1)
def zero_catalog():
    path = DATA_ROOT / "native-class-morph933-level-zero.json"
    if not protocol_catalog.exists(path):
        return None  # Explicitly missing source; caller cannot authorize absent level0.
    source = protocol_catalog.load(path)
    references = set(effect_catalog()["spell_reference_closure"])
    if set(map(int, source["spells"])) != references or set(source["spells"]) != set(
        source["casting"]
    ):
        raise ValueError("Incomplete original class morph zero-level casting source")
    return source
