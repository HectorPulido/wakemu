import unittest
import threading
import os
from unittest.mock import patch
from tests.test_ai_service import service
from wakfu_ai.transport.framed_server import FramedServer
from wakfu_server.combat_ai import snapshot, validate
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_ai import plan


class AITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.channel = FramedServer(("127.0.0.1", 0))
        cls.thread = threading.Thread(target=cls.channel.serve_forever, daemon=True)
        cls.thread.start()
        cls.environment = patch.dict(
            os.environ,
            {"WAKFU_AI_URL": "tcp://127.0.0.1:" + str(cls.channel.server_address[1])},
        )
        cls.environment.start()

    @classmethod
    def tearDownClass(cls):
        cls.environment.stop()
        cls.channel.shutdown()
        cls.channel.server_close()
        cls.thread.join(2)

    def fight(self, mp=3):
        cells = {(x, 0, 0) for x in range(6)}
        edges = {
            (c, (c[0] + d, 0, 0))
            for c in cells
            for d in (-1, 1)
            if (c[0] + d, 0, 0) in cells
        }
        pc = Actor(1, 0, (5, 0, 0), 60, 6, 3, 0, 1, 1, True)
        npc = Actor(-2, 1, (0, 0, 0), 12, 6, mp, 5, 1)
        fight = Fight(1, [pc, npc], cells, {0: {pc.position}, 1: {npc.position}}, edges)
        fight.ready(1)
        return fight

    def test_approach_stops_adjacent_and_respects_mp(self):
        fight = self.fight()
        self.assertEqual(fight.current.id, -2)
        result = plan(fight, -2)
        self.assertEqual(result["path"], [(1, 0, 0), (2, 0, 0), (3, 0, 0)])
        self.assertIsNone(result["attack"])
        fight.actors[-2].position = (3, 0, 0)
        self.assertEqual(plan(fight, -2)["path"], [(4, 0, 0)])
        fight.actors[-2].position = (4, 0, 0)
        self.assertEqual(plan(fight, -2)["path"], [])

    def test_missing_edge_prevents_invented_crossing(self):
        fight = self.fight()
        fight.edges.remove(((2, 0, 0), (3, 0, 0)))
        self.assertEqual(plan(fight, -2)["path"], [])
        fight.edges = None
        with self.assertRaises(ValueError):
            plan(fight, -2)

    def test_controlled_actor_cannot_be_driven_by_server_ai(self):
        fight = self.fight()
        fight.actors[-2].controlled = True
        with self.assertRaises(ValueError):
            plan(fight, -2)

    def test_bridge_rejects_wrong_request_illegal_path_and_budget(self):
        fight = self.fight()
        request = snapshot(fight, -2)
        base = dict(
            protocol=1,
            requestId=request["requestId"],
            stateKey=request["stateKey"],
            decision=dict(
                actor_id=-2, target_id=1, path=[], attack=None, reason="test"
            ),
        )
        for response in (
            dict(base, requestId="stale-request"),
            dict(base, decision=dict(base["decision"], path=[[2, 0, 0]])),
            dict(
                base,
                decision=dict(
                    base["decision"], path=[[1, 0, 0], [2, 0, 0], [3, 0, 0], [4, 0, 0]]
                ),
            ),
            dict(base, decision=dict(base["decision"], target_id=-2)),
        ):
            with self.assertRaises(ValueError):
                validate(fight, -2, request, response)
        self.assertEqual(fight.actors[-2].position, (0, 0, 0))

    def test_service_outage_does_not_move_or_fallback_to_in_process_planner(self):
        fight = self.fight()
        with patch(
            "wakfu_server.combat_ai.urllib.request.urlopen",
            side_effect=OSError("isolated outage"),
        ):
            result = plan(fight, -2)
        self.assertEqual(result["path"], [])
        self.assertIsNone(result["target_id"])
        self.assertEqual(fight.actors[-2].position, (0, 0, 0))
