"""Atomic obsolete-fight repair from real World/Positions exterior authority.

The inconsistent old durable location is deliberately seeded as incident data;
this does not claim a native client produced that mismatch in this test.
"""
from contextlib import ExitStack
from dataclasses import replace

from postgres_case import PostgresCase


class CombatEntryRecoveryPostgresTests(PostgresCase):
    def fixture(self, *, already_outside=False):
        from test_combat_admin_recovery import CombatAdminRecoveryTests
        from wakfu_server.combat_shared import Session
        from wakfu_server.native_entry_authority import capture
        from wakfu_server.world import World
        from wakfu_server.characters.captured_roster import (
            CapturedCreature,
            OwnedCapturedRoster,
        )
        from wakfu_server.characters.captured_roster_store import save
        from wakfu_server.fight_checkpoint_store import Checkpoints
        from wakfu_server.checkpoint_worker import CheckpointWorker

        fixture = CombatAdminRecoveryTests.fixture(self, terminal=False, leader_breed=2)
        shared = fixture["shared"]
        leader = fixture["owners"][0]
        slots = [None] * 10
        slots[1] = CapturedCreature(1, 4, "Existing Tofu")
        slots[3] = CapturedCreature(3, 1152, "Existing Capture")
        roster = OwnedCapturedRoster(leader[2], tuple(slots), (False,) * 10, 1)
        shared.fight.native_captured_rosters = {str(leader[2]): roster.to_record()}
        with self.store.connection() as db:
            save(db, self.store.character(leader[0], leader[2], db), roster)
        Checkpoints(self.store).save_shared(shared, leader[0], leader[1])
        writer = CheckpointWorker(Checkpoints(self.store), workers=1)
        self.addCleanup(writer.close)
        writer.submit(shared, leader[0], leader[1])
        self.assertTrue(writer.flush_fight(shared.fight.id, timeout=10))
        portal = fixture["run"]["catalog"]["entrances"][0]
        outside = dict(
            map_id=portal["map_id"],
            instance_id=0,
            x=portal["x"],
            y=portal["y"],
            z=portal["z"],
        )
        original_locations = {}
        with self.store.connection() as db:
            for identity in fixture["ids"]:
                row = db.execute(
                    "SELECT id,map_id,instance_id,x,y,z FROM characters WHERE id=%s",
                    (identity,),
                ).fetchone()
                original_locations[identity] = row
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=ANY(%s)",
                (
                    outside["map_id"],
                    outside["x"],
                    outside["y"],
                    outside["z"],
                    fixture["ids"],
                ),
            )
        world = World(lambda actor: b"", lambda actor: b"", lambda *args: None)
        current, rows = [], []
        for account, previous, identity in fixture["owners"]:
            generation = self.store.begin_session(account, ttl=10000)
            actor = self.store.select_character(account, generation, identity)
            fixture["positions"].attach(account, generation, actor)
            world.join(generation, object(), actor)
            current.append(Session(account, identity, generation, actor["map_id"], 0))
            rows.append(dict(id=identity, account_id=account, generation=generation))
        if not already_outside:
            # Recreate stale durable interior data only for that incident
            # variant. The already-outside case retains actual exterior rows.
            with self.store.connection() as db:
                for identity, row in original_locations.items():
                    db.execute(
                        "UPDATE characters SET map_id=%s,instance_id=%s,x=%s,y=%s,z=%s WHERE id=%s",
                        (
                            row["map_id"],
                            row["instance_id"],
                            row["x"],
                            row["y"],
                            row["z"],
                            identity,
                        ),
                    )

        def proof():
            return capture(
                current[0],
                rows,
                fixture["ids"],
                world,
                fixture["positions"],
                portal,
                lambda actor, source: actor["instance_id"] == 0
                and actor["map_id"] == source["map_id"]
                and max(abs(actor["x"] - source["x"]), abs(actor["y"] - source["y"]))
                <= 3,
            )

        fixture.update(
            world=world,
            current=tuple(current),
            proof=proof,
            writer=writer,
            roster=roster,
            outside=outside,
        )
        return fixture

    def durable(self, fixture):
        with self.store.connection() as db:
            return dict(
                fight=db.execute(
                    "SELECT * FROM combat_fights WHERE id=%s",
                    (fixture["shared"].fight.id,),
                ).fetchone(),
                members=db.execute(
                    "SELECT * FROM combat_fight_participants WHERE fight_id=%s ORDER BY character_id",
                    (fixture["shared"].fight.id,),
                ).fetchall(),
                characters=db.execute(
                    "SELECT id,map_id,instance_id,hp,max_hp,hp_damage,health_dead FROM characters "
                    "WHERE id=ANY(%s) ORDER BY id",
                    (fixture["ids"],),
                ).fetchall(),
                checkpoint=db.execute(
                    "SELECT * FROM fight_checkpoints WHERE fight_id=%s",
                    (fixture["shared"].fight.id,),
                ).fetchone(),
                run=db.execute(
                    "SELECT * FROM rift_instances WHERE instance_id=%s",
                    (fixture["shared"].instance_id,),
                ).fetchone(),
                captures=db.execute(
                    "SELECT * FROM character_captured_rosters WHERE character_id=%s",
                    (fixture["owners"][0][2],),
                ).fetchall(),
                exits=db.execute(
                    "SELECT * FROM fight_health_exits WHERE fight_id=%s ORDER BY character_id",
                    (fixture["shared"].fight.id,),
                ).fetchall(),
            )

    def test_active_outside_repair_rolls_back_then_commits_real_health_and_capture_teardown(
        self,
    ):
        self.qualify_repair(self.fixture())

    def test_durable_already_outside_active_encounter_repairs_without_forging_its_old_origin(
        self,
    ):
        from wakfu_server.combat_entry_recovery import prepare

        fixture = self.fixture(already_outside=True)
        before = self.durable(fixture)
        outside_scope = (fixture["outside"]["map_id"], 0)
        self.assertTrue(
            all(
                (row["map_id"], row["instance_id"]) == outside_scope
                for row in before["characters"]
            )
        )
        with ExitStack() as barriers:
            for owner in fixture["current"]:
                barriers.enter_context(
                    fixture["positions"].account_barrier(owner.account_id)
                )
            with self.assertRaisesRegex(
                ValueError, "durable outside-repair origin changed"
            ):
                with prepare(
                    self.store,
                    fixture["registry"],
                    fixture["proof"](),
                    checkpoint_writer=fixture["writer"],
                ) as recovery:
                    with self.store.connection() as db:
                        db.execute(
                            "UPDATE characters SET instance_id=%s WHERE id=%s",
                            (fixture["shared"].instance_id + 1, fixture["heroes"][0]),
                        )
                        recovery.commit(db)
        self.assertEqual(self.durable(fixture), before)
        self.qualify_repair(fixture)

    def qualify_repair(self, fixture):
        from wakfu_server.combat_entry_recovery import prepare, take_entry_recovery
        from wakfu_server.characters.captured_roster import OwnedCapturedRoster
        from wakfu_server.fight_checkpoint_store import snapshot

        registry, shared = fixture["registry"], fixture["shared"]
        before = self.durable(fixture)
        original_fight = snapshot(shared.fight, runtime=shared.runtime)
        participants, connected = dict(shared.participants), set(shared.connected)
        with ExitStack() as barriers:
            for owner in fixture["current"]:
                barriers.enter_context(
                    fixture["positions"].account_barrier(owner.account_id)
                )
            with prepare(
                self.store,
                registry,
                fixture["proof"](),
                checkpoint_writer=fixture["writer"],
            ) as recovery:
                with self.assertRaisesRegex(ValueError, "new admission rejected"):
                    with self.store.connection() as db:
                        recovery.commit(db)
                        self.assertIs(registry.lookup(shared.fight.id), shared)
                        raise ValueError("new admission rejected")
                self.assertEqual(self.durable(fixture), before)
                with self.assertRaisesRegex(ValueError, "cannot retire before"):
                    recovery.retire()
            self.assertEqual(shared.participants, participants)
            self.assertEqual(shared.connected, connected)
            self.assertEqual(
                snapshot(shared.fight, runtime=shared.runtime), original_fight
            )
            with prepare(
                self.store,
                registry,
                fixture["proof"](),
                checkpoint_writer=fixture["writer"],
            ) as recovery:
                with self.store.connection() as db:
                    result = recovery.commit(db)
                    self.assertEqual(set(result["exits"]), set(fixture["ids"]))
                    # The actual next admission is exercised by the native-entry
                    # compound; stage its position writes here in this same TX.
                    point = fixture["outside"]
                    db.execute(
                        "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=ANY(%s)",
                        (
                            point["map_id"],
                            point["x"],
                            point["y"],
                            point["z"],
                            fixture["ids"],
                        ),
                    )
                self.assertTrue(recovery.retire())
                self.assertFalse(recovery.retire())
        after = self.durable(fixture)
        self.assertEqual(after["fight"]["status"], "aborted")
        self.assertEqual(after["checkpoint"]["status"], "aborted")
        self.assertEqual(after["run"]["status"], "closed")
        self.assertEqual(len(after["exits"]), 5)
        for row in after["characters"]:
            self.assertEqual(row["hp"], fixture["expected"][row["id"]])
        restored = OwnedCapturedRoster.from_record(
            after["captures"][0]["record"], expected_owner_id=fixture["owners"][0][2]
        )
        self.assertEqual(restored.slots, fixture["roster"].slots)
        self.assertEqual(restored.selected_slot, fixture["roster"].selected_slot)
        self.assertEqual(restored.available, (True,) * 10)
        self.assertFalse(registry.fights)
        self.assertFalse(registry.by_character)
        self.assertFalse(registry.by_actor)
        self.assertEqual(shared.participants, participants)
        self.assertFalse(shared.connected)
        for owner in fixture["current"]:
            self.assertIsNone(
                take_entry_recovery(
                    registry, owner.account_id, "stale", owner.character_id
                )
            )
            self.assertEqual(
                take_entry_recovery(
                    registry, owner.account_id, owner.generation, owner.character_id
                ),
                shared.fight.id,
            )
            self.assertIsNone(
                take_entry_recovery(
                    registry, owner.account_id, owner.generation, owner.character_id
                )
            )
        self.assertFalse(registry.entry_recovery_notices)

    def test_inside_peer_foreign_roster_and_stale_exterior_proof_preserve_everything(
        self,
    ):
        from wakfu_server.combat_entry_recovery import prepare

        fixture = self.fixture()
        before = self.durable(fixture)
        proof = fixture["proof"]()
        foreign_owner = replace(
            proof.owners[1], account_id=proof.owners[1].account_id + 10000
        )
        for rejected in (
            replace(
                proof,
                character_ids=tuple(
                    identity
                    for identity in proof.character_ids
                    if identity != fixture["heroes"][0]
                ),
            ),
            replace(proof, owners=(proof.owners[0], foreign_owner, *proof.owners[2:])),
            replace(proof, validate_live=lambda: False),
        ):
            with self.assertRaises(ValueError):
                with prepare(self.store, fixture["registry"], rejected):
                    self.fail("Invalid exterior proof admitted")
        peer = fixture["current"][1]
        old = self.store.character(peer.account_id, peer.character_id)
        fixture["world"].join(peer.generation, object(), old)
        with self.assertRaises(ValueError):
            with prepare(self.store, fixture["registry"], proof):
                self.fail("A genuinely interior peer was ignored")
        self.assertEqual(self.durable(fixture), before)
        self.assertIs(
            fixture["registry"].lookup(fixture["shared"].fight.id), fixture["shared"]
        )
