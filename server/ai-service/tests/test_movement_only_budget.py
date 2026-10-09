"""Budget allocation must speed proven walking without starving unknown casts."""
import unittest

from test_query_search import fixture, run_search


class MovementOnlyBudgetTests(unittest.TestCase):
    def test_empty_native_repertoire_delivers_first_move_before_more_exploration(self):
        session = fixture([])
        session.envelope["nativeBudgetMs"] = 10000
        now = [0.0]
        original = session.request

        def query(request):
            result = original(request)
            if request["operation"] == "preview":
                now[0] += 0.125
            result["nativeBudgetMs"] = 10000
            return result

        session.request = query
        result = run_search(session, clock=lambda: now[0])
        self.assertEqual(result["action"]["type"], "move")
        self.assertEqual(len(session.preview_actions), 1)
        evidence = result["searchBudgetEvidence"]
        self.assertTrue(evidence["movementOnly"])
        self.assertEqual(evidence["movementOnlyBudgetMs"], 100)
        self.assertIn("movement_only_budget", evidence["stopReasons"])
        self.assertNotIn("native_commit_reserve", evidence["stopReasons"])
        self.assertLess(now[0], 0.2)

    def test_unknown_spell_keeps_full_decision_budget_and_native_cast(self):
        session = fixture([dict(spellId=100, level=1)], effects={100: "damage"})
        session.envelope["nativeBudgetMs"] = 10000
        now = [0.0]
        original = session.request

        def query(request):
            result = original(request)
            if request["operation"] == "preview":
                now[0] += 0.125
            result["nativeBudgetMs"] = 10000
            return result

        session.request = query
        result = run_search(session, clock=lambda: now[0])
        self.assertFalse(result["searchBudgetEvidence"]["movementOnly"])
        self.assertNotIn(
            "movement_only_budget", result["searchBudgetEvidence"]["stopReasons"]
        )
        self.assertTrue(
            any(action["type"] == "cast" for action in session.preview_actions)
        )
        self.assertGreater(len(session.preview_actions), 1)

    def test_custom_budget_and_invalid_values_are_checked(self):
        session = fixture([])
        session.envelope["policy"]["movementOnlySearchMs"] = 300
        result = run_search(session, clock=lambda: 0.0)
        self.assertEqual(result["searchBudgetEvidence"]["movementOnlyBudgetMs"], 300)
        for value in (True, 0, -1, 10001, "100", float("inf")):
            with self.subTest(value=value):
                session = fixture([])
                session.envelope["policy"]["movementOnlySearchMs"] = value
                with self.assertRaisesRegex(ValueError, "movement-only search budget"):
                    run_search(session)
