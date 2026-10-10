"""Native portable furniture templates and item-action reference mappings.

The catalog is exported from aLM and aLO by the client's own bIx action
parser. Production reads use the versioned PostgreSQL native catalog service.
"""
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT

CATALOG_PATH = DATA_ROOT / "haven-bag-furniture-catalog.json"


@lru_cache(maxsize=1)
def _catalog():
    document = native_catalog.load(Path(CATALOG_PATH))
    if document.get("schema_version") != 1:
        raise ValueError("Unsupported haven bag furniture catalog schema")
    templates = {}
    for row in document["templates"]:
        template_id = row["template_id"]
        if type(template_id) is not int or template_id <= 0 or template_id in templates:
            raise ValueError("Invalid or duplicate furniture template")
        if len(row["interaction_cells_by_direction"]) != 8:
            raise ValueError(
                "Furniture interaction directions must contain eight lists"
            )
        templates[template_id] = row
    items = {}
    for row in document["items"]:
        reference = row["item_ref"]
        if type(reference) is not int or reference <= 0 or reference in items:
            raise ValueError("Invalid or duplicate furniture item reference")
        if row["template_id"] not in templates:
            raise ValueError("Unknown furniture template in item mapping")
        items[reference] = row
    return templates, items


def furniture_templates():
    """Return isolated native metadata indexed by template ID."""
    return deepcopy(_catalog()[0])


def resolve_item(reference):
    """Return portable metadata for an item, or None for an unknown reference."""
    if type(reference) is not int or reference <= 0:
        return None
    templates, items = _catalog()
    item = items.get(reference)
    if item is None:
        return None
    result = deepcopy(templates[item["template_id"]])
    result.update(item)
    return result
