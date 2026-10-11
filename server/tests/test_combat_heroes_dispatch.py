"""Exercise the dispatcher’s real hero-conditional placement branch."""
import ast
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from wakfu_server.combat_bootstrap import should_rebuild_placement


class HeroPlacementDispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        cls.branch = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.If)
            and ast.unparse(node.test)
            == "should_rebuild_placement(candidate, hero_admission['actors'])"
        )
        cls.module = ast.Module(body=[cls.branch], type_ignores=[])

    def test_empty_owned_roster_preserves_original_placement_packets(self):
        original = [(13652, b"native-create-placement"), (12847, b"native-bootstrap")]
        serializer = Mock(side_effect=AssertionError("unexpected hero reserialization"))
        namespace = {
            "hero_admission": {"actors": ()},
            "packets": original,
            "placement_messages": serializer,
            "candidate": SimpleNamespace(),
            "should_rebuild_placement": should_rebuild_placement,
        }
        exec(
            compile(self.module, "local_game_server.py:hero placement", "exec"),
            namespace,
        )
        self.assertIs(original, namespace["packets"])
        serializer.assert_not_called()

    def test_owned_hero_rebuild_uses_fresh_native_player_and_monster_payloads(self):
        hero = SimpleNamespace(id=202, controlled=True, position=(1, 0, 0))
        enemy = SimpleNamespace(
            id=-9, controlled=False, position=(3, 0, 0), native_obstacle_id=17
        )
        candidate = SimpleNamespace(id=88, actors={202: hero, -9: enemy})
        source = {"id": 202, "account_id": 7, "level": 1}
        mob = {"id": -9, "ref": 3214, "x": 3, "y": 0, "z": 0}
        payloads = {
            202: (b"fresh-player-state", b"player-effects"),
            -9: (b"fresh-monster-state", b"monster-effects"),
        }
        player_payload = Mock(return_value=payloads[202])
        monster_stats = Mock(return_value=payloads[-9][0])
        effects = Mock(side_effect=[payloads[-9][1]])
        placement = Mock(return_value=[(12847, b"fresh-bootstrap")])
        namespace = {
            "hero_admission": {
                "actors": (hero,),
                "characters": {202: source},
                "fight": candidate,
            },
            "candidate": candidate,
            "character": {"id": 101, "account_id": 7},
            "TEST_MONSTERS": (mob,),
            "TEST_MONSTERS_BY_ID": {-9: mob},
            "live_wp": Mock(return_value=(3, 6)),
            "player_payload": player_payload,
            "monster_actor_stats": monster_stats,
            "actor_effects": effects,
            "placement_messages": placement,
            "arena": {"terrain_effect_id": 10338},
            "terrain_instance_id": 44,
            "placement_duration": 30_000,
            "should_rebuild_placement": should_rebuild_placement,
        }
        exec(
            compile(self.module, "local_game_server.py:hero placement", "exec"),
            namespace,
        )
        self.assertEqual([(12847, b"fresh-bootstrap")], namespace["packets"])
        player_payload.assert_called_once_with(source, hero, candidate.id, wp=3)
        monster_stats.assert_called_once_with(
            mob, candidate.id, direction=3, obstacle_id=17
        )
        call = placement.call_args
        self.assertIs(candidate, call.args[0])
        self.assertEqual(payloads, call.args[2])


if __name__ == "__main__":
    unittest.main()
