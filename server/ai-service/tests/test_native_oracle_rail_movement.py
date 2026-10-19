"""The service oracle serializes the rail mode selected by the native FSM."""
import copy
from types import SimpleNamespace
import unittest


class NativeOracleRailMovementTests(unittest.TestCase):
    def _runtime(self, *, network=True, mixed=False):
        from test_combat_rail_movement import RailMovementTests

        runtime = RailMovementTests().actual_fight(networks=network)
        if mixed:
            from wakfu_server.combat_microbot_network import SOURCE

            runtime.fight.native_microbot_networks[7] = dict(
                source=SOURCE,
                segments=[[[0, 0, 0], [3, 0, 0]]],
                cells=[(x, 0, 0) for x in range(4)],
            )
        return runtime

    def _preview(self, runtime, path):
        from wakfu_ai.native.native_oracle import NativeOracle

        oracle = object.__new__(NativeOracle)
        oracle.flags = {"native_area_callbacks": False}
        oracle.runtime = runtime
        oracle.fork = lambda runtime=None: SimpleNamespace(
            fight=copy.deepcopy(runtime.fight),
            action_id=runtime.action_id,
            awaiting_ack=None,
            pending=[],
        )
        authority = runtime.fight.native_rail_movement_authority
        oracle.factory = lambda fight, action_id, rng: (
            SimpleNamespace(native_rail_movement_authority=authority),
            None,
        )
        return oracle.preview(
            runtime,
            {"type": "move", "path": [list(cell) for cell in path]},
            forecast=True,
        )

    def test_service_oracle_serializes_rail_ordinary_and_mixed_fsm_events(self):
        from wakfu_server.fight_checkpoint_store import snapshot

        cases = (
            (self._runtime(), [(1, 0, 0), (2, 0, 0), (3, 0, 0)], 4),
            (self._runtime(network=False), [(1, 0, 0), (2, 0, 0), (3, 0, 0)], 0),
            (self._runtime(mixed=True), [(x, 0, 0) for x in range(1, 7)], 0),
        )
        for runtime, path, expected_animation in cases:
            with self.subTest(expected_animation=expected_animation, length=len(path)):
                before = snapshot(runtime.fight)
                private, packets, _ = self._preview(runtime, path)
                self.assertEqual(packets[0][0], 13624)
                self.assertEqual(packets[0][1][21], expected_animation)
                self.assertEqual(private.fight.actors[7].position, path[-1])
                self.assertEqual(snapshot(runtime.fight), before)
