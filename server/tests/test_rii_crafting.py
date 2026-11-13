"""Rii crafting quest accepts only the owned native workshop and recipe."""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from wakfu_server.achievements import rii_crafting


class RiiCraftingTests(unittest.TestCase):
    def setUp(self):
        self.actor = {"id": 42, "account_id": 3, "map_id": 1385, "instance_id": 0}
        self.occupation = {
            "state": "completed",
            "token": "craft-token",
            "account_id": 3,
            "character_id": 42,
            "map_id": 1385,
            "instance_id": 0,
            "table_uid": 34659,
            "definition_id": 194,
            "recipe_id": 9445,
            "products": [{"reference": 31159, "quantity": 1}],
        }
        self.db = Mock()
        self.db.execute.return_value.fetchall.return_value = [
            {
                "definition_id": 5156,
                "data": {"native": {"d": 5156, "cjJ": [{"d": 10602}]}},
            },
            {"definition_id": 5160, "data": {"native": {"d": 5160}}},
        ]
        self.store = SimpleNamespace(
            now=lambda: SimpleNamespace(timestamp=lambda: 1234)
        )
        self.before = {"running": [5156, 5160], "objectives": []}
        self.plan = ({}, [], [10602], [5156])
        self.patches = [
            patch.object(rii_crafting.storage, "load_locked", return_value=self.before),
            patch.object(rii_crafting.storage, "record_event", return_value=True),
            patch.object(
                rii_crafting.mission_progress,
                "advance_objective",
                return_value=self.plan,
            ),
            patch.object(
                rii_crafting.mission_dependencies,
                "settle",
                return_value={"packets": [(7, b"ok")]},
            ),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)

    def test_completed_native_recipe_settles_child_and_parent_together(self):
        self.assertEqual(
            rii_crafting.settle(self.db, self.store, self.actor, self.occupation),
            [(7, b"ok")],
        )
        args = rii_crafting.mission_dependencies.settle.call_args
        self.assertEqual(args.args[6], ((5160, 10619, 5156),))
        self.assertEqual(args.kwargs["now_ms"], 1234000)
        rii_crafting.storage.record_event.assert_called_once()

    def test_wrong_workshop_recipe_or_character_is_ignored(self):
        for changes in (
            {"table_uid": 1},
            {"definition_id": 1},
            {"recipe_id": 1},
            {"character_id": 43},
            {"state": "active"},
            {"products": [{"reference": 31159, "quantity": 0}]},
        ):
            self.assertEqual(
                rii_crafting.settle(
                    self.db, self.store, self.actor, {**self.occupation, **changes}
                ),
                [],
            )
        rii_crafting.storage.load_locked.assert_not_called()

    def test_not_running_or_already_done_does_not_award(self):
        for state in (
            {"running": [], "objectives": []},
            {"running": [5156], "objectives": [10602]},
        ):
            rii_crafting.storage.load_locked.return_value = state
            self.assertEqual(
                rii_crafting.settle(self.db, self.store, self.actor, self.occupation),
                [],
            )
        rii_crafting.storage.record_event.assert_not_called()


if __name__ == "__main__":
    unittest.main()
