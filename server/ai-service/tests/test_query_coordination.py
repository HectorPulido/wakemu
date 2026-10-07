"""Source-bound coordination through the actual v3 search coroutine."""
import unittest

from test_query_search import ALLY_ID, ENEMY_ID, fixture, run_search


def context(session, *, reserved=(), focus=None):
    session.envelope.update(fightInstanceId="native-encounter-one", stateRevision=97)
    session.envelope["teamContext"] = dict(
        fightInstanceId="native-encounter-one",
        stateRevision=97,
        team=1,
        focusId=focus,
        reservedCells=[list(cell) for cell in reserved],
        future_field={"kept": True},
    )


class QueryCoordinationTests(unittest.TestCase):
    def test_json_reservation_keeps_corridor_clear(self):
        session = fixture([])
        context(session, reserved=[(1, 0, 0)])
        result = run_search(session)
        self.assertEqual(result["action"], {"type": "end_turn"})

    def test_actor_already_in_corridor_is_rewarded_for_leaving(self):
        session = fixture([])
        context(session, reserved=[(0, 0, 0)])
        result = run_search(session)
        self.assertEqual(result["action"], {"type": "move", "path": [[1, 0, 0]]})
        self.assertEqual(result["components"]["coordination"], 5)

    def test_stale_foreign_revision_or_team_reject_before_native_query(self):
        for field, value in (
            ("fightInstanceId", "another-encounter"),
            ("stateRevision", 96),
            ("team", 0),
        ):
            session = fixture([])
            context(session)
            session.envelope["teamContext"][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(
                ValueError, "Stale or foreign"
            ):
                run_search(session)
            self.assertEqual(session.preview_actions, [])

    def test_dead_or_friendly_focus_rejects_before_native_query(self):
        for focus in (ALLY_ID, 404, True, ENEMY_ID):
            session = fixture([])
            context(session, focus=focus)
            if focus == ENEMY_ID:
                session.envelope["root"]["actors"][-1]["hp"] = 0
            with self.subTest(focus=focus), self.assertRaisesRegex(
                ValueError, "Invalid native team focus"
            ):
                run_search(session)

    def test_xyz_reservation_preserves_height(self):
        session = fixture([])
        context(session, reserved=[(1, 0, 1)])
        result = run_search(session)
        self.assertEqual(result["action"]["type"], "move")
        self.assertEqual(result["components"]["coordination"], 0)

    def test_malformed_json_reservation_rejects(self):
        for cell in ([1, 0], [True, 0, 0], [1, "0", 0]):
            session = fixture([])
            context(session)
            session.envelope["teamContext"]["reservedCells"] = [cell]
            with self.subTest(cell=cell), self.assertRaisesRegex(
                ValueError, "Invalid native team reservations"
            ):
                run_search(session)
