"""Native external portal retries reconcile retained instance ownership."""
import ast
from pathlib import Path
import struct
from types import SimpleNamespace

from postgres_case import PostgresCase
from wakfu_server import heroes, player_parties, rift_transition_delivery
from wakfu_server.position_buffer import Positions
from wakfu_server.world import World


class ExternalRiftEntryRecoveryTests(PostgresCase):
    def fixture(self, *, pending_only=False):
        owners, identities = [], []
        for index in range(2):
            account = self.store.register(
                f"rift-external-retry-{index}", "test-password"
            )["id"]
            main = self.store.create_character(account, f"PortalMain{chr(65 + index)}")[
                "id"
            ]
            generation = self.store.begin_session(account, ttl=10000)
            self.store.select_character(account, generation, main)
            owners.append((account, generation, main))
            identities.append(main)
        token = player_parties.invite(self.store, *owners[0], owners[1][2])
        party_id = player_parties.answer(self.store, *owners[1], token, True)
        for index, (owner, count) in enumerate(zip(owners, (2, 1))):
            for slot in range(count):
                hero = self.store.create_character(
                    owner[0], f"PortalHero{chr(65 + index)}{chr(65 + slot)}"
                )["id"]
                heroes.add(self.store, *owner, hero)
                identities.append(hero)
        with self.store.connection() as db:
            catalog = db.execute(
                "SELECT value FROM settings WHERE name='rift_catalog'"
            ).fetchone()["value"]["3"]
            portal = catalog["entrances"][0]
            db.execute(
                "UPDATE characters SET level=33,map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=ANY(%s)",
                (
                    portal["map_id"],
                    int(portal["x"]),
                    int(portal["y"] + 1),
                    int(portal["z"]),
                    identities,
                ),
            )
        body = struct.pack(">qHH", portal["object_id"], 11, 0)
        positions = Positions(self.store, lease_active=lambda *key: key in owners)
        old = rift_transition_delivery.enter(
            self.store,
            positions,
            *owners[0],
            portal["map_id"],
            body,
            source_allowed=lambda actor, source: True,
            resolve_destination=lambda *_: dict(
                map_id=catalog["map_id"], x=0, y=1, z=0
            ),
            seed="retained-old-run",
        )
        for owner in owners:
            self.addCleanup(
                rift_transition_delivery.acknowledge, *owner, old["destination"]
            )
        if pending_only:
            return SimpleNamespace(
                owners=owners,
                identities=identities,
                old=old,
                positions=positions,
                body=body,
                portal=portal,
                catalog=catalog,
                party_id=party_id,
            )
        old_owners = list(owners)
        for owner in old_owners:
            self.assertEqual(
                rift_transition_delivery.pending(*owner), old["destination"]
            )
            self.addCleanup(
                rift_transition_delivery.acknowledge, *owner, old["destination"]
            )
        # Model the existing failure: real exterior selection succeeded but
        # the old run and its superseded-generation transport were retained.
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=ANY(%s)",
                (
                    portal["map_id"],
                    int(portal["x"]),
                    int(portal["y"] + 1),
                    int(portal["z"]),
                    identities,
                ),
            )
        for index, owner in enumerate(old_owners):
            generation = self.store.begin_session(owner[0], ttl=10000)
            self.store.select_character(owner[0], generation, owner[2])
            owners[index] = (owner[0], generation, owner[2])
        world = World(
            lambda actor: (1, b"spawn"),
            lambda actor: (2, b"remove"),
            lambda *args: None,
        )
        for owner in owners:
            actor = self.store.character(owner[0], owner[2])
            positions.attach(owner[0], owner[1], actor)
            world.join(owner[1], SimpleNamespace(shutdown=lambda *_: None), actor)
            self.assertEqual(world.live_identity(character_id=owner[2])[0], owner[1])
        with self.store.connection() as db:
            preserved = db.execute(
                "SELECT id,account_id,hp,max_hp,hp_damage,health_dead,hp_zero_valid FROM characters WHERE id=ANY(%s) ORDER BY id",
                (identities,),
            ).fetchall()
            decks = db.execute(
                "SELECT character_id,build_index,deck FROM character_builds WHERE character_id=ANY(%s) ORDER BY character_id,build_index",
                (identities,),
            ).fetchall()
            slots = db.execute(
                "SELECT account_id,slot,character_id FROM account_hero_slots ORDER BY account_id,slot"
            ).fetchall()
        return SimpleNamespace(
            owners=owners,
            identities=identities,
            old=old,
            old_owners=old_owners,
            world=world,
            positions=positions,
            body=body,
            portal=portal,
            catalog=catalog,
            preserved=preserved,
            decks=decks,
            slots=slots,
            party_id=party_id,
        )

    def call(self, fixture, *, destination=None, overrides=None):
        source = Path(__file__).resolve().parents[1] / "local_game_server.py"
        tree = ast.parse(source.read_text())
        call = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and ast.unparse(node.func) == "rift_transition_delivery.enter"
        )
        namespace = dict(
            rift_transition_delivery=rift_transition_delivery,
            STORE=self.store,
            POSITIONS=fixture.positions,
            WORLD=fixture.world,
            COMBAT_SESSIONS=SimpleNamespace(registry=None),
            COMBAT_GROUPS=None,
            CHECKPOINT_WRITER=None,
            account_id=fixture.owners[0][0],
            generation=fixture.owners[0][1],
            character=fixture.world.live_identity(character_id=fixture.owners[0][2])[1],
            body=fixture.body,
            resolve_destination=lambda *_: (
                destination or dict(map_id=fixture.catalog["map_id"], x=0, y=1, z=0)
            ),
            map_geometry=lambda *_: None,
        )
        namespace.update(overrides or {})
        return eval(compile(ast.Expression(call), str(source), "eval"), namespace)

    def test_native_current_outside_company_retries_retained_old_run_without_resetting_players(
        self,
    ):
        fixture = self.fixture()
        owners, identities, old = fixture.owners, fixture.identities, fixture.old
        old_owners, positions = fixture.old_owners, fixture.positions
        preserved, decks, slots, party_id = (
            fixture.preserved,
            fixture.decks,
            fixture.slots,
            fixture.party_id,
        )
        with self.assertRaisesRegex(ValueError, "Unverified native rift arrival"):
            self.call(
                fixture,
                destination=dict(map_id=fixture.catalog["map_id"] + 1, x=0, y=1, z=0),
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM rift_instances WHERE instance_id=%s",
                    (old["run"]["instance_id"],),
                ).fetchone()["status"],
                "entered",
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM rift_instances").fetchone()["n"],
                1,
            )
        self.assertEqual(set(positions.entries), set(owners))
        for owner in old_owners:
            self.assertEqual(
                rift_transition_delivery.pending(*owner), old["destination"]
            )
        result = self.call(fixture)
        for owner in owners:
            self.addCleanup(
                rift_transition_delivery.acknowledge, *owner, result["destination"]
            )
        self.assertEqual(set(result["run"]["members"]), set(identities))
        self.assertNotEqual(result["run"]["instance_id"], old["run"]["instance_id"])
        with self.store.connection() as db:
            old_row = db.execute(
                "SELECT status,fight_id FROM rift_instances WHERE instance_id=%s",
                (old["run"]["instance_id"],),
            ).fetchone()
            self.assertEqual(old_row, dict(status="closed", fight_id=None))
            self.assertEqual(
                db.execute(
                    "SELECT id,account_id,hp,max_hp,hp_damage,health_dead,hp_zero_valid FROM characters WHERE id=ANY(%s) ORDER BY id",
                    (identities,),
                ).fetchall(),
                preserved,
            )
            self.assertEqual(
                db.execute(
                    "SELECT character_id,build_index,deck FROM character_builds WHERE character_id=ANY(%s) ORDER BY character_id,build_index",
                    (identities,),
                ).fetchall(),
                decks,
            )
            self.assertEqual(
                db.execute(
                    "SELECT account_id,slot,character_id FROM account_hero_slots ORDER BY account_id,slot"
                ).fetchall(),
                slots,
            )
            self.assertEqual(
                [
                    r["character_id"]
                    for r in db.execute(
                        "SELECT character_id FROM player_party_members WHERE party_id=%s ORDER BY character_id",
                        (party_id,),
                    ).fetchall()
                ],
                sorted(owner[2] for owner in owners),
            )
            self.assertEqual(
                {
                    r["generation"]
                    for r in db.execute(
                        "SELECT generation FROM sessions WHERE account_id=ANY(%s)",
                        ([owner[0] for owner in owners],),
                    ).fetchall()
                },
                {owner[1] for owner in owners},
            )
            rows = db.execute(
                "SELECT id,map_id,instance_id,x,y,z FROM characters WHERE id=ANY(%s)",
                (identities,),
            ).fetchall()
            self.assertTrue(
                all(
                    {key: row[key] for key in result["destination"]}
                    == result["destination"]
                    for row in rows
                )
            )
        self.assertEqual(positions.entries, {})
        for owner in old_owners:
            self.assertIsNone(rift_transition_delivery.pending(*owner))
        for owner in owners:
            self.assertEqual(
                rift_transition_delivery.pending(*owner), result["destination"]
            )
            self.addCleanup(
                rift_transition_delivery.acknowledge, *owner, result["destination"]
            )

    def test_current_pending_resumes_same_run_without_moving_the_already_loaded_peer(
        self,
    ):
        fixture = self.fixture(pending_only=True)
        fixture.world = World(
            lambda actor: (1, b"spawn"),
            lambda actor: (2, b"remove"),
            lambda *args: None,
        )
        caller, peer = fixture.owners
        original_main = next(
            row for row in fixture.old["members"] if row["id"] == caller[2]
        )
        fixture.world.join(
            caller[1], SimpleNamespace(shutdown=lambda *_: None), original_main
        )
        peer_actor = self.store.character(peer[0], peer[2])
        fixture.positions.attach(peer[0], peer[1], peer_actor)
        fixture.world.join(
            peer[1], SimpleNamespace(shutdown=lambda *_: None), peer_actor
        )
        # The old entry really released the caller's source position buffer;
        # its loaded World source and current pending intent remain real.
        self.assertNotIn(caller, fixture.positions.entries)
        peer_entry = dict(fixture.positions.entries[peer]["current"])
        with self.store.connection() as db:
            original = db.execute(
                "SELECT id,map_id,instance_id,x,y,z,hp,hp_damage FROM characters WHERE id=ANY(%s) ORDER BY id",
                (fixture.identities,),
            ).fetchall()
        for _attempt in range(2):
            result = self.call(fixture)
            self.assertTrue(result["resumed"])
            self.assertEqual(
                result["run"]["instance_id"], fixture.old["run"]["instance_id"]
            )
            self.assertEqual(set(result["run"]["members"]), set(fixture.identities))
            self.assertEqual(fixture.positions.entries[peer]["current"], peer_entry)
            self.assertEqual(
                fixture.world.live_identity(character_id=peer[2])[1]["instance_id"],
                fixture.old["run"]["instance_id"],
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM rift_instances").fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT id,map_id,instance_id,x,y,z,hp,hp_damage FROM characters WHERE id=ANY(%s) ORDER BY id",
                    (fixture.identities,),
                ).fetchall(),
                original,
            )
        for owner in fixture.owners:
            self.assertEqual(
                rift_transition_delivery.pending(*owner), fixture.old["destination"]
            )
            self.addCleanup(
                rift_transition_delivery.acknowledge, *owner, fixture.old["destination"]
            )

    def test_foreign_request_and_genuinely_inside_peer_do_not_cancel_retained_membership(
        self,
    ):
        fixture = self.fixture()
        caller, peer = fixture.owners
        with self.assertRaises(ValueError):
            self.call(fixture, overrides=dict(account_id=peer[0]))
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM rift_instances WHERE instance_id=%s",
                    (fixture.old["run"]["instance_id"],),
                ).fetchone()["status"],
                "entered",
            )
        # Replace only the peer's actual server World/buffer with a genuine
        # loaded interior. Exterior authority for the full company is absent.
        fixture.positions.release(*peer)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s,x=0,y=1,z=0 WHERE id=%s",
                (fixture.catalog["map_id"], fixture.old["run"]["instance_id"], peer[2]),
            )
        inside = self.store.character(peer[0], peer[2])
        fixture.positions.attach(peer[0], peer[1], inside)
        fixture.world.join(peer[1], SimpleNamespace(shutdown=lambda *_: None), inside)
        with self.assertRaises(ValueError):
            self.call(fixture)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM rift_instances WHERE instance_id=%s",
                    (fixture.old["run"]["instance_id"],),
                ).fetchone()["status"],
                "entered",
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM rift_instances").fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT instance_id FROM characters WHERE id=%s", (peer[2],)
                ).fetchone()["instance_id"],
                fixture.old["run"]["instance_id"],
            )
        self.assertEqual(
            fixture.world.live_identity(character_id=peer[2])[1]["instance_id"],
            fixture.old["run"]["instance_id"],
        )
        for owner in fixture.old_owners:
            self.assertEqual(
                rift_transition_delivery.pending(*owner), fixture.old["destination"]
            )

    def test_active_retained_encounter_and_stale_interior_recover_in_the_new_entry_transaction(
        self,
    ):
        from test_combat_admin_recovery import CombatAdminRecoveryTests
        from wakfu_server.checkpoint_worker import CheckpointWorker
        from wakfu_server.fight_checkpoint_store import Checkpoints

        incident = CombatAdminRecoveryTests.fixture(
            self, terminal=False, leader_breed=2
        )
        old_owners, shared = incident["owners"], incident["shared"]
        portal = incident["run"]["catalog"]["entrances"][0]
        writer = CheckpointWorker(Checkpoints(self.store), workers=1)
        self.addCleanup(writer.close)
        writer.submit(shared, old_owners[0][0], old_owners[0][1])
        self.assertTrue(writer.flush_fight(shared.fight.id, timeout=10))
        with self.store.connection() as db:
            original = db.execute(
                "SELECT id,map_id,instance_id,x,y,z FROM characters WHERE id=ANY(%s)",
                (incident["ids"],),
            ).fetchall()
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=ANY(%s)",
                (
                    portal["map_id"],
                    int(portal["x"]),
                    int(portal["y"] + 1),
                    int(portal["z"]),
                    incident["ids"],
                ),
            )
        world = World(
            lambda actor: (1, b"spawn"),
            lambda actor: (2, b"remove"),
            lambda *args: None,
        )
        owners = []
        for account, old_generation, identity in old_owners:
            self.addCleanup(
                rift_transition_delivery.acknowledge,
                account,
                old_generation,
                identity,
                dict(
                    map_id=shared.map_id, instance_id=shared.instance_id, x=0, y=1, z=0
                ),
            )
            generation = self.store.begin_session(account, ttl=10000)
            actor = self.store.select_character(account, generation, identity)
            incident["positions"].attach(account, generation, actor)
            world.join(generation, SimpleNamespace(shutdown=lambda *_: None), actor)
            owners.append((account, generation, identity))
        # Actual selected exterior authority survives, but the old durable
        # private scope and active encounter remain as the seeded incident.
        with self.store.connection() as db:
            for row in original:
                db.execute(
                    "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                    (
                        row["map_id"],
                        row["instance_id"],
                        row["x"],
                        row["y"],
                        row["z"],
                        row["id"],
                    ),
                )
        fixture = SimpleNamespace(
            owners=owners,
            identities=incident["ids"],
            positions=incident["positions"],
            world=world,
            body=struct.pack(">qHH", portal["object_id"], 11, 0),
            catalog=incident["run"]["catalog"],
        )
        overrides = dict(
            COMBAT_SESSIONS=SimpleNamespace(registry=incident["registry"]),
            CHECKPOINT_WRITER=writer,
        )
        participants_before = dict(shared.participants)
        with self.assertRaisesRegex(ValueError, "Unverified native rift arrival"):
            self.call(
                fixture,
                overrides=overrides,
                destination=dict(map_id=fixture.catalog["map_id"] + 1, x=0, y=1, z=0),
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (shared.fight.id,)
                ).fetchone()["status"],
                "active",
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM rift_instances WHERE instance_id=%s",
                    (shared.instance_id,),
                ).fetchone()["status"],
                "running",
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM fight_health_exits WHERE fight_id=%s",
                    (shared.fight.id,),
                ).fetchone()["n"],
                0,
            )
        self.assertEqual(shared.participants, participants_before)
        self.assertIs(incident["registry"].lookup(shared.fight.id), shared)
        result = self.call(fixture, overrides=overrides)
        for owner in owners:
            self.addCleanup(
                rift_transition_delivery.acknowledge, *owner, result["destination"]
            )
        self.assertEqual(result["recovered_fight_id"], shared.fight.id)
        self.assertEqual(set(result["run"]["members"]), set(incident["ids"]))
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (shared.fight.id,)
                ).fetchone()["status"],
                "aborted",
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM fight_checkpoints WHERE fight_id=%s",
                    (shared.fight.id,),
                ).fetchone()["status"],
                "aborted",
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM rift_instances WHERE instance_id=%s",
                    (shared.instance_id,),
                ).fetchone()["status"],
                "closed",
            )
            health = db.execute(
                "SELECT id,hp FROM characters WHERE id=ANY(%s)", (incident["ids"],)
            ).fetchall()
            self.assertEqual(
                {row["id"]: row["hp"] for row in health}, incident["expected"]
            )
        with self.assertRaises(ValueError):
            incident["registry"].lookup(shared.fight.id)
        self.assertEqual(incident["positions"].entries, {})
