"""Duel companies retain actor membership and one transport per real owner."""
import unittest
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_shared import Registry, Session


class FriendlyDuelHeroRegistryTests(unittest.TestCase):
    def setUp(self):
        self.sessions = (Session(1, 11, "a", 527, 0), Session(2, 21, "b", 527, 0))
        self.registry = Registry(lambda session: session in self.sessions)
        self.fight = Fight(
            99,
            [
                Actor(identity, team, (x, 0, 0), 60, 6, 3, 10, 1, owner, True)
                for identity, team, x, owner in (
                    (11, 0, 0, 1),
                    (12, 0, 1, 1),
                    (21, 1, 3, 2),
                    (22, 1, 4, 2),
                )
            ],
            {(x, 0, 0) for x in range(5)},
            {0: {(0, 0, 0), (1, 0, 0)}, 1: {(3, 0, 0), (4, 0, 0)}},
        )

    def register(self):
        return self.registry.register_duel(
            self.fight,
            self.sessions,
            initial_packets={1: ((12847, b"a"),), 2: ((12847, b"b"),)},
        )

    def test_company_actors_share_transport_without_losing_membership(self):
        shared = self.register()
        self.assertEqual(set(shared.participants), {1, 2})
        self.assertEqual(set(shared.outboxes), {1, 2})
        for identity in (11, 12, 21, 22):
            self.assertIs(self.registry.lookup_character(identity), shared)
        self.assertEqual(
            self.registry.drain(99, self.sessions[0])[0].packets, ((12847, b"a"),)
        )

    def test_disconnect_forfeits_to_opposing_company_without_killing_heroes(self):
        self.register()
        self.assertTrue(self.registry.forfeit_duel(self.sessions[0]))
        self.assertEqual(self.fight.winner, 1)
        self.assertEqual(self.fight.phase, "finished")
        self.assertTrue(all(actor.hp == 60 for actor in self.fight.actors.values()))

    def test_rollback_removes_every_hero_index(self):
        self.register()
        self.assertTrue(self.registry.unregister_unpublished(99))
        for identity in (11, 12, 21, 22):
            self.assertIsNone(self.registry.lookup_character(identity))

    def test_foreign_hero_or_wrong_team_is_not_silently_admitted(self):
        hero = self.fight.actors[12]
        hero.owner_id = 3
        with self.assertRaisesRegex(ValueError, "consenting owner's team"):
            self.register()
        hero.owner_id = 2
        with self.assertRaisesRegex(ValueError, "consenting owner's team"):
            self.register()

    def test_nominated_same_account_opponents_use_one_real_session(self):
        fight = Fight(
            100,
            [
                Actor(11, 0, (0, 0, 0), 60, 6, 3, 10, 1, 1, True),
                Actor(12, 1, (4, 0, 0), 60, 6, 3, 9, 1, 1, True),
            ],
            {(x, 0, 0) for x in range(5)},
            {0: {(0, 0, 0)}, 1: {(4, 0, 0)}},
        )
        shared = self.registry.register_duel(
            fight,
            self.sessions[:1],
            initial_packets={1: ()},
            join_context={"leaders": {0: 11, 1: 12}},
        )
        self.assertEqual(set(shared.participants), {1})
        self.assertEqual(set(shared.outboxes), {1})
        self.assertIs(self.registry.lookup_character(12), shared)
        from wakfu_server.combat_effective_control import require_effective_owner

        self.assertIs(
            require_effective_owner(fight, fight.actors[12], 1), fight.actors[12]
        )
        self.assertTrue(self.registry.forfeit_duel(self.sessions[0]))
        self.assertEqual(fight.winner, 1)


from postgres_case import PostgresCase


