import struct, unittest
from wakfu_server.combat_actor import actor_stats, actor_effects, characteristics


class CombatActorTests(unittest.TestCase):
    def character(self):
        return dict(
            id=7,
            account_id=9,
            level=1,
            breed=8,
            hp=41,
            max_hp=60,
            x=-12,
            y=-8,
            z=-1,
            map_id=1134,
        )

    def test_actor_identity_and_live_hp_are_own(self):
        c = self.character()
        b = actor_stats(c, 123, team=1, wp=6)
        self.assertEqual(b[0], 3)
        self.assertEqual(struct.unpack(">qBqBh", b[-20:]), (7, 0, 9, 0, 1))
        self.assertEqual(struct.unpack_from(">iihqBB", b, 9), (-12, -8, -1, 1134, 0, 0))
        self.assertEqual(
            struct.unpack_from(">Biiii", characteristics(c, wp=6), 2), (1, 41, 0, 60, 0)
        )
        self.assertEqual(actor_effects(), b"\x00\x00")

    def test_invalid_actor_state_rejected(self):
        c = self.character()
        for kwargs in (
            {"fight_id": 0},
            {"fight_id": 123, "team": -1},
            {"fight_id": 123, "direction": 8},
        ):
            with self.assertRaises(ValueError):
                actor_stats(c, wp=6, **kwargs)
        c["hp"] = 61
        with self.assertRaises(ValueError):
            actor_stats(c, 123, wp=6)

    def test_current_resources_preserve_maxima_after_cast_and_movement(self):
        from types import SimpleNamespace
        from wakfu_server.combat_actor import actual_actor_stats

        actor = SimpleNamespace(
            id=7,
            controlled=True,
            hp=29,
            max_hp=60,
            ap=3,
            max_ap=6,
            mp=1,
            max_mp=3,
            initiative=0,
            team=0,
            position=(-11, -8, -1),
        )
        b = actual_actor_stats(self.character(), actor, 123, wp_current=4, wp_maximum=6)
        # format3, XP8, position20, fight10, then characteristic count2.
        stats = [struct.unpack_from(">Biiii", b, 41 + i * 17) for i in range(4)]
        self.assertEqual(
            stats,
            [(1, 29, 0, 60, 0), (2, 3, 0, 6, 0), (3, 1, 0, 3, 0), (4, 4, 0, 6, 0)],
        )
        self.assertEqual(struct.unpack_from(">iih", b, 9), (-11, -8, -1))
        with self.assertRaises(ValueError):
            actual_actor_stats(self.character(), actor, 123, wp_current=7, wp_maximum=6)

    def test_current_npc_resources_preserve_maxima(self):
        from types import SimpleNamespace
        from wakfu_server.combat_actor import actual_monster_actor_stats

        monster = dict(id=-7, ref=5525, level=1, map_id=1134)
        actor = SimpleNamespace(
            id=-7,
            controlled=False,
            hp=8,
            max_hp=20,
            ap=1,
            max_ap=3,
            mp=0,
            max_mp=3,
            initiative=0,
            team=1,
            position=(2, 0, 0),
        )
        b = actual_monster_actor_stats(monster, actor, 123, wp_current=0, wp_maximum=6)
        stats = [struct.unpack_from(">Biiii", b, 33 + i * 17) for i in range(4)]
        self.assertEqual(
            stats, [(1, 8, 0, 20, 0), (2, 1, 0, 3, 0), (3, 0, 0, 3, 0), (4, 0, 0, 6, 0)]
        )
