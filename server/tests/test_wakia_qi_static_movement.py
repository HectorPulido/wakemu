"""Native corpse occupancy remains visible to the separate movement planner."""

import unittest

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_qi_fight import (
    prepare_fresh_actor_slots,
    install_fresh_actor_slots,
)
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_qi_movement import (
    planner_static_blocked_cells,
    movement_blocked_cells,
)
from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_snapshot import _reachable


class WakiaQIStaticMovementTests(unittest.TestCase):
    def fight(self):
        actors = [
            Actor(7, 0, (0, 1, 0), 200, 8, 4, 10, 10),
            Actor(8, 0, (2, 1, 0), 40, 6, 3, 10, 10, controlled=True, owner_id=1),
            Actor(9, 1, (4, 1, 0), 20, 6, 3, 10, 10),
        ]
        for actor in actors:
            actor.physical_radius = 0
        cells = frozenset((x, y, 0) for x in range(5) for y in range(3))
        edges = frozenset(
            (a, b)
            for a in cells
            for b in cells
            if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
        )
        fight = Fight(
            42,
            actors,
            cells,
            {0: {actors[0].position, actors[1].position}, 1: {actors[2].position}},
            edges,
        )
        for actor in actors:
            actor.native_fight_property_counts = {}
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=5, height=3, cell_masks=[0] * 15
        )
        initialize_global_pv_collections(fight, tuple(actor.id for actor in actors))
        prepared = prepare_fresh_actor_slots(
            fight, physical_radii={actor.id: 0 for actor in actors}
        )
        install_fresh_actor_slots(fight, prepared)
        fight.ready(1)
        for actor in actors:
            actor.effect_stats = {1: actor.hp, 2: actor.ap, 3: actor.mp, 7: 0, 8: 0}
        # Produce an owned OFF_PLAY lifecycle; QI occupancy outlives the body.
        fight.apply_effect_damage(actors[0].id, actors[1].id, actors[1].hp)
        return fight, actors

    def test_corpse_anchor_is_exported_and_reachability_uses_a_real_detour(self):
        fight, (mover, corpse, target) = self.fight()
        static = planner_static_blocked_cells(
            fight, mover, fight.walkable, dynamic_actor_ids=[mover.id, target.id]
        )
        self.assertIn(corpse.position, static)
        self.assertNotIn(target.position, static)
        self.assertIn(
            corpse.position, movement_blocked_cells(fight, mover, fight.walkable)
        )
        reachable, _, exported = _reachable(
            fight,
            mover,
            include_movement_blocked=True,
            dynamic_actor_ids=[mover.id, target.id],
        )
        self.assertIn(corpse.position, exported)
        self.assertNotIn(corpse.position, reachable)
        self.assertEqual(reachable[(2, 0, 0)], 3)
        self.assertNotIn((3, 1, 0), reachable)  # Native detour needs five MP.

    def test_living_actor_remains_dynamic_and_native_override_is_preserved(self):
        fight, (mover, corpse, target) = self.fight()
        before = tuple(fight.native_qi_ignored_slots)
        self.assertNotIn(
            target.position,
            planner_static_blocked_cells(
                fight, mover, fight.walkable, dynamic_actor_ids=[mover.id, target.id]
            ),
        )
        self.assertIn(
            target.position,
            planner_static_blocked_cells(
                fight, mover, fight.walkable, dynamic_actor_ids=[mover.id]
            ),
        )
        self.assertEqual(tuple(fight.native_qi_ignored_slots), before)
        fight.native_qi_movement_override = True
        self.assertNotIn(
            corpse.position, planner_static_blocked_cells(fight, mover, fight.walkable)
        )
        fight.native_qi_snapshot["cell_masks"][2 + 1 * 5] |= 768
        self.assertIn(
            corpse.position, planner_static_blocked_cells(fight, mover, fight.walkable)
        )
