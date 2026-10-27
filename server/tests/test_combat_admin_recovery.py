"""Administrative cancellation of a deliberately reconstructed offline incident.

The terminal round-7 fixture is not proof of normal native combat completion.
Rift entry, durable incident roster, health/checkpoint persistence, exterior and later Store
selection/creation/fight creation are real isolated PostgreSQL operations.
"""
import struct
import json
import threading
import urllib.error
import urllib.request
from collections import deque

from postgres_case import PostgresCase
from wakfu_server import fight_store, heroes, player_parties
from wakfu_server import rift_runtime, rift_transition_delivery
from wakfu_server.combat_admin_recovery import (
    CombatAdminRecovery,
    CombatRecoveryRejected,
)
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_encounter_roles import bind_roles
from wakfu_server.rift_encounter_roles import roles_for_catalog
from wakfu_server.combat_shared import Registry, Session, SharedFight
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.command_permissions import set_admin
from wakfu_server.fight_checkpoint_store import Checkpoints
from wakfu_server.position_buffer import Positions


class CombatAdminRecoveryTests(PostgresCase):
    def fixture(self, *, terminal=True, leader_breed=1):
        admin = self.store.register("recovery-admin", "private-test-password")["id"]
        set_admin(
            self.store, admin, True, operator="fixture", reason="isolated recovery QA"
        )
        owners = []
        for index, name in enumerate(
            ("Recovery Main", "Recovery Peer A", "Recovery Peer B")
        ):
            account = self.store.register(
                "recovery-owner-" + str(index), "private-test-password"
            )["id"]
            character = self.store.create_character(
                account, name, breed=leader_breed if index == 0 else 1
            )["id"]
            generation = self.store.begin_session(account, ttl=10000)
            self.store.select_character(account, generation, character)
            owners.append((account, generation, character))
        leader = owners[0]
        hero_ids = []
        for name in ("Recovery Hero A", "Recovery Hero B"):
            hero = self.store.create_character(leader[0], name)["id"]
            heroes.add(self.store, *leader, hero)
            hero_ids.append(hero)
        for owner in owners[1:]:
            invitation = player_parties.invite(self.store, *leader, owner[2])
            player_parties.answer(self.store, *owner, invitation, True)
        identities = [owner[2] for owner in owners] + hero_ids
        with self.store.connection() as db:
            catalog = db.execute(
                "SELECT value FROM settings WHERE name='rift_catalog'"
            ).fetchone()["value"]["3"]
            portal = catalog["entrances"][0]
            db.execute(
                "UPDATE characters SET level=33,map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=ANY(%s)",
                (portal["map_id"], portal["x"], portal["y"], portal["z"], identities),
            )
        # The fixture raised level directly, so establish its real effective
        # maximum through the production health policy before freezing entry HP.
        # This requires the complete qualified native publication, not a mock.
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.health_policy import reconfigure

        owner_by_character = {owner[2]: owner[0] for owner in owners}
        owner_by_character.update({hero: leader[0] for hero in hero_ids})
        with self.store.connection() as db:
            for identity in identities:
                character = self.store.character(
                    owner_by_character[identity], identity, db
                )
                hp = reconfigure(
                    db, character, effective_character(character)["max_hp"]
                )
                now = self.store.now()
                db.execute(
                    "UPDATE character_regeneration SET initial_hp=%s,started_at=%s,last_at=%s WHERE character_id=%s",
                    (hp, now, now, identity),
                )
        positions = Positions(
            self.store,
            lease_active=lambda *key: self.store.current_character_session(*key),
        )
        for owner in owners:
            positions.attach(*owner[:2], self.store.character(owner[0], owner[2]))
        entered = rift_transition_delivery.enter(
            self.store,
            positions,
            *leader,
            portal["map_id"],
            struct.pack(">qHH", portal["object_id"], 11, 0),
            source_allowed=lambda actor, source: actor["map_id"] == source["map_id"]
            and max(abs(actor["x"] - source["x"]), abs(actor["y"] - source["y"])) <= 3
            and abs(actor["z"] - source["z"]) <= 2,
            resolve_destination=lambda *_: dict(
                map_id=catalog["map_id"], x=0, y=1, z=0
            ),
            seed="admin-recovery-fixture"
        )
        run = entered["run"]
        characters = {
            identity: self.store.character(
                next(owner[0] for owner in owners if identity == owner[2])
                if identity not in hero_ids
                else leader[0],
                identity,
            )
            for identity in identities
        }
        sessions = [
            Session(
                account, identity, generation, catalog["map_id"], run["instance_id"]
            )
            for account, generation, identity in owners
        ]
        leader_session = sessions[0]
        roles = roles_for_catalog(
            run["catalog"],
            run["policy"],
            monster_references=(run["catalog"]["species_refs"][0],),
        )
        fight_id = fight_store.create(self.store, *leader, team=roles.player_team)
        # Deliberately construct an incident roster from real durable health
        # baselines. This is not native NPC construction or combat admission.
        actors = [
            Actor(
                identity,
                roles.player_team,
                (index, 1, 0),
                character["hp"],
                6,
                3,
                100,
                character["level"],
                character["account_id"],
                True,
                max_hp=character["max_hp"],
            )
            for index, (identity, character) in enumerate(characters.items())
        ]
        actors.append(Actor(-200, roles.npc_team, (5, 1, 0), 20, 4, 2, 10, 1))
        cells = {(x, 1, 0) for x in range(6)}
        fight = Fight(
            fight_id,
            actors,
            cells,
            {
                roles.player_team: {(x, 1, 0) for x in range(5)},
                roles.npc_team: {(5, 1, 0)},
            },
        )
        bind_roles(fight, roles, player_ids=identities, npc_ids=(-200,))
        with self.store.connection() as db:
            for hero in hero_ids:
                baseline = fight_store._health_baseline(db, leader[0], hero)
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation,entry_hp,entry_max_hp,entry_hp_damage,entry_health_dead) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        fight_id,
                        hero,
                        leader[0],
                        roles.player_team,
                        leader[1],
                        *baseline,
                    ),
                )
            for owner in owners[1:]:
                fight_store.join_participant(
                    self.store,
                    db,
                    *owner,
                    fight_id,
                    target_character_id=leader[2],
                    team=roles.player_team
                )
        registry = Registry(
            lambda session: self.store.current_character_session(
                session.account_id, session.generation, session.character_id
            )
        )
        shared = SharedFight(
            fight, catalog["map_id"], run["instance_id"], RuntimeMessages(fight)
        )
        shared.participants = {session.account_id: session for session in sessions}
        shared.connected = {session.account_id for session in sessions}
        shared.outboxes = {session.account_id: deque() for session in sessions}
        registry.fights[fight_id] = shared
        registry.by_character = {identity: fight_id for identity in identities}
        registry.by_actor = {identity: fight_id for identity in fight.actors}
        for owner in owners:
            shared.fight.ready(owner[0])
        fight_store.activate(self.store, *leader, fight_id)
        with self.store.connection() as db:
            rift_runtime.start(db, run["instance_id"], leader[2], fight_id)
        shared.runtime = RuntimeMessages(shared.fight)
        shared.fight.rift_wave_state = dict(
            instance_id=run["instance_id"],
            wave=1,
            turn_budget=40,
            staged_receipts=[],
            pending_wave=None,
        )
        shared.fight.native_timeline_round = 7
        expected = {}
        for loss, identity in enumerate(sorted(identities), 1):
            actor = shared.fight.actors[identity]
            expected[identity] = max(1, actor.hp - loss)
            shared.fight.apply_effect_damage(
                -200, identity, actor.hp - expected[identity]
            )
        if terminal:
            # Deliberately reconstruct the incident's early terminal state.
            # The active variant retains the real ready/activate/start path.
            shared.fight.phase = "finished"
            shared.fight.winner = roles.player_team
        revision, _ = Checkpoints(self.store).save_shared(shared, leader[0], leader[1])
        service = CombatAdminRecovery(self.store, registry, positions)
        return dict(
            admin=admin,
            owners=owners,
            heroes=hero_ids,
            ids=identities,
            sessions=sessions,
            shared=shared,
            registry=registry,
            positions=positions,
            expected=expected,
            run=run,
            revision=revision,
            service=service,
        )

    def http_client(self, service, administrator):
        from wakfu_server.api import serve_api

        token = self.store.issue_token(administrator, "api")
        ready = threading.Event()
        servers = []

        def on_ready(server):
            servers.append(server)
            ready.set()

        thread = threading.Thread(
            target=serve_api,
            args=(self.store, "127.0.0.1", 0),
            kwargs=dict(combat_recovery=service, on_ready=on_ready),
            daemon=True,
        )
        thread.start()
        self.assertTrue(ready.wait(2))
        server = servers[0]
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.shutdown)

        def post(body):
            request = urllib.request.Request(
                "http://127.0.0.1:"
                + str(server.server_port)
                + "/test/admin/combat-recovery",
                data=json.dumps(body).encode(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer " + token,
                },
            )
            try:
                response = urllib.request.urlopen(request, timeout=8)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                return response.status, json.load(response)

        return post

    def test_actual_five_member_offline_abort_preserves_health_then_reselect_create_and_new_fight(
        self,
    ):
        fixture = self.fixture()
        service = fixture["service"]
        shared = fixture["shared"]
        admin = fixture["admin"]
        owner = fixture["owners"][0]
        inspect = dict(
            action="inspect", fight_id=shared.fight.id, character_id=owner[2]
        )
        request = dict(
            inspect,
            action="abort",
            checkpoint_revision=fixture["revision"],
            request_id="five-owner-incident",
            reason="Explicit isolated QA incident cancellation",
        )
        with self.assertRaises(PermissionError):
            service.execute(owner[0], inspect)
        self.assertFalse(service.execute(admin, inspect)["eligible"])
        with self.assertRaises(CombatRecoveryRejected):
            service.execute(admin, request)
        for session in fixture["sessions"]:
            fixture["registry"].disconnect(session)
            self.store.end_session(session.account_id, session.generation)
        self.assertTrue(service.execute(admin, inspect)["eligible"])
        with self.assertRaises(CombatRecoveryRejected):
            service.execute(
                admin, dict(request, checkpoint_revision=fixture["revision"] + 1)
            )
        with self.store.connection() as db:
            self.assertFalse(
                db.execute(
                    "SELECT 1 FROM fight_health_exits WHERE fight_id=%s",
                    (shared.fight.id,),
                ).fetchone()
            )
            db.execute(
                "INSERT INTO rift_settlement_receipts(instance_id,fight_id,outcome,result) VALUES(%s,%s,'closed','{}')",
                (fixture["run"]["instance_id"], shared.fight.id),
            )
        with self.assertRaises(CombatRecoveryRejected):
            service.execute(admin, request)
        with self.store.connection() as db:
            db.execute(
                "DELETE FROM rift_settlement_receipts WHERE fight_id=%s",
                (shared.fight.id,),
            )
        post = self.http_client(service, admin)
        status, inspection = post(inspect)
        self.assertEqual(status, 200)
        self.assertTrue(inspection["eligible"])
        status, result = post(request)
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["request_id"], request["request_id"])
        self.assertFalse(result["replayed"])
        self.assertEqual(set(result["character_ids"]), set(fixture["ids"]))
        self.assertEqual(len(result["destinations"]), 3)
        self.assertNotIn(shared.fight.id, fixture["registry"].fights)
        self.assertFalse(set(fixture["ids"]) & set(fixture["registry"].by_character))
        self.assertFalse(set(shared.fight.actors) & set(fixture["registry"].by_actor))
        self.assertFalse(fixture["positions"].entries)
        with self.store.connection() as db:
            rows = list(
                db.execute(
                    "SELECT id,account_id,hp,map_id,instance_id FROM characters WHERE id=ANY(%s)",
                    (fixture["ids"],),
                )
            )
            exits = list(
                db.execute(
                    "SELECT character_id,reason FROM fight_health_exits WHERE fight_id=%s",
                    (shared.fight.id,),
                )
            )
            self.assertEqual(
                {row["character_id"] for row in exits}, set(fixture["ids"])
            )
            self.assertEqual({row["reason"] for row in exits}, {"abort"})
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (shared.fight.id,)
                ).fetchone()["status"],
                "aborted",
            )
            checkpoint = db.execute(
                "SELECT status,revision,snapshot FROM fight_checkpoints WHERE fight_id=%s",
                (shared.fight.id,),
            ).fetchone()
            self.assertEqual(checkpoint["status"], "aborted")
            self.assertEqual(checkpoint["revision"], result["checkpoint_revision"])
            self.assertEqual(
                {
                    int(identity): actor["hp"]
                    for identity, actor in checkpoint["snapshot"]["actors"].items()
                    if actor["controlled"]
                },
                fixture["expected"],
            )
            # RiftRuntime.abort_bound_fight closes the run; the fight and
            # checkpoint carry the distinct aborted disposition.
            self.assertEqual(
                db.execute(
                    "SELECT status FROM rift_instances WHERE instance_id=%s",
                    (fixture["run"]["instance_id"],),
                ).fetchone()["status"],
                "closed",
            )
            for table in (
                "fight_rewards",
                "fight_reward_policy_receipts",
                "rift_settlement_receipts",
            ):
                self.assertFalse(
                    db.execute(
                        "SELECT 1 FROM " + table + " WHERE fight_id=%s",
                        (shared.fight.id,),
                    ).fetchone()
                )
        for row in rows:
            self.assertEqual(row["hp"], fixture["expected"][row["id"]])
            self.assertEqual(row["instance_id"], 0)
            self.assertNotEqual(row["map_id"], shared.map_id)
        for participant in fixture["owners"]:
            self.assertIsNone(rift_transition_delivery.pending(*participant))
        status, repeated = post(request)
        self.assertEqual(status, 200)
        self.assertTrue(repeated["replayed"])
        with self.assertRaises(CombatRecoveryRejected):
            service.execute(
                admin,
                dict(
                    request, reason="A different request cannot reuse the receipt key"
                ),
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM admin_panel_audit WHERE action=%s",
                    (service.ACTION,),
                ).fetchone()["n"],
                1,
            )
        for account, generation, identity in fixture["owners"]:
            new_generation = self.store.begin_session(account)
            selected = self.store.select_character(account, new_generation, identity)
            self.assertEqual(selected["instance_id"], 0)
            self.assertEqual(selected["hp"], fixture["expected"][identity])
        account = owner[0]
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, owner[2])
        created = self.store.create_character(
            account, "After Admin Recovery", selection_generation=generation
        )
        self.store.select_character(account, generation, created["id"])
        next_fight = fight_store.create(
            self.store, account, generation, created["id"], team=0
        )
        self.assertNotEqual(next_fight, shared.fight.id)
