"""A lethal controlled summon action waits for every owner, but no spectator."""
import struct
import unittest

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_shared import Registry, Session
from wakfu_server.combat_runtime_messages import RuntimeMessages


class DefeatedTurnAckMultiOwnerTests(unittest.TestCase):
    def test_dead_summon_transition_requires_each_owner_not_spectator_or_actor(self):
        owner_one = Session(1, 10, "owner-one", 1134, 0)
        owner_two = Session(2, 20, "owner-two", 1134, 0)
        spectator = Session(3, 30, "spectator", 1134, 0)
        live = {owner_one, owner_two, spectator}
        registry = Registry(lambda session: session in live)
        fight = Fight(
            99,
            [
                Actor(10, 0, (0, 0, 0), 60, 6, 3, 100, 1, 1, True),
                Actor(115, 0, (1, 0, 0), 20, 6, 3, 90, 1, 1, True),
                Actor(-200, 1, (4, 0, 0), 20, 4, 2, 1, 1),
            ],
            {(x, 0, 0) for x in range(5)},
            {0: {(0, 0, 0), (1, 0, 0), (2, 0, 0)}, 1: {(4, 0, 0)}},
        )
        runtime = RuntimeMessages(fight)
        shared = registry.register(fight, owner_one, runtime=runtime)
        registry.join(
            owner_two,
            struct.pack(">qB", 10, 0),
            Actor(20, 0, (2, 0, 0), 60, 6, 3, 80, 1, 2, True),
            actor_payload=lambda *_args: (b"stats", b"effects"),
            bootstrap_packets=lambda *_args: [],
        )
        fight = shared.fight
        fight.ready(1)
        fight.ready(2)
        fight.order = [115, -200, 10, 20]
        fight.turn_index = 0
        fight.turn_id = 1
        fight.actors[115].turn_count = 1
        # Spectators never enter the participant membership used by the ACK
        # barrier. The second owner is joined through the normal registry path.

        def acknowledge(session, turn):
            return registry.acknowledge(
                fight.id,
                session,
                struct.pack(">i", turn),
                lambda current, current_runtime, body: current_runtime.acknowledge_turn(
                    body
                ),
            )

        registry.execute(
            fight.id,
            owner_one,
            115,
            lambda candidate, current_runtime: (
                candidate.apply_damage(115, 115, 20),
                [(12727, b"lethal-current-summon")],
            )[1],
        )
        self.assertEqual(shared.fight.current.id, -200)
        self.assertEqual(shared.ack.turn, 1)
        self.assertEqual(set(shared.ack.expected), {1, 2})
        self.assertNotIn(spectator.account_id, shared.ack.expected)
        self.assertNotIn(115, shared.ack.expected)

        # A stale counter cannot advance AI, and one owner's valid ACK is not
        # enough to release the other connected owner's presentation barrier.
        with self.assertRaisesRegex(ValueError, "Invalid/stale shared turn ACK"):
            acknowledge(owner_one, 2)
        self.assertFalse(acknowledge(owner_one, 1))
        with self.assertRaisesRegex(ValueError, "Session does not own"):
            acknowledge(spectator, 1)
        self.assertEqual(shared.fight.current.id, -200)
        self.assertTrue(acknowledge(owner_two, 1))

        registry.execute_server(
            fight.id,
            -200,
            lambda candidate, current_runtime: current_runtime.end_server_turn(
                -200, candidate.turn_id
            ),
            expected_sequence=shared.sequence,
        )
        self.assertEqual(shared.ack.turn, 2)
        self.assertEqual(set(shared.ack.expected), {1, 2})
        self.assertFalse(acknowledge(owner_two, 2))
        self.assertTrue(acknowledge(owner_one, 2))
        self.assertEqual(shared.fight.current.id, 10)


if __name__ == "__main__":
    unittest.main()
