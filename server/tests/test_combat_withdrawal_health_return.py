"""Receipt-fenced dead exploration return; combat corpses stay untouched."""
from dataclasses import replace
import struct
from unittest.mock import patch
from postgres_case import PostgresCase
import test_combat_pve_withdraw as withdrawal_fixture
from wakfu_server import health_store, health_policy, health
from wakfu_server.combat_state import Actor
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.combat_pve_withdraw_store import acknowledge, recover_pending


class WithdrawalHealthReturnTests(PostgresCase):
    def test_party_hud_pending_withdrawal_then_real_return_uses_exploration_health(
        self,
    ):
        from wakfu_server import party_dispatch, player_parties
        from wakfu_server.fight_checkpoint_store import Checkpoints
        from wakfu_server.world import World
        from test_party_snapshot import PartySnapshotTests

        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            other_account,
            other_generation,
            other,
        ) = values
        token = player_parties.invite(
            store, account, generation, character["id"], other["id"]
        )
        party_id = player_parties.answer(
            store, other_account, other_generation, other["id"], token, True
        )
        Checkpoints(store).save(other_account, other_generation, shared.fight)
        sent = []
        world = World(
            lambda c: ("spawn", c["id"]),
            lambda c: ("remove", c["id"]),
            lambda peer, opcode, body: sent.append((opcode, body)),
        )
        world.join(generation, object(), character)
        world.join(other_generation, object(), other)
        parties = party_dispatch.Parties(store, world)

        def hud():
            sent.clear()
            self.assertTrue(parties._publish(party_id))
            packets = [body for opcode, body in sent if opcode == 1184]
            self.assertEqual(len(packets), 2)
            self.assertEqual(packets[0], packets[1])
            return {
                row["id"]: row for row in PartySnapshotTests._decode_roster(packets[0])
            }

        pending = hud()
        self.assertTrue(pending[character["id"]]["in_fight"])
        self.assertEqual(pending[character["id"]]["hp"], 0)
        returned = adapter.return_withdrawn_pve(
            owner, fight.id, receipt["character"], struct.pack(">iB", fight.id, 1), wp=6
        )
        after = hud()
        self.assertFalse(after[character["id"]]["in_fight"])
        self.assertFalse(after[character["id"]]["dead"])
        self.assertEqual(after[character["id"]]["hp"], returned["character"]["hp"])
        self.assertGreater(after[character["id"]]["hp"], 0)
        self.assertTrue(after[other["id"]]["in_fight"])
        self.assertEqual(after[other["id"]]["hp"], shared.fight.actors[other["id"]].hp)
        self.assertEqual(shared.fight.actors[character["id"]].hp, 0)
        self.assertEqual(shared.fight.phase, "active")

    def withdrawn(self, *, hero=False):
        values = withdrawal_fixture.WithdrawalPostgresTests.state(self)
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *other,
        ) = values
        # The public trusted damage API requires the actual source turn.
        # Advance the real FSM instead of rewriting current/order or using a
        # reaction-only API to bypass ordinary damage source validation.
        for _ in range(len(fight.actors) * 2):
            if fight.current.id == -200:
                break
            current = fight.current
            if current.controlled:
                fight.end_turn(current.owner_id, current.id, current.turn_count)
            else:
                fight.end_server_turn(current.id, fight.turn_id)
        self.assertEqual(fight.current.id, -200)
        hero_character = None
        if hero:
            hero_character = store.create_character(account, "Return Hero")
            actor = Actor(
                hero_character["id"],
                0,
                (3, 0, 0),
                hero_character["hp"],
                6,
                3,
                80,
                hero_character["level"],
                account,
                True,
                max_hp=hero_character["max_hp"],
            )
            fight.walkable.add(actor.position)
            fight.placement[0].add(actor.position)
            fight.actors[actor.id] = actor
            adapter.registry.by_character[actor.id] = fight.id
            adapter.registry.by_actor[actor.id] = fight.id
            with store.connection() as db:
                db.execute(
                    "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                    (fight.id, actor.id, account, generation),
                )
            fight.apply_damage(-200, actor.id, actor.hp)
        actor = fight.actors[character["id"]]
        fight.apply_damage(-200, actor.id, actor.hp)
        self.assertEqual(fight.phase, "active")
        self.assertEqual(actor.hp, 0)
        receipt = adapter.withdraw_pve(owner, character, b"")
        self.assertEqual(receipt["character"]["hp"], 0)
        self.assertTrue(receipt["character"]["health_dead"])
        return values, receipt, hero_character

    def test_dead_ack_recovers_committed_health_packets_regeneration_and_preserves_active_corpse(
        self,
    ):
        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        corpse = shared.fight.actors[character["id"]]
        ledger = corpse.state_ledger
        before = snapshot(shared.fight)
        from wakfu_server import combat_abandon

        actual_return = combat_abandon.return_to_world
        prior = []

        def observe_return(*args, **kwargs):
            result = actual_return(*args, **kwargs)
            prior.extend(result["packets"])
            return result

        with patch.object(
            combat_abandon, "return_to_world", side_effect=observe_return
        ):
            returned = adapter.return_withdrawn_pve(
                owner,
                fight.id,
                receipt["character"],
                struct.pack(">iB", fight.id, 1),
                wp=6,
            )
        # Every actor's format17/FOR_PHOENIX teardown must remain byte-exact;
        # sharing opcode13046 does not make it the selected fmt3 HP refresh.
        old_teardown = [
            packet
            for packet in prior
            if packet[0] == 13046 and packet[1][10:11] == b"\x11"
        ]
        self.assertTrue(old_teardown)
        self.assertEqual(
            [
                packet
                for packet in returned["packets"]
                if packet[0] == 13046 and packet[1][10:11] == b"\x11"
            ],
            old_teardown,
        )
        self.assertEqual(returned["character"]["hp"], 1)
        self.assertFalse(returned["character"]["health_dead"])
        hp_packets = [
            payload for opcode, payload in returned["packets"] if opcode == 12436
        ]
        self.assertEqual(
            hp_packets,
            [
                struct.pack(
                    ">qii",
                    character["id"],
                    1,
                    health.exploration_coefficient(returned["character"]["max_hp"], 1),
                )
            ],
        )
        self.assertIs(shared.fight.actors[character["id"]], corpse)
        self.assertIs(corpse.state_ledger, ledger)
        self.assertEqual(snapshot(shared.fight), before)
        self.assertEqual(shared.fight.phase, "active")
        self.assertEqual(fight.actors[character["id"]].hp, 0)
        with store.connection() as db:
            row = db.execute(
                "SELECT reason,return_acknowledged_at FROM fight_health_exits WHERE fight_id=%s AND character_id=%s",
                (fight.id, character["id"]),
            ).fetchone()
            self.assertEqual(row["reason"], "abort")
            self.assertIsNone(row["return_acknowledged_at"])
            self.assertIsNotNone(
                db.execute(
                    "SELECT health_returned_at FROM combat_pve_withdrawals WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["health_returned_at"]
            )
        store.clock = lambda: 1005
        maximum = store.character(account, character["id"])["max_hp"]
        coefficient = health.exploration_coefficient(maximum, 1)
        self.assertEqual(
            health_store.tick(store, account, generation, character["id"], 1)["hp"],
            health.regenerated(1, maximum, 5000, coefficient),
        )

    def test_duplicate_ack_does_not_reverse_later_world_death_or_restart_regeneration(
        self,
    ):
        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        acknowledge(store, owner, fight.id)
        store.clock = lambda: 1005
        health_store.sync(
            store, account, generation, character["id"], 1, 0, coefficient=0
        )
        before = store.character(account, character["id"])
        with store.connection() as db:
            baseline = dict(
                db.execute(
                    "SELECT * FROM character_regeneration WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()
            )
        self.assertEqual(acknowledge(store, owner, fight.id)["hp"], 0)
        self.assertEqual(store.character(account, character["id"]), before)
        with store.connection() as db:
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM character_regeneration WHERE character_id=%s",
                        (character["id"],),
                    ).fetchone()
                ),
                baseline,
            )

    def test_replacement_lease_completes_interrupted_dead_return_once(self):
        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        new = store.begin_session(account)
        selected = store.select_character(account, new, character["id"])
        session = replace(owner, generation=new)
        result = recover_pending(store, session)
        self.assertEqual(result["hp"], 1)
        self.assertFalse(result["health_dead"])
        self.assertIsNone(recover_pending(store, session))
        self.assertEqual(shared.fight.actors[character["id"]].hp, 0)

    def test_historical_already_returned_dead_exit_can_complete_only_unchanged_baseline(
        self,
    ):
        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        with store.connection() as db:
            db.execute(
                "UPDATE combat_pve_withdrawals SET returned_at=%s WHERE fight_id=%s",
                (store.now(), fight.id),
            )
        result = recover_pending(store, owner)
        self.assertEqual(result["hp"], 1)
        self.assertIsNone(recover_pending(store, owner))

    def test_historical_changed_dead_baseline_is_not_discovered_or_healed(self):
        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        with store.connection() as db:
            db.execute(
                "UPDATE combat_pve_withdrawals SET returned_at=%s WHERE fight_id=%s",
                (store.now(), fight.id),
            )
        store.clock = lambda: 1005
        health_store.initialize(
            store, account, generation, character["id"], coefficient=0
        )
        self.assertIsNone(recover_pending(store, owner))
        with self.assertRaisesRegex(ValueError, "exit baseline"):
            acknowledge(store, owner, fight.id)
        self.assertEqual(store.character(account, character["id"])["hp"], 0)

    def test_replacement_lease_preserves_newer_dead_baseline_and_finishes_pending_return(
        self,
    ):
        self._assert_newer_dead_baseline_recovery(use_registry=False)

    def test_replacement_lease_preserves_newer_dead_baseline_with_retained_registry(
        self,
    ):
        self._assert_newer_dead_baseline_recovery(use_registry=True)

    def test_selector_return_same_lease_preserves_newer_dead_baseline(self):
        self._assert_newer_dead_baseline_recovery(
            use_registry=True, replace_lease=False
        )

    def _assert_newer_dead_baseline_recovery(self, *, use_registry, replace_lease=True):
        values, _, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        store.clock = lambda: 1005
        # A later authoritative exploration initialization must not be undone
        # by an older unacknowledged withdrawal when this account reconnects.
        health_store.initialize(
            store, account, generation, character["id"], coefficient=0
        )
        if replace_lease:
            generation = store.begin_session(account)
            store.select_character(account, generation, character["id"])
        replacement = replace(owner, generation=generation)
        before = store.character(account, character["id"])
        combat_before = snapshot(shared.fight)
        with store.connection() as db:
            regeneration = dict(
                db.execute(
                    "SELECT * FROM character_regeneration WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()
            )
        recovered = (
            adapter.recover_withdrawn_pve(replacement)
            if use_registry
            else recover_pending(store, replacement)
        )
        self.assertEqual(recovered, before)
        self.assertTrue(recovered["health_dead"])
        self.assertEqual(recovered["hp"], 0)
        self.assertIsNone(recover_pending(store, replacement))
        self.assertEqual(snapshot(shared.fight), combat_before)
        with store.connection() as db:
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM character_regeneration WHERE character_id=%s",
                        (character["id"],),
                    ).fetchone()
                ),
                regeneration,
            )
            exit_row = db.execute(
                "SELECT return_acknowledged_at FROM fight_health_exits WHERE fight_id=%s AND character_id=%s",
                (fight.id, character["id"]),
            ).fetchone()
            self.assertIsNone(exit_row["return_acknowledged_at"])
            continuation = db.execute(
                "SELECT returned_at,health_returned_at,session_generation FROM combat_pve_withdrawals "
                "WHERE fight_id=%s AND character_id=%s",
                (fight.id, character["id"]),
            ).fetchone()
            self.assertIsNotNone(continuation["returned_at"])
            self.assertIsNotNone(continuation["health_returned_at"])
            self.assertEqual(continuation["session_generation"], generation)

    def test_pending_recovery_does_not_consume_old_return_while_current_fight_is_active(
        self,
    ):
        values, _, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        store.clock = lambda: 1005
        health_store.initialize(
            store, account, generation, character["id"], coefficient=0
        )
        generation = store.begin_session(account)
        store.select_character(account, generation, character["id"])
        replacement = replace(owner, generation=generation)
        combat_before = snapshot(shared.fight)
        before = store.character(account, character["id"])
        with store.connection() as db:
            active = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) "
                "VALUES(%s,%s,%s,0,%s)",
                (active, character["id"], account, generation),
            )
            baseline = dict(
                db.execute(
                    "SELECT * FROM character_regeneration WHERE character_id=%s",
                    (character["id"],),
                ).fetchone()
            )
            receipt = dict(
                db.execute(
                    "SELECT * FROM combat_pve_withdrawals WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()
            )
        self.assertIsNone(recover_pending(store, replacement))
        self.assertEqual(store.character(account, character["id"]), before)
        self.assertEqual(snapshot(shared.fight), combat_before)
        with store.connection() as db:
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM character_regeneration WHERE character_id=%s",
                        (character["id"],),
                    ).fetchone()
                ),
                baseline,
            )
            self.assertEqual(
                dict(
                    db.execute(
                        "SELECT * FROM combat_pve_withdrawals WHERE fight_id=%s AND character_id=%s",
                        (fight.id, character["id"]),
                    ).fetchone()
                ),
                receipt,
            )
            self.assertEqual(
                db.execute(
                    "SELECT status FROM combat_fights WHERE id=%s", (active,)
                ).fetchone()["status"],
                "active",
            )

    def test_missing_malformed_or_older_regeneration_repairs_full_owned_cohort_without_healing(
        self,
    ):
        from datetime import timedelta

        values, _, hero = self.withdrawn(hero=True)
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            other_account,
            _,
            other,
        ) = values
        old_generation = generation
        store.clock = lambda: 1005
        generation = store.begin_session(account)
        store.select_character(account, generation, character["id"])
        replacement = replace(owner, generation=generation)
        identities = [character["id"], hero["id"]]
        before = {
            identity: store.character(account, identity) for identity in identities
        }
        foreign = store.character(other_account, other["id"])
        combat_before = snapshot(shared.fight)
        with store.connection() as db:
            exits = {
                row["character_id"]: row["created_at"]
                for row in db.execute(
                    "SELECT character_id,created_at FROM fight_health_exits WHERE fight_id=%s AND character_id=ANY(%s)",
                    (fight.id, identities),
                )
            }
        for defect in ("missing", "malformed_damage", "older", "clock_regression"):
            with self.subTest(defect=defect):
                store.clock = (
                    (lambda: 999) if defect == "clock_regression" else (lambda: 1005)
                )
                with store.connection() as db:
                    db.execute(
                        "UPDATE combat_pve_withdrawals SET returned_at=NULL,health_returned_at=NULL,session_generation=%s "
                        "WHERE fight_id=%s AND account_id=%s",
                        (old_generation, fight.id, account),
                    )
                    for identity in identities:
                        db.execute(
                            "INSERT INTO character_regeneration(character_id,initial_hp,started_at,coefficient,last_at) "
                            "VALUES(%s,0,%s,0,%s) ON CONFLICT(character_id) DO UPDATE SET "
                            "initial_hp=excluded.initial_hp,started_at=excluded.started_at,coefficient=0,last_at=excluded.last_at",
                            (identity, exits[identity], exits[identity]),
                        )
                    if defect == "missing":
                        db.execute(
                            "DELETE FROM character_regeneration WHERE character_id=ANY(%s)",
                            (identities,),
                        )
                    elif defect == "malformed_damage":
                        db.execute(
                            "UPDATE character_regeneration SET initial_damage=initial_damage+7 WHERE character_id=ANY(%s)",
                            (identities,),
                        )
                    else:
                        db.execute(
                            "UPDATE character_regeneration SET started_at=%s WHERE character_id=ANY(%s)",
                            (min(exits.values()) - timedelta(seconds=2), identities),
                        )
                self.assertEqual(
                    recover_pending(store, replacement), before[character["id"]]
                )
                self.assertIsNone(recover_pending(store, replacement))
                for identity in identities:
                    self.assertEqual(
                        store.character(account, identity), before[identity]
                    )
                self.assertEqual(store.character(other_account, other["id"]), foreign)
                self.assertEqual(snapshot(shared.fight), combat_before)
                with store.connection() as db:
                    for identity in identities:
                        baseline = db.execute(
                            "SELECT * FROM character_regeneration WHERE character_id=%s",
                            (identity,),
                        ).fetchone()
                        self.assertEqual(
                            (
                                baseline["initial_hp"],
                                baseline["initial_damage"],
                                baseline["coefficient"],
                            ),
                            (0, before[identity]["hp_damage"], 0),
                        )
                        self.assertEqual(baseline["started_at"], store.now())
                        self.assertEqual(baseline["last_at"], store.now())
                        receipt = db.execute(
                            "SELECT w.returned_at,w.health_returned_at,w.session_generation,e.return_acknowledged_at "
                            "FROM combat_pve_withdrawals w JOIN fight_health_exits e USING(fight_id,character_id) "
                            "WHERE w.fight_id=%s AND w.character_id=%s",
                            (fight.id, identity),
                        ).fetchone()
                        self.assertIsNotNone(receipt["returned_at"])
                        self.assertIsNotNone(receipt["health_returned_at"])
                        self.assertEqual(receipt["session_generation"], generation)
                        self.assertIsNone(receipt["return_acknowledged_at"])

    def test_all_owned_dead_heroes_recover_without_touching_foreign_owner(self):
        values, receipt, hero = self.withdrawn(hero=True)
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            other_account,
            other_generation,
            other,
        ) = values
        foreign = store.character(other_account, other["id"])
        acknowledge(store, owner, fight.id)
        for identity in (character["id"], hero["id"]):
            saved = store.character(account, identity)
            self.assertEqual(saved["hp"], 1)
            self.assertFalse(saved["health_dead"])
            self.assertEqual(shared.fight.actors[identity].hp, 0)
        self.assertEqual(store.character(other_account, other["id"]), foreign)
        self.assertEqual(shared.fight.phase, "active")

    def test_health_recovery_failure_rolls_back_receipt_and_hp_together(self):
        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        real = health_policy.apply_damage

        def fail_after_write(*args, **kwargs):
            real(*args, **kwargs)
            raise RuntimeError("after owned recovery")

        with patch.object(health_policy, "apply_damage", side_effect=fail_after_write):
            with self.assertRaisesRegex(RuntimeError, "after owned recovery"):
                acknowledge(store, owner, fight.id)
        self.assertEqual(store.character(account, character["id"])["hp"], 0)
        with store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT returned_at FROM combat_pve_withdrawals WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["returned_at"]
            )
            self.assertIsNone(
                db.execute(
                    "SELECT return_acknowledged_at FROM fight_health_exits WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["return_acknowledged_at"]
            )
            self.assertIsNone(
                db.execute(
                    "SELECT health_returned_at FROM combat_pve_withdrawals WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["health_returned_at"]
            )

    def test_foreign_or_replaced_lease_cannot_complete_health_return(self):
        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        with self.assertRaises(ValueError):
            acknowledge(store, replace(owner, account_id=999), fight.id)
        store.begin_session(account)
        with self.assertRaises(ValueError):
            acknowledge(store, owner, fight.id)
        self.assertEqual(store.character(account, character["id"])["hp"], 0)

    def test_obsolete_historical_receipt_does_not_block_new_death_or_live_fight(self):
        # Each subcase needs its own isolated schema/owner because the earlier
        # fixture registers fixed usernames. Separate transactions below reuse
        # one historical receipt while adding/removing only the later guard.
        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        with store.connection() as db:
            db.execute(
                "UPDATE combat_pve_withdrawals SET returned_at=%s WHERE fight_id=%s",
                (store.now(), fight.id),
            )
            other_fight = db.execute(
                "INSERT INTO combat_fights(status) VALUES('finished') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,%s,%s,0,%s)",
                (other_fight, character["id"], account, generation),
            )
            # Deliberately retain the old matching regeneration baseline so
            # this tests the newer durable-exit exclusion itself.
            db.execute(
                "INSERT INTO fight_health_exits(fight_id,character_id,generation,reason,created_at) VALUES(%s,%s,%s,'abort',%s)",
                (other_fight, character["id"], generation, store.now()),
            )
        self.assertIsNone(recover_pending(store, owner))
        self.assertEqual(store.character(account, character["id"])["hp"], 0)
        with store.connection() as db:
            db.execute(
                "DELETE FROM fight_health_exits WHERE fight_id=%s", (other_fight,)
            )
            db.execute(
                "UPDATE combat_fights SET status='active' WHERE id=%s", (other_fight,)
            )
        self.assertIsNone(recover_pending(store, owner))
        self.assertEqual(store.character(account, character["id"])["hp"], 0)
        with store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT return_acknowledged_at FROM fight_health_exits WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["return_acknowledged_at"]
            )
            self.assertIsNone(
                db.execute(
                    "SELECT health_returned_at FROM combat_pve_withdrawals WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["health_returned_at"]
            )

    def test_original_abort_ack_constraint_and_withdrawal_return_constraint_remain_enforced(
        self,
    ):
        from psycopg.errors import CheckViolation

        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        with self.assertRaises(CheckViolation), store.connection() as db:
            db.execute(
                "UPDATE fight_health_exits SET return_acknowledged_at=%s WHERE fight_id=%s AND character_id=%s",
                (store.now(), fight.id, character["id"]),
            )
        with self.assertRaises(CheckViolation), store.connection() as db:
            db.execute(
                "UPDATE combat_pve_withdrawals SET health_returned_at=%s WHERE fight_id=%s AND character_id=%s",
                (store.now(), fight.id, character["id"]),
            )
        self.assertEqual(store.character(account, character["id"])["hp"], 0)

    def test_pre190_historical_returned_dead_row_upgrades_without_backfill_then_recovers_owned(
        self,
    ):
        from pathlib import Path
        from wakfu_server.paths import PROJECT_ROOT

        values, receipt, _ = self.withdrawn()
        (
            store,
            account,
            generation,
            character,
            fight,
            adapter,
            owner,
            shared,
            *_,
        ) = values
        with store.connection() as db:
            # Remove only the new additive schema while all prior migrations,
            # original abort receipt and actual dead-exit data remain intact.
            db.execute(
                "ALTER TABLE combat_pve_withdrawals DROP CONSTRAINT pve_withdrawal_health_requires_return"
            )
            db.execute(
                "ALTER TABLE combat_pve_withdrawals DROP COLUMN health_returned_at"
            )
            db.execute(
                "UPDATE combat_pve_withdrawals SET returned_at=%s WHERE fight_id=%s",
                (store.now(), fight.id),
            )
            db.execute(
                (
                    PROJECT_ROOT
                    / "server/migrations/190_pve_withdrawal_health_returns.sql"
                ).read_text()
            )
            row = db.execute(
                "SELECT returned_at,health_returned_at FROM combat_pve_withdrawals WHERE fight_id=%s AND character_id=%s",
                (fight.id, character["id"]),
            ).fetchone()
            self.assertIsNotNone(row["returned_at"])
            self.assertIsNone(row["health_returned_at"])
        self.assertEqual(store.character(account, character["id"])["hp"], 0)
        self.assertEqual(recover_pending(store, owner)["hp"], 1)
        self.assertIsNone(recover_pending(store, owner))
        with store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT return_acknowledged_at FROM fight_health_exits WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["return_acknowledged_at"]
            )
            self.assertIsNotNone(
                db.execute(
                    "SELECT health_returned_at FROM combat_pve_withdrawals WHERE fight_id=%s AND character_id=%s",
                    (fight.id, character["id"]),
                ).fetchone()["health_returned_at"]
            )
