"""Actual roster writes preserve durable exterior storage in private scenes."""
from postgres_case import PostgresCase
from wakfu_server.characters import heroes, hero_private_scene
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import RanchSession, destination


class HeroPrivateRosterPostgresTests(PostgresCase):
    def check_roster_cycle(self, *, ranch, visitor):
        account = self.store.register("private-company", "password")["id"]
        main = self.store.create_character(account, "Company Main")
        first = self.store.create_character(account, "Company First")
        second = self.store.create_character(account, "Company Second")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        main = self.store.character(account, main["id"])
        host = None
        if visitor:
            foreign = self.store.register("private-host", "password")["id"]
            host = self.store.create_character(foreign, "Private Host")
        bag = HavenBagSession(main, owner=host)
        scene = bag
        if ranch:
            scene = RanchSession(
                bag, bag.inside, destination(35), lease=generation, now_ms=1
            )
        live = scene.inside
        exterior = tuple(main[k] for k in hero_private_scene.LOCATION_KEYS)
        hero_private_scene.authorize(scene, live, generation)
        added = heroes.add(self.store, account, generation, main["id"], first["id"])
        projected = hero_private_scene.project(added, scene, live, generation)
        self.assertEqual(live["instance_id"], projected["heroes"][0]["instance_id"])
        switched = heroes.switch_main(
            self.store, account, generation, main["id"], first["id"]
        )
        live = scene.rebind(live, switched["leader"])
        added = heroes.add(self.store, account, generation, first["id"], second["id"])
        projected = hero_private_scene.project(added, scene, live, generation)
        self.assertEqual(2, len(projected["heroes"]))
        self.assertEqual(
            {live["instance_id"]}, {h["instance_id"] for h in projected["heroes"]}
        )
        removed = heroes.remove(
            self.store, account, generation, first["id"], second["id"]
        )
        projected = hero_private_scene.project(removed, scene, live, generation)
        self.assertEqual([main["id"]], [h["id"] for h in projected["heroes"]])
        for identity in (main["id"], first["id"], second["id"]):
            saved = self.store.character(account, identity)
            self.assertEqual(
                exterior, tuple(saved[k] for k in hero_private_scene.LOCATION_KEYS)
            )
        self.assertEqual(not visitor, bag.is_owner)
        self.assertTrue(scene.owns(live))
        if host is not None:
            with self.assertRaisesRegex(ValueError, "foreign"):
                heroes.add(self.store, account, generation, first["id"], host["id"])
            self.assertEqual(host["account_id"], bag.owner["account_id"])

    def test_owned_bag_add_switch_remove(self):
        self.check_roster_cycle(ranch=False, visitor=False)

    def test_owned_ranch_add_switch_remove(self):
        self.check_roster_cycle(ranch=True, visitor=False)

    def test_visited_bag_add_switch_remove_isolates_host(self):
        self.check_roster_cycle(ranch=False, visitor=True)

    def test_visited_ranch_add_switch_remove_isolates_host(self):
        self.check_roster_cycle(ranch=True, visitor=True)
