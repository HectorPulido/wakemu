"""Native control decisions use current team while constructor identity stays intact."""
from pathlib import Path
import sys
import unittest

AI_ROOT = Path(__file__).resolve().parents[1] / "ai-service"
if str(AI_ROOT) not in sys.path:
    sys.path.insert(0, str(AI_ROOT))

import test_combat_controller_registry as registry_fixtures
from wakfu_server.combat_state import Actor
from wakfu_server.combat_controller_registry import (
    register_native_controller,
    apply_native_controller_transfer,
    remove_native_controller_transfer,
)
from wakfu_server.combat_effective_control import effective_affiliation
from wakfu_server.combat_ai_capabilities import target_affinity
from wakfu_server.combat_tactical_ai import NativeProvider
from wakfu_ai.planning.team_blackboard import observe, team_context
from wakfu_ai.bridge.world_host import execute


class ControllerAffiliation207Tests(unittest.TestCase):
    def setUp(self):
        self.fight = registry_fixtures.NativeControllerRegistryTests().fight()
        self.player, self.npc = self.fight.actors.values()
        self.player.controlled = True
        self.player.owner_id = 3
        self.player.native_controlled_by_ai = False
        self.npc.native_controlled_by_ai = True
        self.old_ally = Actor(8, 0, (0, 1, 0), 100, 6, 3, 1, 68, 3, True)
        self.old_ally.native_controlled_by_ai = False
        self.fight.actors[8] = self.old_ally
        register_native_controller(self.fight, 8, team=0, controller_id=8)
        self.fight.current = self.player
        self.fight.phase = "active"
        self.fight.turn_id = 3
        self.fight.sequence = 0

    def transfer(self):
        return apply_native_controller_transfer(
            self.fight, -7, 7, use_current_controller=False
        )

    def test_current_allies_and_former_allies_use_native_team_in_tactical_targets(self):
        self.transfer()
        provider = object.__new__(NativeProvider)
        damage = {"tags": ["damage"]}
        targets = provider._useful_targets(self.fight, damage)
        self.assertIn(self.old_ally, targets)
        self.assertNotIn(self.npc, targets)
        self.assertEqual(
            target_affinity(damage, self.player, self.old_ally, fight=self.fight)[0], 0
        )
        self.assertEqual(
            target_affinity(damage, self.player, self.npc, fight=self.fight)[0], 2
        )
        self.assertEqual(self.player.team, 0)

    def test_blackboard_observation_and_context_publish_current_native_team(self):
        self.transfer()
        self.assertEqual(observe(self.fight)["team"], 1)
        self.assertEqual(observe(self.fight)["actors"][7]["team"], 1)
        self.assertEqual(team_context(self.fight, "instance", 7)["team"], 1)
        self.assertEqual(self.player.team, 0)

    def test_restoration_restores_advisory_team_without_changing_original_identity(
        self,
    ):
        previous = self.transfer()
        self.assertEqual(effective_affiliation(self.fight, self.player), 1)
        remove_native_controller_transfer(self.fight, 7, previous_ai=previous)
        self.assertEqual(effective_affiliation(self.fight, self.player), 0)
        self.assertEqual(
            (self.player.owner_id, self.player.controlled, self.player.team),
            (3, True, 0),
        )

    def test_production_bridge_routes_only_current_server_ai_player(self):
        runtime = type("Runtime", (), {})()
        runtime.fight = self.fight
        runtime.awaiting_ack = None
        runtime.pending = []
        calls = []

        def runner(*args, **kwargs):
            calls.append(args[0].fight.current.id)
            return iter(())

        context = {
            "globals": {
                "STORE": None,
                "character": {"id": 7},
                "TEST_MONSTERS_BY_ID": {},
            },
            "scopes": [],
        }
        list(execute(runtime, context, runner))
        self.assertEqual(calls, [])
        self.transfer()
        list(execute(runtime, context, runner))
        self.assertEqual(calls, [7])
        self.assertTrue(self.player.controlled)


if __name__ == "__main__":
    unittest.main()
