"""Native execution bridge keeps QI current before each original Qs callback."""
import copy
import unittest
from unittest.mock import patch

import test_native_oracle as fixture_module
from wakfu_server.combat_geometry_snapshot import freeze_terrain
from wakfu_server.combat_qi_fight import current_registry, move_registered_actor
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.spells import default_deck


class NativeMovementQIBoundaryTests(unittest.TestCase):
    def test_multi_step_area_callbacks_use_current_qk_and_preserve_live_source(self):
        fixture = fixture_module.NativeOracleTests.wonejo_fixture()
        from wakfu_server.combat_qi_snapshot import NativeQISnapshot

        qi = NativeQISnapshot(fixture.fight.native_qi_snapshot)
        neighbors = {}
        for source, target in fixture.fight.edges:
            if (
                source in fixture.fight.walkable
                and target in fixture.fight.walkable
                and source[2] == target[2]
                and abs(source[0] - target[0]) + abs(source[1] - target[1]) == 1
                and fixture.pc.position not in (source, target)
            ):
                neighbors.setdefault(source, []).append(target)
        routes = [
            (source, middle, target)
            for source, middles in neighbors.items()
            for middle in middles
            for target in neighbors.get(middle, ())
            if len({source, middle, target}) == 3
            and all(qi.aK(*cell[:2]) for cell in (source, middle, target))
        ]
        self.assertTrue(routes, "Original arena must provide a legal two-step route")
        # Prefer native perimeter callbacks, reproducing the incident's faP
        # consumer rather than inventing a cropped walkable/QI rectangle.
        path = min(
            routes,
            key=lambda route: (-sum(qi.P(*cell[:2]) for cell in route[1:]), route),
        )
        move_registered_actor(fixture.fight, fixture.npc, path[0])
        freeze_terrain(fixture.fight)
        runtime = RuntimeMessages(fixture.fight)
        oracle = fixture_module.NativeOracleTests.oracle_for(
            runtime,
            fixture.character,
            fixture.monster,
            default_deck(fixture.character),
            flags={"native_area_callbacks": True},
        )
        before = copy.deepcopy(fixture.fight.native_qi_slots)
        observed = []
        from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime

        original = NativeAreaEventRuntime.movement

        def observe(events, identity, *, from_cell, to_cell):
            registry = current_registry(events.fight)
            actor = events.fight.actors[identity]
            self.assertEqual(actor.position, to_cell)
            self.assertEqual(
                tuple(registry.slots[actor.native_obstacle_id]["position"]), to_cell[:2]
            )
            observed.append((from_cell, to_cell))
            return original(events, identity, from_cell=from_cell, to_cell=to_cell)

        with patch.object(NativeAreaEventRuntime, "movement", observe):
            private, _, _ = oracle.preview(
                runtime, {"type": "move", "path": [list(cell) for cell in path[1:]]}
            )
        self.assertEqual(observed, list(zip(path, path[1:])))
        self.assertEqual(private.fight.actors[fixture.npc.id].position, path[-1])
        self.assertEqual(fixture.fight.native_qi_slots, before)
        self.assertEqual(fixture.npc.position, path[0])
