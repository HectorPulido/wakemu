"""Class-owned original fyF/eVg inputs for faC/faE copied-book selection."""
from wakfu_server import native_catalog as protocol_catalog
from functools import lru_cache
import json
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def native_copy_book_document():
    document = protocol_catalog.load(DATA_ROOT / "native-class-copy-book-flags.json")
    scope, spells = document.get("scope"), document.get("spells")
    if (
        document.get("schema") != 1
        or document.get("missing") != []
        or not isinstance(document.get("source_identity"), dict)
        or not isinstance(scope, list)
        or not isinstance(spells, dict)
        or any(type(ref) is not int or ref <= 0 for ref in scope)
        or len(scope) != len(set(scope))
        or set(spells) != {str(ref) for ref in scope}
    ):
        raise ValueError("Incomplete native class-copy selection metadata")
    for row in spells.values():
        if (
            not isinstance(row, dict)
            or type(row.get("native_elO")) is not bool
            or type(row.get("native_element")) is not int
            or type(row.get("native_neutral_copy")) is not bool
            or row.get("native_elemental_copy") is not None
            and type(row.get("native_elemental_copy")) is not bool
        ):
            raise ValueError("Invalid native class-copy selection flags")
    return document


def native_copy_maximum_caps(document, level):
    if (
        type(level) is not int
        or not 0 <= level <= 32767
        or document.get("maximum_bound_rules") != []
        or document.get("maximum_bound_source", {}).get("producer")
        != "eGK.constructor.empty_registry.no_installed_registration_caller"
    ):
        raise ValueError("Missing actual original copied PA maximum-bound registry")
    return {}


def native_copy_book_flags():
    return native_copy_book_document()["spells"]


@lru_cache(maxsize=1)
def native_copy_characteristics():
    document = protocol_catalog.load(
        DATA_ROOT / "native-class-copy-characteristics.json"
    )
    breeds, definitions = document.get("breeds"), document.get("fresh_characteristics")
    order = document.get("native_characteristic_order")
    if (
        document.get("schema") != 1
        or not isinstance(breeds, dict)
        or not isinstance(definitions, dict)
        or not isinstance(order, list)
        or not isinstance(document.get("source_identity"), dict)
        or set(breeds) != {str(v) for v in document.get("class_breeds", ())}
        or len(breeds) != 18
        or len(definitions) != 92
        or len(order) != len(definitions)
        or {str(v) for v in order} != set(definitions)
    ):
        raise ValueError("Incomplete original class-copy PA constructor metadata")
    return document
