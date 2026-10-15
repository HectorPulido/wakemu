"""The production entry boundary preserves inherited summon idle facings."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest

from wakfu_server.combat_orientation import INITIAL_PLAYER_DIRECTION
from wakfu_server.combat_summon import summon_specification
from wakfu_server.combat_summon_codec import summon_descriptor_blob


class CombatEntrySummonFacingTests(unittest.TestCase):
    def test_live_entry_keeps_initialized_facing_for_drheller_birth(self):
        # Execute the actual dispatcher boundary without importing the listening
        # server or starting a database. This catches post-constructor resets
        # that constructor-only tests cannot see.
        path = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(path.read_text())
        boundary = None
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if not isinstance(body, list):
                continue
            for index, statement in enumerate(body):
                if not isinstance(statement, ast.Expr) or not isinstance(
                    statement.value, ast.Call
                ):
                    continue
                if not any(
                    keyword.arg == "event"
                    and isinstance(keyword.value, ast.Constant)
                    and keyword.value.value == "combat_forced_terrain_ready"
                    for keyword in statement.value.keywords
                ):
                    continue
                end = next(
                    i
                    for i in range(index + 1, len(body))
                    if isinstance(body[i], ast.ImportFrom)
                    and body[i].module == "wakfu_server.combat_monster_world"
                )
                boundary = body[index + 1 : end]
        self.assertIsNotNone(boundary)
        owner = SimpleNamespace(direction=INITIAL_PLAYER_DIRECTION, controlled=True)
        hero = SimpleNamespace(direction=5, controlled=True)
        enemy = SimpleNamespace(direction=3, controlled=False)
        candidate = SimpleNamespace(actors={29: owner, 15: hero, -7: enemy})
        exec(
            compile(ast.Module(body=boundary, type_ignores=[]), str(path), "exec"),
            {"candidate": candidate},
        )
        self.assertEqual((owner.direction, hero.direction, enemy.direction), (1, 5, 3))
        specification = summon_specification(
            {"effect_class": 307},
            {"parameters": [1382, -2, 0, -1, -1, 2, 0]},
            evaluation_level=1,
            container_present=True,
            caster_level=1,
            caster_team=0,
            caster_direction=owner.direction,
            native_minimum_level=1,
        )
        self.assertEqual(specification.direction, 1)
        blob = summon_descriptor_blob(
            specification,
            actor_id=117,
            caster_id=29,
            obstacle_index=6,
            properties=(15,),
        )
        # vJ.Uq is the signed int direction at offset22, after the307 flag.
        import struct

        self.assertEqual(struct.unpack_from(">i", blob, 22)[0], 1)


if __name__ == "__main__":
    unittest.main()
