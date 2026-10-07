from copy import deepcopy
from types import SimpleNamespace
import unittest

from wakfu_ai.planning.corridor_reservations import draft, valid
from wakfu_ai.planning.team_blackboard import observe, confirm, team_context
from wakfu_ai.planning.scoring import evaluate
from wakfu_ai.planning.tactical import DEFAULT_WEIGHTS


def fixture():
    def actor(identity, team, position):
        return SimpleNamespace(
            id=identity,
            team=team,
            position=position,
            hp=20,
            effect_stats={97: 0},
            physical_radius=0,
            native_obstacle_id=identity,
            native_los_height=10,
            turn_count=1,
        )

    owner, ally, enemy = (
        actor(-1, 1, (0, 0, 0)),
        actor(-2, 1, (0, 1, 0)),
        actor(7, 0, (3, 0, 0)),
    )
    fight = SimpleNamespace(
        actors={a.id: a for a in (owner, ally, enemy)},
        current=owner,
        sequence=10,
        turn_id=1,
        native_table_turn=1,
        walkable={(0, 0, 0), (0, 1, 0), (1, 0, 0), (1, 0, 9), (2, 0, 0), (3, 0, 0)},
    )
    return SimpleNamespace(fight=fight, tactical_encounter_id="instance-one")


def record(runtime, *, rays=None):
    fight = runtime.fight
    result = draft(
        fight,
        fight.actors[-1],
        dict(type="cast", spellId=987654, level=1, target=[3, 0, 0], targetId=7),
        1134,
        rays=rays or (lambda *args, **kwargs: ((True, {(1, 0), (2, 0)}),)),
        legacy=lambda *args: None,
        footprint=lambda position, radius: (tuple(position[:2]),),
    )
    result.update(
        instanceId=runtime.tactical_encounter_id, sourceRevision=10, expiresRound=2
    )
    return result


def publish(runtime):
    before = observe(runtime.fight)
    reservation = record(runtime)
    runtime.fight.actors[7].hp -= 2
    runtime.fight.sequence += 1
    confirm(
        runtime,
        before,
        [
            dict(
                action=dict(
                    type="cast", spellId=987654, level=1, target=[3, 0, 0], targetId=7
                ),
                coordinationDraft=reservation,
            )
        ],
    )
    return reservation


