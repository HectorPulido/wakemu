import struct
import tempfile
import unittest
from pathlib import Path
from wakfu_server.store import Store
from wakfu_server import health_store, combat_abandon
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages


class AbandonTests(unittest.TestCase):
    def setup(self, directory):
        store = Store(Path(directory) / "world.db", lambda: 1000)
        account = store.register("one", "local-password")["id"]
        gen = store.begin_session(account)
        char = store.create_character(account, "One")
        char = store.select_character(account, gen, char["id"])
        char = health_store.initialize(store, account, gen, char["id"], coefficient=0)
        fight = Fight(
            7,
            [
                Actor(char["id"], 0, (0, 0, 0), char["hp"], 6, 3, 0, account, 1, True),
                Actor(-200, 1, (1, 0, 0), 20, 4, 2, 10, 1),
            ],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(0, 0, 0)}, 1: {(1, 0, 0)}},
        )
        return store, account, gen, char, fight, RuntimeMessages(fight)

    def test_abandon_placement_waits_for_matching_callback_without_rewards(self):
        with tempfile.TemporaryDirectory() as directory:
            s, a, g, c, f, r = self.setup(directory)
            result = combat_abandon.prepare(s, a, g, c, r, b"")
            self.assertEqual([op for op, body in result["packets"]], [12238, 13420])
            self.assertEqual(result["packets"][0][1][12], 0)
            self.assertEqual(
                result["packets"][0][1][13:],
                struct.pack(">bqbqb", 1, c["id"], 1, -200, 0),
            )
            self.assertEqual((f.phase, f.winner), ("finished", None))
            self.assertFalse(
                combat_abandon.prepare(s, a, g, result["character"], r, b"")["applied"]
            )
            with self.assertRaises(ValueError):
                combat_abandon.return_to_world(
                    s, a, g, result["character"], r, struct.pack(">iB", 8, 1), wp=6
                )
            with self.assertRaises(ValueError):
                combat_abandon.return_to_world(
                    s, a, g, result["character"], r, struct.pack(">iB", 7, 2), wp=6
                )
            returned = combat_abandon.return_to_world(
                s, a, g, result["character"], r, struct.pack(">iB", 7, 1), wp=6
            )
            self.assertEqual(returned["character"]["hp"], c["hp"])
            self.assertEqual(
                [op for op, body in returned["packets"]], [13046, 13046, 13046, 12436]
            )
            self.assertFalse(
                combat_abandon.return_to_world(
                    s, a, g, returned["character"], r, struct.pack(">iB", 7, 0), wp=6
                )["applied"]
            )
            with s.connection() as db:
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM fight_rewards").fetchone()[0], 0
                )
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM fight_health_exits").fetchone()[0],
                    1,
                )

    def test_rejected_ready_without_message_runtime_can_abandon_and_return(self):
        from wakfu_server.combat_ready import prepare_ready

        with tempfile.TemporaryDirectory() as directory:
            s, a, g, c, fight, unused = self.setup(directory)

            def rejected(preview, action_id):
                raise ValueError("Unsupported HasStateFromUser actor selector")

            with self.assertRaisesRegex(ValueError, "HasStateFromUser"):
                prepare_ready(
                    fight,
                    a,
                    True,
                    initialize=rejected,
                    stats_serializer=lambda actor: b"",
                    effects_serializer=lambda: b"",
                )
            self.assertEqual(fight.phase, "placement")
            runtime = combat_abandon.placement_runtime(fight, None)
            done = combat_abandon.prepare(s, a, g, c, runtime, b"")
            delivery = runtime.prepare_delivery(done["packets"])
            self.assertEqual([op for op, _ in delivery], [12238, 13420])
            self.assertEqual(fight.phase, "finished")
            returned = combat_abandon.return_to_world(
                s,
                a,
                g,
                done["character"],
                runtime,
                struct.pack(">iB", fight.id, 1),
                wp=6,
            )
            self.assertTrue(returned["applied"])
            self.assertTrue(runtime.abandon_returned)
            self.assertEqual(returned["character"]["hp"], c["hp"])

    def test_runtime_recovery_does_not_replace_active_counters_or_accept_foreign_fight(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            s, a, g, c, fight, runtime = self.setup(directory)
            runtime.native_action_id = 37
            self.assertIs(combat_abandon.placement_runtime(fight, runtime), runtime)
            self.assertEqual(runtime.native_action_id, 37)
            with self.assertRaisesRegex(ValueError, "disagrees"):
                combat_abandon.placement_runtime(object(), runtime)
            fight.ready(a)
            with self.assertRaisesRegex(ValueError, "outside placement"):
                combat_abandon.placement_runtime(fight, None)
            with self.assertRaisesRegex(ValueError, "outside placement"):
                combat_abandon.placement_runtime(None, None)

    def test_legacy_client_win_presentation_still_returns_owned_abort(self):
        # Clients already cleaned by the old reversed lists legitimately send
        # huO=false. Outcome remains an abort, never a rewarded victory.
        with tempfile.TemporaryDirectory() as directory:
            s, a, g, c, f, r = self.setup(directory)
            prepared = combat_abandon.prepare(s, a, g, c, r, b"")
            returned = combat_abandon.return_to_world(
                s, a, g, prepared["character"], r, struct.pack(">iB", f.id, 0), wp=6
            )
            self.assertTrue(returned["applied"])
            self.assertEqual((f.phase, f.winner), ("finished", None))
            self.assertTrue(r.abandon_returned)
            with s.connection() as db:
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM fight_rewards").fetchone()[0], 0
                )
            with self.assertRaises(ValueError):
                combat_abandon.return_to_world(
                    s, a + 1, g, c, r, struct.pack(">iB", f.id, 0), wp=6
                )

    def test_active_damage_survives_abort_and_invalid_request_is_nonmutating(self):
        with tempfile.TemporaryDirectory() as directory:
            s, a, g, c, f, r = self.setup(directory)
            f.ready(a)
            f.actors[c["id"]].hp -= 5
            r.awaiting_ack = 1
            r.pending = [(1, b"pending")]
            with self.assertRaises(ValueError):
                combat_abandon.prepare(s, a, g, c, r, b"\0")
            self.assertEqual(f.phase, "active")
            self.assertEqual(r.awaiting_ack, 1)
            done = combat_abandon.prepare(s, a, g, c, r, b"")
            self.assertEqual(done["character"]["hp"], c["hp"] - 5)
            self.assertIsNone(r.awaiting_ack)
            self.assertEqual(r.pending, [])

    def test_stale_owner_cannot_mutate_fsm_or_health(self):
        with tempfile.TemporaryDirectory() as directory:
            s, a, g, c, f, r = self.setup(directory)
            s.begin_session(a)
            with self.assertRaises(ValueError):
                combat_abandon.prepare(s, a, g, c, r, b"")
            self.assertEqual(f.phase, "placement")
            self.assertEqual(r.action_id, 0)