class FriendlyDuelOwnedInvitationTests(PostgresCase):
    def test_own_hero_invitation_is_answered_by_selected_main_without_fake_session(
        self,
    ):
        import struct
        from wakfu_server.characters.heroes import add
        from wakfu_server.friendly_duels import invite_challenge, answer_challenge

        account = self.store.register("duel-own-hero", "local-password")["id"]
        main = self.store.create_character(account, "Main Duel")
        hero = self.store.create_character(account, "Hero Duel")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, main["id"])
        add(self.store, account, generation, main["id"], hero["id"])
        main = self.store.character(account, main["id"])
        hero = self.store.character(account, hero["id"])
        session = Session(
            account, main["id"], generation, main["map_id"], main["instance_id"]
        )
        target = Session(
            account, hero["id"], generation, hero["map_id"], hero["instance_id"]
        )
        result = invite_challenge(
            self.store,
            session,
            target,
            struct.pack(">qii hBB", hero["id"], hero["x"], hero["y"], hero["z"], 0, 1),
        )
        self.assertEqual(result["target_character_id"], hero["id"])
        refused = answer_challenge(
            self.store, session, struct.pack(">qBB", main["id"], 0, 0)
        )
        self.assertFalse(refused["accepted"])
        self.assertEqual(refused["packet"], (12708, b"\x01"))
        self.assertTrue(
            self.store.current_character_session(account, generation, main["id"])
        )
        self.assertFalse(
            self.store.current_character_session(account, generation, hero["id"])
        )

    def _accept_and_return(self, same_account):
        import struct
        from wakfu_server.characters.heroes import add
        from wakfu_server.friendly_duels import (
            invite_challenge,
            answer_challenge,
            settle,
            return_packets,
        )
        from wakfu_server.friendly_duel_runtime import prepare_and_register
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_terrain import map_geometry

        cells = map_geometry(527)["edges"][0]
        accounts, sessions, characters = [], [], []
        for index in range(1 if same_account else 2):
            account = self.store.register(f"company-{index}", "local-password")["id"]
            label = ("One", "Two")[index]
            main = self.store.create_character(account, f"Leader {label}")
            hero = self.store.create_character(account, f"Companion {label}")
            generation = self.store.begin_session(account)
            self.store.select_character(account, generation, main["id"])
            with self.store.connection() as db:
                db.execute(
                    "UPDATE characters SET map_id=527,instance_id=0,x=%s,y=%s,z=%s "
                    "WHERE account_id=%s",
                    (*cells[index], account),
                )
            add(self.store, account, generation, main["id"], hero["id"])
            main = self.store.character(account, main["id"])
            hero = self.store.character(account, hero["id"])
            accounts.append(account)
            characters.extend((main, hero))
            sessions.append(Session(account, main["id"], generation, 527, 0))
        first = sessions[0]
        target = (
            Session(first.account_id, characters[1]["id"], first.generation, 527, 0)
            if same_account
            else sessions[1]
        )
        before = {row["id"]: (row["kamas"], row["xp"]) for row in characters}
        with self.store.connection() as db:
            inventory_before = tuple(
                db.execute("SELECT * FROM inventory_items ORDER BY uid")
            )
        invite_challenge(
            self.store,
            first,
            target,
            struct.pack(">qii hBB", target.character_id, 0, 0, 0, 0, 1),
        )
        adapter = CombatSessionAdapter(self.store)

        def prepare(db, fight_id, invitation, challenger, opponent):
            result = prepare_and_register(
                self.store,
                adapter,
                db,
                fight_id,
                invitation,
                challenger,
                opponent,
                auto_locked=False,
            )
            return result, result["rollback"]

        accepted = answer_challenge(
            self.store,
            first if same_account else target,
            struct.pack(">qBB", first.character_id, 1, 0),
            prepare_duel=prepare,
        )
        self.assertTrue(accepted["accepted"])
        prepared = accepted["prepared"]
        fight = prepared["fight"]
        self.assertEqual(set(fight.actors), {row["id"] for row in characters})
        self.assertEqual(len(prepared["shared"].outboxes), len(sessions))
        self.assertTrue(adapter.registry.forfeit_duel(first, reason="defeat"))
        result = settle(
            self.store,
            first.account_id,
            first.generation,
            first.character_id,
            fight,
            reason="defeat",
        )
        self.assertEqual(set(result["positions"]), set(fight.actors))
        for session in sessions:
            return_packets(
                self.store,
                session.account_id,
                session.generation,
                session.character_id,
                fight,
                struct.pack(">iB", fight.id, 0),
            )
        for row in characters:
            saved = self.store.character(row["account_id"], row["id"])
            self.assertEqual((saved["kamas"], saved["xp"]), before[row["id"]])
            self.assertEqual(saved["hp"], saved["max_hp"])
            self.assertFalse(saved["health_dead"])
        with self.store.connection() as db:
            self.assertEqual(
                tuple(db.execute("SELECT * FROM inventory_items ORDER BY uid")),
                inventory_before,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM fight_rewards").fetchone()["n"], 0
            )
            exits = tuple(
                db.execute(
                    "SELECT return_acknowledged_at FROM fight_health_exits "
                    "WHERE fight_id=%s",
                    (fight.id,),
                )
            )
            self.assertEqual(len(exits), len(characters))
            self.assertTrue(
                all(row["return_acknowledged_at"] is not None for row in exits)
            )

    def test_same_account_acceptance_settlement_and_return_preserve_rewards_and_items(
        self,
    ):
        self._accept_and_return(True)

    def test_two_account_hero_companies_settle_and_return_every_member(self):
        self._accept_and_return(False)
