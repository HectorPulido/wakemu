"""Original missing spell-definition closures referenced by class family426."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def effect_catalog():
    source = protocol_catalog.load(
        DATA_ROOT / "native-class-triggered426-effect-closure.json"
    )
    if (
        source.get("schema") != "native-class-triggered426-effect-closure-v1"
        or source.get("class_dependency_domain") != "triggered426"
        or set(source["spell_reference_closure"]) != {7697, 7698, 7699, 8509, 6849}
        or set(map(int, source["effects"])) != set(source["effect_reference_closure"])
    ):
        raise ValueError("Unattested original class426 dependency closure")
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
            raise ValueError("Conflicting original class426 active-effect metadata")
        if "native_active_effect" not in present:
            merged[reference] = {
                **present,
                "native_active_effect": effect["native_active_effect"],
            }
    return merged


@lru_cache(maxsize=1)
def zero_catalog():
    path = DATA_ROOT / "native-class-triggered426-level-zero.json"
    if not protocol_catalog.exists(path):
        return None  # Explicitly missing source; caller cannot authorize absent level0.
    source = protocol_catalog.load(path)
    if set(map(int, source["spells"])) != {7697, 7698, 7699, 8509, 6849} or set(
        source["spells"]
    ) != set(source["casting"]):
        raise ValueError("Incomplete original class426 zero-level casting source")
    return source
