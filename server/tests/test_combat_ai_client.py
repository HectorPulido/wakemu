import unittest
from unittest.mock import patch
from tests.test_combat_ai import AITests
from wakfu_server.combat_ai import snapshot, validate, plan


class AIClientTests(unittest.TestCase):
    def test_rejects_stale_response_and_occupied_or_over_budget_paths(self):
        fight = AITests().fight()
        request = snapshot(fight, -2)
        response = dict(
            protocol=1,
            requestId=request["requestId"],
            stateKey=request["stateKey"],
            decision=dict(actor_id=-2, target_id=1, path=[[1, 0, 0]], attack=None),
        )
        self.assertEqual(validate(fight, -2, request, response)["path"], [(1, 0, 0)])
        with self.assertRaises(ValueError):
            validate(fight, -2, request, {**response, "requestId": "old"})
        for path in ([[5, 0, 0]], [[1, 0, 0], [2, 0, 0], [3, 0, 0], [4, 0, 0]]):
            with self.assertRaises(ValueError):
                validate(
                    fight,
                    -2,
                    request,
                    {**response, "decision": {**response["decision"], "path": path}},
                )

    def test_unavailable_service_cannot_invent_movement(self):
        with patch(
            "wakfu_server.combat_ai.urllib.request.urlopen",
            side_effect=OSError("offline"),
        ):
            response = plan(AITests().fight(), -2)
        self.assertEqual(response["path"], [])
        self.assertIn("unavailable", response["reason"])
