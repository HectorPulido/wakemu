import struct, unittest
from protocol_codec import Reader
from wakfu_server.monsters import owned_instance
from wakfu_server.combat_monster_world import spawn_monster, world_actor


class MonsterWorldTests(unittest.TestCase):
    def test_console_large_identities_survive_native_wire_fields(self):
        # Actual !mob identities reported by the current client inspector. This
        # protects the i64 contract; it does not claim that UI picking succeeds.
        from wakfu_server.combat_monster_world import spawn_group

        for group_id in (2532662579537660980, 4498523304664558568):
            npc = owned_instance(5525, 1, -group_id, map_id=1134, x=-10, y=-2, z=-1)
            r = Reader(spawn_group([npc], group_id=group_id))
            self.assertEqual(
                (r.number("B"), r.number("B"), r.number("B"), r.number("q")),
                (0, 1, 1, -group_id),
            )
            e = Reader(r.take(r.number("H")))
            r.finish()
            self.assertEqual(
                (e.number("B"), e.number("q"), e.number("B"), e.number("q")),
                (11, -group_id, 1, -1),
            )
            e.text("H")
            e.number("h")
            e.take(20)
            e.take(5)
            e.take(11)
            e.take(1)
            self.assertEqual(e.number("q"), group_id)
            self.assertEqual(e.number("H"), 1)
            self.assertEqual((e.number("h"), e.number("h")), (5525, 1))

    def test_spawn_has_own_npc_identity_name_and_ref(self):
        npc = owned_instance(5525, 1, -200, map_id=1134, x=-7, y=-7, z=-1)
        body = spawn_monster(npc, group_id=200, name="Monstruo local")
        r = Reader(body)
        self.assertEqual(
            (r.number("B"), r.number("B"), r.number("B"), r.number("q")),
            (0, 1, 1, -200),
        )
        blob = r.take(r.number("H"))
        r.finish()
        e = Reader(blob)
        self.assertEqual(
            (e.number("B"), e.number("q"), e.number("B"), e.number("q")),
            (11, -200, 1, -1),
        )
        self.assertEqual((e.text("H"), e.number("h")), ("Monstruo local", 5525))
        self.assertEqual(
            tuple(e.number(t) for t in ("i", "i", "h", "q", "B", "B")),
            (-7, -7, -1, 1134, 3, 0),
        )
        self.assertEqual(e.number("B"), 1)
        self.assertEqual(len(blob), 114)
        with self.assertRaises(ValueError):
            world_actor({**npc, "ref": 999999}, group_id=200)
        with self.assertRaises(ValueError):
            world_actor({**npc, "hp": 999}, group_id=200)
        with self.assertRaises(ValueError):
            world_actor(npc, group_id=0)