class CorridorReservationTests(unittest.TestCase):
    def test_real_native_ray_corridor_matches_authoritative_visibility_and_dynamic_blocker(
        self,
    ):
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint

        runtime = fixture()
        fight = runtime.fight
        fight.actors[-1].position = (-14, -10, -1)
        fight.actors[-2].position = (-14, -9, -1)
        fight.actors[7].position = (-11, -10, -1)
        for actor in fight.actors.values():
            actor.native_los_height = 6
        fight.walkable = {(x, -10, -1) for x in range(-14, -10)} | {(-14, -9, -1)}
        action = dict(
            type="cast", spellId=987654, level=1, target=[-11, -10, -1], targetId=7
        )
        footprints = {
            a.id: footprint(a.position, a.physical_radius)
            for a in fight.actors.values()
        }
        self.assertTrue(
            authoritative_visible(
                1134,
                fight.actors[-1].position,
                fight.actors[7].position,
                fight,
                blocking_footprints=footprints,
            )
        )
        reservation = draft(fight, fight.actors[-1], action, 1134)
        reservation.update(
            instanceId=runtime.tactical_encounter_id, sourceRevision=10, expiresRound=2
        )
        self.assertIn([-13, -10, -1], reservation["cells"])
        self.assertTrue(valid(reservation, fight, 1))
        fight.actors[-2].position = (-13, -10, -1)
        self.assertFalse(valid(reservation, fight, 1))
        with self.assertRaises(ValueError):
            draft(fight, fight.actors[-1], action, 1134)

    def test_malformed_checkpoint_coordinates_are_discarded_without_aborting_turn_context(
        self,
    ):
        for name, bad in (("source", None), ("target", 7), ("source", [True, 0, 0])):
            runtime = fixture()
            publish(runtime)
            row = runtime.fight.native_ai_team_context["1"]["corridors"][0]
            row[name] = bad
            self.assertFalse(valid(row, runtime.fight, 1))
            self.assertEqual(
                team_context(runtime.fight, "instance-one", -2)["reservedCells"], []
            )

    def test_native_probes_cover_all_walkable_heights_without_interpolating(self):
        runtime = fixture()
        reservation = record(runtime)
        self.assertEqual(reservation["cells"], [[1, 0, 0], [1, 0, 9], [2, 0, 0]])
        self.assertTrue(valid(reservation, runtime.fight, 1))
        self.assertNotIn([0, 0, 0], reservation["cells"])
        self.assertNotIn([3, 0, 0], reservation["cells"])

    def test_choose_first_native_ray_that_passes_actual_blocker_predicate(self):
        runtime = fixture()
        reservation = record(
            runtime,
            rays=lambda *args, **kwargs: (
                (True, {(0, 1)}),
                (True, {(1, 0)}),
                (True, {(2, 0)}),
            ),
        )
        self.assertEqual(reservation["probes"], [[1, 0]])
        self.assertEqual(reservation["cells"], [[1, 0, 0], [1, 0, 9]])

    def test_unknown_or_blocked_ray_never_creates_a_corridor(self):
        for alternatives in (
            ((False, {(1, 0)}),),
            ((True, {(0, 1)}),),
            ((True, {(99, 99)}),),
        ):
            with self.subTest(alternatives=alternatives), self.assertRaises(ValueError):
                record(fixture(), rays=lambda *args, **kwargs: alternatives)

    def test_dead_moved_restarted_or_expired_endpoints_invalidate(self):
        for change in (
            lambda f: setattr(f.actors[-1], "hp", 0),
            lambda f: setattr(f.actors[7], "hp", 0),
            lambda f: setattr(f.actors[-1], "position", (0, 1, 0)),
            lambda f: setattr(f.actors[7], "position", (2, 0, 0)),
            lambda f: setattr(f.actors[-1], "turn_count", 2),
            lambda f: setattr(f, "native_table_turn", 3),
        ):
            runtime = fixture()
            reservation = record(runtime)
            change(runtime.fight)
            self.assertFalse(valid(reservation, runtime.fight, 1))

    def test_new_blocker_at_another_height_invalidates_read_without_mutating_memory(
        self,
    ):
        runtime = fixture()
        publish(runtime)
        saved = deepcopy(runtime.fight.native_ai_team_context)
        runtime.fight.actors[-2].position = (1, 0, 9)
        self.assertEqual(
            team_context(runtime.fight, "instance-one", -2)["reservedCells"], []
        )
        self.assertEqual(saved, runtime.fight.native_ai_team_context)

    def test_draft_is_unpublished_then_shared_only_with_other_allies(self):
        runtime = fixture()
        record(runtime)
        self.assertEqual(
            team_context(runtime.fight, "instance-one", -2)["reservedCells"], []
        )
        publish(runtime)
        ally = team_context(runtime.fight, "instance-one", -2)
        self.assertEqual(ally["reservedCells"], [[1, 0, 0], [1, 0, 9], [2, 0, 0]])
        self.assertEqual(ally["corridors"][0]["basis"], "native_los_probes")
        self.assertEqual(
            team_context(runtime.fight, "instance-one", -1)["reservedCells"], []
        )
        self.assertEqual(
            team_context(runtime.fight, "instance-one", 7)["reservedCells"], []
        )
        self.assertEqual(
            team_context(runtime.fight, "foreign-instance", -2)["reservedCells"], []
        )

    def test_owner_move_clears_its_corridor_even_when_it_returns_to_same_cell(self):
        runtime = fixture()
        publish(runtime)
        before = observe(runtime.fight)
        confirm(runtime, before, [dict(action=dict(type="move", path=[[0, 0, 0]]))])
        self.assertEqual(
            team_context(runtime.fight, "instance-one", -2)["reservedCells"], []
        )

    def test_end_turn_keeps_established_corridor_until_owner_next_turn(self):
        runtime = fixture()
        publish(runtime)
        before = observe(runtime.fight)
        runtime.fight.current = runtime.fight.actors[-2]
        confirm(runtime, before, [dict(action=dict(type="end_turn"))])
        self.assertTrue(
            team_context(runtime.fight, "instance-one", -2)["reservedCells"]
        )
        runtime.fight.actors[-1].turn_count += 1
        self.assertEqual(
            team_context(runtime.fight, "instance-one", -2)["reservedCells"], []
        )

    def test_unrelated_or_foreign_diagnostic_cannot_confirm_a_reservation(self):
        for change in (
            lambda row: row.update(instanceId="foreign-instance"),
            lambda row: row.update(ownerId=-2),
            lambda row: row.update(sourceRevision=99),
            lambda row: row.update(spellId=1),
        ):
            runtime = fixture()
            reservation = record(runtime)
            change(reservation)
            before = observe(runtime.fight)
            confirm(
                runtime,
                before,
                [
                    dict(
                        action=dict(
                            type="cast", spellId=987654, level=1, target=[3, 0, 0]
                        ),
                        coordinationDraft=reservation,
                    )
                ],
            )
            self.assertEqual(
                team_context(runtime.fight, "instance-one", -2)["reservedCells"], []
            )

    def test_soft_score_checks_native_footprint_and_ignored_los_actor(self):
        row = dict(
            team=1,
            hp=20,
            armor=0,
            ap=6,
            mp=3,
            wp=2,
            position=(0, 1, 0),
            blockingFootprint=[[0, 1]],
            blocksNativeLos=True,
        )
        root = dict(actors={-2: row}, position=0, threat=0, uncertainty=0)
        state = deepcopy(root)
        state["actors"][-2].update(
            position=(0, 0, 9), blockingFootprint=[[0, 0], [1, 0]]
        )
        team = dict(reservedCells=[[1, 0, 0]])
        score, components, *_ = evaluate(root, state, -2, DEFAULT_WEIGHTS, team)
        self.assertEqual(
            components["coordination"], -5 * DEFAULT_WEIGHTS["coordination"]
        )
        state["actors"][-2]["blocksNativeLos"] = False
        self.assertEqual(
            evaluate(root, state, -2, DEFAULT_WEIGHTS, team)[1]["coordination"], 0
        )
