import struct, unittest
from unittest.mock import patch
from protocol_codec import Reader
from wakfu_server.monsters import owned_instance
from wakfu_server.combat_monster_world import spawn_monster, world_actor


class MonsterWorldTests(unittest.TestCase):
    def test_world_spawn_r_e_carries_each_native_direction(self):
        from protocol_codec import Reader

        npc = owned_instance(5525, 1, -200, map_id=1134, x=-10, y=-2, z=-1)
        for direction in range(8):
            with self.subTest(direction=direction):
                body = world_actor(npc, group_id=200, direction=direction)
                reader = Reader(body)
                self.assertEqual(reader.number("B"), 11)
                reader.number("q")
                reader.number("B")
                reader.number("q")
                reader.text("H")
                reader.number("h")
                x, y, z, map_id, encoded_direction, present = (
                    reader.number(kind) for kind in ("i", "i", "h", "q", "B", "B")
                )
                self.assertEqual(
                    (-10, -2, -1, 1134, direction, 0),
                    (x, y, z, map_id, encoded_direction, present),
                )
                reader.take(len(body) - reader.pos)
                reader.finish()

        for invalid in (True, -1, 8):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                world_actor(npc, group_id=200, direction=invalid)

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

    def test_mixed_group_resolves_individual_names_and_preserves_full_roster(self):
        from wakfu_server.combat_monster_world import spawn_group
        from wakfu_server.monsters import reference

        members = [
            owned_instance(
                ref,
                reference(ref)["min_level"],
                identity,
                map_id=1134,
                x=-7,
                y=-7,
                z=-1,
            )
            for ref, identity in ((5525, -200), (4168, -201))
        ]
        expected_roster = [(m["ref"], m["level"]) for m in members]
        # Repeated publication models join/return/respawn: names must not depend
        # on a previous serialization or on the leader's reference.
        for _ in range(2):
            r = Reader(spawn_group(members, group_id=200))
            self.assertEqual((r.number("B"), r.number("B")), (0, 2))
            for member, expected_name in zip(members, ("Wonejo", "Dragonito vivaz")):
                self.assertEqual((r.number("B"), r.number("q")), (1, member["id"]))
                e = Reader(r.take(r.number("H")))
                self.assertEqual(
                    (e.number("B"), e.number("q"), e.number("B"), e.number("q")),
                    (11, member["id"], 1, -1),
                )
                self.assertEqual(
                    (e.text("H"), e.number("h")), (expected_name, member["ref"])
                )
                e.take(20 + 5 + 11 + 1)
                self.assertEqual((e.number("q"), e.number("H")), (200, 2))
                self.assertEqual(
                    [(e.number("h"), e.number("h")) for _ in members], expected_roster
                )
            r.finish()

    def test_missing_name_is_not_replaced_with_debug_label_and_group_not_registered(
        self,
    ):
        from wakfu_server.combat_groups import Groups

        npc = owned_instance(5525, 1, -200, map_id=1134, x=-7, y=-7, z=-1)
        groups = Groups()
        with patch(
            "wakfu_server.combat_monster_world.reference", return_value={"name": ""}
        ):
            with self.assertRaises(ValueError):
                groups.register(1134, 0, 200, [npc])
        self.assertEqual(groups.available(1134, 0), [])
