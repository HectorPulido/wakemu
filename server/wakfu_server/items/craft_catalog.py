"""Complete native recipe data, without inventing unresolved ingredient rules.

Loading a recipe does not authorize it. Raw criteria, ingredient qualifiers
and timing fields remain available for the native rule adapter to interpret.
"""
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from wakfu_server.paths import DATA_ROOT


@dataclass(frozen=True)
class CraftCatalog:
    """Native recipe and station data, with audit anomalies kept separate."""

    recipes: dict
    definitions: dict
    table_instances: tuple
    validation: dict

    def resolve_table(self, map_id, object_id):
        for row in self.table_instances:
            if row["map_id"] == map_id and row["object_id"] == object_id:
                return row
        return None

    def authorize_recipe(self, definition_id, recipe_id, *, profession_id=None):
        """Apply native station membership and profession availability checks.

        Recipe/definition mismatches are audit findings, not additional policy:
        the native station UI checks recipe membership and station profession
        separately. Unknown definitions, recipes, professions, and nonmembers
        are denied.
        """
        if (
            type(definition_id) is not int
            or definition_id <= 0
            or type(recipe_id) is not int
            or recipe_id <= 0
        ):
            return False
        definition = self.definitions.get(definition_id)
        if definition is None:
            return False
        recipe = self.recipes.get(recipe_id)
        if recipe is None:
            return False
        if recipe_id not in definition["allowed_recipe_ids"]:
            return False
        if profession_id is not None:
            if (
                type(profession_id) is not int
                or profession_id != definition["profession_id"]
            ):
                return False
        return True


def load_catalog(path=DATA_ROOT / "craft-recipes.json"):
    document = json.loads(Path(path).read_text())
    summary, recipes = document.get("summary"), document.get("recipes")
    if not isinstance(summary, dict) or not isinstance(recipes, list):
        raise ValueError("Missing native crafting catalog")
    counts = (
        "recipe_records_seen",
        "recipe_records_exported",
        "ingredient_records_exported",
        "product_records_exported",
        "record_errors",
    )
    if any(type(summary.get(key)) is not int or summary[key] < 0 for key in counts):
        raise ValueError("Invalid crafting catalog counts")
    if (
        summary["record_errors"] != 0
        or not recipes
        or summary["recipe_records_seen"] != len(recipes)
        or summary["recipe_records_exported"] != len(recipes)
    ):
        raise ValueError("Incomplete crafting catalog extraction")
    indexed = {}
    ingredients = products = 0
    for recipe in recipes:
        if not isinstance(recipe, dict):
            raise ValueError("Invalid native recipe row")
        identity = recipe.get("recipe_id")
        if (
            type(identity) is not int
            or not 0 < identity < 2**31
            or identity in indexed
        ):
            raise ValueError("Duplicate or invalid native recipe identity")
        for field in ("profession_id", "minimum_level", "raw_duration"):
            if type(recipe.get(field)) is not int or recipe[field] < 0:
                raise ValueError("Invalid native recipe requirement")
        for field in ("ingredients", "products"):
            rows = recipe.get(field)
            if not isinstance(rows, list) or not rows:
                raise ValueError("Missing native recipe items")
            for item in rows:
                if not isinstance(item, dict) or any(
                    type(item.get(key)) is not int or not 0 < item[key] < 2**31
                    for key in ("item_id", "quantity")
                ):
                    raise ValueError("Invalid native recipe item")
                if field == "ingredients" and type(item.get("extra_raw")) is not int:
                    raise ValueError("Missing native ingredient qualifier")
            if field == "ingredients":
                ingredients += len(rows)
            else:
                products += len(rows)
        indexed[identity] = deepcopy(recipe)
    if (
        ingredients != summary["ingredient_records_exported"]
        or products != summary["product_records_exported"]
    ):
        raise ValueError("Incomplete native recipe item extraction")

    definition_rows = document.get("craft_table_definition_rows")
    instance_rows = document.get("craft_table_instances")
    definition_meta = document.get("craft_table_definitions")
    if (
        not isinstance(definition_meta, dict)
        or definition_meta.get("status") != "exported_from_native_reader"
        or not isinstance(definition_rows, list)
        or not isinstance(instance_rows, list)
    ):
        raise ValueError("Missing native crafting station catalog")
    definition_summary = definition_meta.get("field_mapping")
    if not isinstance(definition_summary, dict):
        raise ValueError("Missing native crafting definition mapping")

    definitions = {}
    for row in definition_rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid native crafting definition row")
        identity = row.get("definition_id")
        profession = row.get("profession_id")
        family = row.get("station_family_key")
        allowed = row.get("allowed_recipe_ids")
        raw_bbk = row.get("runtime_bBK_raw")
        if (
            type(identity) is not int
            or identity <= 0
            or identity in definitions
            or type(profession) is not int
            or profession < 0
            or type(family) is not int
            or family < 0
            or type(raw_bbk) is not int
            or not isinstance(allowed, list)
            or any(
                type(recipe_id) is not int or recipe_id <= 0 for recipe_id in allowed
            )
            or len(set(allowed)) != len(allowed)
        ):
            raise ValueError("Invalid native crafting definition")
        definitions[identity] = deepcopy(row)

    tables = []
    seen_tables = set()
    for row in instance_rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid native CraftTable instance")
        map_id, object_id = row.get("map_id"), row.get("object_id")
        key = (map_id, object_id)
        if (
            type(map_id) is not int
            or map_id <= 0
            or type(object_id) is not int
            or object_id <= 0
            or key in seen_tables
        ):
            raise ValueError("Duplicate or invalid native CraftTable identity")
        seen_tables.add(key)
        definition_id = row.get("definition_id")
        if row.get("status") == "resolved":
            definition = definitions.get(definition_id)
            if (
                definition is None
                or row.get("profession_id") != definition["profession_id"]
                or row.get("station_family_key") != definition["station_family_key"]
                or row.get("allowed_recipe_count")
                != len(definition["allowed_recipe_ids"])
            ):
                raise ValueError("Inconsistent native CraftTable definition reference")
        elif row.get("status") != "definition_not_found":
            raise ValueError("Unresolved native CraftTable instance")
        tables.append(deepcopy(row))

    validation = document.get("craft_table_definition_validation")
    if not isinstance(validation, dict):
        raise ValueError("Missing native crafting definition audit")
    # Do not reject source catalog anomalies: the audit is surfaced to callers,
    # while authorization below independently fails closed for unknown recipes.
    return CraftCatalog(
        recipes=MappingProxyType(indexed),
        definitions=MappingProxyType(definitions),
        table_instances=tuple(tables),
        validation=deepcopy(validation),
    )


def load(path=DATA_ROOT / "craft-recipes.json"):
    """Backward-compatible recipe-only view of the full native catalog."""
    return dict(load_catalog(path).recipes)
