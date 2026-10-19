"""Server policy for finite, empty-effect glyph markers broken by contact.

The native ally-activation filter remains authoritative for ordinary glyphs.
The user-authorized destructible-contact policy applies only to this complete
content capability, never to a species, spell or area reference whitelist.
"""
from collections.abc import Mapping


def permits_ally_contact_consumption(row, definition, effects):
    """A single-use empty point marker can be consumed by any real entrant."""
    from .combat_area_property import area_properties

    if (
        row.get("native_area_contract") != "faY"
        or type(row.get("remaining_activations")) is not int
        or row["remaining_activations"] != 1
        or definition.get("type") != "GLYPH"
        or type(definition.get("raw_bde")) is not int
        or definition["raw_bde"] != 1
        or definition.get("raw_bdf") != 0
        or definition.get("native_shape_class") != "anD"
        or definition.get("native_shape_description") != "point"
        or definition.get("shape_parameters") not in ([], ())
        or definition.get("entry_masks") not in ([10001], (10001,))
        or definition.get("exit_masks") not in ([], ())
        or area_properties(row, definition) != frozenset((1, 2))
        or not isinstance(effects, Mapping)
    ):
        return False
    roots = definition.get("effect_ids")
    if not isinstance(roots, (list, tuple)) or len(roots) != 1:
        return False
    root = effects.get(str(roots[0]))
    return (
        isinstance(root, Mapping)
        and type(root.get("effect_class")) is int
        and root["effect_class"] == 400
        and root.get("criteria") == ""
        and root.get("children") in ([], ())
        and root.get("parameters") in ([], ())
    )
