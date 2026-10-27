"""Late real recovery requests after terminal birth staging keep normal returns."""
from copy import deepcopy
import struct
import unittest
from test_combat_shared_timeline_recovery import SharedTimelineRecoveryTests
from wakfu_server.combat_session_adapter import CombatSessionAdapter
from wakfu_server.combat_reconnect_birth_stage import (
    BirthPresentation,
    PendingBirthPresentation,
)
from wakfu_server.combat_recovery import recovery_packet


class ReconnectTerminalAdapterTests(unittest.TestCase):
    def test_terminal_then_late_native_recovery_and_ack_allow_all_owner_returns(self):
        registry, shared, owners, _, live = SharedTimelineRecoveryTests().state()

        class Store:
            def current_character_session(self, account, generation, character):
                return any(
                    (s.account_id, s.generation, s.character_id)
                    == (account, generation, character)
                    for s in live
                )

        adapter = CombatSessionAdapter(Store())
        adapter.registry = registry
        owner = owners[0]
        counter = shared.fight.turn_id
        original = (
            (12502, struct.pack(">iiiqii", 377, 77, -1, owner.character_id, -1, 0)),
            (13420, struct.pack(">i", 377)),
        )
        tail = recovery_packet(shared.fight, struct.pack(">i", 377), deadline_ms=20000)
        presentation = BirthPresentation(counter, (1205,), (tail,), original, False)
        shared.reconnect_presentations[
            owner.account_id
        ] = PendingBirthPresentation.bind(owner, presentation)
        # The native prefix is already on this transport. A real terminal event
        # wins the race before its aUM sends13332 followed by13510.
        shared.fight.apply_effect_damage(25, -200, 1000)
        self.assertEqual(shared.fight.phase, "finished")
        adapter.publish(owners[1], 377, ((13579, b"terminal-presentation"),))
        self.assertNotIn(owner.account_id, shared.reconnect_presentations)
        before = deepcopy(shared.ack.__dict__)
        self.assertFalse(
            adapter.recover_timeline(owner, 377, struct.pack(">i", 377), now_ms=20000)
        )
        self.assertFalse(
            adapter.acknowledge(
                owner,
                377,
                struct.pack(">i", counter),
                lambda *args: self.fail("late private ACK released a terminal turn"),
            )
        )
        self.assertEqual(shared.ack.__dict__, before)
        self.assertEqual(shared.fight.phase, "finished")
        self.assertNotIn(
            12053,
            [op for batch in adapter.drain(owner, 377) for op, _ in batch.packets],
        )
        # The ordinary settlement hook represents its existing durable owner
        # transaction; this test owns only dispatch and Registry retirement.
        self.assertTrue(
            adapter.settle_finished(
                owner,
                377,
                lambda state: {
                    s.account_id: ((13579, b"owned-result"),) for s in owners
                },
            )
        )
        for index, session in enumerate(owners):
            self.assertEqual(
                adapter.mark_returned(session, 377), index == len(owners) - 1
            )
            self.assertIsNone(adapter.lookup_character(session.character_id))
            selected = adapter.session(
                session.account_id,
                session.generation,
                dict(id=session.character_id, map_id=1134, instance_id=0),
            )
            self.assertEqual(selected, session)
        with self.assertRaisesRegex(ValueError, "Unknown shared fight"):
            registry.lookup(377)
        self.assertFalse(registry.by_character)
        self.assertFalse(registry.by_actor)


if __name__ == "__main__":
    unittest.main()
