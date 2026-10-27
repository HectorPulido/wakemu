"""A real selector may reconnect an admitted hero without changing combat actors.

The socket branch and PostgreSQL company/participant authority are production
code. Absolute world bootstrap and actor serialization remain explicit fixture
boundaries; this does not certify native GUI rendering.
"""
import copy
from dataclasses import replace
from types import SimpleNamespace
from psycopg.types.json import Jsonb

import test_character_selection_socket_postgres as socket_fixture
from wakfu_server import fight_store, heroes
from wakfu_server.combat_heroes import admit_owned_heroes, player_actor
from wakfu_server.combat_session_adapter import CombatSessionAdapter
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_instance_publication import (
    bind_party_encounter,
    require_current_publication,
)
from wakfu_server.combat_instance_publication_recovery import rebind_recovered_owner
from test_party_instance_publication_recovery import published


class HeroAlternateMainLiveReconnectTests(
    socket_fixture.CharacterSelectionSocketPostgresTests
):
    def prepare_live_company(self, phase):
        self.actor = self.store.create_character(self.account, "Reconnect Eni", breed=7)
        self.other = self.store.create_character(
            self.account, "Reconnect Steamer", breed=16
        )
        self.osa = self.store.create_character(self.account, "Reconnect Osa", breed=2)
        self.store.select_character(self.account, self.generation, self.actor["id"])
        heroes.add(
            self.store,
            self.account,
            self.generation,
            self.actor["id"],
            self.other["id"],
        )
        heroes.add(
            self.store, self.account, self.generation, self.actor["id"], self.osa["id"]
        )
        outsider = self.store.create_character(self.account, "Outside Live Company")
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0,x=0,y=0,z=0 "
                "WHERE account_id=%s",
                (self.account,),
            )
            party = db.execute(
                "SELECT p.* FROM player_parties p JOIN player_party_members m "
                "ON m.party_id=p.id WHERE m.character_id=%s",
                (self.actor["id"],),
            ).fetchone()
            identities = [self.actor["id"], self.other["id"], self.osa["id"]]
            if phase == "placement":
                self.instance = db.execute(
                    "INSERT INTO dungeon_instances(party_id,party_revision,created_by_character_id,"
                    "template_id,definition_id,entry_map_id,entry_object_id,entry_destination_id,start_map_id) "
                    "VALUES(%s,%s,%s,1,1,527,1,1,312) RETURNING *",
                    (party["id"], party["revision"], self.actor["id"]),
                ).fetchone()
                for index, identity in enumerate(identities):
                    db.execute(
                        "INSERT INTO dungeon_instance_members(instance_id,party_id,character_id,"
                        "session_generation,party_revision,role) VALUES(%s,%s,%s,%s,%s,%s)",
                        (
                            self.instance["instance_id"],
                            party["id"],
                            identity,
                            self.generation,
                            party["revision"],
                            "leader" if index == 0 else "member",
                        ),
                    )
                    db.execute(
                        "INSERT INTO dungeon_transition_outbox(instance_id,party_id,transition_revision,"
                        "character_id,session_generation,source_map_id,source_instance_id,source_x,source_y,source_z,"
                        "destination_map_id,destination_instance_id,destination_x,destination_y,destination_z) "
                        "VALUES(%s,%s,1,%s,%s,527,0,0,0,0,312,%s,0,0,0)",
                        (
                            self.instance["instance_id"],
                            party["id"],
                            identity,
                            self.generation,
                            self.instance["instance_id"],
                        ),
                    )
                map_id = 312
            else:
                self.instance = db.execute(
                    "INSERT INTO rift_instances(wave_definition_id,owner_character_id,members,catalog,policy,seed,status) "
                    "VALUES(1,%s,%s,%s,%s,'alternate-main','entered') RETURNING *",
                    (
                        self.actor["id"],
                        Jsonb(identities),
                        Jsonb({}),
                        Jsonb({"max_members": 6}),
                    ),
                ).fetchone()
                map_id = 1314
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s WHERE id=ANY(%s)",
                (map_id, self.instance["instance_id"], identities),
            )
        fight_id = fight_store.create(
            self.store, self.account, self.generation, self.actor["id"], team=0
        )
        source = self.store.character(self.account, self.actor["id"])
        cells = {(x, 0, 0) for x in range(6)}
        fight = Fight(
            fight_id,
            [player_actor(source, 0), Actor(-200, 1, (5, 0, 0), 20, 4, 2, 10, 1)],
            cells,
            {0: cells - {(5, 0, 0)}, 1: {(5, 0, 0)}},
        )
        self.adapter = CombatSessionAdapter(self.store)
        old = self.adapter.session(self.account, self.generation, source)
        with self.store.connection() as db:
            fight = admit_owned_heroes(db, self.store, old, fight)["fight"]
        runtime = SimpleNamespace(
            awaiting_ack=None, native_action_id=17, turn_deadline=None
        )
        shared = self.adapter.registry.register(fight, old, runtime=runtime)
        self.old_publication = published(old)
        self.assertTrue(
            bind_party_encounter(
                shared.fight,
                publications=(self.old_publication,),
                npc_ids=(-200,),
                player_ids=tuple(identities),
            )
        )
        if phase == "active":
            self.adapter.registry.ready(fight_id, old, True, lambda *_: [])
            with self.store.connection() as db:
                db.execute(
                    "UPDATE combat_fights SET status='active' WHERE id=%s", (fight_id,)
                )
                db.execute(
                    "UPDATE rift_instances SET status='running',fight_id=%s "
                    "WHERE instance_id=%s",
                    (fight_id, self.instance["instance_id"]),
                )
        self.namespace["COMBAT_SESSIONS"] = self.adapter
        self.before = self.combat_snapshot(shared.fight)
        self.namespace["reconcile_closed_rift_login"] = lambda *args, **kwargs: None
        self.health_before = self.health_rows()
        self.decks_before = self.deck_rows()
        with self.assertRaisesRegex(ValueError, "during combat"):
            heroes.switch_main(
                self.store,
                self.account,
                self.generation,
                self.actor["id"],
                self.other["id"],
            )
        self.old_generation = self.generation
        self.generation = self.store.begin_session(self.account)
        self.namespace["generation"] = self.generation
        self.assertFalse(self.adapter._lease_is_current(old))
        self.adapter.registry.disconnect(old)
        self.old_publication[0].invalidate()
        return shared, old, outsider

    @staticmethod
    def combat_snapshot(fight):
        return copy.deepcopy(
            (
                {
                    key: (
                        actor.id,
                        actor.owner_id,
                        actor.controlled,
                        actor.hp,
                        actor.ap,
                        actor.mp,
                        actor.position,
                        actor.turn_count,
                    )
                    for key, actor in fight.actors.items()
                },
                fight.order,
                fight.turn_index,
                fight.turn_id,
                fight.events,
            )
        )

    def health_rows(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT id,hp_damage,health_dead,hp,max_hp FROM characters "
                "WHERE account_id=%s ORDER BY id",
                (self.account,),
            ).fetchall()

    def deck_rows(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT b.* FROM character_builds b JOIN characters c ON c.id=b.character_id "
                "WHERE c.account_id=%s ORDER BY b.character_id,b.build_index",
                (self.account,),
            ).fetchall()

    def assert_alternate_selection(self, phase):
        shared, old, outsider = self.prepare_live_company(phase)
        self.send(23664, self.select_body(outsider))
        self.assertEqual(self.receive(), (23082, b"\x01"))
        self.receive()  # Native explanation; selection socket remains usable.
        self.send(23664, self.select_body(self.other))
        packet = self.receive()
        self.assertNotEqual(
            packet,
            (23082, b"\x01"),
            "An admitted company hero must remain selectable on reconnect",
        )
        while packet[0] != 13778:
            packet = self.receive()
        replacement = self.adapter.session(
            self.account,
            self.generation,
            self.store.character(self.account, self.other["id"]),
        )
        self.assertTrue(self.adapter.live_reconnect_available(replacement))
        self.assertEqual(
            (old.map_id, old.instance_id), (shared.map_id, shared.instance_id)
        )
        for invalid_location in (
            replace(replacement, map_id=replacement.map_id + 1),
            replace(replacement, instance_id=replacement.instance_id + 1),
        ):
            self.assertFalse(self.adapter.live_reconnect_available(invalid_location))
            with self.assertRaisesRegex(ValueError, "Foreign combat takeover"):
                self.adapter.registry.takeover(
                    shared.fight.id,
                    invalid_location,
                    lambda *_: [],
                    persist_takeover=lambda *_: None,
                )
        with self.assertRaisesRegex(ValueError, "durable lease fence"):
            self.adapter.registry.takeover(shared.fight.id, replacement, lambda *_: [])
        with self.store.connection() as db:
            db.execute(
                "UPDATE combat_fight_participants SET session_generation='foreign-generation' "
                "WHERE fight_id=%s AND character_id=%s",
                (shared.fight.id, self.actor["id"]),
            )
        try:
            self.assertFalse(self.adapter.live_reconnect_available(replacement))
            with self.assertRaisesRegex(ValueError, "Foreign combat takeover"):
                self.adapter.registry.takeover(
                    shared.fight.id,
                    replacement,
                    lambda *_: [],
                    persist_takeover=lambda *_: None,
                )
        finally:
            with self.store.connection() as db:
                db.execute(
                    "UPDATE combat_fight_participants SET session_generation=%s "
                    "WHERE fight_id=%s AND character_id=%s",
                    (self.old_generation, shared.fight.id, self.actor["id"]),
                )
        self.assertEqual(shared.participants[self.account], old)
        self.assertEqual(self.combat_snapshot(shared.fight), self.before)
        if phase == "placement":
            from wakfu_server import dungeon_recovery

            # The scoped socket skips geometry/world publication. Exercise the
            # real retained dungeon membership/outbox reconciliation separately.
            dungeon_recovery.resume_member(
                self.store,
                self.account,
                self.generation,
                self.other["id"],
                self.instance["instance_id"],
                in_fight=lambda identity: self.adapter.lookup_character(identity)
                is not None,
            )
            with self.store.connection() as db:
                members = db.execute(
                    "SELECT character_id,session_generation FROM dungeon_instance_members "
                    "WHERE instance_id=%s",
                    (self.instance["instance_id"],),
                ).fetchall()
                statuses = db.execute(
                    "SELECT status FROM dungeon_transition_outbox WHERE instance_id=%s",
                    (self.instance["instance_id"],),
                ).fetchall()
            self.assertEqual(
                {row["session_generation"] for row in members}, {self.generation}
            )
            self.assertEqual({row["status"] for row in statuses}, {"superseded"})
        else:
            with self.store.connection() as db:
                rift = db.execute(
                    "SELECT * FROM rift_instances WHERE instance_id=%s",
                    (self.instance["instance_id"],),
                ).fetchone()
            self.assertEqual(rift["members"], self.instance["members"])
            self.assertEqual(rift["owner_character_id"], self.other["id"])

        def persist(previous):
            self.assertEqual(previous, old)
            return fight_store.takeover_participant(
                self.store,
                self.account,
                self.generation,
                self.other["id"],
                shared.fight.id,
                previous_generation=previous.generation,
            )

        original_runtime = copy.deepcopy(vars(shared.runtime))
        new_publication = published(replacement)
        self.adapter.registry.takeover(
            shared.fight.id,
            replacement,
            lambda *_: [],
            persist_takeover=persist,
            recover_disconnected=True,
            prepare_authority=lambda fight, view, owner: rebind_recovered_owner(
                fight,
                view,
                owner,
                new_publication,
                session_live=self.adapter.registry._lease_live,
                owner_matches=self.adapter.reconnect_owner_matches,
            ),
        )
        self.assertEqual(vars(shared.runtime), original_runtime)
        require_current_publication(shared.fight)
        self.assertEqual(
            shared.fight.native_instance_publication_lease.owner_bindings,
            (new_publication,),
        )
        self.assertEqual(shared.participants[self.account], replacement)
        with self.store.connection() as db:
            participants = db.execute(
                "SELECT character_id,session_generation FROM combat_fight_participants "
                "WHERE fight_id=%s ORDER BY character_id",
                (shared.fight.id,),
            ).fetchall()
        self.assertEqual(
            {row["character_id"] for row in participants},
            {self.actor["id"], self.other["id"], self.osa["id"]},
        )
        self.assertEqual(
            {row["session_generation"] for row in participants}, {self.generation}
        )
        self.assertEqual(self.health_rows(), self.health_before)
        self.assertEqual(self.deck_rows(), self.decks_before)
        self.assertEqual(self.combat_snapshot(shared.fight), self.before)
        with self.assertRaises(ValueError):
            self.adapter.registry.takeover(shared.fight.id, old, lambda *_: [])

    def test_placement_selects_an_already_admitted_hero_on_new_generation(self):
        self.assert_alternate_selection("placement")

    def test_active_selects_an_already_admitted_hero_on_new_generation(self):
        self.assert_alternate_selection("active")


# Reuse the socket harness without repeating its unrelated selection cases.
for _name in dir(socket_fixture.CharacterSelectionSocketPostgresTests):
    if _name.startswith("test_"):
        setattr(HeroAlternateMainLiveReconnectTests, _name, None)
