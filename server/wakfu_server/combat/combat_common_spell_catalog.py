"""Scoped original retained-item common spells, independent of class grants."""
from functools import lru_cache

from wakfu_server import native_catalog as protocol_catalog
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def effects():
    data = protocol_catalog.load(DATA_ROOT / "native-common-spell-effect-trees.json")
    from wakfu_server.spells import COMMON_ITEM_SPELLS

    references = data.get("spell_references")
    if (
        data.get("schema") != "native-retained-item-common-spell-effects-v1"
        or references != sorted(COMMON_ITEM_SPELLS)
        or set(data.get("spells", {})) != {str(ref) for ref in references}
    ):
        raise ValueError("Unattested retained-item common spell domain")
    required = set()

    def visit(reference):
        key = str(reference)
        if key in required:
            return
        row = data["effects"].get(key)
        if row is None:
            raise ValueError("Incomplete original common spell effect closure")
        required.add(key)
        for child in row["children"]:
            visit(child)

    from .combat_native_spell_casting import catalog as casting_catalog

    casting = casting_catalog()
    for reference in references:
        source = casting[str(reference)]
        levels = data["spells"][str(reference)]["levels"]
        if len(levels) != source["maximum_level"] or levels != source["levels"]:
            raise ValueError("Common spell effect roots differ from native casting")
        for level in levels:
            for root in level[2]:
                visit(root)
    if required != set(data["effects"]):
        raise ValueError("Unscoped common spell effect definitions")
    return data


def merge_effect_catalog(existing):
    source = effects()
    result = dict(existing)
    for collection in ("spells", "effects"):
        rows = dict(existing[collection])
        for reference, row in source[collection].items():
            if reference in rows and rows[reference] != row:
                raise ValueError("Conflicting native common spell definition")
            rows.setdefault(reference, row)
        result[collection] = rows
    return result


@lru_cache(maxsize=1)
def casting_roots():
    source = protocol_catalog.load(DATA_ROOT / "native-common-spell-casting-roots.json")
    common = effects()
    expected = {
        str(root)
        for row in common["spells"].values()
        for level in row["levels"]
        for root in level[2]
    }
    if (
        source.get("schema") != "native-class-casting-roots-v1"
        or source.get("spell_references") != common["spell_references"]
        or set(source.get("roots", {})) != expected
    ):
        raise ValueError("Incomplete native common spell casting root authority")
    return source


def native_rows():
    from .combat_native_spell_casting import catalog as casting_catalog

    casting = casting_catalog()
    return {
        str(reference): casting[str(reference)]
        for reference in effects()["spell_references"]
    }


def merge_cost_records(existing):
    result = dict(existing)
    for reference, row in native_rows().items():
        result.setdefault(
            reference, dict(levels=row["costs"], conditional=len(row["conditional"]))
        )
    return result


def merge_conditional_catalog(existing):
    result = dict(existing)
    spells = dict(existing["spells"])
    categories = dict(existing["spell_categories"])
    for reference, row in native_rows().items():
        spells.setdefault(
            reference,
            [
                dict(criteria=rule["criteria"], levels=rule["levels"])
                for rule in row["conditional"]
            ],
        )
        categories.setdefault(reference, row["categories"])
    result.update(spells=spells, spell_categories=categories)
    return result
