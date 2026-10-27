"""Authenticated abandonment ACK for a genuinely admitted main/hero/sidekick."""
from copy import deepcopy
import struct

from postgres_case import PostgresCase
import test_rift_earned_rewards as earned
from wakfu_server import combat_abandon, combat_abandon_health_return
from wakfu_server.combat_companions import registered_companion_ids
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.fight_checkpoint_store import _plain
from wakfu_server.combat_characteristic_link import characteristic_adoption_bindings


class NativeCompanyAbandonTests(PostgresCase):
    # Reuse the real Store company, native companion admission and QI snapshots;
    # do not inherit the unrelated reward test methods.
    _company = earned.RiftEarnedRewardTests._company
    _fixture = earned.RiftEarnedRewardTests._fixture
    _admitted_native_companion_and_hero_fixture = (
        earned.RiftEarnedRewardTests._admitted_native_companion_and_hero_fixture
    )

    def test_last_native_company_owner_aborts_after_other_owner_ko_and_both_ack(self):
        from wakfu_server import fight_store
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.combat_shared_abandon import prepare
        from wakfu_server.combat_state import Actor
        from wakfu_server.equipment_stats import combat_resources, effective_character

        _, fight, _, companion_id = self._admitted_native_companion_and_hero_fixture()
        main = self.store.character(self.account, self.ids[0])
        peer_account = self.store.register("native-abandon-peer", "peer-password")["id"]
        peer = self.store.create_character(peer_account, "Nativeabandonpeer")
        peer_generation = self.store.begin_session(peer_account)
        self.store.select_character(peer_account, peer_generation, peer["id"])
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET map_id=%s,instance_id=%s WHERE id=%s",
                (main["map_id"], main.get("instance_id", 0), peer["id"]),
            )
            db.execute(
                "UPDATE combat_fights SET status='placement' WHERE id=%s", (fight.id,)
            )
            # The reused earned-reward fixture only needs membership IDs.
            # Shared abort additionally requires the original entry health,
            # captured by the same Store authority as fight_store.create/join,
            # before any combat damage or exit has occurred.
            for identity in self.ids:
                baseline = fight_store._health_baseline(db, self.account, identity)
                row = db.execute(
                    "UPDATE combat_fight_participants SET entry_hp=%s,entry_max_hp=%s,"
                    "entry_hp_damage=%s,entry_health_dead=%s WHERE fight_id=%s "
                    "AND character_id=%s AND account_id=%s AND entry_hp IS NULL "
                    "AND entry_max_hp IS NULL AND entry_hp_damage IS NULL "
                    "AND entry_health_dead IS NULL",
                    (*baseline, fight.id, identity, self.account),
                )
                self.assertEqual(row.rowcount, 1)
        peer = self.store.character(peer_account, peer["id"])
        adapter = CombatSessionAdapter(self.store)
        owner = adapter.session(self.account, self.generation, main)
        other = adapter.session(peer_account, peer_generation, peer)
        shared = adapter.register(owner, fight, runtime=RuntimeMessages(fight))
        team = fight.actors[main["id"]].team
        occupied = {actor.position for actor in fight.actors.values()}
        position = next(
            cell for cell in sorted(fight.placement[team]) if cell not in occupied
        )
        projected = effective_character(peer)
        resources = combat_resources(projected)
        actor = Actor(
            peer["id"],
            team,
            position,
            projected["hp"],
            resources["ap"],
            resources["mp"],
            resources["initiative"],
            projected["level"],
            peer_account,
            True,
            max_hp=projected["max_hp"],
        )
        build_player_snapshot(
            projected,
            actor,
            wp_current=resources["wp"],
            wp_maximum=resources["wp"],
            running_effects=(),
        ).install(actor)

        def persist_member(candidate, newcomer, original, session):
            with self.store.connection() as db:
                fight_store.join_participant(
                    self.store,
                    db,
                    peer_account,
                    peer_generation,
                    peer["id"],
                    fight.id,
                    target_character_id=main["id"],
                    team=team,
                )

        # Placement presentation is outside this server/PG abort component;
        # participant ownership and constructor snapshots are genuine.
        adapter.registry.join(
            other,
            struct.pack(">qB", main["id"], team),
            actor,
            actor_payload=lambda *_: (b"stats", b"effects"),
            bootstrap_packets=lambda *_: [(12847, b"placement")],
            persist_member=persist_member,
        )
        shared.fight.ready(self.account, True)
        shared.fight.ready(peer_account, True)
        fight_store.activate(
            self.store, self.account, self.generation, main["id"], fight.id
        )
        victim = shared.fight.actors[peer["id"]]
        shared.fight.apply_effect_damage(
            next(iter(fight.rift_monsters)), victim.id, victim.hp
        )
        self.assertEqual(victim.hp, 0)
        self.assertEqual(shared.fight.phase, "active")
        self.assertGreater(shared.fight.actors[companion_id].hp, 0)
        result = prepare(self.store, adapter.registry, owner, main, b"")
        self.assertTrue(result["shared_full_abort"])
        self.assertTrue(any(opcode == 12238 for opcode, _ in result["packets"]))
        self.assertEqual((shared.fight.phase, shared.fight.winner), ("finished", None))
        humans = {*self.ids, peer["id"]}
        with self.store.connection() as db:
            for table in ("combat_pve_withdrawals", "fight_health_exits"):
                rows = db.execute(
                    "SELECT character_id FROM " + table + " WHERE fight_id=%s",
                    (fight.id,),
                ).fetchall()
                self.assertEqual({row["character_id"] for row in rows}, humans)
            companion = db.execute(
                "SELECT health_settled_at,experience_settled_at FROM combat_fight_companions "
                "WHERE fight_id=%s AND companion_id=%s",
                (fight.id, companion_id),
            ).fetchone()
            self.assertIsNotNone(companion["health_settled_at"])
            self.assertIsNotNone(companion["experience_settled_at"])
        for session in (other, owner):
            saved = self.store.character(session.account_id, session.character_id)
            ack = adapter.return_withdrawn_pve(
                session,
                fight.id,
                saved,
                struct.pack(">iB", fight.id, 1),
                wp=6,
                pending=shared.withdrawals[session.account_id],
            )
            self.assertTrue(ack["packets"])
            self.assertIn(session.account_id, shared.returned)
        self.assertGreater(self.store.character(peer_account, peer["id"])["hp"], 0)
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT character_id,returned_at,health_returned_at FROM combat_pve_withdrawals "
                "WHERE fight_id=%s",
                (fight.id,),
            ).fetchall()
            self.assertEqual({row["character_id"] for row in rows}, humans)
            self.assertTrue(
                all(
                    row["returned_at"] is not None
                    and row["health_returned_at"] is not None
                    for row in rows
                )
            )

    def test_last_owner_native_company_abandon_ack_preserves_human_health_roster(self):
        (
            _,
            fight,
            characters,
            companion_id,
        ) = self._admitted_native_companion_and_hero_fixture()
        main_id, hero_id = self.ids
        main = self.store.character(self.account, main_id)
        self.assertEqual(registered_companion_ids(fight), {companion_id})
        fight.ready(self.account, True)
        self.assertEqual(fight.phase, "active")
        enemy_id = next(iter(fight.rift_monsters))
        fight.apply_effect_damage(enemy_id, main_id, 1)
        fight.apply_effect_damage(enemy_id, hero_id, 2)
        expected_hp = {identity: fight.actors[identity].hp for identity in self.ids}
        self.assertTrue(all(value > 0 for value in expected_hp.values()))
        companion = fight.actors[companion_id]
        companion_before = _plain(companion.__dict__)
        companion_objects = dict(companion.__dict__)
        live_bindings = characteristic_adoption_bindings(fight)
        runtime = RuntimeMessages(fight)

        aborted = combat_abandon.prepare(
            self.store, self.account, self.generation, main, runtime, b""
        )
        self.assertTrue(aborted["applied"])
        self.assertTrue(any(opcode == 12238 for opcode, _ in aborted["packets"]))
        self.assertEqual((fight.phase, fight.winner), ("finished", None))
        with self.store.connection() as db:
            receipts = tuple(
                db.execute(
                    "SELECT character_id,reason,abandon_return_acknowledged_at "
                    "FROM fight_health_exits WHERE fight_id=%s ORDER BY character_id",
                    (fight.id,),
                )
            )
            self.assertEqual({row["character_id"] for row in receipts}, set(self.ids))
            self.assertTrue(all(row["reason"] == "abort" for row in receipts))
            self.assertTrue(
                all(row["abandon_return_acknowledged_at"] is None for row in receipts)
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (fight.id,)
                ).fetchone()["status"],
                "aborted",
            )
            # A controlled actor with no valid companion registration still
            # cannot disappear from the exact human membership comparison.
            unregistered = deepcopy(fight)
            unregistered.native_companion_sources = {}
            with self.assertRaisesRegex(ValueError, "complete owned roster"):
                combat_abandon_health_return.complete(
                    self.store, db, self.account, self.generation, main, unregistered
                )

        ack = struct.pack(">iB", fight.id, 0)
        returned = combat_abandon.return_to_world(
            self.store, self.account, self.generation, main, runtime, ack, wp=6
        )
        self.assertTrue(returned["applied"])
        self.assertTrue(returned["packets"])
        self.assertEqual(returned["character"]["id"], main_id)
        self.assertIs(fight.actors[companion_id], companion)
        self.assertEqual(_plain(companion.__dict__), companion_before)
        # Compare persisted state by value and live listener/owner objects by
        # identity: deepcopy deliberately creates different StateLedger objects.
        for name, value in companion_objects.items():
            if value is not None and type(value) not in (str, int, float, bool, tuple):
                self.assertIs(getattr(companion, name), value)
        after_bindings = characteristic_adoption_bindings(fight)
        self.assertEqual(len(after_bindings), len(live_bindings))
        self.assertTrue(
            all(after is before for before, after in zip(live_bindings, after_bindings))
        )
        with self.store.connection() as db:
            acknowledged = tuple(
                db.execute(
                    "SELECT character_id,reason,abandon_return_acknowledged_at "
                    "FROM fight_health_exits WHERE fight_id=%s ORDER BY character_id",
                    (fight.id,),
                )
            )
            self.assertTrue(
                all(
                    row["abandon_return_acknowledged_at"] is not None
                    for row in acknowledged
                )
            )
        reopened = self.reopen()
        for identity, hp in expected_hp.items():
            self.assertEqual(reopened.character(self.account, identity)["hp"], hp)
        repeated = combat_abandon.return_to_world(
            self.store, self.account, self.generation, main, runtime, ack, wp=6
        )
        self.assertFalse(repeated["applied"])
        self.assertEqual(repeated["packets"], [])
