"""Exercise the actual server resolver without starting listeners or fixtures."""
import ast
from pathlib import Path
import unittest
from wakfu_server.combat_groups import Groups
from wakfu_server.monsters import owned_instance

source = Path(__file__).resolve().parents[1] / "local_game_server.py"
module = ast.parse(source.read_text())
function = next(
    node
    for node in module.body
    if isinstance(node, ast.FunctionDef) and node.name == "combat_group_for_target"
)
namespace = {}
exec(
    compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"),
    namespace,
)
resolve = namespace["combat_group_for_target"]


class CombatTargetTests(unittest.TestCase):
    def registry(self):
        groups = Groups()
        first = [owned_instance(5525, 1, -200, map_id=1134, x=-7, y=-7, z=-1)]
        second = [
            owned_instance(5525, 1, -300 - i, map_id=1385, x=3, y=-12 + i, z=1)
            for i in range(2)
        ]
        groups.register(1134, 0, 200, first)
        groups.register(1385, 0, 300, second)
        return groups

    def test_map_target_selects_actual_roster_without_default_group(self):
        groups = self.registry()
        selected = resolve(groups, dict(map_id=1385, instance_id=0), -301)
        self.assertEqual(selected["key"], (1385, 0, 300))
        self.assertEqual([m["id"] for m in selected["members"]], [-300, -301])
        selected["members"][0]["x"] = 900
        self.assertEqual(
            resolve(groups, dict(map_id=1134, instance_id=0), -200)["members"][0]["x"],
            -7,
        )
        self.assertEqual(
            resolve(groups, dict(map_id=1385, instance_id=0), -300)["members"][0]["x"],
            3,
        )

    def test_foreign_map_instance_or_claimed_target_cannot_start_another_fight(self):
        groups = self.registry()
        for character, target in [
            (dict(map_id=1134, instance_id=0), -300),
            (dict(map_id=1385, instance_id=1), -300),
            (dict(map_id=1385, instance_id=0), -999),
        ]:
            with self.assertRaises(ValueError):
                resolve(groups, character, target)
        group = resolve(groups, dict(map_id=1385, instance_id=0), -300)
        lease, members = groups.claim(group["key"], "session", 71)
        with self.assertRaises(ValueError):
            resolve(groups, dict(map_id=1385, instance_id=0), -301)
        groups.finish(lease, defeated=False)
        self.assertEqual(
            resolve(groups, dict(map_id=1385, instance_id=0), -301)["members"], members
        )
