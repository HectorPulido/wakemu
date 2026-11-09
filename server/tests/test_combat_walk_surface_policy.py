"""Sn point-mover bLF gates run before movement resources or events commit."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight


MAP_ID = 910
SOURCE_SHA256 = "eb36ad4b882069928893bdd5d7a0a360adcef2e71ce23f65386f446393dc0835"


class NativeWalkSurfacePolicyTests(unittest.TestCase):
    @staticmethod
    def _columns(*, flags=None):
        from wakfu_server.combat_sn_path import NativeSnColumns

        flags = flags or {2: 2, 3: 3, 4: 8, 6: 1}
        rows = [[x, 56, [[0, 0, 0, flags.get(x, 0), 0, False]]] for x in range(8)]
        data = {
            "schema": "native-Sn-Vy-columns-v1",
            "map_id": MAP_ID,
            "source_sha256": SOURCE_SHA256,
            "chunks": [{"x": 0, "y": 55, "width": 18, "height": 18, "columns": rows}],
        }
        return NativeSnColumns(data, map_id=MAP_ID, source_sha256=SOURCE_SHA256)

    def test_paid_server_move_distinguishes_blf_two_from_fight_sterile(self):
        from wakfu_server.combat_sn_path import NativeSnColumns
        import wakfu_server.combat_ground_support as ground
        import wakfu_server.combat_world_properties as world_properties

        columns = self._columns()
        actor = Actor(7, 0, (1, 56, 0), 100, 6, 3, 10, 1)
        actor.physical_radius = 0
        actor.native_death_status = {"actor_kind": "bje"}
        actor.native_world_properties = frozenset()
        actor.native_fight_properties = frozenset()
        opponent = Actor(8, 1, (5, 56, 0), 100, 6, 3, 1, 1, 8, True)
        opponent.physical_radius = 0
        walkable = {(x, y, 0) for x in range(0, 8) for y in range(55, 58)}
        edges = {((x, y, 0), (x + 1, y, 0)) for x in range(0, 7) for y in range(55, 58)}
        edges |= {(target, source) for source, target in edges}
        fight = Fight(
            508, [actor, opponent], walkable, {0: walkable, 1: walkable}, edges
        )
        fight.native_qi_surface_provenance = {
            "map_id": MAP_ID,
            "source_sha256": SOURCE_SHA256,
        }
        # Isolate the verified physical-column rule from external catalog I/O.
        # Fight.server_move itself validates path, movement cost, mutation and event.
        with (
            patch.object(NativeSnColumns, "from_published", return_value=columns),
            patch.object(ground, "supported", return_value=True),
            patch.object(
                world_properties,
                "registry",
                return_value={"85": {"name": "RELIC_SPECIAL_JUMP"}},
            ),
            patch.object(world_properties, "has_world_property", return_value=False),
        ):
            fight.phase = "active"
            fight.order = [actor.id]
            fight.turn_index = 0
            result = fight.server_move(actor.id, [(2, 56, 0)])
            self.assertEqual(actor.position, (2, 56, 0))
            self.assertEqual(actor.mp, 2)
            self.assertEqual(result["kind"], "movement")
            self.assertEqual(result["cost"], 1)

            # bLF=3 has bit zero set; reject it before resource/event mutation.
            before = self._snapshot(fight, actor)
            with self.assertRaisesRegex(ValueError, "fight-sterile"):
                fight.server_move(actor.id, [(3, 56, 0)])
            self.assertEqual(self._snapshot(fight, actor), before)

            # A normal neighboring cell remains a valid paid route.
            result = fight.server_move(actor.id, [(1, 56, 0)])
            self.assertEqual(actor.position, (1, 56, 0))
            self.assertEqual(actor.mp, 1)
            self.assertEqual(result["cost"], 1)

            # The special-jump surface remains gated independently.
            actor.position = (5, 56, 0)
            opponent.position = (0, 56, 0)
            actor.mp = 3
            before = self._snapshot(fight, actor)
            with self.assertRaisesRegex(ValueError, "special-jump"):
                fight.server_move(actor.id, [(4, 56, 0)])
            self.assertEqual(self._snapshot(fight, actor), before)

            second = Actor(27, 0, (5, 56, 0), 100, 6, 3, 10, 1)
            second.physical_radius = 0
            second.native_death_status = {"actor_kind": "bje"}
            second.native_world_properties = frozenset()
            second.native_fight_properties = frozenset()
            far_opponent = Actor(28, 1, (0, 56, 0), 100, 6, 3, 1, 1, 28, True)
            far_opponent.physical_radius = 0
            bit_one_fight = Fight(
                510, [second, far_opponent], walkable, {0: walkable, 1: walkable}, edges
            )
            bit_one_fight.native_qi_surface_provenance = {
                "map_id": MAP_ID,
                "source_sha256": SOURCE_SHA256,
            }
            bit_one_fight.phase = "active"
            bit_one_fight.order = [second.id]
            bit_one_fight.turn_index = 0
            before = self._snapshot(bit_one_fight, second)
            with self.assertRaisesRegex(ValueError, "fight-sterile"):
                bit_one_fight.server_move(second.id, [(6, 56, 0)])
            self.assertEqual(self._snapshot(bit_one_fight, second), before)

        # A separately authorized bjo still crosses a native jump-origin/landing
        # pair, with the ordinary movement cost and public Fight transition.
        jump_columns = self._columns(flags={2: 16, 3: 8})
        jumper = Actor(17, 0, (1, 56, 0), 100, 6, 3, 10, 1)
        jumper.physical_radius = 0
        jumper.native_death_status = {"actor_kind": "bjo"}
        jumper.native_world_properties = frozenset({85})
        jumper.native_fight_properties = frozenset()
        opponent = Actor(18, 1, (5, 56, 0), 100, 6, 3, 1, 1, 18, True)
        opponent.physical_radius = 0
        jump_fight = Fight(
            509, [jumper, opponent], walkable, {0: walkable, 1: walkable}, edges
        )
        jump_fight.native_qi_surface_provenance = {
            "map_id": MAP_ID,
            "source_sha256": SOURCE_SHA256,
        }
        with (
            patch.object(NativeSnColumns, "from_published", return_value=jump_columns),
            patch.object(ground, "supported", return_value=True),
            patch.object(
                world_properties,
                "registry",
                return_value={"85": {"name": "RELIC_SPECIAL_JUMP"}},
            ),
            patch.object(world_properties, "has_world_property", return_value=True),
        ):
            jump_fight.phase = "active"
            jump_fight.order = [jumper.id]
            jump_fight.turn_index = 0
            movement = jump_fight.server_move(jumper.id, [(2, 56, 0), (3, 56, 0)])
        self.assertEqual(jumper.position, (3, 56, 0))
        self.assertEqual(jumper.mp, 1)
        self.assertEqual(movement["cost"], 2)

    def test_npc_walk_projection_separates_sterile_jump_and_floor_policy(self):
        from wakfu_server.combat_sn_path import NativeSnColumns
        from wakfu_server.combat_walk_surface_policy import (
            native_npc_point_placement_allowed,
            native_npc_walk_blocked_cells,
        )
        import wakfu_server.combat_ground_support as ground

        columns = self._columns()
        actor = SimpleNamespace(
            id=7,
            position=(1, 56, 0),
            physical_radius=0,
            native_death_status={"actor_kind": "bje"},
        )
        fight = SimpleNamespace(
            actors={7: actor},
            walkable={(x, 56, 0) for x in range(1, 6)},
            edges=set(),
            native_qi_surface_provenance={
                "map_id": MAP_ID,
                "source_sha256": SOURCE_SHA256,
            },
        )
        cells = [(2, 56, 0), (3, 56, 0), (4, 56, 0), (5, 56, 0), (6, 56, 0)]
        with (
            patch.object(NativeSnColumns, "from_published", return_value=columns),
            patch.object(ground, "escape_prefix_cells", return_value=frozenset()),
            patch.object(
                ground,
                "supported",
                side_effect=lambda _map, cell, _sha: cell != (5, 56, 0),
            ),
        ):
            # bLF=2 is traversable; bit0, special jump and unsupported floor
            # remain excluded from the ordinary NPC planner.
            self.assertEqual(
                native_npc_walk_blocked_cells(fight, actor, cells),
                {(3, 56, 0), (4, 56, 0), (5, 56, 0), (6, 56, 0)},
            )
            with patch.object(ground, "supported", return_value=True):
                self.assertFalse(
                    native_npc_point_placement_allowed(columns, (2, 56, 0))
                )
                self.assertFalse(
                    native_npc_point_placement_allowed(columns, (3, 56, 0))
                )
                self.assertTrue(native_npc_point_placement_allowed(columns, (6, 56, 0)))

    def fixture(
        self,
        *,
        kind="bjo",
        special_jump=False,
        radius=0,
        controlled=True,
        provenance=True,
    ):
        actor = Actor(
            7,
            0,
            (1, 56, 0),
            100,
            6,
            3,
            10,
            1,
            7 if controlled else None,
            controlled,
        )
        actor.physical_radius = radius
        actor.native_death_status = {
            "source": "fresh.bjo.constructor"
            if kind == "bjo"
            else "fresh.bjm.constructor",
            "actor_kind": kind,
            "mwD": False,
            "dtM_status": None,
        }
        actor.native_world_properties = frozenset({85}) if special_jump else frozenset()
        actor.native_fight_properties = frozenset()
        actors = [actor]
        other = Actor(8, 1, (5, 56, 0), 100, 6, 3, 1, 1, 8, True)
        other.physical_radius = 0
        actors.append(other)
        walkable = {(x, y, 0) for x in range(0, 7) for y in range(55, 58)}
        fight = Fight(
            508,
            actors,
            walkable,
            {0: set(walkable), 1: set(walkable)},
        )
        if controlled:
            fight.ready(7)
        fight.ready(8)
        if provenance:
            fight.native_qi_surface_provenance = {
                "map_id": MAP_ID,
                "source_sha256": SOURCE_SHA256,
            }
        return fight, actor

    def _snapshot(self, fight, actor):
        return actor.position, actor.ap, actor.mp, tuple(fight.events)

    def test_public_move_rejects_special_surface_without_property_before_payment(self):
        fight, actor = self.fixture(special_jump=False)
        before = self._snapshot(fight, actor)
        with self.assertRaisesRegex(ValueError, "special-jump"):
            fight.move(actor.owner_id, actor.id, [(2, 56, 0)])
        self.assertEqual(self._snapshot(fight, actor), before)

    def test_relic_jump_origin_and_landing_allow_the_published_two_step_crossing(self):
        fight, actor = self.fixture(special_jump=True)
        movement = fight.move(actor.owner_id, actor.id, [(2, 56, 0), (3, 56, 0)])
        self.assertEqual(actor.position, (3, 56, 0))
        self.assertEqual(actor.mp, 1)
        self.assertIsNotNone(movement)

    def test_fresh_ordinary_npc_without_innates_gets_constructor_status_for_walk(self):
        from wakfu_server.combat_npc_initialization import install_initial_properties
        from wakfu_server.combat_walk_surface_policy import require_native_walk_surfaces

        fight, actor, *_ = self._planner_fixture()
        del actor.native_death_status
        install_initial_properties(actor, {"fight": {}, "world": {}})
        self.assertEqual(actor.native_death_status["actor_kind"], "bje")
        require_native_walk_surfaces(fight, actor, [(1, 55, 0)])

    def test_multistep_rejection_preserves_all_costs_and_event_history(self):
        fight, actor = self.fixture(special_jump=False)
        before = self._snapshot(fight, actor)
        with self.assertRaisesRegex(ValueError, "special-jump"):
            fight.move(actor.owner_id, actor.id, [(2, 56, 0), (3, 56, 0)])
        self.assertEqual(self._snapshot(fight, actor), before)

    def test_radius_positive_and_legacy_without_surface_provenance_keep_old_movement(
        self,
    ):
        cases = (
            self.fixture(special_jump=False, radius=1),
            self.fixture(special_jump=False, provenance=False),
        )
        for fight, actor in cases:
            with self.subTest(
                radius=actor.physical_radius,
                provenance=hasattr(fight, "native_qi_surface_provenance"),
            ):
                fight.move(actor.owner_id, actor.id, [(2, 56, 0)])
                self.assertEqual(actor.position, (2, 56, 0))

    def _planner_fixture(self, *, kind="bje", radius=0, special_jump=False):
        from wakfu_server.combat_walk_surface_policy import (
            native_npc_walk_blocked_cells,
        )
        from wakfu_server.combat_tactical_ai import _distances, _nearest_distance

        cells = {
            (1, 56, 0),
            (2, 56, 0),
            (3, 56, 0),
            (1, 55, 0),
            (2, 55, 3),
            (3, 55, 0),
        }
        edges = set()
        for route in (
            [(1, 56, 0), (2, 56, 0), (3, 56, 0)],
            [(1, 56, 0), (1, 55, 0), (2, 55, 3), (3, 55, 0), (3, 56, 0)],
        ):
            edges.update(zip(route, route[1:]))
        actor = SimpleNamespace(
            id=7,
            position=(1, 56, 0),
            hp=100,
            physical_radius=radius,
            native_death_status={"actor_kind": kind},
            native_world_properties=frozenset({85}) if special_jump else frozenset(),
            native_fight_properties=frozenset(),
        )
        fight = SimpleNamespace(
            actors={7: actor},
            walkable=cells,
            edges=edges,
            native_qi_surface_provenance={
                "map_id": MAP_ID,
                "source_sha256": SOURCE_SHA256,
            },
        )
        return (
            fight,
            actor,
            _distances,
            _nearest_distance,
            native_npc_walk_blocked_cells,
        )

    def test_npc_planner_avoids_mob_sterile_surface_and_keeps_alternate_path(self):
        fight, actor, distances, nearest_distance, _ = self._planner_fixture()
        reached = distances(fight, actor.position, actor.id)
        self.assertNotIn((2, 56, 0), reached)
        self.assertIn((3, 56, 0), reached)
        self.assertEqual(
            nearest_distance(fight, actor, lambda cell: cell == (3, 56, 0)), 4
        )

    def test_npc_only_filter_does_not_change_bjo_jump_or_radius_planning(self):
        for kind, radius, special_jump in (
            ("bjo", 0, False),
            ("bjo", 0, True),
            ("bje", 1, False),
        ):
            fight, actor, distances, _, blocked_cells = self._planner_fixture(
                kind=kind, radius=radius, special_jump=special_jump
            )
            candidates = fight.walkable - {actor.position}
            self.assertEqual(blocked_cells(fight, actor, candidates), set())
            with patch(
                "wakfu_server.combat_qi_movement.movement_blocked_cells",
                return_value=set(),
            ):
                reached = distances(fight, actor.position, actor.id)
            self.assertIn((2, 56, 0), reached)


if __name__ == "__main__":
    unittest.main()
