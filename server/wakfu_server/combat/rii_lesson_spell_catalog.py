"""Native effect closures of the Rii training spells.

The spell identities are supported by the installed localized names and native
effect trees; the four elemental identities also match the lesson screenshot.
Importing definitions never authorizes a cast: the normal owned temporary-spell
registry remains authoritative. Later lesson encounters are not enabled by
publishing these definitions.
"""
from functools import lru_cache


SPELL_ROOTS = {
    7963: (361189, 361195),
    7964: (361190, 361196),
    7965: (361191, 361194),
    7966: (361192, 361197),
    7967: (361204,),
    7968: (361213, 361214),
    7969: (367103,),
    7970: (367142,),
    7971: (367145,),
    7972: (367262,),
    7973: (367263,),
    7974: (367264, 367383),
    7975: (367265,),
}
GRANT_EFFECT = 347172


def select(source):
    """Return only complete original closures for the known lesson spells."""
    if (
        not isinstance(source, dict)
        or not isinstance(source.get("spells"), dict)
        or not isinstance(source.get("effects"), dict)
    ):
        raise ValueError("Invalid native training spell catalog")
    effects = {}
    pending = [GRANT_EFFECT]
    for spell, roots in SPELL_ROOTS.items():
        record = source["spells"].get(str(spell))
        if not isinstance(record, dict) or record.get("level_zero_roots") != list(
            roots
        ):
            raise ValueError("Native training spell roots changed")
        pending.extend(roots)
    while pending:
        reference = pending.pop()
        key = str(reference)
        if key in effects:
            continue
        effect = source["effects"].get(key)
        if not isinstance(effect, dict) or not isinstance(effect.get("children"), list):
            raise ValueError("Incomplete native training effect closure")
        if any(type(child) is not int or child <= 0 for child in effect["children"]):
            raise ValueError("Invalid native training effect dependency")
        effects[key] = effect
        pending.extend(effect["children"])
    if effects[str(GRANT_EFFECT)].get("effect_class") != 649:
        raise ValueError("Native training grant effect changed")
    return {"effects": effects}


@lru_cache(maxsize=1)
def catalog():
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    return select(native_catalog.load(DATA_ROOT / "native-npc-spell-effect-trees.json"))
