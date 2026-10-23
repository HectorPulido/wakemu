"""Native secret-recipe criteria stay narrowly account-knowledge gated."""
import re
import unittest

from wakfu_server.craft_catalog import load_catalog
from wakfu_server.crafting import _recipe


class _RecipeCatalogView:
    def __init__(self, recipes):
        self.recipes = recipes

    @staticmethod
    def authorize_recipe(definition_id, recipe_id):
        return type(definition_id) is int and definition_id > 0 and recipe_id > 0


class _KnowledgeCursor:
    def __init__(self, actions):
        self.row = {"actions": list(actions)}

    def fetchone(self):
        return self.row


class _KnowledgeDB:
    def __init__(self, actions_by_account_profession):
        self.actions = actions_by_account_profession
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        account_id, profession_id = params
        return _KnowledgeCursor(self.actions.get((account_id, profession_id), ()))


class SecretRecipeCriterionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native_catalog = load_catalog()
        cls.catalog = _RecipeCatalogView(cls.native_catalog.recipes)
        cls.supported_recipe_ids = []
        cls.unsupported_recipe_ids = []
        for recipe_id, recipe in cls.native_catalog.recipes.items():
            ordinary = (
                recipe.get("raw_clT") == ""
                and recipe.get("raw_cvc") == ""
                and recipe.get("raw_cvd") is False
                and recipe.get("raw_ckE") == []
            )
            if ordinary:
                continue
            expression = recipe.get("raw_clT")
            known = (
                re.fullmatch(
                    r"IsKnownRecipe\(\s*([0-9]+)\s*,\s*([0-9]+)\s*\)",
                    expression.strip(),
                )
                if isinstance(expression, str)
                else None
            )
            exact_pair = (
                known is not None
                and recipe.get("raw_cvc") == ""
                and recipe.get("raw_cvd") is False
                and recipe.get("raw_ckE") == [0]
                and tuple(map(int, known.groups()))
                == (recipe.get("profession_id"), recipe_id)
            )
            (
                cls.supported_recipe_ids if exact_pair else cls.unsupported_recipe_ids
            ).append(recipe_id)

    def test_all_226_exact_native_known_recipe_pairs_authorize_and_other_45_stay_closed(
        self,
    ):
        supported = self.supported_recipe_ids
        unsupported = self.unsupported_recipe_ids
        self.assertEqual((len(supported), len(unsupported)), (226, 45))

        for recipe_id in supported:
            recipe = self.native_catalog.recipes[recipe_id]
            with self.subTest(recipe_id=recipe_id):
                db = _KnowledgeDB({(71, recipe["profession_id"]): [recipe_id]})
                self.assertIs(
                    _recipe(
                        self.catalog,
                        {"definition_id": 182},
                        recipe_id,
                        db=db,
                        account_id=71,
                    ),
                    recipe,
                )
                self.assertEqual(db.calls[0][1], (71, recipe["profession_id"]))

        for recipe_id in unsupported:
            recipe = self.native_catalog.recipes[recipe_id]
            with self.subTest(unsupported_recipe_id=recipe_id):
                db = _KnowledgeDB({(71, recipe["profession_id"]): [recipe_id]})
                with self.assertRaisesRegex(
                    ValueError,
                    "Unsupported native crafting recipe criterion or flags",
                ):
                    _recipe(
                        self.catalog,
                        {"definition_id": 182},
                        recipe_id,
                        db=db,
                        account_id=71,
                    )

    def test_account_profession_and_recipe_id_must_match_exact_expression(self):
        recipe_id = next(iter(self.supported_recipe_ids))
        source = self.native_catalog.recipes[recipe_id]
        account_id = 71
        profession_id = source["profession_id"]

        # Knowledge held by another account or another profession does not
        # satisfy this account's native IsKnownRecipe(profession, recipe).
        for knowledge in (
            {(72, profession_id): [recipe_id]},
            {(account_id, profession_id + 1): [recipe_id]},
        ):
            db = _KnowledgeDB(knowledge)
            with self.assertRaisesRegex(ValueError, "has not been learned"):
                _recipe(
                    self.catalog,
                    {"definition_id": 182},
                    recipe_id,
                    db=db,
                    account_id=account_id,
                )

        db = _KnowledgeDB({(account_id, profession_id): [recipe_id, recipe_id + 1]})
        for change in (
            {"raw_clT": f"IsKnownRecipe({profession_id + 1}, {recipe_id})"},
            {"raw_clT": f"IsKnownRecipe({profession_id}, {recipe_id + 1})"},
            {"raw_ckE": [1]},
            {"raw_clT": "IsKnownRecipe("},
            {"raw_cvc": "unsupported-counter"},
            {"raw_cvd": True},
        ):
            modified = dict(source, **change)
            recipes = dict(self.native_catalog.recipes)
            recipes[recipe_id] = modified
            with self.subTest(change=change):
                with self.assertRaisesRegex(
                    ValueError,
                    "Unsupported native crafting recipe criterion or flags",
                ):
                    _recipe(
                        _RecipeCatalogView(recipes),
                        {"definition_id": 182},
                        recipe_id,
                        db=db,
                        account_id=account_id,
                    )

        db = _KnowledgeDB({})
        with self.assertRaisesRegex(ValueError, "has not been learned"):
            _recipe(
                self.catalog,
                {"definition_id": 182},
                recipe_id,
                db=db,
                account_id=account_id,
            )
