"""Settlement publishes native quest changes and flat physical registry packets."""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import struct
import unittest
from unittest.mock import Mock, patch

from wakfu_server import combat_drops, combat_drop_delivery, inventory_move
from wakfu_server.inventory_items import equipment_inventory
from wakfu_server.items.quest_inventory import REFERENCES


class QuestLootPublicationTests(unittest.TestCase):
    def test_both_settlement_paths_publish_owned_absolute_quest_quantities(self):
        for name in ("shared_loot", "resolve_fight_loot"):
            with self.subTest(path=name):
                self.check_settlement(name, existing=3, awarded=2)

    def test_replayed_settlement_does_not_repeat_quest_addition(self):
        for name in ("shared_loot", "resolve_fight_loot"):
            with self.subTest(path=name):
                self.check_settlement(name, existing=5, awarded=0)

    def check_settlement(self, name, *, existing, awarded):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == name
        )
        reference = min(REFERENCES)
        before = dict(
            id=7,
            inventory_items=[],
            quest_items=[dict(character_id=7, reference=reference, quantity=existing)],
        )
        after = deepcopy(before)
        after["quest_items"][0]["quantity"] += awarded
        store = SimpleNamespace(character=Mock(side_effect=[before, after]))
        synchronization = Mock(return_value=(13713, b"bags"))
        namespace = dict(
            STORE=store,
            account_id=2,
            generation=4,
            character=before,
            fight=SimpleNamespace(id=3, actors={7: object()}),
            TEST_MONSTERS=[],
            frozen_contexts={7: (None, {})},
            combat_reward_context=SimpleNamespace(build_drop_context=lambda *a: {}),
            combat_drops=combat_drops,
            combat_drop_delivery=combat_drop_delivery,
            synchronization=synchronization,
            equipment_inventory=equipment_inventory,
        )
        exec(
            compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"),
            namespace,
        )
        with patch.object(combat_drops, "resolve", return_value=object()), patch.object(
            combat_drops, "native_prospection_bonus", return_value=0
        ), patch.object(combat_drops, "report_loots", return_value=[]), patch.object(
            combat_drop_delivery, "apply"
        ), patch.object(
            combat_drop_delivery, "temporary_update", return_value=(13728, b"temporary")
        ), patch.object(
            inventory_move, "synchronization", synchronization
        ):
            if name == "shared_loot":
                result = namespace[name](
                    None, dict(character_id=7, account_id=2, session_generation=4), None
                )
            else:
                result = namespace[name](None, None)
        packets = result["packets"]
        self.assertTrue(
            all(
                type(opcode) is int and isinstance(body, bytes)
                for opcode, body in packets
            )
        )
        self.assertIn(equipment_inventory(after), packets)
        quest = [body for opcode, body in packets if opcode == 13879]
        self.assertEqual(
            quest,
            [struct.pack(">qBih", 7, 2, reference, existing + awarded)]
            if awarded
            else [],
        )


if __name__ == "__main__":
    unittest.main()
