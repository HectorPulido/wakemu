import struct
import unittest
from wakfu_server import combat_abandon
from wakfu_server.combat_spectator_events import is_normal_finish_packet


class AbortedSpectatorTerminalTests(unittest.TestCase):
    def fixture(self):
        from test_combat_pve_withdraw import WithdrawalPlanTests

        case = WithdrawalPlanTests()
        case.setUp()
        case.fight.phase = "finished"
        case.fight.winner = None
        return case.fight, case.runtime

    def test_normal_abort_codec_retains_none_outcome_and_actual_hp_without_mutation(
        self,
    ):
        fight, runtime = self.fixture()
        hp = {identity: actor.hp for identity, actor in fight.actors.items()}
        counters = runtime.action_id, runtime.native_action_id
        packets = combat_abandon.aborted_terminal_packets(fight, runtime, losing_team=0)
        self.assertTrue(is_normal_finish_packet(packets[0], fight.id))
        body = packets[0][1]
        self.assertEqual(body[12], 0)
        offset, lists = 13, []
        for _ in range(3):
            count = body[offset]
            offset += 1
            lists.append(
                tuple(
                    struct.unpack_from(">q", body, offset + index * 8)[0]
                    for index in range(count)
                )
            )
            offset += count * 8
        self.assertEqual(lists, [(10, 20), (-200,), ()])
        self.assertIsNone(fight.winner)
        self.assertEqual(
            {identity: actor.hp for identity, actor in fight.actors.items()}, hp
        )
        self.assertEqual((runtime.action_id, runtime.native_action_id), counters)

    def test_placement_abort_without_runtime_has_normal_terminal_codec(self):
        fight, _ = self.fixture()
        packets = combat_abandon.aborted_terminal_packets(fight, losing_team=0)
        self.assertTrue(is_normal_finish_packet(packets[0], fight.id))
        self.assertIsNone(fight.winner)

    def test_rejects_active_stale_or_resolved_runtime(self):
        fight, runtime = self.fixture()
        fight.phase = "active"
        with self.assertRaises(ValueError):
            combat_abandon.aborted_terminal_packets(fight, runtime, losing_team=0)
        fight.phase, fight.winner = "finished", 1
        with self.assertRaises(ValueError):
            combat_abandon.aborted_terminal_packets(fight, runtime, losing_team=0)
        fight.winner = None
        runtime.fight = object()
        with self.assertRaises(ValueError):
            combat_abandon.aborted_terminal_packets(fight, runtime, losing_team=0)
