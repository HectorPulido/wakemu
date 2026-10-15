"""Execute the actual dispatcher cosmetic branch without importing the server loop."""
import ast
from pathlib import Path
from types import SimpleNamespace
import struct
import unittest
from unittest.mock import Mock


class CombatCosmeticSelectionTests(unittest.TestCase):
    def branch(self):
        tree = ast.parse(Path("server/local_game_server.py").read_text())
        node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.If)
            and ast.unparse(n.test) == "opcode in (12455, 13765) and loaded"
        )
        return compile(
            ast.fix_missing_locations(
                ast.Module(
                    body=[next(n for n in node.body if isinstance(n, ast.Try))],
                    type_ignores=[],
                )
            ),
            "<cosmetic-dispatch>",
            "exec",
        )

    def test_owned_choice_persists_without_replacing_live_resources(self):
        saved = dict(id=7, hp=999, owned_cosmetics={"new": True})
        store = SimpleNamespace(equip_owned_finishers=Mock(return_value=saved))
        cosmetic = SimpleNamespace(
            inventory_component=lambda: b"I", preset_component=lambda: b"P"
        )
        ctx = dict(
            fight=object(),
            character=dict(id=7, hp=20, ap=3, owned_cosmetics={}),
            STORE=store,
            account_id=1,
            opcode=12455,
            body=b"choice",
            OwnedCosmetics=SimpleNamespace(from_record=Mock(return_value=cosmetic)),
            send=Mock(),
            connection=object(),
            service="world",
            struct=struct,
            actor_update=Mock(
                side_effect=AssertionError("exploration update in combat")
            ),
            WORLD=Mock(),
            publish_mount_equipment=Mock(),
            record=Mock(),
        )
        exec(self.branch(), ctx)
        store.equip_owned_finishers.assert_called_once_with(1, 7, 12455, b"choice")
        self.assertEqual(ctx["character"]["hp"], 20)
        self.assertEqual(ctx["character"]["ap"], 3)
        self.assertEqual(ctx["character"]["owned_cosmetics"], {"new": True})
        ctx["actor_update"].assert_not_called()
        ctx["WORLD"].update.assert_not_called()
        self.assertEqual(ctx["send"].call_args.args[2], 13873)

    def test_ownership_rejection_does_not_mutate_live_character(self):
        live = dict(id=7, hp=20, owned_cosmetics={})
        ctx = dict(
            fight=object(),
            character=live,
            STORE=SimpleNamespace(
                equip_owned_finishers=Mock(side_effect=ValueError("Cosmetic not owned"))
            ),
            account_id=1,
            opcode=13765,
            body=b"choice",
            record=Mock(),
        )
        exec(self.branch(), ctx)
        self.assertIs(ctx["character"], live)
        self.assertEqual(
            ctx["record"].call_args.kwargs["event"], "owned_finishers_rejected"
        )
