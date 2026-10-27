"""Execute the production idle regeneration gate across combat cleanup."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


class WorldRegenerationDispatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse(
            (Path(__file__).resolve().parents[1] / "local_game_server.py").read_text()
        )
        gate = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and any(
                isinstance(call, ast.Call)
                and ast.unparse(call.func) == "health_store.tick_company"
                for call in ast.walk(node)
            )
            and "last_health_tick" in ast.unparse(node.test)
        )
        cls.code = compile(
            ast.fix_missing_locations(ast.Module(body=[gate], type_ignores=[])),
            "<actual-world-regeneration-gate>",
            "exec",
        )

    def context(self, *, fight=None, combat_session=None):
        return dict(
            loaded=True,
            character=dict(id=4, hp=60, max_hp=60),
            fight=fight,
            combat_session=combat_session,
            last_health_tick=0,
            time=SimpleNamespace(monotonic=lambda: 10),
            health_store=SimpleNamespace(
                tick_company=Mock(
                    return_value=(
                        dict(
                            id=4,
                            hp=61,
                            max_hp=70,
                            hp_damage=9,
                            health_dead=False,
                            previous_hp=60,
                            regeneration_coefficient=3,
                            health_changed=True,
                        ),
                    )
                )
            ),
            STORE=object(),
            account_id=2,
            generation="owned",
            WORLD=Mock(),
            health=SimpleNamespace(packet=Mock(return_value=b"hp")),
            record=Mock(),
        )

    def test_combat_and_finished_shared_awaiting_return_do_not_tick_stale_world_hp(
        self,
    ):
        for phase in ("placement", "active", "finished"):
            with self.subTest(phase=phase):
                context = self.context(
                    fight=SimpleNamespace(phase=phase), combat_session=object()
                )
                context["health_store"].tick_company.side_effect = ValueError(
                    "Stale health update"
                )
                exec(self.code, context)
                context["health_store"].tick_company.assert_not_called()
                self.assertEqual(context["character"]["hp"], 60)
                context["WORLD"].update.assert_not_called()

    def test_attached_session_without_local_fight_does_not_regenerate(self):
        context = self.context(combat_session=object())
        exec(self.code, context)
        context["health_store"].tick_company.assert_not_called()

    def test_exploration_still_uses_owned_expected_hp_and_sends_regeneration(self):
        context = self.context()
        exec(self.code, context)
        context["health_store"].tick_company.assert_called_once_with(
            context["STORE"], 2, "owned", 4, 60
        )
        self.assertEqual(context["character"]["hp"], 61)
        self.assertEqual(context["character"]["max_hp"], 70)
        context["WORLD"].update.assert_called_once_with(
            "owned", context["character"], 12436, b"hp"
        )
