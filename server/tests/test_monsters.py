import unittest
from wakfu_server import monsters


class MonsterTests(unittest.TestCase):
    def test_reference_level_bounds_and_known_low_level_monster(self):
        ref = monsters.reference(2)
        self.assertEqual(
            (ref["min_level"], ref["max_level"], ref["sprite_id"]), (4, 8, 100200002)
        )
        for level in (3, 9):
            with self.assertRaises(ValueError):
                monsters.statistics(2, level)
        stats = monsters.statistics(2, 4)
        self.assertEqual(stats, {k: v["base"] for k, v in ref["statistics"].items()})

    def test_java_growth_uses_truncation_and_float32_not_player_curve(self):
        self.assertEqual(monsters._java_double_to_int(-1.9), -1)
        self.assertEqual(monsters._java_double_to_int(1.9), 1)
        ref = next(
            r
            for r in monsters.REFERENCES.values()
            if r["max_level"] > r["min_level"]
            and r["statistics"]["HP"]["per_level"] > 0
        )
        self.assertGreaterEqual(
            monsters.statistics(ref["ref"], ref["max_level"])["HP"],
            ref["statistics"]["HP"]["base"],
        )

    def test_own_negative_actor_id_and_position_are_explicit(self):
        actor = monsters.owned_instance(2, 4, -10001, map_id=1385, x=1, y=2, z=0)
        self.assertEqual(
            (actor["id"], actor["breed"], actor["sprite_id"]), (-10001, 2, 100200002)
        )
        self.assertEqual((actor["map_id"], actor["x"], actor["y"]), (1385, 1, 2))
        for uid in (0, 2**63):
            with self.assertRaises(ValueError):
                monsters.owned_instance(2, 4, uid, map_id=1385, x=1, y=2, z=0)

    def test_ogrest_resource_curve_is_bounded_before_combat_snapshot(self):
        from wakfu_server.combat.combat_actor_snapshot import build_npc_snapshot
        from wakfu_server.combat.combat_state import Actor

        self.assertEqual(monsters.statistics(3046, 999)["WP"], 25)
        monster = monsters.owned_instance(3046, 999, -10002, map_id=1385, x=1, y=2, z=0)
        self.assertEqual(monster["wp"], 20)
        actor = Actor(
            monster["id"],
            1,
            (1, 2, 0),
            monster["hp"],
            monster["ap"],
            monster["mp"],
            monster["initiative"],
            999,
            max_hp=monster["max_hp"],
        )
        snapshot = build_npc_snapshot(
            monster,
            actor,
            wp_current=monster["wp"],
            wp_maximum=monster["wp"],
            running_effects=(),
        )
        self.assertEqual((snapshot.stats[4], snapshot.maxima[4]), (20, 20))

    def test_native_abilities_are_csd_and_csr_is_loot(self):
        record = monsters.reference(5525)
        self.assertNotIn("spell_forms", record)
        self.assertEqual(
            monsters.native_abilities(5525, 1),
            [dict(spell_id=7962, level_parameter=-1, spell_level=1)],
        )
        ref = monsters.reference(2)
        self.assertEqual(monsters.native_abilities(2, 4)[0]["spell_id"], 5769)
        self.assertTrue(
            any(drop["item_reference_id"] == 2026 for drop in ref["loot_definitions"])
        )
        self.assertFalse(any(a["spell_id"] == 2026 for a in ref["native_abilities"]))
