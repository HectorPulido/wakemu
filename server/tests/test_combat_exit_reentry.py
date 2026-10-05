"""Serving helpers over isolated SQLite: exits cannot poison the next Ready."""
import struct
import tempfile
import unittest
import test_combat_abandon as abandon_fixture
import test_combat_rewards as reward_fixture
from wakfu_server import combat_abandon
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_lifecycle import prepare_finish, return_to_world
from wakfu_server.combat_rewards import Policy
from wakfu_server import health_store


def fresh_ready(character, account, identity):
    cells = {(0, 0, 0), (1, 0, 0)}
    fight = Fight(
        identity,
        [
            Actor(
                character["id"],
                0,
                (0, 0, 0),
                character["hp"],
                6,
                3,
                0,
                account,
                1,
                True,
            ),
            Actor(-200, 1, (1, 0, 0), 20, 4, 2, 10, 1),
        ],
        cells,
        {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
    )
    # This test isolates serving transitions, not a breed initialization audit.
    preview, runtime, packets = prepare_ready(
        fight,
        account,
        True,
        initialize=lambda preview, action: (preview, ()),
        stats_serializer=lambda actor: b"",
        effects_serializer=lambda: b"\0\0",
    )
    return fight, preview, runtime, packets


class ExitReentryTests(unittest.TestCase):
    def test_active_abort_return_and_new_ready_preserve_own_damage(self):
        with tempfile.TemporaryDirectory() as directory:
            (
                store,
                account,
                generation,
                char,
                fight,
                runtime,
            ) = abandon_fixture.AbandonTests().setup(directory)
            fight.ready(account)
            fight.actors[char["id"]].hp -= 5
            runtime.awaiting_ack = 1
            runtime.pending = [(1, b"old pending")]
            aborted = combat_abandon.prepare(
                store, account, generation, char, runtime, b""
            )
            returned = combat_abandon.return_to_world(
                store,
                account,
                generation,
                aborted["character"],
                runtime,
                struct.pack(">iB", fight.id, 1),
                wp=6,
            )
            self.assertEqual(returned["character"]["hp"], char["hp"] - 5)
            source, next_fight, next_runtime, packets = fresh_ready(
                returned["character"], account, fight.id + 1
            )
            self.assertEqual(
                (source.phase, next_fight.phase, fight.phase),
                ("placement", "active", "finished"),
            )
            self.assertEqual(next_fight.actors[char["id"]].hp, char["hp"] - 5)
            self.assertIsNone(next_runtime.awaiting_ack)
            self.assertFalse(hasattr(next_runtime, "abandon_owner"))
            self.assertEqual([op for op, _ in packets].count(12514), 1)
            self.assertEqual(runtime.pending, [])

    def test_victory_return_and_new_ready_do_not_reuse_finished_fsm(self):
        with tempfile.TemporaryDirectory() as directory:
            (
                store,
                account,
                char,
                generation,
                fight,
            ) = reward_fixture.RewardTests().setup_state(directory)
            char = health_store.initialize(
                store, account, generation, char["id"], coefficient=0
            )
            from wakfu_server.combat_runtime_messages import RuntimeMessages

            runtime = RuntimeMessages(fight)
            fight.actors[char["id"]].hp = char["hp"]
            fight.actors[char["id"]].max_hp = char["max_hp"]
            metadata = {
                char["id"]: dict(
                    kind="player",
                    account_id=account,
                    name=char["name"],
                    breed=char["breed"],
                    is_male=True,
                ),
                -200: dict(kind="monster", ref=5525),
            }
            done = prepare_finish(
                store,
                account,
                generation,
                char,
                runtime,
                metadata,
                duration_ms=1000,
                fight_instance_id=8,
                policy=Policy(),
            )
            result = return_to_world(
                store,
                account,
                generation,
                done["character"],
                runtime,
                struct.pack(">iB", fight.id, 0),
                wp=6,
            )
            source, next_fight, next_runtime, packets = fresh_ready(
                result["character"], account, fight.id + 1
            )
            self.assertEqual(
                (fight.phase, source.phase, next_fight.phase),
                ("finished", "placement", "active"),
            )
            self.assertEqual(
                next_fight.actors[char["id"]].hp, result["character"]["hp"]
            )
            self.assertEqual(next_fight.ready_owners, {account})
            self.assertFalse(hasattr(next_runtime, "abandon_owner"))
