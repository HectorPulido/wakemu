import tempfile, unittest
from tests import test_combat_rewards
from wakfu_server import health_store
from wakfu_server.combat_health import persist, persist_aborted_fight


class FightExitHealthTests(unittest.TestCase):
    def state(self, directory):
        (
            store,
            account,
            char,
            generation,
            fight,
        ) = test_combat_rewards.RewardTests().setup_state(directory)
        char = health_store.initialize(
            store, account, generation, char["id"], coefficient=0
        )
        actor = fight.actors[char["id"]]
        actor.hp = char["hp"] - 9
        actor.max_hp = char["max_hp"]
        return store, account, char, generation, fight

    def test_disconnect_persists_damage_without_rewards_and_duplicate_keeps_world_updates(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            s, a, c, g, f = self.state(directory)
            f.phase = "active"
            f.winner = None
            result = persist_aborted_fight(s, a, g, c, f)
            self.assertTrue(result["applied"])
            self.assertEqual(result["character"]["hp"], f.actors[c["id"]].hp)
            self.assertEqual(
                (result["character"]["xp"], result["character"]["kamas"]), (c["xp"], 0)
            )
            self.assertEqual(f.phase, "active")
            with s.connection() as db:
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM fight_rewards").fetchone()[0], 0
                )
                db.execute("UPDATE characters SET hp=hp+1,x=44 WHERE id=?", (c["id"],))
                baseline = db.execute(
                    "SELECT started_ms FROM character_regeneration"
                ).fetchone()[0]
            s.clock = lambda: 1001
            again = persist_aborted_fight(s, a, g, c, f)
            self.assertFalse(again["applied"])
            self.assertEqual(again["character"]["x"], 44)
            self.assertEqual(again["character"]["hp"], result["character"]["hp"] + 1)
            with s.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT started_ms FROM character_regeneration"
                    ).fetchone()[0],
                    baseline,
                )

    def test_replaced_lease_and_stale_health_do_not_overwrite_new_state(self):
        with tempfile.TemporaryDirectory() as directory:
            s, a, c, g, f = self.state(directory)
            with s.connection() as db:
                db.execute("UPDATE characters SET hp=hp-1 WHERE id=?", (c["id"],))
            self.assertIsNone(persist_aborted_fight(s, a, g, c, f))
            new = s.begin_session(a)
            s.select_character(a, new, c["id"])
            self.assertIsNone(persist_aborted_fight(s, a, g, c, f))
            self.assertEqual(s.character(a, c["id"])["hp"], c["hp"] - 1)
            with s.connection() as db:
                self.assertEqual(
                    db.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE name='fight_health_exits'"
                    ).fetchone()[0],
                    0,
                )

    def test_duplicate_return_does_not_reset_health_or_create_another_award(self):
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_lifecycle import return_to_world
        import struct

        with tempfile.TemporaryDirectory() as directory:
            s, a, c, g, f = self.state(directory)
            runtime = RuntimeMessages(f)
            body = struct.pack(">iB", f.id, 0)
            first = return_to_world(s, a, g, c, runtime, body, wp=6)
            self.assertTrue(first["applied"])
            again = return_to_world(s, a, g, c, runtime, body, wp=6)
            self.assertFalse(again["applied"])
            self.assertEqual(again["packets"], [])
            self.assertEqual(again["character"], first["character"])

    def test_defeat_persists_zero_hp_without_implicit_regeneration_or_rewards(self):
        with tempfile.TemporaryDirectory() as directory:
            s, a, c, g, f = self.state(directory)
            f.actors[c["id"]].hp = 0
            f.winner = 1
            result = persist(s, a, g, c, f)
            self.assertEqual((result["character"]["hp"], result["coefficient"]), (0, 0))
            reopened = health_store.initialize(s, a, g, c["id"], coefficient=1)
            self.assertEqual(reopened["hp"], 0)
            s.clock = lambda: 1005
            current = health_store.tick(s, a, g, c["id"], 0)
            self.assertEqual(current["hp"], 0)
            self.assertEqual((current["xp"], current["kamas"]), (c["xp"], 0))
            with s.connection() as db:
                self.assertEqual(
                    db.execute("SELECT COUNT(*) FROM fight_rewards").fetchone()[0], 0
                )
