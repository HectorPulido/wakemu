"""Private returns retain live health while restoring only scene-owned state."""
import unittest

from postgres_case import PostgresCase
from wakfu_server import health_store
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import RanchSession


class PrivateSceneReturnHealthTests(PostgresCase):
    def test_regeneration_survives_nested_ranch_and_bag_return_then_next_tick(self):
        store = self.store
        store.clock = lambda: 1000
        account = store.register("private-return-health", "test-password")["id"]
        saved = store.create_character(account, "Private Return")
        generation = store.begin_session(account)
        saved = store.select_character(account, generation, saved["id"])
        started = 1000000
        wounded = health_store.sync(
            store,
            account,
            generation,
            saved["id"],
            saved["hp"],
            saved["hp"] - 24,
            coefficient=4,
            now_ms=started,
        )
        wounded.update(
            native_world_id=527, _native_haven_world_position={"source": "outside"}
        )
        bag = HavenBagSession(wounded)
        current = dict(bag.inside)

        def tick(character, elapsed):
            updated = health_store.tick(
                store,
                account,
                generation,
                saved["id"],
                character["hp"],
                now_ms=started + elapsed,
            )
            return {**character, **updated}

        current = tick(current, 4000)
        self.assertGreater(current["hp"], wounded["hp"])
        child = RanchSession(
            bag,
            current,
            dict(biome_id=1, map_id=1440, x=28, y=6, z=4),
            lease="current",
            now_ms=started + 4000,
        )
        current = tick(child.inside, 8000)
        # Reproduce the previous return-point copy's stale-HP rejection before
        # proving the corrected live-state projection reaches the same CAS.
        with self.assertRaisesRegex(ValueError, "Stale health update"):
            tick(dict(child.return_point), 8000)
        returned = child.leave(current)
        self.assertEqual(returned["hp"], current["hp"])
        self.assertTrue(bag.owns(returned))
        self.assertNotIn("haven_ranch_session", returned)
        self.assertNotIn("native_world_id", returned)
        self.assertEqual(returned["hp_damage"], 16)
        returned = tick(returned, 12000)
        with self.assertRaisesRegex(ValueError, "Stale health update"):
            tick(dict(bag.outside), 12000)
        exterior = bag.leave(returned)
        self.assertEqual(exterior["hp"], returned["hp"])
        for key in (
            "map_id",
            "instance_id",
            "x",
            "y",
            "z",
            "native_world_id",
            "_native_haven_world_position",
            "haven_bag",
        ):
            self.assertEqual(exterior.get(key), wounded.get(key))
        self.assertNotIn("haven_bag_visitor", exterior)
        exterior = tick(exterior, 16000)
        canonical = store.character(account, saved["id"])
        self.assertEqual(exterior["hp"], canonical["hp"])
        self.assertEqual(canonical["hp_damage"], 8)
        self.assertFalse(canonical["health_dead"])


class PrivateSceneReturnStateTests(unittest.TestCase):
    def test_guest_restores_own_scene_metadata_without_reverting_live_death_or_progress(
        self,
    ):
        visitor = dict(
            id=3,
            account_id=2,
            name="Visitor",
            map_id=527,
            instance_id=0,
            x=1,
            y=2,
            z=3,
            hp=20,
            hp_damage=10,
            health_dead=False,
            hp_zero_valid=False,
            haven_bag={"owner": "visitor"},
            native_world_id=77,
        )
        host = dict(visitor, id=9, account_id=8, haven_bag={"owner": "host"})
        bag = HavenBagSession(visitor, owner=host)
        child = RanchSession(
            bag,
            bag.inside,
            dict(biome_id=1, map_id=1440, x=28, y=6, z=4),
            lease="guest",
            now_ms=1000,
        )
        live = dict(
            child.inside,
            hp=0,
            hp_damage=30,
            health_dead=True,
            hp_zero_valid=False,
            xp=12345,
            inventory_revision=19,
        )
        returned = child.leave(live)
        self.assertEqual(returned["haven_bag"], host["haven_bag"])
        self.assertTrue(returned["haven_bag_visitor"])
        exterior = bag.leave(returned)
        self.assertEqual(exterior["haven_bag"], visitor["haven_bag"])
        self.assertEqual(exterior["native_world_id"], 77)
        self.assertNotIn("haven_bag_visitor", exterior)
        self.assertNotIn("haven_ranch_session", exterior)
        for key in (
            "hp",
            "hp_damage",
            "health_dead",
            "hp_zero_valid",
            "xp",
            "inventory_revision",
        ):
            self.assertEqual(exterior[key], live[key])
