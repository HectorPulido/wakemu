"""Certified lifecycle risk survives exhaustion of optional rival search time."""
import unittest

from test_query_threat import AI_ID, FakeProvider, run_forecast


class NativeRiskProjectionTests(unittest.TestCase):
    def test_projection_damage_survives_deadline_without_claiming_complete(self):
        provider = FakeProvider()
        original_query = provider.query
        elapsed = [0.0]
        operations = []

        def query(request):
            operations.append(request["operation"])
            answer = original_query(request)
            if request["operation"] == "project_turn":
                next(a for a in answer["result"]["actors"] if a["id"] == AI_ID)[
                    "hp"
                ] -= 7
                elapsed[0] = 2.0
            return answer

        provider.query = query
        result = run_forecast(provider, deadline=1.0, clock=lambda: elapsed[0])
        self.assertEqual(operations, ["project_turn"])
        self.assertEqual(result["knownLowerBound"], 7)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["risk"])
        self.assertIn("rival_search_deadline_reached", result["unknownDependencies"])
        self.assertEqual(provider.state["actors"][0]["hp"], 30)

    def test_projection_missing_existing_actor_is_rejected(self):
        provider = FakeProvider()
        original_query = provider.query

        def query(request):
            answer = original_query(request)
            if request["operation"] == "project_turn":
                answer["result"]["actors"] = [
                    actor
                    for actor in answer["result"]["actors"]
                    if actor["id"] != AI_ID
                ]
            return answer

        provider.query = query
        with self.assertRaisesRegex(ValueError, "projection omitted existing actor"):
            run_forecast(provider)

    def test_primary_enemy_projects_before_lower_id_construct_and_all_remain_unknown(
        self,
    ):
        provider = FakeProvider(rivals=(3, 9))
        next(actor for actor in provider.state["actors"] if actor["id"] == 3)[
            "registeredSummon"
        ] = True
        original_query = provider.query
        elapsed = [0.0]
        projected = []

        def query(request):
            if request["operation"] == "project_turn":
                projected.append(request["actorId"])
                elapsed[0] = 2.0
            return original_query(request)

        provider.query = query
        result = run_forecast(provider, deadline=1.0, clock=lambda: elapsed[0])
        self.assertEqual(projected, [9])
        self.assertEqual([rival["actorId"] for rival in result["rivals"]], [9, 3])
        self.assertFalse(result["complete"])
        self.assertTrue(all(not rival["complete"] for rival in result["rivals"]))
        self.assertEqual(result["knownLowerBound"], 0)


if __name__ == "__main__":
    unittest.main()
