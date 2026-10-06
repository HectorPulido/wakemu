import unittest
from postgres_case import PostgresCase
from wakfu_server.profession_store import level, ensure_learned, learned
from wakfu_server.monster_collect import resolve_target
from wakfu_server.combat_groups import Groups
from wakfu_server.monsters import owned_instance


class ProfessionTests(PostgresCase):
    def test_fresh_zero_persisted_level_and_foreign_lease(self):
        store = self.store
        a = store.register("profession-owner", "local-password")["id"]
        one = store.create_character(a, "Profession First")
        two = store.create_character(a, "Profession Second")
        gen = store.begin_session(a)
        store.select_character(a, gen, one["id"])
        self.assertEqual(level(store, a, gen, one["id"], 74), 0)
        with store.connection() as db:
            db.execute(
                "INSERT INTO character_professions VALUES(%s,%s,%s)",
                (one["id"], 74, 20),
            )
        self.assertEqual(level(store, a, gen, one["id"], 74), 20)
        with self.assertRaises(ValueError):
            level(store, a, gen, two["id"], 74)
        with self.assertRaises(ValueError):
            level(store, a, "stale", one["id"], 74)
        store.select_character(a, gen, two["id"])
        self.assertEqual(level(store, a, gen, two["id"], 74), 0)

    def test_registry_resolves_actual_instance_and_rejects_claimed_group(self):
        groups = Groups()
        npc = owned_instance(5525, 1, -200, map_id=1134, x=-7, y=-7, z=-1)
        groups.register(1134, 7, 200, [npc])
        character = dict(map_id=1134, instance_id=7)
        self.assertEqual(resolve_target(groups, character, -200)["instance_id"], 7)
        with self.assertRaises(ValueError):
            resolve_target(groups, dict(map_id=1134, instance_id=0), -200)
        groups.claim((1134, 7, 200), "own-generation", 123)
        with self.assertRaises(ValueError):
            resolve_target(groups, character, -200)

    def test_learning_preserves_level_and_fences_foreign_character(self):
        store = self.store
        a = store.register("learner", "local-password")["id"]
        one = store.create_character(a, "Learn First")
        two = store.create_character(a, "Learn Second")
        gen = store.begin_session(a)
        store.select_character(a, gen, one["id"])
        result = ensure_learned(store, a, gen, one["id"], [72, 74])
        self.assertEqual(result["levels"], {72: 0, 74: 0})
        self.assertEqual([p[0] for p in result["packets"]], [12675, 12675])
        self.assertTrue(learned(store, a, gen, one["id"], 74))
        with store.connection() as db:
            db.execute(
                "UPDATE character_professions SET level=20 WHERE character_id=%s AND profession_id=74",
                (one["id"],),
            )
        self.assertEqual(
            ensure_learned(store, a, gen, one["id"], [74])["levels"][74], 20
        )
        with self.assertRaises(ValueError):
            ensure_learned(store, a, gen, two["id"], [74])
        with self.assertRaises(ValueError):
            ensure_learned(store, a, gen, one["id"], [999999])
