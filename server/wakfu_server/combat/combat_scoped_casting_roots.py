"""Source-attested class dependency casting roots, independent effect geometry."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def morph_casting_roots():
    source = protocol_catalog.load(
        DATA_ROOT / "native-class-morph933-casting-roots.json"
    )
    from .combat_morph_spellbook import native_morph_profiles

    references = sorted(
        {
            action["reference"]
            for profile in native_morph_profiles().values()
            for action in profile["abilities"]
        }
    )
    if (
        source.get("schema") != "native-class-casting-roots-v1"
        or source.get("class_dependency_domain") != "morph933"
        or source.get("class_id") != 11
        or source.get("profile_id") != 5900
        or source.get("spell_references") != references
    ):
        raise ValueError("Unattested original class morph casting roots")
    from wakfu_server.combat_morph_dependencies import zero_catalog

    expected = {
        str(root)
        for row in zero_catalog()["casting"].values()
        for level in row["levels"]
        for root in level[2]
    }
    if set(source["roots"]) != expected:
        raise ValueError("Incomplete source class morph casting root domain")
    for row in source["roots"].values():
        if (
            set(row)
            != {
                "native_casting_collision_area",
                "native_selector_present",
                "native_target_selector",
            }
            or type(row["native_selector_present"]) is not bool
            or row["native_selector_present"]
            != (row["native_target_selector"] is not None)
        ):
            raise ValueError("Missing original null/selector casting root contract")
    return source


def merge_casting_roots(existing, source):
    for field in ("fight_properties", "normal_casting_overrides"):
        if existing[field] != source[field]:
            raise ValueError("Conflicting original casting global metadata")
    roots = dict(existing["roots"])
    for reference, record in source["roots"].items():
        if reference in roots and roots[reference] != record:
            raise ValueError("Conflicting original casting root metadata")
        roots.setdefault(reference, record)
    return {**existing, "roots": roots}


@lru_cache(maxsize=1)
def captured_casting_roots():
    source = protocol_catalog.load(
        DATA_ROOT / "native-class-captured-casting-roots.json"
    )
    profiles = protocol_catalog.load(DATA_ROOT / "native-class-captured-profiles.json")[
        "profiles"
    ]
    references = sorted(
        {
            row["reference"]
            for profile in profiles.values()
            for row in profile["abilities"]
        }
    )
    if (
        source.get("schema") != "native-class-casting-roots-v1"
        or source.get("class_dependency_domain") != "captured_class2"
        or source.get("class_id") != 2
        or source.get("profile_ids") != sorted(map(int, profiles))
        or source.get("spell_references") != references
    ):
        raise ValueError("Unattested original class captured casting roots")
    casting = protocol_catalog.load(DATA_ROOT / "native-spell-casting.json")["spells"]
    from .combat_captured_dependencies import captured_zero_catalog

    zero = captured_zero_catalog()["casting"]
    expected = {
        str(root)
        for reference in references
        for level in casting[str(reference)]["levels"] + zero[str(reference)]["levels"]
        for root in level[2]
    }
    if set(source["roots"]) != expected:
        raise ValueError("Incomplete original captured casting root domain")
    for row in source["roots"].values():
        if (
            set(row)
            != {
                "native_casting_collision_area",
                "native_selector_present",
                "native_target_selector",
            }
            or type(row["native_selector_present"]) is not bool
            or row["native_selector_present"]
            != (row["native_target_selector"] is not None)
        ):
            raise ValueError("Missing original captured casting selector contract")
    return source
