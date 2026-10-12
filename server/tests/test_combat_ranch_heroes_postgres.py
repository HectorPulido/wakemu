"""Actual hero admission accepts only a leased private ranch projection."""
from postgres_case import PostgresCase
from wakfu_server import fight_store
from wakfu_server.characters import heroes
from wakfu_server.combat.combat_heroes import admit_owned_heroes, player_actor
from wakfu_server.combat.combat_shared import Session
from wakfu_server.combat.combat_state import Actor, Fight
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import POSITION, RanchSession, destination


class RanchHeroAdmissionTests(PostgresCase):
    def setup_admission(self, *, with_hero):
        account = self.store.register("ranch-company", "password")["id"]
        main = self.store.create_character(account, "Ranch Main")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        hero = None
        if with_hero:
            hero = self.store.create_character(account, "Ranch Hero")
            heroes.add(self.store, account, generation, main["id"], hero["id"])
        bag = HavenBagSession(main)
        ranch = RanchSession(
            bag, bag.inside, destination(35), lease=generation, now_ms=1
        )
        live = ranch.move(ranch.inside, dict(x=10, y=10, z=0))
        session = Session(account, main["id"], generation, 1440, live["instance_id"])
        identity = fight_store.create(self.store, account, generation, main["id"])
        fight = Fight(
            identity,
            [player_actor(live, 0), Actor(-200, 1, (12, 10, 0), 20, 4, 2, 10, 1)],
            {(10, 10, 0), (11, 10, 0), (12, 10, 0)},
            {0: {(10, 10, 0), (11, 10, 0)}, 1: {(12, 10, 0)}},
        )
        return account, main, hero, generation, ranch, live, session, fight

    def admit(self, session, fight, ranch):
        with self.store.connection() as db:
            return admit_owned_heroes(
                db, self.store, session, fight, private_scene=ranch
            )

    def verify_scope(self, result, account, main, hero, ranch, live):
        expected = {key: live[key] for key in ("map_id", "instance_id")}
        self.assertEqual({key: result["leader"][key] for key in expected}, expected)
        for character in result["characters"].values():
            self.assertEqual({key: character[key] for key in expected}, expected)
        self.assertEqual(len(result["actors"]), int(hero is not None))
        for character in (main, hero):
            if character is not None:
                saved = self.store.character(account, character["id"])
                self.assertEqual(
                    {key: saved[key] for key in POSITION},
                    {key: character[key] for key in POSITION},
                )
        self.assertTrue(ranch.owns(live))

    def test_actual_no_hero_admission_uses_private_leader_scope(self):
        (
            account,
            main,
            hero,
            generation,
            ranch,
            live,
            session,
            fight,
        ) = self.setup_admission(with_hero=False)
        result = self.admit(session, fight, ranch)
        self.verify_scope(result, account, main, hero, ranch, live)
        self.assertIs(result["fight"], fight)

    def test_actual_hero_admission_preserves_sql_colocation_and_private_scope(self):
        (
            account,
            main,
            hero,
            generation,
            ranch,
            live,
            session,
            fight,
        ) = self.setup_admission(with_hero=True)
        result = self.admit(session, fight, ranch)
        self.verify_scope(result, account, main, hero, ranch, live)
        self.assertIn(hero["id"], result["fight"].actors)
        with self.store.connection() as db:
            participant = db.execute(
                "SELECT account_id,session_generation FROM combat_fight_participants "
                "WHERE fight_id=%s AND character_id=%s",
                (fight.id, hero["id"]),
            ).fetchone()
        self.assertEqual(
            (participant["account_id"], participant["session_generation"]),
            (account, generation),
        )

    def test_stale_or_foreign_capability_and_moved_sql_hero_reject_atomically(self):
        (
            account,
            main,
            hero,
            generation,
            ranch,
            live,
            session,
            fight,
        ) = self.setup_admission(with_hero=True)
        for bad in (
            Session(account, main["id"], "stale", 1440, live["instance_id"]),
            Session(account, main["id"], generation, 1440, live["instance_id"] + 1),
        ):
            with self.assertRaises(ValueError):
                self.admit(bad, fight, ranch)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=map_id+1 WHERE id=%s", (hero["id"],)
            )
        with self.assertRaises(ValueError):
            self.admit(session, fight, ranch)
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM combat_fight_participants WHERE fight_id=%s AND character_id=%s",
                    (fight.id, hero["id"]),
                ).fetchone()
            )
