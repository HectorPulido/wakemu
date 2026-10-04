from pathlib import Path
import tempfile
import unittest
from wakfu_server.store import Store
from wakfu_server.position_buffer import Positions


class PositionBufferTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.now = 1000
        self.store = Store(Path(self.tmp.name) / "world.db", lambda: self.now)
        self.live = set()
        self.buffer = Positions(
            self.store, lease_active=lambda a, g, c: (a, g, c) in self.live
        )

    def tearDown(self):
        self.tmp.cleanup()

    def attach(self, name):
        account = self.store.register(name, "local-password")["id"]
        generation = self.store.begin_session(account)
        char = self.store.create_character(account, name)
        char = self.store.select_character(account, generation, char["id"])
        self.live.add((account, generation, char["id"]))
        self.buffer.attach(account, generation, char)
        return account, generation, char

    def test_many_moves_one_batch_and_exact_final_position(self):
        a, g, c = self.attach("One")
        original = dict(c)
        for i in range(100):
            end = {k: c[k] for k in ("x", "y", "z")}
            end["x"] += 1
            c = self.buffer.move(a, g, c["id"], c, end)
        self.assertEqual(self.store.character(a, c["id"])["x"], original["x"])
        self.assertEqual(self.buffer.flush(), 1)
        self.assertEqual(self.store.character(a, c["id"])["x"], c["x"])
        self.assertEqual(self.buffer.flush(), 0)
        self.buffer.release(a, g, c["id"])

    def test_stale_generation_cannot_write_or_erase_replacement(self):
        a, g, c = self.attach("One")
        end = {k: c[k] for k in ("x", "y", "z")}
        end["x"] += 1
        self.buffer.move(a, g, c["id"], c, end)
        self.store.begin_session(a)
        self.assertEqual(self.buffer.flush(), 0)
        self.assertEqual(self.buffer.evictions, [(a, g, c["id"])])
        self.assertEqual(self.store.character(a, c["id"])["x"], c["x"])
        self.live.remove((a, g, c["id"]))
        self.buffer.release(a, g, c["id"], discard_stale=True)

    def test_batch_conflict_rolls_back_other_character_and_keeps_pending(self):
        a, g, c = self.attach("One")
        b, h, d = self.attach("Two")
        for account, gen, char in ((a, g, c), (b, h, d)):
            self.buffer.move(
                account,
                gen,
                char["id"],
                char,
                {**{k: char[k] for k in ("x", "y", "z")}, "x": char["x"] + 1},
            )
        self.store.move(
            b, h, d["id"], d, {**{k: d[k] for k in ("x", "y", "z")}, "y": d["y"] + 1}
        )
        with self.assertRaisesRegex(ValueError, "CAS conflict"):
            self.buffer.flush()
        self.assertEqual(self.store.character(a, c["id"])["x"], c["x"])
        self.assertTrue(all(e["dirty"] for e in self.buffer.entries.values()))
        self.assertEqual(self.buffer.flush(account_id=a, generation=g), 1)

    def test_transition_barrier_and_health_merge_preserve_authoritative_position(self):
        a, g, c = self.attach("One")
        end = {k: c[k] for k in ("x", "y", "z")}
        end["x"] += 1
        current = self.buffer.move(a, g, c["id"], c, end)
        refreshed = {**c, "hp": 1}
        current = self.buffer.merge(a, g, refreshed)
        self.assertEqual(current["x"], end["x"])
        self.assertEqual(current["hp"], 1)
        destination = {k: current[k] for k in ("map_id", "instance_id", "x", "y", "z")}
        destination["map_id"] = 527
        with self.assertRaises(ValueError):
            self.store.transition_map(a, g, c["id"], current, destination)
        self.buffer.flush(account_id=a, generation=g, character_id=c["id"])
        moved = self.store.transition_map(a, g, c["id"], current, destination)
        self.buffer.release(a, g, c["id"])
        self.buffer.attach(a, g, moved)
        self.assertEqual(moved["map_id"], 527)

    def test_stale_account_does_not_poison_other_accounts_batch(self):
        a, g, c = self.attach("One")
        b, h, d = self.attach("Two")
        for account, gen, char in ((a, g, c), (b, h, d)):
            self.buffer.move(
                account,
                gen,
                char["id"],
                char,
                {**{k: char[k] for k in ("x", "y", "z")}, "x": char["x"] + 1},
            )
        self.store.begin_session(a)
        self.assertEqual(self.buffer.flush(), 1)
        self.assertEqual(self.store.character(b, d["id"])["x"], d["x"] + 1)
        self.assertEqual(self.store.character(a, c["id"])["x"], c["x"])
        self.assertEqual(self.buffer.evictions, [(a, g, c["id"])])

    def test_own_bag_session_keeps_outside_position_durable(self):
        from wakfu_server.haven_bag import HavenBagSession

        a, g, c = self.attach("One")
        current = self.buffer.move(
            a, g, c["id"], c, {**{k: c[k] for k in ("x", "y", "z")}, "x": c["x"] + 1}
        )
        self.buffer.flush(account_id=a, generation=g, character_id=c["id"])
        bag = HavenBagSession(current)
        inside = dict(bag.inside)
        self.assertEqual(inside["map_id"], 9)
        self.assertEqual(self.store.character(a, c["id"])["x"], current["x"])
        self.assertEqual(bag.leave(inside)["x"], current["x"])

    def test_health_transaction_and_buffered_move_do_not_restore_old_hp(self):
        from wakfu_server import health_store

        a, g, c = self.attach("One")
        c = health_store.initialize(self.store, a, g, c["id"], coefficient=0)
        self.buffer.merge(a, g, c)
        current = self.buffer.move(
            a, g, c["id"], c, {**{k: c[k] for k in ("x", "y", "z")}, "x": c["x"] + 1}
        )
        refreshed = health_store.sync(
            self.store, a, g, c["id"], c["hp"], c["hp"] - 5, coefficient=0
        )
        current.update(hp=refreshed["hp"], max_hp=refreshed["max_hp"])
        self.buffer.merge(a, g, current)
        latest = self.buffer.move(
            a,
            g,
            c["id"],
            current,
            {**{k: current[k] for k in ("x", "y", "z")}, "x": current["x"] + 1},
        )
        self.assertEqual(latest["hp"], c["hp"] - 5)
        self.buffer.flush()
        saved = self.store.character(a, c["id"])
        self.assertEqual(saved["hp"], latest["hp"])
        self.assertEqual(saved["x"], latest["x"])
