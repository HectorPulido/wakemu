"""Actual AI observers can describe a retained actor after genuine fdt removal."""
from types import SimpleNamespace
import unittest

from wakfu_server.combat_state import Actor
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    register_global_fighter,
    unregister_global_fighter,
)
from wakfu_ai.planning.team_blackboard import observe
from wakfu_ai.bridge.world_bridge import NativeSession


class RetiredActorObserverTests(unittest.TestCase):
    def test_blackboard_and_session_keep_removed_actor_diagnostic_without_controller(
        self,
    ):
        cells = frozenset((x, 0, 0) for x in range(4))
        actors = [
            Actor(15, 0, (0, 0, 0), 100, 6, 3, 1, 200),
            Actor(31, 0, (1, 0, 0), 100, 6, 4, 1, 200),
            Actor(-7, 1, (3, 0, 0), 100, 6, 6, 1, 200),
        ]
        fight = SimpleNamespace(
            actors={a.id: a for a in actors},
            native_effect_areas={},
            current=actors[2],
            turn_id=8,
            phase="active",
            sequence=20,
            walkable=cells,
            edges=frozenset(
                (a, b) for a in cells for b in cells if abs(a[0] - b[0]) == 1
            ),
        )
        initialize_global_pv_collections(
            fight, (15, 31, -7), controller_registration=True
        )
        child = Actor(208, 0, (2, 0, 0), 80, 6, 3, 1, 200)
        fight.actors[208] = child
        register_global_fighter(fight, 208, controller_id=15)
        for actor in fight.actors.values():
            actor.effect_stats = {4: 6, 97: 0}
            actor.physical_radius = 0
            actor.direction = 0
        fight.actors[31].hp = 0
        unregister_global_fighter(fight, 31)
        original_rows = {
            k: dict(v) for k, v in fight.native_controller_registry["fighters"].items()
        }

        observation = observe(fight)
        self.assertEqual(observation["actors"][31]["team"], -1)
        self.assertEqual(observation["actors"][208]["team"], 0)
        self.assertEqual(observation["actors"][208]["hp"], 80)

        session = NativeSession.__new__(NativeSession)
        session.states = {"root": SimpleNamespace(fight=fight)}
        session.state_identities = {"root": "0" * 64}
        session.oracle = SimpleNamespace()
        # Repertoire caching is unrelated to this actual observation projection.
        # No action/eligibility result is substituted for controller queries.
        session._actor_repertoire_cache = {("root", tuple(sorted(fight.actors))): {}}
        description = session.describe("root")
        rows = {row["id"]: row for row in description["actors"]}
        self.assertEqual(rows[31]["team"], -1)
        self.assertEqual(rows[31]["hp"], 0)
        self.assertEqual(rows[208]["team"], 0)
        self.assertEqual(rows[208]["hp"], 80)
        self.assertEqual(fight.native_controller_registry["fighters"], original_rows)
        self.assertNotIn("31", original_rows)
