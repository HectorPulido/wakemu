"""Sn point-mover bLF gates run before movement resources or events commit."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight


MAP_ID = 910
SOURCE_SHA256 = "eb36ad4b882069928893bdd5d7a0a360adcef2e71ce23f65386f446393dc0835"


class NativeWalkSurfacePolicyTests(unittest.TestCase):
    def fixture(
        self,
        *,
        kind="bjo",
        special_jump=False,
        radius=0,
        controlled=True,
        provenance=True
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

    def test_server_moved_bje_cannot_enter_mob_sterile_surface_even_with_property(self):
        fight, actor = self.fixture(kind="bje", special_jump=True, controlled=False)
        before = self._snapshot(fight, actor)
        with self.assertRaisesRegex(ValueError, "actor kind"):
            fight.server_move(actor.id, [(2, 56, 0)])
        self.assertEqual(self._snapshot(fight, actor), before)

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

    def test_npc_planner_avoids_forbidden_point_and_keeps_alternate_valid_path(self):
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
