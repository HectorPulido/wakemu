import copy
import unittest

import test_combat_tactical_ai as original
from wakfu_server.combat_tactical_ai import Preview

from wakfu_server import combat_tactical_ai as module


class ForecastOverlapTests(unittest.TestCase):
    def request(self, dead=False, root_overlap=False):
        runtime, _ = original.TacticalBridgeTests().make_runtime()
        if root_overlap:
            runtime.fight.actors[7].position = runtime.fight.current.position
        before = original.fight_snapshot(runtime.fight)
        identities = dict(runtime.fight.actors)

        class Provider(original.FakeNativeProvider):
            def actions(self, fight):
                yield {"type": "cast", "spellId": 5815, "target": [4, 0, 0]}
                yield from super().actions(fight)

            def preview(self, fight, action, action_id, *, forecast):
                if action["type"] != "cast":
                    return super().preview(fight, action, action_id, forecast=forecast)
                summon = copy.deepcopy(fight.actors[7])
                summon.id = 3
                summon.hp = 0 if dead else summon.hp
                fight.actors[3] = summon
                return Preview(fight, ())

        result = module.build_request(runtime, Provider(), max_previews=2, depth=1)
        self.assertEqual(original.fight_snapshot(runtime.fight), before)
        self.assertTrue(
            all(runtime.fight.actors[k] is v for k, v in identities.items())
        )
        return result

    def test_occupied_summon_candidate_rejected_valid_movement_preserved(self):
        request = self.request()
        root = next(s for s in request["states"] if s["key"] == request["rootState"])
        self.assertEqual([t["action"]["type"] for t in root["transitions"]], ["move"])
        self.assertEqual(len(request["states"]), 2)

    def test_outside_arena_summon_candidate_does_not_poison_valid_movement(self):
        runtime, _ = original.TacticalBridgeTests().make_runtime()
        before = original.fight_snapshot(runtime.fight)

        class Provider(original.FakeNativeProvider):
            def actions(self, fight):
                yield {"type": "cast", "spellId": 2923, "target": [0, 0, 0]}
                yield from super().actions(fight)

            def preview(self, fight, action, action_id, *, forecast):
                if action["type"] != "cast":
                    return super().preview(fight, action, action_id, forecast=forecast)
                summon = copy.deepcopy(fight.actors[7])
                summon.id = 17
                summon.position = (-17, -14, 1)
                fight.actors[17] = summon
                return Preview(fight, ())

        request = module.build_request(runtime, Provider(), max_previews=2, depth=1)
        root = next(s for s in request["states"] if s["key"] == request["rootState"])
        self.assertEqual([t["action"]["type"] for t in root["transitions"]], ["move"])
        self.assertEqual(original.fight_snapshot(runtime.fight), before)
        self.assertEqual(len(request["states"]), 2)

    def test_dead_actor_overlap_remains_allowed(self):
        request = self.request(dead=True)
        root = next(s for s in request["states"] if s["key"] == request["rootState"])
        self.assertEqual(len(root["transitions"]), 2)

    def test_invalid_root_still_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Living forecast actors overlap"):
            self.request(root_overlap=True)


if __name__ == "__main__":
    unittest.main()
