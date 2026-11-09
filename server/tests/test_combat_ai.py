import unittest
from wakfu_server.combat_ai import snapshot, validate
from wakfu_server.combat_state import Actor, Fight


class AITests(unittest.TestCase):
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
        fight.phase, fight.order, fight.turn_index = "active", [npc.id, pc.id], 0
        return fight

    def test_snapshot_requires_edges_and_preserves_only_verified_edges(self):
        fight = self.fight()
        fight.edges.remove(((2, 0, 0), (3, 0, 0)))
        request = snapshot(fight, -2)
        self.assertNotIn([[2, 0, 0], [3, 0, 0]], request["edges"])
        fight.edges = None
        with self.assertRaises(ValueError):
            snapshot(fight, -2)

    def test_snapshot_rejects_controlled_actor(self):
        fight = self.fight()
        fight.actors[-2].controlled = True
        with self.assertRaises(ValueError):
            snapshot(fight, -2)

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
